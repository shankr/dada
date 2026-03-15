const axios = require('axios');
const BaseScraper = require('./base-scraper');

class CustomApiScraper extends BaseScraper {
  async scrape() {
    const jobs = [];
    const maxJobs = this.globalConfig.max_jobs_per_board || 50;
    const api = this.boardConfig.api || {};
    const pagination = api.pagination || {};
    const headers = {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...(api.headers || {})
    };

    try {
      console.log(`\nScraping custom API board: ${this.boardConfig.name}`);
      await this.ensureSessionHeaders(api, headers);

      let offset = pagination.offset_start || 0;
      const size = pagination.page_size || 10;
      let total = null;
      let pageNum = 1;

      while (maxJobs === 0 || jobs.length < maxJobs) {
        console.log(`  Processing page ${pageNum}...`);

        const payload = { ...(api.payload || {}) };
        if (pagination.offset_field) payload[pagination.offset_field] = offset;
        if (pagination.size_field) payload[pagination.size_field] = size;

        const response = await axios({
          method: api.http_method || 'POST',
          url: this.boardConfig.url,
          headers,
          data: payload,
          timeout: 30000
        });

        const data = response.data;
        const results = this.getByPath(data, api.results_path) || [];
        const totalHits = api.total_path ? this.getByPath(data, api.total_path) : null;
        if (!Array.isArray(results) || results.length === 0) {
          const topKeys = data && typeof data === 'object' ? Object.keys(data) : [];
          console.log(`    No results returned (totalHits=${totalHits ?? 'unknown'}). Top-level keys: ${topKeys.join(', ')}`);
          break;
        }

        for (const item of results) {
          if (maxJobs > 0 && jobs.length >= maxJobs) break;

          const job = this.mapJob(item, api);
          if (!job || !job.url) continue;

          const normalizedUrl = job.url.trim().toLowerCase();
          if (normalizedUrl && this.globalConfig.known_job_urls?.has(normalizedUrl)) {
            const cachedJob = this.globalConfig.results_db?.getJobByUrl(job.url);
            if (cachedJob) {
              jobs.push(cachedJob);
              console.log(`    ↺ Cached ${cachedJob.title}`);
              continue;
            }
          }

          jobs.push(job);
          console.log(`    ✓ ${job.title}`);
        }

        if (total == null && api.total_path) {
          total = totalHits;
        }

        offset += size;
        if (total != null && offset >= total) break;

        pageNum++;
        await this.delay(this.globalConfig.request_delay_ms || 2000);
      }
    } catch (error) {
      console.error(`Error scraping custom API board: ${error.message}`);
    }

    console.log(`  Total jobs scraped: ${jobs.length}`);
    return jobs;
  }

  mapJob(item, api) {
    const title = this.getByPath(item, api.title_path) || '';
    const location = this.getByPath(item, api.location_path) || 'Not specified';
    const url = this.getByPath(item, api.url_path) || '';
    const description = api.description_path ? this.getByPath(item, api.description_path) : '';
    const postedDate = api.posted_date_path ? this.getByPath(item, api.posted_date_path) : '';

    if (!title || !url) return null;

    return {
      title: String(title).trim(),
      location: String(location).trim(),
      url: String(url).trim(),
      description: description ? String(description).trim() : '',
      postedDate: postedDate ? String(postedDate).trim() : '',
      source: 'CustomAPI',
      company: this.boardConfig.name
    };
  }

  getByPath(obj, path) {
    if (!obj || !path) return null;
    const parts = String(path).split('.').filter(Boolean);
    let cur = obj;
    for (const p of parts) {
      if (cur == null) return null;
      cur = cur[p];
    }
    return cur;
  }

  async ensureSessionHeaders(api, headers) {
    const bootstrap = api.session_bootstrap || {};
    if (!bootstrap.enabled) return;

    const needsCookie = this.isMissingHeader(headers.Cookie);
    const needsCsrf = this.isMissingHeader(headers['X-CSRF-TOKEN']);
    if (!needsCookie && !needsCsrf) return;

    if (!this.page) return;

    const url = bootstrap.url || this.boardConfig.url;
    await this.page.goto(url, { waitUntil: 'networkidle2' });
    await this.delay(2000);

    const cookies = await this.page.cookies();
    if (needsCookie) {
      headers.Cookie = cookies.map(c => `${c.name}=${c.value}`).join('; ');
    }

    if (needsCsrf) {
      let csrf = null;

      // Try common cookie names.
      const csrfCookie = cookies.find(c => /csrf|xsrf/i.test(c.name));
      if (csrfCookie) csrf = csrfCookie.value;

      // Try extracting csrfToken from PLAY_SESSION JWT payload.
      if (!csrf) {
        const session = cookies.find(c => c.name === 'PLAY_SESSION');
        if (session) {
          const payload = this.decodeJwtPayload(session.value);
          csrf = payload?.data?.csrfToken || payload?.csrfToken || null;
        }
      }

      // Try meta tag.
      if (!csrf) {
        csrf = await this.page.evaluate(() => {
          const el = document.querySelector('meta[name="csrf-token"]');
          return el ? el.getAttribute('content') : null;
        });
      }

      if (csrf) {
        headers['X-CSRF-TOKEN'] = csrf;
      }
    }
  }

  isMissingHeader(value) {
    return !value || String(value).includes('${');
  }

  decodeJwtPayload(token) {
    try {
      const parts = token.split('.');
      if (parts.length < 2) return null;
      const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
      const json = Buffer.from(payload, 'base64').toString('utf8');
      return JSON.parse(json);
    } catch (_) {
      return null;
    }
  }
}

module.exports = CustomApiScraper;
