#!/usr/bin/env python3

import asyncio
import logging
import os
import sys
from pathlib import Path

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

    ttl_days = int(config.get("scrape_cache_ttl_days", 28))
    ttl_seconds = ttl_days * 24 * 3600

    log.info("Parsing resume: %s", resume_path)
    parser = PDFParser(resume_path)
    resume_data = parser.extract_resume_data()
    log.info("Resume loaded: %d pages, %d characters",
             resume_data["numPages"], len(resume_data["cleanText"]))

    log.info("Cache DB: %s", cache_db_path)
    cache_db = ATSCacheDB(cache_db_path)
    cache_db.initialize()

    known_urls_before = set(cache_db.get_all_job_urls())
    log.info("Known job URLs in cache: %d", len(known_urls_before))

    all_jobs = []
    scraper_instance = BaseScraper({})

    async def run_scrapers():
        try:
            for board in config["job_boards"]:
                board_name = board.get("name", "Unknown")
                board_type = board.get("type", "custom")

                log.info("=== Board: %s (%s) ===", board_name, board_type)
                board_jobs = []

                try:
                    scraper = get_scraper(board)
                    if board_type == "custom-api":
                        async for job in scraper.scrape(scraper_instance):
                            board_jobs.append(job)
                    else:
                        await scraper_instance.ensure_browser()
                        async for job in scraper.scrape(scraper_instance):
                            board_jobs.append(job)

                    for job in board_jobs:
                        cached = cache_db.get_scraped_job(board_name, job.get("url"), ttl_seconds)
                        if cached:
                            job["description"] = cached.get("description", "")
                            if not job.get("postedDate"):
                                job["postedDate"] = cached.get("postedDate", "")
                            log.info("  ✓ %s (cached listing)", job.get("title", "?")[:60])
                        else:
                            log.info("  ✓ %s", job["title"])

                        cache_db.set_scraped_job(board_name, job)

                    discovered_urls = {j["url"] for j in board_jobs if j.get("url")}
                    cache_db.prune_scraped_jobs(board_name, discovered_urls)

                    log.info("Board %s done: %d jobs", board_name, len(board_jobs))
                    all_jobs.extend(board_jobs)

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

    resume_profile = scoring_result.get("normalizedResumeProfile")
    if resume_profile and scored_jobs:
        scored_jobs[0]["normalizedResumeProfile"] = resume_profile

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
