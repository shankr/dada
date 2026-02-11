const BaseScraper = require('./base-scraper');

class GreenhouseScraper extends BaseScraper {
  async scrape() {
    const jobs = [];
    const selectors = this.boardConfig.selectors;
    const maxJobs = this.globalConfig.max_jobs_per_board || 50;
    
    try {
      console.log(`\nScraping Greenhouse board: ${this.boardConfig.name}`);
      await this.page.goto(this.boardConfig.url, { waitUntil: 'networkidle2' });
      
      await this.waitForSelector(selectors.job_list_container, 10000);
      await this.delay(2000);
      
      let hasNextPage = true;
      let pageNum = 1;
      
      while (hasNextPage && (maxJobs === 0 || jobs.length < maxJobs)) {
        console.log(`  Processing page ${pageNum}...`);
        
        const pageJobs = await this.page.evaluate((sel) => {
          const jobCards = document.querySelectorAll(sel.job_card);
          const extracted = [];
          
          jobCards.forEach(card => {
            const titleEl = card.querySelector(sel.title);
            const locationEl = card.querySelector(sel.location);
            
            if (titleEl) {
              const linkEl = titleEl.tagName === 'A' ? titleEl : card.querySelector('a');
              extracted.push({
                title: titleEl.textContent.trim(),
                location: locationEl ? locationEl.textContent.trim() : 'Not specified',
                url: linkEl ? linkEl.href : '',
                source: 'Greenhouse'
              });
            }
          });
          
          return extracted;
        }, selectors);
        
        // Get details for each job
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
        
        // Try to go to next page
        hasNextPage = await this.goToNextPage(selectors.next_button);
        if (hasNextPage) {
          pageNum++;
          await this.delay(this.globalConfig.request_delay_ms || 2000);
        }
      }
      
    } catch (error) {
      console.error(`Error scraping Greenhouse board: ${error.message}`);
    }
    
    console.log(`  Total jobs scraped: ${jobs.length}`);
    return jobs;
  }
  
  async getJobDetails(job) {
    try {
      // Navigate to job detail page
      await this.page.goto(job.url, { waitUntil: 'networkidle2' });
      await this.delay(2000);
      
      const selectors = this.boardConfig.selectors;
      
      // Extract description
      const description = await this.page.evaluate(() => {
        // Try multiple selectors for Greenhouse job descriptions
        const selectors = [
          '#content',
          '.job-description',
          '[data-qa="job-description"]',
          '.description',
          '#job_description'
        ];
        
        for (const sel of selectors) {
          const el = document.querySelector(sel);
          if (el) {
            return el.textContent.trim();
          }
        }
        
        // Fallback: get all text content
        return document.body.innerText.substring(0, 3000);
      });
      
      return {
        ...job,
        description: description.substring(0, 3000),
        company: this.boardConfig.name
      };
    } catch (e) {
      return { ...job, description: '', company: this.boardConfig.name };
    }
  }
  
  async goToNextPage(nextButtonSelector) {
    if (!nextButtonSelector) return false;
    
    try {
      const nextButton = await this.page.$(nextButtonSelector);
      if (!nextButton) return false;
      
      const href = await nextButton.evaluate(el => el.getAttribute('href'));
      if (!href || href === '#' || href === '') return false;
      
      await nextButton.click();
      await this.delay(3000);
      return true;
    } catch (e) {
      return false;
    }
  }
}

module.exports = GreenhouseScraper;