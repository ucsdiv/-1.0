from datetime import datetime
from typing import List

import httpx

from app.config import settings
from app.plugins.base import PluginBase
from app.schemas import SearchResult, Link


class UpstreamPanSouPlugin(PluginBase):
    name = "upstream_pansou"
    enabled = settings.upstream_pansou_enabled
    timeout = settings.upstream_pansou_timeout

    async def search(self, keyword: str, limit: int = 20) -> List[SearchResult]:
        if not self.enabled:
            return []

        url = f"{settings.upstream_pansou_base_url.rstrip('/')}/api/search"
        payload = {"kw": keyword, "res": "merge", "limit": limit}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            return []

        results: List[SearchResult] = []
        merged = data.get("merged_by_type") or {}

        for disk_type, items in merged.items():
            for item in items:
                link = Link(
                    type=disk_type,
                    url=item.get("url", ""),
                    password=item.get("password", ""),
                    note=item.get("note", ""),
                    source=item.get("source", f"upstream:{self.name}"),
                    images=item.get("images") or [],
                )
                dt = item.get("datetime")
                if isinstance(dt, str):
                    try:
                        link.published_at = datetime.fromisoformat(dt.replace("Z", "+00:00"))
                    except Exception:
                        pass

                results.append(SearchResult(
                    title=link.note or "无标题",
                    links=[link],
                    source=f"upstream:{self.name}",
                    published_at=link.published_at,
                ))

        return results
