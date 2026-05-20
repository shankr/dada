import json
import logging
import re
from urllib.parse import urljoin

log = logging.getLogger(__name__)


class WorkdayScraper:
    def __init__(self, board_config):
        self.board_config = board_config

    def get_selector(self, key, default=None):
        sel = self.board_config.get("selectors", {})
        return sel.get(key, default)

    async def _get_job_link(self, job_card, page_url):
        sel = self.get_selector("title", "a[data-automation-id='jobTitle']")
        link = await job_card.query_selector(sel)
        if link:
            href = await link.get_attribute("href")
            if href:
                return urljoin(page_url, href)
        alt_sel = self.get_selector("job_url_attribute")
        if alt_sel:
            attr_val = await job_card.get_attribute(alt_sel)
            if attr_val:
                return f"{page_url.split('?')[0].rstrip('/')}/{attr_val}"
        return None

    async def _get_title(self, job_card):
        sel = self.get_selector("title", "a[data-automation-id='jobTitle']")
        el = await job_card.query_selector(sel)
        if el:
            return (await el.inner_text()).strip()
        return ""

    async def _get_location(self, job_card):
        sel = self.get_selector("location", "[data-automation-id='jobPostingLocation']")
        el = await job_card.query_selector(sel)
        if el:
            return (await el.inner_text()).strip()
        return ""

    async def _get_description(self, page):
        sel = self.get_selector("description", "[data-automation-id='jobPostingDescription']")
        el = await page.query_selector(sel)
        if el:
            return (await el.inner_text()).strip()
        return ""

    async def _get_posted_date(self, page):
        date_patterns = [
            r"Posted\s*(?:on|:)?\s*(\w+ \d+,?\s*\d{4})",
            r"Date posted[:\s]+(\w+ \d+,?\s*\d{4})",
            r"Posted\s+(\d+)\s+(day|days|week|weeks|month|months)\s+ago",
            r"(\w+ \d+,?\s*\d{4})",
        ]
        text = await page.inner_text("body")
        for pat in date_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return ""

    async def scrape(self, base_scraper):
        url = self.board_config["url"]
        max_pages = self.board_config.get("max_pages", 10)
        known_urls = set()

        log.info("Scraping Workday board: %s", self.board_config["name"])

        page = await base_scraper.new_page()
        try:
            await base_scraper.goto_with_retry(page, url)

            for page_num in range(1, max_pages + 1):
                log.info("  Processing page %d...", page_num)

                list_sel = self.get_selector("job_list_container",
                                             "[data-automation-id='jobPostingList']")
                card_sel = self.get_selector("job_card",
                                             "[data-automation-id='jobPosting']")

                await page.wait_for_selector(card_sel, timeout=15000)
                job_cards = await page.query_selector_all(card_sel)

                for card in job_cards:
                    job_link = await self._get_job_link(card, url)
                    if not job_link or job_link in known_urls:
                        continue
                    known_urls.add(job_link)

                    title = await self._get_title(card)
                    location = await self._get_location(card)

                    posted_date = ""
                    job_desc = ""
                    try:
                        detail_page = await base_scraper.new_page()
                        try:
                            await base_scraper.goto_with_retry(detail_page, job_link)
                            job_desc = await self._get_description(detail_page)
                            posted_date = await self._get_posted_date(detail_page)
                        finally:
                            await detail_page.close()
                    except Exception:
                        log.warning("  Could not load detail for %s", title)

                    yield {
                        "url": job_link,
                        "title": title,
                        "company": self.board_config.get("name", ""),
                        "location": location or "Not specified",
                        "description": job_desc or "Not available",
                        "source": "Workday",
                        "postedDate": posted_date,
                    }

                next_sel = self.get_selector("next_button",
                                             "button[data-automation-id='nextPage']")
                next_btn = await page.query_selector(next_sel)
                if not next_btn:
                    log.info("  No more pages (no next button)")
                    break

                is_disabled = await next_btn.get_attribute("disabled")
                if is_disabled is not None:
                    log.info("  No more pages (next button disabled)")
                    break

                await next_btn.click()
                await page.wait_for_timeout(3000)

        finally:
            await page.close()
