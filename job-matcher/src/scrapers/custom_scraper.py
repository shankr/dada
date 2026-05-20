import json
import logging
import re
from urllib.parse import urljoin

log = logging.getLogger(__name__)


class CustomScraper:
    def __init__(self, board_config):
        self.board_config = board_config

    def get_selector(self, key, default=None):
        sel = self.board_config.get("selectors", {})
        return sel.get(key, default)

    async def scrape(self, base_scraper):
        url = self.board_config["url"]
        max_pages = self.board_config.get("max_pages", 10)
        known_urls = set()

        log.info("Scraping custom board: %s", self.board_config["name"])

        page = await base_scraper.new_page()
        try:
            await base_scraper.goto_with_retry(page, url)
            await page.wait_for_timeout(2000)

            for page_num in range(1, max_pages + 1):
                log.info("  Processing page %d...", page_num)

                await self._expand_page(page)

                card_sel = self.get_selector("job_card", "li, .job-listing, .job-card, tr")
                await page.wait_for_selector(card_sel, timeout=15000)
                job_cards = await page.query_selector_all(card_sel)

                if not job_cards:
                    log.info("  No job cards found on page %d", page_num)
                    break

                for card in job_cards:
                    job_data = await self._extract_job_data(page, card, url)
                    if not job_data:
                        continue
                    if job_data["url"] in known_urls:
                        continue
                    known_urls.add(job_data["url"])

                    job_data["description"] = await self._fetch_description(base_scraper, job_data["url"])

                    yield job_data

                next_btn = await self._find_next_button(page)
                if not next_btn:
                    log.info("  No more pages (no next button)")
                    break

                is_disabled = await self._is_button_disabled(page, next_btn)
                if is_disabled:
                    log.info("  No more pages (next button disabled)")
                    break

                await self._click_navigate(page, next_btn)
                await page.wait_for_timeout(3000)

        finally:
            await page.close()

    async def _expand_page(self, page):
        selectors = self.board_config.get("selectors", {})

        show_all = selectors.get("show_all_button")
        if show_all:
            clicked = await self._click_if_visible(page, show_all)
            if clicked:
                await page.wait_for_timeout(2500)
                return

        view_more = selectors.get("view_more_button")
        if view_more:
            for _ in range(10):
                clicked = await self._click_if_visible(page, view_more)
                if not clicked:
                    break
                await page.wait_for_timeout(1500)

    async def _click_if_visible(self, page, selector):
        try:
            result = await page.evaluate(
                """(sel) => {
                    const el = document.querySelector(sel);
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    const hidden = style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity || '1') === 0;
                    const disabled = el.disabled || el.getAttribute('aria-disabled') === 'true' || el.classList.contains('disabled');
                    if (hidden || disabled) return false;
                    el.click();
                    return true;
                }""",
                selector,
            )
            return result
        except Exception:
            return False

    async def _extract_job_data(self, page, card, base_url):
        selectors = self.board_config.get("selectors", {})
        title_sel = selectors.get("title", "a, h2, h3, .title, .job-title")

        title_el = await card.query_selector(title_sel)
        if not title_el:
            return None

        title = (await title_el.inner_text()).strip()

        job_link = await self._extract_job_link(page, card, title_el, base_url, selectors)
        if not job_link:
            return None

        if selectors.get("require_link"):
            link_el = await card.query_selector(selectors.get("link", "a"))
            if not link_el:
                return None

        req_attr = selectors.get("require_link_attr")
        if req_attr:
            link_el = await card.query_selector(selectors.get("link", "a"))
            if not link_el or not await link_el.get_attribute(req_attr):
                return None

        url_pattern = selectors.get("url_pattern")
        if url_pattern and url_pattern not in job_link:
            return None

        loc_sel = selectors.get("location", ".location, .job-location")
        loc_el = await card.query_selector(loc_sel) if loc_sel else None
        location = (await loc_el.inner_text()).strip() if loc_el else ""

        date_sel = selectors.get("posted_date", ".date, .posted-date, .job-date")
        date_el = await card.query_selector(date_sel) if date_sel else None
        posted_date = (await date_el.inner_text()).strip() if date_el else ""

        return {
            "url": job_link,
            "title": title,
            "company": self.board_config.get("name", ""),
            "location": location or "Not specified",
            "description": "",
            "source": "Custom",
            "postedDate": posted_date,
        }

    async def _extract_job_link(self, page, card, title_el, base_url, selectors):
        attr_mode = selectors.get("job_url_attribute")
        if attr_mode == "href":
            link_sel = selectors.get("link")
            if link_sel:
                link_el = await card.query_selector(link_sel)
            else:
                tag = await title_el.evaluate("el => el.tagName")
                link_el = title_el if tag == "A" else await card.query_selector("a")
            if link_el:
                href = await link_el.get_attribute("href")
                if href:
                    return urljoin(base_url, href)
            return None

        if attr_mode:
            if attr_mode == "href":
                return None
            attr_val = await card.get_attribute(attr_mode)
            if attr_val:
                return urljoin(base_url, attr_val)
            return None

        href = await title_el.get_attribute("href")
        if href:
            return urljoin(base_url, href)
        return None

    async def _fetch_description(self, base_scraper, job_url):
        try:
            detail_page = await base_scraper.new_page()
            try:
                await base_scraper.goto_with_retry(detail_page, job_url)
                desc_sel = self.get_selector("description")
                if desc_sel:
                    desc_el = await detail_page.query_selector(desc_sel)
                else:
                    desc_el = None
                if not desc_el:
                    desc_el = await detail_page.query_selector("body")
                if desc_el:
                    return (await desc_el.inner_text()).strip()
                return "Not available"
            finally:
                await detail_page.close()
        except Exception:
            log.warning("  Could not load detail for %s", job_url)
            return "Not available"

    async def _find_next_button(self, page):
        next_sel = self.get_selector("next_button")
        if next_sel:
            btn = await page.query_selector(next_sel)
            if btn:
                return btn

        fallback = "a[rel='next'], .next, .pagination-next, button:has-text('Next')"
        return await page.query_selector(fallback)

    async def _is_button_disabled(self, page, btn):
        try:
            return await btn.evaluate(
                """(el) => {
                    return el.disabled
                        || el.getAttribute('aria-disabled') === 'true'
                        || el.classList.contains('disabled');
                }"""
            )
        except Exception:
            return True

    async def _click_navigate(self, page, btn):
        is_anchor = await btn.evaluate("el => el.tagName === 'A'")
        href = await btn.get_attribute("href") if is_anchor else None

        if is_anchor and href:
            next_url = urljoin(page.url, href)
            await page.goto(next_url, wait_until="networkidle")
        else:
            await btn.evaluate("el => el.click()")
            await page.wait_for_timeout(3000)
