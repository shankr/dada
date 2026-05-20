#!/usr/bin/env python3

import asyncio
import logging
import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.config.config_loader import ConfigLoader
from src.parsers.pdf_parser import PDFParser
from src.storage.ats_cache_db import ATSCacheDB
from src.scrapers.base_scraper import BaseScraper
from src.scrapers.scraper_factory import get_scraper
from src.ats.ats_scorer import ATSScorer
from src.output.report_generator import ReportGenerator

log = logging.getLogger(__name__)


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main():
    setup_logging()
    config = ConfigLoader.load()

    resume_path = config["resume_path"]
    output_path = config["output_path"]
    cache_db_path = config["ats_cache_db_path"]

    # Parse resume
    log.info("Parsing resume: %s", resume_path)
    parser = PDFParser(resume_path)
    resume_data = parser.extract_resume_data()
    log.info("Resume loaded: %d pages, %d characters",
             resume_data["numPages"], len(resume_data["cleanText"]))

    # Initialize cache
    log.info("Cache DB: %s", cache_db_path)
    cache_db = ATSCacheDB(cache_db_path)
    cache_db.initialize()

    # Snapshot known URLs before scraping
    known_urls_before = set(cache_db.get_all_job_urls())
    log.info("Known job URLs in cache: %d", len(known_urls_before))

    # Scrape all job boards
    all_jobs = []
    scraper_instance = BaseScraper({})

    async def run_scrapers():
        try:
            for board in config["job_boards"]:
                board_name = board.get("name", "Unknown")
                board_type = board.get("type", "custom")
                log.info("=== Scraping board: %s (%s) ===", board_name, board_type)

                try:
                    if board_type == "custom-api":
                        scraper = get_scraper(board)
                        async for job in scraper.scrape(scraper_instance):
                            log.info("  ✓ %s", job["title"])
                            all_jobs.append(job)
                    else:
                        await scraper_instance.ensure_browser()
                        scraper = get_scraper(board)
                        async for job in scraper.scrape(scraper_instance):
                            log.info("  ✓ %s", job["title"])
                            all_jobs.append(job)
                except Exception as e:
                    log.error("Error scraping %s: %s. Skipping to next board.", board_name, e)
                    continue
        finally:
            await scraper_instance.close()

    asyncio.run(run_scrapers())

    log.info("Total jobs scraped: %d", len(all_jobs))

    if not all_jobs:
        log.warning("No jobs scraped. Exiting.")
        sys.exit(0)

    # Mark new jobs
    for job in all_jobs:
        job["isNewThisRun"] = job.get("url") not in known_urls_before

    log.info("Scoring %d jobs...", len(all_jobs))

    scorer = ATSScorer(config, cache_db)

    def on_progress(job, idx, total):
        pct = f"{idx + 1}/{total}"
        log.info("  Scoring: %s - %s...", pct, job.get("title", "")[:60])

    scoring_result = asyncio.run(
        scorer.score_jobs_batch(resume_data["cleanText"], all_jobs, on_progress)
    )

    scored_jobs = scoring_result.get("jobs", [])

    # Attach resume profile to first job for report
    resume_profile = scoring_result.get("normalizedResumeProfile")
    if resume_profile and scored_jobs:
        scored_jobs[0]["normalizedResumeProfile"] = resume_profile

    # Sort by score descending
    scored_jobs.sort(key=lambda j: j.get("atsScore", 0), reverse=True)

    resume_info = {
        "filePath": resume_path,
        "numPages": resume_data["numPages"],
    }

    log.info("Generating report: %s", output_path)
    report_gen = ReportGenerator(output_path)
    report_gen.generate(scored_jobs, resume_info)
    report_gen.generate_json(scored_jobs, resume_info)

    log.info("Done. Reports written to %s", os.path.dirname(output_path))


if __name__ == "__main__":
    main()
