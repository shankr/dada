const WorkdayScraper = require('./workday-scraper');
const GreenhouseScraper = require('./greenhouse-scraper');
const LeverScraper = require('./lever-scraper');
const BaseScraper = require('./base-scraper');

class ScraperFactory {
  static createScraper(boardConfig, globalConfig) {
    switch (boardConfig.type.toLowerCase()) {
      case 'workday':
        return new WorkdayScraper(boardConfig, globalConfig);
      case 'greenhouse':
        return new GreenhouseScraper(boardConfig, globalConfig);
      case 'lever':
        return new LeverScraper(boardConfig, globalConfig);
      case 'custom':
        return new CustomScraper(boardConfig, globalConfig);
      default:
        console.warn(`Unknown scraper type: ${boardConfig.type}, using generic scraper`);
        return new CustomScraper(boardConfig, globalConfig);
    }
  }
}

// Generic scraper for custom job boards
class CustomScraper extends BaseScraper {
  async scrape() {
    const jobs = [];
    const selectors = this.boardConfig.selectors;
    const maxJobs = this.globalConfig.max_jobs_per_board || 50;
    
    try {
      console.log(`\nScraping custom board: ${this.boardConfig.name}`);
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
            const locationEl = sel.location ? card.querySelector(sel.location) : null;
            
            if (titleEl) {
              let url = '';
              if (sel.job_url_attribute) {
                if (sel.job_url_attribute === 'href') {
                  const linkEl = titleEl.tagName === 'A' ? titleEl : card.querySelector('a');
                  url = linkEl ? linkEl.href : '';
                } else {
                  url = card.getAttribute(sel.job_url_attribute) || '';
                }
              }
              
              extracted.push({
                title: titleEl.textContent.trim(),
                location: locationEl ? locationEl.textContent.trim() : 'Not specified',
                url: url,
                source: 'Custom'
              });
            }
          });
          
          return extracted;
        }, selectors);
        
        for (const job of pageJobs) {
          if (maxJobs > 0 && jobs.length >= maxJobs) break;
          
          try {
            const jobDetail = await this.getJobDetails(job);
            if (jobDetail) {
              jobs.push(jobDetail);
              console.log(`    ✓ ${job.title}`);
            }
          } catch (e) {
            console.log(`    ✗ Error: ${e.message}`);
          }
          
          await this.delay(1000);
        }
        
        hasNextPage = await this.goToNextPage(selectors.next_button);
        if (hasNextPage) {
          pageNum++;
          await this.delay(this.globalConfig.request_delay_ms || 2000);
        }
      }
      
    } catch (error) {
      console.error(`Error scraping custom board: ${error.message}`);
    }
    
    console.log(`  Total jobs scraped: ${jobs.length}`);
    return jobs;
  }
  
  async getJobDetails(job) {
    try {
      if (job.url && job.url !== this.boardConfig.url) {
        await this.page.goto(job.url, { waitUntil: 'networkidle2' });
        await this.delay(2000);
      }
      
      const selectors = this.boardConfig.selectors;
      const description = await this.page.evaluate((sel) => {
        if (sel.description) {
          const el = document.querySelector(sel.description);
          if (el) return el.textContent.trim();
        }
        return document.body.innerText.substring(0, 3000);
      }, selectors);
      
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
      
      const isDisabled = await nextButton.evaluate(el => 
        el.disabled || 
        el.getAttribute('aria-disabled') === 'true' ||
        el.classList.contains('disabled')
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

module.exports = ScraperFactory;