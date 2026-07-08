import re
from datetime import datetime
from typing import List

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.plugins.base import PluginBase
from app.schemas import SearchResult, Link
from app.utils.link_parser import detect_disk_type


class PanSearchPlugin(PluginBase):
    name = "pansearch"
    enabled = settings.native_plugins_enabled
    timeout = settings.plugin_timeout
    base_url = "https://www.pansearch.me"

    async def search(self, keyword: str, limit: int = 20) -> List[SearchResult]:
        results: List[SearchResult] = []
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(f"{self.base_url}/search", params={"key": keyword})
                resp.raise_for_status()
        except Exception:
            return results

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select(".search-item")[:limit]

        for item in items:
            title_el = item.select_one(".title")
            content_el = item.select_one(".content")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            content = content_el.get_text(strip=True) if content_el else ""
            links: List[Link] = []

            for a in item.find_all("a", href=True):
                url = a["href"]
                disk_type = detect_disk_type(url)
                if disk_type:
                    links.append(Link(type=disk_type, url=url, note=title, source=f"plugin:{self.name}"))

            for url in re.findall(r"https?://[^\s<>\"]+", content):
                disk_type = detect_disk_type(url)
                if disk_type and not any(l.url == url for l in links):
                    links.append(Link(type=disk_type, url=url, note=title, source=f"plugin:{self.name}"))

            if links:
                results.append(SearchResult(
                    title=title, content=content, links=links,
                    source=f"plugin:{self.name}", published_at=datetime.utcnow(),
                ))

        return results
