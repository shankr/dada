const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

class ATSCacheDB {
  constructor(dbPath) {
    this.dbPath = dbPath;
    this.initialized = false;
  }

  initialize() {
    if (this.initialized) return;

    fs.mkdirSync(path.dirname(this.dbPath), { recursive: true });
    this.runSql(`
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
      const safeNow = this.escape(now);
      this.runSql(`
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
          COALESCE(scored_at, '${safeNow}'),
          COALESCE(provider, ''),
          COALESCE(model, ''),
          '${safeNow}',
          '${safeNow}'
        FROM ats_scores;
      `);
    }

    this.runSqlAllowError(`ALTER TABLE job_results ADD COLUMN posted_date TEXT;`);

    this.initialized = true;
  }

  getByUrl(jobUrl) {
    if (!jobUrl) return null;

    const safeUrl = this.escape(jobUrl);
    const output = this.runSql(
      `SELECT json_object('ats_score', ats_score, 'ats_reasoning', ats_reasoning, 'scored_at', scored_at) FROM job_results WHERE job_url = '${safeUrl}' LIMIT 1;`,
      true
    );

    const line = output.split('\n').find(Boolean);
    if (!line) return null;

    let payload;
    try {
      payload = JSON.parse(line);
    } catch (_) {
      return null;
    }

    return {
      score: parseInt(payload.ats_score, 10) || 0,
      reasoning: payload.ats_reasoning || '',
      scoredAt: payload.scored_at || new Date().toISOString()
    };
  }

  getJobByUrl(jobUrl) {
    if (!jobUrl) return null;

    const safeUrl = this.escape(jobUrl);
    const output = this.runSql(
      `SELECT json_object(
        'job_url', job_url,
        'title', title,
        'location', location,
        'company', company,
        'description', description,
        'source', source,
        'posted_date', posted_date,
        'ats_score', ats_score,
        'ats_reasoning', ats_reasoning,
        'scored_at', scored_at
      ) FROM job_results WHERE job_url = '${safeUrl}' LIMIT 1;`,
      true
    );

    const line = output.split('\n').find(Boolean);
    if (!line) return null;

    let payload;
    try {
      payload = JSON.parse(line);
    } catch (_) {
      return null;
    }

    return {
      url: payload.job_url || '',
      title: payload.title || '',
      location: payload.location || 'Not specified',
      company: payload.company || '',
      description: payload.description || '',
      source: payload.source || '',
      postedDate: payload.posted_date || '',
      atsScore: parseInt(payload.ats_score, 10) || 0,
      atsReasoning: payload.ats_reasoning || '',
      scoredAt: payload.scored_at || new Date().toISOString()
    };
  }

  getAllJobUrls() {
    const output = this.runSql('SELECT job_url FROM job_results;', true);
    if (!output) return [];
    return output.split('\n').map(line => line.trim()).filter(Boolean);
  }

  touchJobUrl(jobUrl) {
    if (!jobUrl) return;
    const safeUrl = this.escape(jobUrl);
    const safeNow = this.escape(new Date().toISOString());
    this.runSql(`
      UPDATE job_results
      SET last_seen_at = '${safeNow}'
      WHERE job_url = '${safeUrl}';
    `);
  }

  upsert(job, atsResult, provider, model) {
    if (!job?.url) return;

    const now = new Date().toISOString();
    const safe = {
      jobUrl: this.escape(job.url),
      title: this.escape(job.title || ''),
      company: this.escape(job.company || ''),
      location: this.escape(job.location || ''),
      description: this.escape(job.description || ''),
      source: this.escape(job.source || ''),
      postedDate: this.escape(job.postedDate || ''),
      reasoning: this.escape(atsResult.reasoning || ''),
      scoredAt: this.escape(atsResult.timestamp || new Date().toISOString()),
      provider: this.escape(provider || ''),
      model: this.escape(model || ''),
      firstSeenAt: this.escape(now),
      lastSeenAt: this.escape(now)
    };

    const score = Number.isFinite(atsResult.score) ? Math.max(0, Math.min(100, atsResult.score)) : 0;

    this.runSql(`
      INSERT INTO job_results (
        job_url, title, company, location, description, source, posted_date, ats_score, ats_reasoning, scored_at, provider, model, first_seen_at, last_seen_at
      ) VALUES (
        '${safe.jobUrl}', '${safe.title}', '${safe.company}', '${safe.location}', '${safe.description}', '${safe.source}', '${safe.postedDate}', ${score}, '${safe.reasoning}', '${safe.scoredAt}', '${safe.provider}', '${safe.model}', '${safe.firstSeenAt}', '${safe.lastSeenAt}'
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
    `);
  }

  runSql(sql, returnOutput = false) {
    const args = ['-noheader', '-separator', '\t', this.dbPath, sql];
    const result = spawnSync('sqlite3', args, { encoding: 'utf8' });

    if (result.status !== 0) {
      const stderr = (result.stderr || '').trim() || 'Unknown sqlite3 error';
      throw new Error(`SQLite cache error: ${stderr}`);
    }

    return returnOutput ? (result.stdout || '').trim() : '';
  }

  runSqlAllowError(sql) {
    const args = ['-noheader', '-separator', '\t', this.dbPath, sql];
    spawnSync('sqlite3', args, { encoding: 'utf8' });
  }

  escape(value) {
    return String(value).replace(/'/g, "''");
  }

  tableExists(tableName) {
    const safeName = this.escape(tableName);
    const output = this.runSql(
      `SELECT name FROM sqlite_master WHERE type='table' AND name='${safeName}' LIMIT 1;`,
      true
    );
    return Boolean(output.trim());
  }
}

module.exports = ATSCacheDB;
