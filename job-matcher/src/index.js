#!/usr/bin/env node

require('dotenv').config();

const ConfigLoader = require('./config/config-loader');
const PDFParser = require('./parsers/pdf-parser');
const ScraperFactory = require('./scrapers/scraper-factory');
const ATSScorer = require('./ats/ats-scorer');
const ReportGenerator = require('./output/report-generator');
const ATSCacheDB = require('./storage/ats-cache-db');

class JobScraperApp {
  constructor() {
    this.config = null;
    this.resumeData = null;
    this.allJobs = [];
    this.seenJobUrls = new Set();
    this.resultsDb = null;
    this.initialKnownJobUrls = new Set();
  }

  async initialize() {
    console.log('========================================');
    console.log('   Job Scraper with ATS Matching');
    console.log('========================================\n');

    // Load configuration
    console.log('Loading configuration...');
    this.config = ConfigLoader.load();
    this.resultsDb = new ATSCacheDB(this.config.ats_cache_db_path);
    await this.resultsDb.initialize();
    this.initialKnownJobUrls = new Set(
      this.resultsDb.getAllJobUrls().map(url => url.toLowerCase())
    );
    this.config.results_db = this.resultsDb;
    this.config.known_job_urls = new Set(this.initialKnownJobUrls);
    console.log('✓ Configuration loaded\n');

    // Parse resume
    console.log('Parsing resume...');
    const pdfParser = new PDFParser(this.config.resume_path);
    this.resumeData = await pdfParser.extractResumeData();
    console.log(`✓ Resume parsed (${this.resumeData.numPages} pages)\n`);
  }

  async scrapeJobs() {
    console.log('Starting job scraping...');
    console.log(`Found ${this.config.job_boards.length} job boards to scrape\n`);

    for (const boardConfig of this.config.job_boards) {
      const scraper = ScraperFactory.createScraper(boardConfig, this.config);
      
      try {
        await scraper.initialize();
        const jobs = await scraper.scrape();
        const uniqueJobs = [];
        let duplicateCount = 0;

        for (const job of jobs) {
          const normalizedUrl = (job.url || '').trim().toLowerCase();
          if (normalizedUrl) {
            if (this.seenJobUrls.has(normalizedUrl)) {
              duplicateCount++;
              continue;
            }
            this.seenJobUrls.add(normalizedUrl);
            job.isNewThisRun = !this.initialKnownJobUrls.has(normalizedUrl);
          } else {
            job.isNewThisRun = false;
          }
          uniqueJobs.push(job);
        }

        if (duplicateCount > 0) {
          console.log(`  Skipped ${duplicateCount} duplicate job URLs from ${boardConfig.name}`);
        }

        this.allJobs = this.allJobs.concat(uniqueJobs);
      } catch (error) {
        console.error(`Error with board "${boardConfig.name}": ${error.message}`);
      } finally {
        await scraper.close();
      }

      // Delay between boards
      await this.delay(this.config.request_delay_ms || 2000);
    }

    console.log(`\n✓ Scraping complete. Total jobs: ${this.allJobs.length}\n`);
  }

  async scoreJobs() {
    if (this.allJobs.length === 0) {
      console.log('No jobs to score.');
      return;
    }

    console.log('Initializing ATS scoring...');
    const atsScorer = new ATSScorer(this.config);
    
    console.log(`Using provider: ${this.config.llm.provider}`);
    console.log(`Model: ${this.config.llm.model}\n`);

    const scoredJobs = await atsScorer.scoreJobsBatch(
      this.resumeData.cleanText,
      this.allJobs,
      (current, total, title) => {
        process.stdout.write(`\r  Scoring: ${current}/${total} - ${title.substring(0, 45)}...     `);
      }
    );

    this.allJobs = scoredJobs;
    console.log(`\n✓ ATS scoring complete\n`);
  }

  async generateReports() {
    console.log('Generating reports...');
    
    const reportGenerator = new ReportGenerator(this.config.output_path);
    
    // Generate text report
    reportGenerator.generate(this.allJobs, {
      filePath: this.config.resume_path,
      numPages: this.resumeData.numPages
    });

    // Generate JSON report
    reportGenerator.generateJSON(this.allJobs, {
      filePath: this.config.resume_path,
      numPages: this.resumeData.numPages
    });

    console.log('\n✓ All reports generated successfully!');
  }

  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async run() {
    try {
      const startTime = Date.now();
      
      await this.initialize();
      await this.scrapeJobs();
      await this.scoreJobs();
      await this.generateReports();

      const duration = ((Date.now() - startTime) / 1000 / 60).toFixed(2);
      console.log(`\n========================================`);
      console.log(`   Completed in ${duration} minutes`);
      console.log(`========================================`);
      
      // Show top matches
      const topMatches = this.allJobs.slice(0, 5);
      console.log('\nTop 5 Matches:');
      topMatches.forEach((job, i) => {
        console.log(`  ${i + 1}. ${job.title} at ${job.company} - Score: ${job.atsScore}`);
      });

    } catch (error) {
      console.error('\n❌ Error:', error.message);
      console.error(error.stack);
      process.exit(1);
    }
  }
}

// Run the application
const app = new JobScraperApp();
app.run();
