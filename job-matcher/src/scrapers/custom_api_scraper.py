import json
import logging
import httpx

log = logging.getLogger(__name__)


class CustomAPIScraper:
    def __init__(self, board_config):
        self.board_config = board_config

    def _get_field(self, fields, key):
        if not fields:
            return ""
        raw = fields.get(key, "")
        if callable(raw):
            return raw()
        return raw or ""

    def _extract_json_field(self, obj, path):
        if not path:
            return None
        parts = path.split(".")
        current = obj
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    idx = int(part)
                    current = current[idx] if idx < len(current) else None
                except (ValueError, IndexError):
                    return None
            else:
                return None
            if current is None:
                return None
        return current

    def _extract_nested(self, obj, spec):
        if not spec:
            return ""
        if isinstance(spec, str):
            val = self._extract_json_field(obj, spec)
            return str(val) if val is not None else ""
        if isinstance(spec, list):
            parts = []
            for item in spec:
                val = self._extract_nested(obj, item)
                if val:
                    parts.append(str(val))
            return " ".join(parts)
        return ""

    async def scrape(self, base_scraper):
        cfg = self.board_config
        url = cfg["url"]
        name = cfg.get("name", "CustomAPI")
        fields = cfg.get("fields", {})
        pagination = cfg.get("pagination", {})
        method = cfg.get("method", "GET").upper()
        headers = cfg.get("headers", {})
        body_template = cfg.get("body", None)
        bootstrap = cfg.get("bootstrap", None)

        log.info("Scraping Custom API board: %s", name)

        known_urls = set()
        page_size = pagination.get("size", 20)
        max_pages = pagination.get("max_pages", 10)
        offset_field = pagination.get("offset_field", "offset")
        limit_field = pagination.get("limit_field", "limit")
        results_path = pagination.get("results_path", "")
        total_path = pagination.get("total_path", None)

        extra_headers = {}
        cookies = {}

        if bootstrap:
            log.info("  Bootstrapping session for %s...", name)
            bs = await self._bootstrap(base_scraper, name)
            extra_headers.update(bs.get("headers", {}))
            cookies.update(bs.get("cookies", {}))

        async with httpx.AsyncClient(headers={**headers, **extra_headers},
                                     cookies=cookies, timeout=60.0) as client:
            for page_num in range(max_pages):
                log.info("  Fetching page %d (offset %d)...", page_num + 1, page_num * page_size)

                params = {offset_field: page_num * page_size, limit_field: page_size}

                if method == "POST":
                    body = dict(body_template) if body_template else {}
                    body[offset_field] = page_num * page_size
                    body[limit_field] = page_size
                    resp = await client.post(url, json=body, params=params)
                else:
                    resp = await client.get(url, params=params)

                resp.raise_for_status()
                data = resp.json()

                if results_path:
                    items = self._extract_json_field(data, results_path)
                else:
                    items = data if isinstance(data, list) else data.get("data", [])

                if not items:
                    log.info("  No items returned")
                    break

                for item in items:
                    job_url = self._extract_nested(item, fields.get("url"))
                    if not job_url:
                        continue
                    if job_url in known_urls:
                        continue
                    known_urls.add(job_url)

                    yield {
                        "url": job_url,
                        "title": self._extract_nested(item, fields.get("title", "")),
                        "company": self._extract_nested(item, fields.get("company", name)),
                        "location": self._extract_nested(item, fields.get("location", "")),
                        "description": self._extract_nested(item, fields.get("description", "")),
                        "source": name,
                        "postedDate": self._extract_nested(item, fields.get("posted_date", "")),
                    }

                if items and len(items) < page_size:
                    log.info("  Last page (fewer items than page size)")
                    break

                if total_path:
                    total = self._extract_json_field(data, total_path)
                    if isinstance(total, (int, float)) and (page_num + 1) * page_size >= total:
                        log.info("  All pages fetched (%d total)", total)
                        break

    async def _bootstrap(self, base_scraper, board_name):
        bs_cfg = self.board_config.get("bootstrap", {})
        bs_type = bs_cfg.get("type", "playwright")
        result = {"headers": {}, "cookies": {}}

        if bs_type == "playwright":
            bs_url = bs_cfg.get("url")
            if not bs_url:
                log.warning("  Bootstrap missing URL for %s", board_name)
                return result

            page = await base_scraper.new_page()
            try:
                await base_scraper.goto_with_retry(page, bs_url)
                await page.wait_for_timeout(5000)

                cookies = await base_scraper.context.cookies()
                result["cookies"] = {c["name"]: c["value"] for c in cookies}

                token_sel = bs_cfg.get("csrf_token_selector")
                if token_sel:
                    token_el = await page.query_selector(token_sel)
                    if token_el:
                        token = await token_el.get_attribute("content")
                        if token:
                            header_name = bs_cfg.get("csrf_header", "X-CSRF-Token")
                            result["headers"][header_name] = token

                extra_headers = bs_cfg.get("extra_headers", {})
                result["headers"].update(extra_headers)

                log.info("  Bootstrap complete for %s (%d cookies, %d headers)",
                         board_name, len(result["cookies"]), len(result["headers"]))
            finally:
                await page.close()

        return result
