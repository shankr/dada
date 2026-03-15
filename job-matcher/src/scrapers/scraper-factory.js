const WorkdayScraper = require('./workday-scraper');
const GreenhouseScraper = require('./greenhouse-scraper');
const LeverScraper = require('./lever-scraper');
const BaseScraper = require('./base-scraper');
const CustomApiScraper = require('./custom-api-scraper');

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
      case 'custom-api':
        return new CustomApiScraper(boardConfig, globalConfig);
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
    const seenJobKeys = new Set();
    const selectors = this.boardConfig.selectors;
    const maxJobs = this.globalConfig.max_jobs_per_board || 50;
    
    try {
      console.log(`\nScraping custom board: ${this.boardConfig.name}`);
      await this.page.goto(this.boardConfig.url, { waitUntil: 'networkidle2' });
      
      await this.waitForSelector(selectors.job_list_container, 10000);
      await this.delay(2000);
      
      let hasNextPage = true;
      let pageNum = 1;
      let pagesWithoutNewJobs = 0;
      
      while (hasNextPage && (maxJobs === 0 || jobs.length < maxJobs)) {
        console.log(`  Processing page ${pageNum}...`);
        await this.expandCurrentPage(selectors);
        
        const pageJobs = await this.page.evaluate((sel) => {
          const jobCards = document.querySelectorAll(sel.job_card);
          const extracted = [];
          
          jobCards.forEach(card => {
            const titleEl = card.querySelector(sel.title);
            const locationEl = sel.location ? card.querySelector(sel.location) : null;
            
            if (titleEl) {
              let url = '';
              let linkEl = null;
              if (sel.job_url_attribute) {
                if (sel.job_url_attribute === 'href') {
                  linkEl = sel.link ? card.querySelector(sel.link) : (titleEl.tagName === 'A' ? titleEl : card.querySelector('a'));
                  if (linkEl) {
                    url = linkEl.href || '';
                  }
                } else {
                  url = card.getAttribute(sel.job_url_attribute) || '';
                }
              }

              if (sel.require_link && !linkEl) return;
              if (sel.require_link_attr && linkEl && !linkEl.getAttribute(sel.require_link_attr)) return;
              if (sel.url_pattern && url && !url.includes(sel.url_pattern)) return;
              
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
        
        let newJobsOnPage = 0;
        for (const job of pageJobs) {
          if (maxJobs > 0 && jobs.length >= maxJobs) break;

          const normalizedUrl = (job.url || '').trim().toLowerCase();
          const jobKey = (normalizedUrl || `${job.title}|${job.location}`).toLowerCase();
          if (seenJobKeys.has(jobKey)) {
            continue;
          }

          const forceRecompute = this.globalConfig.scoring?.force_recompute === true;
          if (!forceRecompute && normalizedUrl && this.globalConfig.known_job_urls?.has(normalizedUrl)) {
            const cachedJob = this.globalConfig.results_db?.getJobByUrl(job.url);
            if (cachedJob) {
              jobs.push(cachedJob);
              seenJobKeys.add(jobKey);
              newJobsOnPage++;
              console.log(`    ↺ Cached ${cachedJob.title}`);
              continue;
            }
          }
          
          try {
            const jobDetail = await this.getJobDetails(job);
            if (jobDetail) {
              jobs.push(jobDetail);
              seenJobKeys.add(jobKey);
              newJobsOnPage++;
              console.log(`    ✓ ${job.title}`);
            }
          } catch (e) {
            console.log(`    ✗ Error: ${e.message}`);
          }
          
          await this.delay(1000);
        }

        if (newJobsOnPage === 0) {
          pagesWithoutNewJobs++;
          if (pagesWithoutNewJobs >= 2) {
            break;
          }
        } else {
          pagesWithoutNewJobs = 0;
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
    let detailPage = this.page;
    let shouldClosePage = false;

    try {
      if (job.url && job.url !== this.boardConfig.url) {
        detailPage = await this.browser.newPage();
        shouldClosePage = true;
        await detailPage.setViewport({ width: 1920, height: 1080 });
        await detailPage.setUserAgent(
          'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        );
        await detailPage.goto(job.url, { waitUntil: 'networkidle2' });
        await this.delay(2000);
      }
      
      const selectors = this.boardConfig.selectors;
      const description = await detailPage.evaluate((sel) => {
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
    } finally {
      if (shouldClosePage) {
        try {
          await detailPage.close();
        } catch (_) {
          // no-op
        }
      }
    }
  }
  
  async goToNextPage(nextButtonSelector) {
    if (!nextButtonSelector) return false;
    
    try {
      const paginationState = await this.page.evaluate(() => {
        const currentEl = document.querySelector('.pagination-current');
        const totalEl = document.querySelector('.pagination-total-pages');
        if (!currentEl || !totalEl) return null;

        const current = parseInt(currentEl.value || currentEl.textContent || '', 10);
        const total = parseInt((totalEl.textContent || '').replace(/[^\d]/g, ''), 10);
        if (Number.isNaN(current) || Number.isNaN(total)) return null;

        return { current, total };
      });

      if (paginationState && paginationState.current >= paginationState.total) {
        return false;
      }

      const nextButton = await this.page.$(nextButtonSelector);
      if (!nextButton) return false;
      
      const { isDisabled, href, isAnchor } = await nextButton.evaluate(el => {
        const disabled =
          el.disabled ||
          el.getAttribute('aria-disabled') === 'true' ||
          el.classList.contains('disabled');
        const anchorHref = el.tagName === 'A' ? el.getAttribute('href') : null;
        return {
          isDisabled: disabled,
          href: anchorHref,
          isAnchor: el.tagName === 'A'
        };
      });
      
      if (isDisabled) return false;

      if (isAnchor && href) {
        const nextUrl = new URL(href, this.page.url()).toString();
        await this.page.goto(nextUrl, { waitUntil: 'networkidle2' });
        return true;
      }
      
      await nextButton.click();
      await this.delay(3000);
      return true;
    } catch (e) {
      return false;
    }
  }

  async expandCurrentPage(selectors) {
    if (!selectors) return;

    // Some boards expose all results via a dedicated "Show All" control.
    if (selectors.show_all_button) {
      const clickedShowAll = await this.clickButtonIfVisible(selectors.show_all_button);
      if (clickedShowAll) {
        await this.delay(2500);
        return;
      }
    }

    if (!selectors.view_more_button) return;

    // Repeatedly click "View More" until no longer visible/clickable.
    for (let i = 0; i < 10; i++) {
      const clicked = await this.clickButtonIfVisible(selectors.view_more_button);
      if (!clicked) break;
      await this.delay(1500);
    }
  }

  async clickButtonIfVisible(selector) {
    try {
      return await this.page.evaluate((sel) => {
        const el = document.querySelector(sel);
        if (!el) return false;

        const style = window.getComputedStyle(el);
        const hidden = style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity || '1') === 0;
        const disabled = el.disabled || el.getAttribute('aria-disabled') === 'true' || el.classList.contains('disabled');
        if (hidden || disabled) return false;

        el.click();
        return true;
      }, selector);
    } catch (e) {
      return false;
    }
  }
}

module.exports = ScraperFactory;
