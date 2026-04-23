const BaseScraper = require('./base-scraper');

class WorkdayScraper extends BaseScraper {
  async scrape() {
    const jobs = [];
    const selectors = this.boardConfig.selectors;
    const maxJobs = this.globalConfig.max_jobs_per_board || 50;
    const seenJobUrls = new Set();
    
    try {
      console.log(`\nScraping Workday board: ${this.boardConfig.name}`);
      await this.page.goto(this.boardConfig.url, { waitUntil: 'networkidle2' });
      
      // Wait for job list to load
      await this.waitForSelector(selectors.job_list_container, 10000);
      await this.delay(3000); // Additional wait for dynamic content
      
      let hasNextPage = true;
      let pageNum = 1;
      
      while (hasNextPage && (maxJobs === 0 || jobs.length < maxJobs)) {
        console.log(`  Processing page ${pageNum}...`);
        
        // Get all job cards on current page
        const pageJobs = await this.page.evaluate((sel) => {
          const jobCards = document.querySelectorAll(sel.job_card);
          const extracted = [];
          
          jobCards.forEach(card => {
            const titleEl = card.querySelector(sel.title);
            const locationEl = card.querySelector(sel.location);
            
            if (titleEl) {
              const href =
                titleEl.getAttribute('href') ||
                titleEl.closest('a')?.getAttribute('href') ||
                '';
              extracted.push({
                title: titleEl.textContent.trim(),
                location: locationEl ? locationEl.textContent.trim() : 'Not specified',
                jobId: card.getAttribute(sel.job_url_attribute) || '',
                url: href ? new URL(href, window.location.href).toString() : '',
                source: 'Workday'
              });
            }
          });
          
          return extracted;
        }, selectors);
        
        // Get job details for each job
        for (const job of pageJobs) {
          if (maxJobs > 0 && jobs.length >= maxJobs) break;

          const normalizedUrl = (job.url || '').trim().toLowerCase();
          if (normalizedUrl && seenJobUrls.has(normalizedUrl)) {
            continue;
          }

          const forceRecompute = this.globalConfig.scoring?.force_recompute === true;
          if (!forceRecompute && normalizedUrl && this.globalConfig.known_job_urls?.has(normalizedUrl)) {
            const cachedJob = this.globalConfig.results_db?.getJobByUrl(job.url);
            if (cachedJob) {
              jobs.push(cachedJob);
              seenJobUrls.add(normalizedUrl);
              console.log(`    ↺ Cached ${cachedJob.title}`);
              continue;
            }
          }
          
          try {
            const jobDetail = await this.getJobDetails(job);
            if (jobDetail) {
              jobs.push(jobDetail);
              if (normalizedUrl) {
                seenJobUrls.add(normalizedUrl);
              }
              console.log(`    ✓ ${job.title}`);
            }
          } catch (e) {
            console.log(`    ✗ Error getting details for ${job.title}: ${e.message}`);
          }
          
          await this.delay(1000);
        }
        
        // Check for next page
        hasNextPage = await this.goToNextPage(selectors.next_button);
        if (hasNextPage) {
          pageNum++;
          await this.delay(this.globalConfig.request_delay_ms || 2000);
        }
      }
      
    } catch (error) {
      console.error(`Error scraping Workday board: ${error.message}`);
    }
    
    console.log(`  Total jobs scraped: ${jobs.length}`);
    return jobs;
  }
  
  async getJobDetails(job) {
    const selectors = this.boardConfig.selectors;
    
    try {
      if (!job.url) {
        return { ...job, description: '', url: this.boardConfig.url, company: this.boardConfig.name };
      }

      const detailPage = await this.browser.newPage();
      await detailPage.setViewport({ width: 1920, height: 1080 });
      await detailPage.setUserAgent(
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
      );
      await detailPage.goto(job.url, { waitUntil: 'networkidle2' });
      await detailPage.waitForSelector('body', { timeout: 10000 });
      await this.delay(1500);

      const description = await detailPage.evaluate((sel) => {
        const descEl = document.querySelector(sel.description);
        return descEl ? descEl.textContent.trim() : '';
      }, selectors);

      await detailPage.close();

      return {
        ...job,
        description: description.substring(0, 3000),
        url: job.url,
        company: this.boardConfig.name
      };
    } catch (e) {
      return { ...job, description: '', url: job.url || this.boardConfig.url, company: this.boardConfig.name };
    }
  }
  
  async goToNextPage(nextButtonSelector) {
    if (!nextButtonSelector) return false;
    
    try {
      const nextButton = await this.page.$(nextButtonSelector);
      if (!nextButton) return false;
      
      const isDisabled = await nextButton.evaluate(el => 
        el.disabled || el.getAttribute('aria-disabled') === 'true'
      );
      
      if (isDisabled) return false;
      
      await nextButton.click();
      await this.delay(3000);
      return true;
    } catch (e) {
      return false;
    }
  }
}

module.exports = WorkdayScraper;
