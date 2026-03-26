const fs = require('fs');
const path = require('path');
const initSqlJs = require('sql.js');

class ATSCacheDB {
  constructor(dbPath) {
    this.dbPath = dbPath;
    this.initialized = false;
    this.db = null;
  }

  async initialize() {
    if (this.initialized) return;

    fs.mkdirSync(path.dirname(this.dbPath), { recursive: true });

    if (!ATSCacheDB.SQL) {
      ATSCacheDB.SQL = await initSqlJs({
        locateFile: file => require.resolve(`sql.js/dist/${file}`)
      });
    }

    const dbBuffer = fs.existsSync(this.dbPath)
      ? fs.readFileSync(this.dbPath)
      : null;

    this.db = dbBuffer && dbBuffer.length > 0
      ? new ATSCacheDB.SQL.Database(dbBuffer)
      : new ATSCacheDB.SQL.Database();

    this.db.exec(`
      CREATE TABLE IF NOT EXISTS job_results (
        job_url TEXT PRIMARY KEY,
        title TEXT,
        company TEXT,
        location TEXT,
        description TEXT,
        source TEXT,
        posted_date TEXT,
        ats_score INTEGER NOT NULL,
        ats_reasoning TEXT,
        scored_at TEXT NOT NULL,
        provider TEXT,
        model TEXT,
        first_seen_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL
      );
    `);

    if (this.tableExists('ats_scores')) {
      const now = new Date().toISOString();
      this.db.exec(`
        INSERT OR IGNORE INTO job_results (
          job_url, title, company, location, description, source, posted_date, ats_score, ats_reasoning, scored_at, provider, model, first_seen_at, last_seen_at
        )
        SELECT
          job_url,
          COALESCE(title, ''),
          COALESCE(company, ''),
          COALESCE(location, ''),
          '',
          '',
          '',
          COALESCE(ats_score, 0),
          COALESCE(ats_reasoning, ''),
          COALESCE(scored_at, '${now}'),
          COALESCE(provider, ''),
          COALESCE(model, ''),
          '${now}',
          '${now}'
        FROM ats_scores;
      `);
    }

    if (!this.columnExists('job_results', 'posted_date')) {
      this.db.exec('ALTER TABLE job_results ADD COLUMN posted_date TEXT;');
    }

    this.persist();
    this.initialized = true;
  }

  getByUrl(jobUrl) {
    if (!jobUrl) return null;

    const payload = this.getOne(
      `
        SELECT ats_score, ats_reasoning, scored_at
        FROM job_results
        WHERE job_url = $jobUrl
        LIMIT 1;
      `,
      { $jobUrl: jobUrl }
    );

    if (!payload) return null;

    return {
      score: parseInt(payload.ats_score, 10) || 0,
      reasoning: payload.ats_reasoning || '',
      scoredAt: payload.scored_at || new Date().toISOString()
    };
  }

  getJobByUrl(jobUrl) {
    if (!jobUrl) return null;

    const payload = this.getOne(
      `
        SELECT
          job_url,
          title,
          location,
          company,
          description,
          source,
          posted_date,
          first_seen_at,
          last_seen_at,
          ats_score,
          ats_reasoning,
          scored_at
        FROM job_results
        WHERE job_url = $jobUrl
        LIMIT 1;
      `,
      { $jobUrl: jobUrl }
    );

    if (!payload) return null;

    return {
      url: payload.job_url || '',
      title: payload.title || '',
      location: payload.location || 'Not specified',
      company: payload.company || '',
      description: payload.description || '',
      source: payload.source || '',
      postedDate: payload.posted_date || '',
      firstSeenAt: payload.first_seen_at || '',
      lastSeenAt: payload.last_seen_at || '',
      atsScore: parseInt(payload.ats_score, 10) || 0,
      atsReasoning: payload.ats_reasoning || '',
      scoredAt: payload.scored_at || new Date().toISOString()
    };
  }

  getAllJobUrls() {
    return this.getAll('SELECT job_url FROM job_results;')
      .map(row => row.job_url)
      .filter(Boolean);
  }

  touchJobUrl(jobUrl) {
    if (!jobUrl) return;

    this.run(
      `
        UPDATE job_results
        SET last_seen_at = $lastSeenAt
        WHERE job_url = $jobUrl;
      `,
      {
        $lastSeenAt: new Date().toISOString(),
        $jobUrl: jobUrl
      }
    );
    this.persist();
  }

  upsert(job, atsResult, provider, model) {
    if (!job?.url) return;

    const now = new Date().toISOString();
    const score = Number.isFinite(atsResult.score)
      ? Math.max(0, Math.min(100, atsResult.score))
      : 0;

    this.run(
      `
        INSERT INTO job_results (
          job_url, title, company, location, description, source, posted_date, ats_score, ats_reasoning, scored_at, provider, model, first_seen_at, last_seen_at
        ) VALUES (
          $jobUrl, $title, $company, $location, $description, $source, $postedDate, $score, $reasoning, $scoredAt, $provider, $model, $firstSeenAt, $lastSeenAt
        )
        ON CONFLICT(job_url) DO UPDATE SET
          title = excluded.title,
          company = excluded.company,
          location = excluded.location,
          description = excluded.description,
          source = excluded.source,
          posted_date = excluded.posted_date,
          ats_score = excluded.ats_score,
          ats_reasoning = excluded.ats_reasoning,
          scored_at = excluded.scored_at,
          provider = excluded.provider,
          model = excluded.model,
          last_seen_at = excluded.last_seen_at;
      `,
      {
        $jobUrl: job.url,
        $title: job.title || '',
        $company: job.company || '',
        $location: job.location || '',
        $description: job.description || '',
        $source: job.source || '',
        $postedDate: job.postedDate || '',
        $score: score,
        $reasoning: atsResult.reasoning || '',
        $scoredAt: atsResult.timestamp || now,
        $provider: provider || '',
        $model: model || '',
        $firstSeenAt: now,
        $lastSeenAt: now
      }
    );
    this.persist();
  }

  tableExists(tableName) {
    return Boolean(
      this.getOne(
        `
          SELECT name
          FROM sqlite_master
          WHERE type = 'table' AND name = $tableName
          LIMIT 1;
        `,
        { $tableName: tableName }
      )
    );
  }

  columnExists(tableName, columnName) {
    const rows = this.getAll(`PRAGMA table_info(${tableName});`);
    return rows.some(row => row.name === columnName);
  }

  getOne(sql, params = {}) {
    const stmt = this.db.prepare(sql);
    try {
      stmt.bind(params);
      if (!stmt.step()) {
        return null;
      }
      return stmt.getAsObject();
    } finally {
      stmt.free();
    }
  }

  getAll(sql, params = {}) {
    const stmt = this.db.prepare(sql);
    const rows = [];

    try {
      stmt.bind(params);
      while (stmt.step()) {
        rows.push(stmt.getAsObject());
      }
      return rows;
    } finally {
      stmt.free();
    }
  }

  run(sql, params = {}) {
    const stmt = this.db.prepare(sql);
    try {
      stmt.run(params);
    } finally {
      stmt.free();
    }
  }

  persist() {
    fs.writeFileSync(this.dbPath, Buffer.from(this.db.export()));
  }
}

module.exports = ATSCacheDB;
