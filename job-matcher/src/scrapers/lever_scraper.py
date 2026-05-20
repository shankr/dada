import json
import logging
import re
from urllib.parse import urljoin

log = logging.getLogger(__name__)


class LeverScraper:
    def __init__(self, board_config):
        self.board_config = board_config

    async def scrape(self, base_scraper):
        url = self.board_config["url"]
        known_urls = set()

        log.info("Scraping Lever board: %s", self.board_config["name"])

        page = await base_scraper.new_page()
        try:
            await base_scraper.goto_with_retry(page, url)

            await page.wait_for_selector(".posting-list, .postings-wrapper", timeout=15000)
            job_cards = await page.query_selector_all(
                "a[href*='/jobs/'], a.posting-title"
            )

            for card in job_cards:
                href = await card.get_attribute("href")
                if not href:
                    continue
                job_url = urljoin(url, href)
                if job_url in known_urls:
                    continue
                known_urls.add(job_url)

                title_el = await card.query_selector("h5, h4, .title")
                title = (await title_el.inner_text()).strip() if title_el else ""

                loc_el = await card.query_selector(".location, .commitment, .workplace-type")
                location = (await loc_el.inner_text()).strip() if loc_el else ""

                team_el = await card.query_selector(".team, .department, .category")
                team = (await team_el.inner_text()).strip() if team_el else ""

                job_desc = ""
                posted_date = ""
                try:
                    detail_page = await base_scraper.new_page()
                    try:
                        await base_scraper.goto_with_retry(detail_page, job_url)
                        desc_el = await detail_page.query_selector(
                            ".content, .posting-description, .description"
                        )
                        if desc_el:
                            job_desc = (await desc_el.inner_text()).strip()

                        body_text = await detail_page.inner_text("body")
                        m = re.search(r"Posted\s+(?:on\s+)?(\w+ \d+,?\s*\d{4})", body_text, re.IGNORECASE)
                        if m:
                            posted_date = m.group(1)
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
                    "source": "Lever",
                    "team": team,
                    "postedDate": posted_date,
                }

        finally:
            await page.close()
