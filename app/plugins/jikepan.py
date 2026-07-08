from datetime import datetime
from typing import List

import httpx

from app.config import settings
from app.plugins.base import PluginBase
from app.schemas import SearchResult, Link
from app.utils.link_parser import detect_disk_type


class JikepanPlugin(PluginBase):
    name = "jikepan"
    enabled = settings.native_plugins_enabled
    timeout = settings.plugin_timeout
    api_url = "https://api.jikepan.xyz/search"

    async def search(self, keyword: str, limit: int = 20) -> List[SearchResult]:
        results: List[SearchResult] = []
        seen = set()
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.post(
                    self.api_url,
                    json={"name": keyword, "is_all": False},
                    headers={
                        "Content-Type": "application/json",
                        "referer": "https://jikepan.xyz/",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("msg") != "success":
                    return results

                for item in data.get("list", [])[:limit]:
                    title = item.get("name", "").strip()
                    links = self._convert_links(item.get("links", []))
                    if not links:
                        continue
                    key = f"{title}|{links[0].url}"
                    if key in seen:
                        continue
                    seen.add(key)
                    results.append(SearchResult(
                        title=title or "无标题",
                        links=links,
                        source=f"plugin:{self.name}",
                        published_at=datetime.utcnow(),
                    ))
        except Exception:
            pass
        return results

    def _convert_links(self, raw_links: List[dict]) -> List[Link]:
        links: List[Link] = []
        seen = set()
        for link in raw_links:
            url = link.get("link", "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            service = link.get("service", "").lower()
            disk_type = self._map_service(service) or detect_disk_type(url)
            if not disk_type:
                continue
            links.append(Link(
                type=disk_type,
                url=url,
                password=link.get("pwd", ""),
                source=f"plugin:{self.name}",
            ))
        return links

    def _map_service(self, service: str) -> str:
        mapping = {
            "baidu": "baidu",
            "aliyun": "aliyun",
            "xunlei": "xunlei",
            "quark": "quark",
            "189cloud": "tianyi",
            "115": "115",
            "123": "123",
            "pikpak": "pikpak",
            "caiyun": "mobile",
            "ed2k": "ed2k",
            "magnet": "magnet",
        }
        if service == "unknown":
            return ""
        return mapping.get(service, "others")
