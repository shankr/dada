import asyncio
import logging
from playwright.async_api import async_playwright

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class BaseScraper:
    def __init__(self, board_config):
        self.board_config = board_config
        self.browser = None
        self.context = None

    async def ensure_browser(self):
        if self.browser and self.context:
            return
        p = await async_playwright().start()
        self.browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        self.context = await self.browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )

    async def close(self):
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.context = None

    async def new_page(self):
        await self.ensure_browser()
        return await self.context.new_page()

    async def scrape(self):
        raise NotImplementedError

    def get_selector(self, key, default=None):
        sel = self.board_config.get("selectors", {})
        return sel.get(key, default)

    @staticmethod
    def safe_text(el, default=""):
        if el is None:
            return default
        return el.strip() if el else default

    @staticmethod
    def extract_date(text):
        import re
        match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        if match:
            return match.group(1)
        return ""

    @staticmethod
    def normalize_job_url(base_url, href):
        if not href:
            return None
        if href.startswith("http://") or href.startswith("https://"):
            return href
        from urllib.parse import urljoin
        return urljoin(base_url, href)

    async def goto_with_retry(self, page, url, max_retries=3, wait_until="networkidle"):
        from playwright.async_api import TimeoutError as PwTimeout

        for attempt in range(max_retries):
            try:
                await page.goto(url, wait_until=wait_until, timeout=30000)
                return
            except PwTimeout:
                log.warning("Timeout loading %s (attempt %d/%d)", url, attempt + 1, max_retries)
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2)
