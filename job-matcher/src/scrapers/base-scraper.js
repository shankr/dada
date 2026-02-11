const puppeteer = require('puppeteer');

class BaseScraper {
  constructor(boardConfig, globalConfig) {
    this.boardConfig = boardConfig;
    this.globalConfig = globalConfig;
    this.browser = null;
    this.page = null;
  }
  
  async initialize() {
    this.browser = await puppeteer.launch({
      headless: 'new',
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage'
      ]
    });
    
    this.page = await this.browser.newPage();
    await this.page.setViewport({ width: 1920, height: 1080 });
    await this.page.setUserAgent(
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    );
  }
  
  async close() {
    if (this.browser) {
      await this.browser.close();
    }
  }
  
  async delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
  
  async waitForSelector(selector, timeout = 5000) {
    try {
      await this.page.waitForSelector(selector, { timeout });
      return true;
    } catch (e) {
      return false;
    }
  }
}

module.exports = BaseScraper;