const BaseScraper = require('./base-scraper');

class LeverScraper extends BaseScraper {
  async scrape() {
    const jobs = [];
    const selectors = this.boardConfig.selectors;
    const maxJobs = this.globalConfig.max_jobs_per_board || 50;
    
    try {
      console.log(`\nScraping Lever board: ${this.boardConfig.name}`);
      await this.page.goto(this.boardConfig.url, { waitUntil: 'networkidle2' });
      
      await this.waitForSelector(selectors.job_list_container, 10000);
      await this.delay(2000);
      
      // Lever typically loads all jobs at once or uses infinite scroll
      // Try scrolling to load all content
      await this.scrollToLoadAll();
      
      const pageJobs = await this.page.evaluate((sel) => {
        const jobCards = document.querySelectorAll(sel.job_card);
        const extracted = [];
        
        jobCards.forEach(card => {
          const titleEl = card.querySelector(sel.title);
          const locationEl = card.querySelector(sel.location);
          const teamEl = card.querySelector(sel.team || '.sort-by-team');
          const linkEl = card.querySelector(sel.apply_link || 'a');
          
          if (titleEl) {
            extracted.push({
              title: titleEl.textContent.trim(),
              location: locationEl ? locationEl.textContent.trim() : 'Not specified',
              team: teamEl ? teamEl.textContent.trim() : '',
              url: linkEl ? linkEl.href : '',
              source: 'Lever'
            });
          }
        });
        
        return extracted;
      }, selectors);
      
      console.log(`  Found ${pageJobs.length} jobs`);
      
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
      
    } catch (error) {
      console.error(`Error scraping Lever board: ${error.message}`);
    }
    
    console.log(`  Total jobs scraped: ${jobs.length}`);
    return jobs;
  }
  
  async scrollToLoadAll() {
    let previousHeight = 0;
    let attempts = 0;
    const maxAttempts = 10;
    
    while (attempts < maxAttempts) {
      const currentHeight = await this.page.evaluate('document.body.scrollHeight');
      if (currentHeight === previousHeight) {
        break;
      }
      
      await this.page.evaluate(() => {
        window.scrollTo(0, document.body.scrollHeight);
      });
      
      await this.delay(1500);
      previousHeight = currentHeight;
      attempts++;
    }
  }
  
  async getJobDetails(job) {
    try {
      // Navigate to job detail page
      if (!job.url) {
        return { ...job, description: '', company: this.boardConfig.name };
      }
      
      await this.page.goto(job.url, { waitUntil: 'networkidle2' });
      await this.delay(2000);
      
      // Extract description
      const description = await this.page.evaluate(() => {
        // Try multiple selectors for Lever job descriptions
        const selectors = [
          '.section.page-centered',
          '[data-qa="job-description"]',
          '.job-description',
          '.description',
          '.posting-content'
        ];
        
        for (const sel of selectors) {
          const el = document.querySelector(sel);
          if (el) {
            return el.textContent.trim();
          }
        }
        
        // Fallback
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
}

module.exports = LeverScraper;