import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone


class ATSCacheDB:
    def __init__(self, db_path):
        self.db_path = db_path
        self._conn = None

    def initialize(self):
        if self._conn:
            return

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")

        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS job_results (
                job_url TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                description TEXT,
                normalized_job_json TEXT,
                score_breakdown_json TEXT,
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
            CREATE TABLE IF NOT EXISTS resume_cache (
                resume_key TEXT PRIMARY KEY,
                resume_path TEXT NOT NULL,
                profile_json TEXT NOT NULL,
                cached_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS scrape_cache (
                board_name TEXT NOT NULL,
                job_url TEXT NOT NULL,
                job_data_json TEXT NOT NULL,
                scraped_at TEXT NOT NULL,
                PRIMARY KEY (board_name, job_url)
            );
        """)

        self._migrate_old_tables()
        self._ensure_columns()
        self._migrate_scrape_cache()
        self._conn.commit()

    def _migrate_old_tables(self):
        cursor = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ats_scores'"
        )
        if cursor.fetchone():
            now = datetime.now(timezone.utc).isoformat()
            self._conn.execute("""
                INSERT OR IGNORE INTO job_results (
                    job_url, title, company, location, description,
                    normalized_job_json, score_breakdown_json, source, posted_date,
                    ats_score, ats_reasoning, scored_at, provider, model,
                    first_seen_at, last_seen_at
                )
                SELECT
                    job_url,
                    COALESCE(title, ''),
                    COALESCE(company, ''),
                    COALESCE(location, ''),
                    '',
                    '',
                    '',
                    '',
                    '',
                    COALESCE(ats_score, 0),
                    COALESCE(ats_reasoning, ''),
                    COALESCE(scored_at, ?),
                    COALESCE(provider, ''),
                    COALESCE(model, ''),
                    ?,
                    ?
                FROM ats_scores
            """, (now, now, now))

    def table_exists(self, name):
        cursor = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
        )
        return cursor.fetchone() is not None

    def column_exists(self, table, col):
        cursor = self._conn.execute(f"PRAGMA table_info({table})")
        return any(row[1] == col for row in cursor.fetchall())

    def _ensure_columns(self):
        for col in ["posted_date", "normalized_job_json", "score_breakdown_json"]:
            if not self.column_exists("job_results", col):
                self._conn.execute(f"ALTER TABLE job_results ADD COLUMN {col} TEXT")

        if not self.column_exists("job_results", "llm_version"):
            self._conn.execute("ALTER TABLE job_results ADD COLUMN llm_version INTEGER NOT NULL DEFAULT 1")

        if not self.column_exists("job_results", "resume_md5_hash"):
            self._conn.execute("ALTER TABLE job_results ADD COLUMN resume_md5_hash TEXT NOT NULL DEFAULT ''")

        if not self.column_exists("resume_cache", "llm_version"):
            self._conn.execute("ALTER TABLE resume_cache ADD COLUMN llm_version INTEGER NOT NULL DEFAULT 1")

    def _migrate_scrape_cache(self):
        if not self.column_exists("scrape_cache", "scraped_at"):
            return
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS scrape_cache_new (
                board_name TEXT NOT NULL,
                job_url TEXT NOT NULL,
                job_data_json TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                PRIMARY KEY (board_name, job_url)
            );
            INSERT INTO scrape_cache_new (board_name, job_url, job_data_json, first_seen_at, last_seen_at)
                SELECT board_name, job_url, job_data_json, scraped_at, scraped_at FROM scrape_cache;
            DROP TABLE scrape_cache;
            ALTER TABLE scrape_cache_new RENAME TO scrape_cache;
        """)

    # ── Score cache (job_results) ──────────────────────────────────────

    def get_by_url(self, job_url, llvm_version=1, resume_md5_hash=""):
        if not job_url:
            return None
        cursor = self._conn.execute(
            "SELECT ats_score, ats_reasoning, scored_at, provider, model "
            "FROM job_results WHERE job_url=? AND llm_version=? AND resume_md5_hash=? LIMIT 1",
            (job_url, llvm_version, resume_md5_hash),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "score": int(row["ats_score"]) if row["ats_score"] else 0,
            "reasoning": row["ats_reasoning"] or "",
            "scoredAt": row["scored_at"] or datetime.now(timezone.utc).isoformat(),
            "provider": row["provider"] or "",
            "model": row["model"] or "",
        }

    def get_job_by_url(self, job_url):
        if not job_url:
            return None
        cursor = self._conn.execute(
            "SELECT * FROM job_results WHERE job_url=? LIMIT 1", (job_url,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "url": row["job_url"] or "",
            "title": row["title"] or "",
            "location": row["location"] or "Not specified",
            "company": row["company"] or "",
            "description": row["description"] or "",
            "normalizedJob": self._parse_json(row["normalized_job_json"]),
            "scoreBreakdown": self._parse_json(row["score_breakdown_json"]),
            "source": row["source"] or "",
            "postedDate": row["posted_date"] or "",
            "firstSeenAt": row["first_seen_at"] or "",
            "lastSeenAt": row["last_seen_at"] or "",
            "provider": row["provider"] or "",
            "model": row["model"] or "",
            "atsScore": int(row["ats_score"]) if row["ats_score"] else 0,
            "atsReasoning": row["ats_reasoning"] or "",
            "scoredAt": row["scored_at"] or datetime.now(timezone.utc).isoformat(),
        }

    def get_all_job_urls(self):
        cursor = self._conn.execute("SELECT job_url FROM job_results")
        return [row["job_url"] for row in cursor.fetchall() if row["job_url"]]

    def touch_job_url(self, job_url):
        if not job_url:
            return
        self._conn.execute(
            "UPDATE job_results SET last_seen_at=? WHERE job_url=?",
            (datetime.now(timezone.utc).isoformat(), job_url),
        )
        self._conn.commit()

    def upsert(self, job, ats_result, provider, model, llm_version=1, resume_md5_hash=""):
        if not job or not job.get("url"):
            return

        now = datetime.now(timezone.utc).isoformat()
        score = ats_result.get("score", 0)
        if isinstance(score, (int, float)):
            score = max(0, min(100, int(score)))
        else:
            score = 0

        self._conn.execute(
            """
            INSERT INTO job_results (
                job_url, title, company, location, description,
                normalized_job_json, score_breakdown_json, source, posted_date,
                ats_score, ats_reasoning, scored_at, provider, model,
                first_seen_at, last_seen_at, llm_version, resume_md5_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_url) DO UPDATE SET
                title=excluded.title,
                company=excluded.company,
                location=excluded.location,
                description=excluded.description,
                normalized_job_json=excluded.normalized_job_json,
                score_breakdown_json=excluded.score_breakdown_json,
                source=excluded.source,
                posted_date=excluded.posted_date,
                ats_score=excluded.ats_score,
                ats_reasoning=excluded.ats_reasoning,
                scored_at=excluded.scored_at,
                provider=excluded.provider,
                model=excluded.model,
                last_seen_at=excluded.last_seen_at,
                llm_version=excluded.llm_version,
                resume_md5_hash=excluded.resume_md5_hash
            """,
            (
                job["url"],
                job.get("title", ""),
                job.get("company", ""),
                job.get("location", ""),
                job.get("description", ""),
                self._serialize_json(ats_result.get("normalizedJob") or job.get("normalizedJob")),
                self._serialize_json(ats_result.get("scoreBreakdown") or job.get("scoreBreakdown")),
                job.get("source", ""),
                job.get("postedDate", ""),
                score,
                ats_result.get("reasoning", ""),
                ats_result.get("timestamp", now),
                provider or "",
                model or "",
                now,
                now,
                llm_version,
                resume_md5_hash,
            ),
        )
        self._conn.commit()

    # ── Resume cache ─────────────────────────────────────────────────

    def compute_resume_key(self, resume_text):
        return hashlib.md5(resume_text.encode()).hexdigest()

    def get_resume_profile(self, resume_key, llm_version=1):
        if not resume_key:
            return None
        cursor = self._conn.execute(
            "SELECT profile_json FROM resume_cache WHERE resume_key=? AND llm_version=?",
            (resume_key, llm_version),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return self._parse_json(row["profile_json"])

    def set_resume_profile(self, resume_key, llm_version, resume_path, profile):
        if not resume_key:
            return
        self._conn.execute(
            "INSERT OR REPLACE INTO resume_cache (resume_key, llm_version, resume_path, profile_json, cached_at) VALUES (?, ?, ?, ?, ?)",
            (resume_key, llm_version, resume_path, self._serialize_json(profile), datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()

    # ── Scrape cache (key: board_name + job_url) ─────────────────────

    def get_scraped_job(self, board_name, job_url, ttl_seconds):
        if not board_name or not job_url:
            return None
        cursor = self._conn.execute(
            "SELECT job_data_json, first_seen_at, last_seen_at FROM scrape_cache WHERE board_name=? AND job_url=?",
            (board_name, job_url),
        )
        row = cursor.fetchone()
        if not row:
            return None
        try:
            last_seen = datetime.fromisoformat(row["last_seen_at"])
            if (datetime.now(timezone.utc) - last_seen).total_seconds() > ttl_seconds:
                return None
        except (ValueError, TypeError):
            return None
        job = self._parse_json(row["job_data_json"])
        if not job:
            return None
        if not job.get("postedDate"):
            job["postedDate"] = row["first_seen_at"]
        return job

    def set_scraped_job(self, board_name, job):
        if not board_name or not job:
            return
        now = datetime.now(timezone.utc).isoformat()
        url = job.get("url", "")
        if not url:
            return
        cursor = self._conn.execute(
            "SELECT first_seen_at FROM scrape_cache WHERE board_name=? AND job_url=?",
            (board_name, url),
        )
        row = cursor.fetchone()
        first_seen = row["first_seen_at"] if row else now
        self._conn.execute(
            "INSERT OR REPLACE INTO scrape_cache (board_name, job_url, job_data_json, first_seen_at, last_seen_at) VALUES (?, ?, ?, ?, ?)",
            (board_name, url, self._serialize_json(job), first_seen, now),
        )
        self._conn.commit()

    def prune_scraped_jobs(self, board_name, keep_urls):
        if not board_name or not keep_urls:
            return
        placeholders = ",".join("?" * len(keep_urls))
        self._conn.execute(
            f"DELETE FROM scrape_cache WHERE board_name=? AND job_url NOT IN ({placeholders})",
            (board_name, *keep_urls),
        )
        self._conn.commit()

    # ── Helpers ───────────────────────────────────────────────────────

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    @staticmethod
    def _parse_json(value):
        if not value:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None

    @staticmethod
    def _serialize_json(value):
        if not value:
            return ""
        try:
            return json.dumps(value)
        except (TypeError, ValueError):
            return ""
