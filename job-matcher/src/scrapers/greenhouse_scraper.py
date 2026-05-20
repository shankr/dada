import json
import logging
import re
from urllib.parse import urljoin

log = logging.getLogger(__name__)


class GreenhouseScraper:
    def __init__(self, board_config):
        self.board_config = board_config

    async def scrape(self, base_scraper):
        url = self.board_config["url"]
        max_pages = self.board_config.get("max_pages", 10)
        known_urls = set()

        log.info("Scraping Greenhouse board: %s", self.board_config["name"])

        page = await base_scraper.new_page()
        try:
            await base_scraper.goto_with_retry(page, url)

            for page_num in range(1, max_pages + 1):
                log.info("  Processing page %d...", page_num)

                await page.wait_for_selector("section.posting-list", timeout=15000)
                job_cards = await page.query_selector_all(
                    "section.posting-list div.posting"
                )

                for card in job_cards:
                    link_el = await card.query_selector("a[href]")
                    if not link_el:
                        continue

                    href = await link_el.get_attribute("href")
                    if not href:
                        continue
                    job_url = urljoin(url, href)
                    if job_url in known_urls:
                        continue
                    known_urls.add(job_url)

                    title_el = await card.query_selector("h2, .title")
                    title = (await title_el.inner_text()).strip() if title_el else ""

                    loc_el = await card.query_selector(".location, .commitment")
                    location = (await loc_el.inner_text()).strip() if loc_el else ""

                    job_desc = ""
                    posted_date = ""
                    try:
                        detail_page = await base_scraper.new_page()
                        try:
                            await base_scraper.goto_with_retry(detail_page, job_url)
                            desc_el = await detail_page.query_selector("#content, .content, .job-description")
                            if desc_el:
                                job_desc = (await desc_el.inner_text()).strip()

                            body_text = await detail_page.inner_text("body")
                            m = re.search(r"Posted\s+(\d+)\s+(day|days|week|weeks)\s+ago", body_text, re.IGNORECASE)
                            if m:
                                posted_date = m.group(0)
                        finally:
                            await detail_page.close()
                    except Exception:
                        log.warning("  Could not load detail for %s", title)

                    yield {
                        "url": job_url,
                        "title": title,
                        "company": self.board_config.get("name", ""),
                        "location": location or "Not specified",
                        "description": job_desc or "Not available",
                        "source": "Greenhouse",
                        "postedDate": posted_date,
                    }

                next_btn = await page.query_selector(
                    "a[rel='next'], button:has-text('Next'), .pagination a:has-text('Next')"
                )
                if not next_btn:
                    log.info("  No more pages (no next button)")
                    break
                await next_btn.click()
                await page.wait_for_timeout(3000)

        finally:
            await page.close()
