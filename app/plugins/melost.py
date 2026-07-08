import re
from datetime import datetime
from typing import List
from urllib.parse import urlparse, parse_qs

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.plugins.base import PluginBase
from app.schemas import SearchResult, Link
from app.utils.link_parser import detect_disk_type


class MelostPlugin(PluginBase):
    name = "melost"
    enabled = settings.native_plugins_enabled
    timeout = settings.plugin_timeout
    base_url = "https://melost.cn"

    async def search(self, keyword: str, limit: int = 20) -> List[SearchResult]:
        results: List[SearchResult] = []
        seen = set()
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(
                    f"{self.base_url}/search",
                    params={"q": keyword},
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Referer": "https://melost.cn/",
                    },
                )
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                items = soup.select("div.search-item")[:limit]

                for item in items:
                    try:
                        title_el = item.select_one("a.search-item-title")
                        if not title_el:
                            continue
                        title = title_el.get_text(strip=True)
                        url = title_el.get("href", "").strip()
                        if not url:
                            continue

                        disk_type = detect_disk_type(url)
                        if not disk_type:
                            continue

                        key = f"{title}|{url}"
                        if key in seen:
                            continue
                        seen.add(key)

                        password = ""
                        parsed = urlparse(url)
                        qs = parse_qs(parsed.query)
                        for key_name in ("pwd", "password"):
                            if key_name in qs:
                                password = qs[key_name][0]
                                break

                        info_el = item.select_one("span.search-item-info")
                        content = self._clean_html(info_el.get_text(strip=True)) if info_el else ""

                        results.append(SearchResult(
                            title=title,
                            content=content,
                            links=[Link(type=disk_type, url=url, password=password, note=title, source=f"plugin:{self.name}")],
                            source=f"plugin:{self.name}",
                            published_at=datetime.utcnow(),
                        ))
                    except Exception:
                        continue
        except Exception:
            pass
        return results

    def _clean_html(self, html: str) -> str:
        text = html
        for tag in ("<em>", "</em>", "<b>", "</b>", "<strong>", "</strong>"):
            text = text.replace(tag, "")
        text = re.sub(r"<[^>]+>", "", text)
        return text.strip()
