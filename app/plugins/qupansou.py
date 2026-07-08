import re
from datetime import datetime
from typing import List

import httpx

from app.config import settings
from app.plugins.base import PluginBase
from app.schemas import SearchResult, Link
from app.utils.link_parser import detect_disk_type


class QuPanSouPlugin(PluginBase):
    name = "qupansou"
    enabled = settings.native_plugins_enabled
    timeout = settings.plugin_timeout
    base_url = "https://www.qupansou.com"

    async def search(self, keyword: str, limit: int = 20) -> List[SearchResult]:
        results: List[SearchResult] = []
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(
                    f"{self.base_url}/search",
                    params={"keyword": keyword},
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                resp.raise_for_status()
        except Exception:
            return results

        text = resp.text
        urls = re.findall(
            r"https?://[^\s<>\"]+(?:pan\.quark\.cn|pan\.baidu\.com|www\.aliyundrive\.com|cloud\.189\.cn)[^\s<>\"]*",
            text,
        )
        seen = set()

        for url in urls[:limit]:
            if url in seen:
                continue
            seen.add(url)
            disk_type = detect_disk_type(url)
            if disk_type:
                results.append(SearchResult(
                    title=f"{keyword} - {disk_type}",
                    links=[Link(type=disk_type, url=url, note=keyword, source=f"plugin:{self.name}")],
                    source=f"plugin:{self.name}",
                    published_at=datetime.utcnow(),
                ))

        return results
