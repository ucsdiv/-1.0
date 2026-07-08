import hashlib
import random
import re
from datetime import datetime
from typing import List

import httpx

from app.config import settings
from app.plugins.base import PluginBase
from app.schemas import SearchResult, Link


class QuarksooPlugin(PluginBase):
    name = "quarksoo"
    enabled = settings.native_plugins_enabled
    timeout = settings.plugin_timeout
    base_url = "https://quarksoo.cc/search.php"

    async def search(self, keyword: str, limit: int = 20) -> List[SearchResult]:
        results: List[SearchResult] = []
        try:
            headers = {
                "User-Agent": random.choice(_USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": "https://quarksoo.cc/",
            }
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(self.base_url, params={"q": keyword}, headers=headers)
                resp.raise_for_status()
        except Exception:
            return results

        pattern = re.compile(
            r"<tr>\s*<td>([^<]+)</td>\s*<td>\s*<a[^>]*href\s*=\s*[\"']([^\"']+)[\"'][^>]*>"
        )
        seen = set()
        for match in pattern.findall(resp.text)[:limit]:
            title = match[0].strip()
            url = match[1].strip()
            if "剧名" in title or "网盘链接" in title:
                continue
            if "pan.quark.cn" not in url and "pan.qoark.cn" not in url:
                continue
            key = f"{title}|{url}"
            if key in seen:
                continue
            seen.add(key)
            unique_id = f"quarksoo-{hashlib.md5(key.encode()).hexdigest()[:8]}"
            results.append(SearchResult(
                title=title,
                links=[Link(type="quark", url=url, note=title, source=f"plugin:{self.name}")],
                source=f"plugin:{self.name}",
                published_at=datetime.utcnow(),
            ))
        return results


_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0",
]
