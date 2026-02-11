const BaseScraper = require('./base-scraper');

class WorkdayScraper extends BaseScraper {
  async scrape() {
    const jobs = [];
    const selectors = this.boardConfig.selectors;
    const maxJobs = this.globalConfig.max_jobs_per_board || 50;
    
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
              extracted.push({
                title: titleEl.textContent.trim(),
                location: locationEl ? locationEl.textContent.trim() : 'Not specified',
                jobId: card.getAttribute(sel.job_url_attribute) || '',
                source: 'Workday'
              });
            }
          });
          
          return extracted;
        }, selectors);
        
        // Get job details for each job
        for (const job of pageJobs) {
          if (maxJobs > 0 && jobs.length >= maxJobs) break;
          
          try {
            const jobDetail = await this.getJobDetails(job);
            if (jobDetail) {
              jobs.push(jobDetail);
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
    // Click on job to get full description
    const selectors = this.boardConfig.selectors;
    
    try {
      // Find and click the job card
      const jobCards = await this.page.$$(selectors.job_card);
      
      for (const card of jobCards) {
        const titleEl = await card.$(selectors.title);
        if (titleEl) {
          const text = await titleEl.evaluate(el => el.textContent.trim());
          if (text === job.title) {
            await card.click();
            await this.delay(2000);
            break;
          }
        }
      }
      
      // Get full description
      const description = await this.page.evaluate((sel) => {
        const descEl = document.querySelector(sel.description);
        return descEl ? descEl.textContent.trim() : '';
      }, selectors);
      
      // Get current URL
      const url = this.page.url();
      
      return {
        ...job,
        description: description.substring(0, 3000), // Limit description length
        url: url,
        company: this.boardConfig.name
      };
    } catch (e) {
      return { ...job, description: '', url: this.boardConfig.url };
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