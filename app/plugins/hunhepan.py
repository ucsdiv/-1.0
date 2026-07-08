import asyncio
import re
import time
from datetime import datetime
from typing import List, Dict, Any

import httpx

from app.config import settings
from app.plugins.base import PluginBase
from app.schemas import SearchResult, Link


class HunhepanPlugin(PluginBase):
    name = "hunhepan"
    enabled = settings.native_plugins_enabled
    timeout = settings.plugin_timeout
    apis = [
        "https://hunhepan.com/open/search/disk",
        "https://qkpanso.com/v1/search/disk",
    ]

    async def search(self, keyword: str, limit: int = 20) -> List[SearchResult]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            tasks = [asyncio.create_task(self._search_api_first_page(client, api, keyword)) for api in self.apis]
            pending = set(tasks)
            all_items: List[Dict[str, Any]] = []
            deadline = time.monotonic() + self.timeout

            while pending and time.monotonic() < deadline:
                timeout = max(0.1, deadline - time.monotonic())
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED, timeout=timeout)
                for task in done:
                    try:
                        item = task.result()
                    except Exception:
                        continue
                    if isinstance(item, list):
                        all_items.extend(item)
                    if len(all_items) >= limit:
                        break
                if len(all_items) >= limit:
                    for t in pending:
                        t.cancel()
                    break

            for t in pending:
                t.cancel()
                try:
                    await t
                except (Exception, asyncio.CancelledError):
                    pass

        unique = self._dedupe(all_items)
        return self._convert(unique)[:limit]

    async def _search_api_first_page(self, client: httpx.AsyncClient, api_url: str, keyword: str) -> List[Dict[str, Any]]:
        body = {
            "page": 1,
            "q": keyword,
            "user": "",
            "exact": False,
            "format": [],
            "share_time": "",
            "size": 10,
            "type": "",
            "exclude_user": [],
            "adv_params": {"wechat_pwd": "", "platform": "pc"},
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": self._referer(api_url),
        }
        try:
            resp = await client.post(api_url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") == 200:
                return data.get("data", {}).get("list", [])
        except (Exception, asyncio.CancelledError):
            pass
        return []

    def _referer(self, api_url: str) -> str:
        if "qkpanso.com" in api_url:
            return "https://qkpanso.com/search"
        if "kuake8.com" in api_url:
            return "https://kuake8.com/search"
        if "misoso.cc" in api_url:
            return "https://www.misoso.cc/search"
        return "https://hunhepan.com/search"

    def _dedupe(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: Dict[str, Dict[str, Any]] = {}
        for item in items:
            item["disk_name"] = self._clean(item.get("disk_name", ""))
            key = item.get("disk_id") or f"{item.get('link')}|{item['disk_name']}"
            existing = seen.get(key)
            if existing:
                score_old = len(existing.get("files", ""))
                score_new = len(item.get("files", ""))
                if existing.get("disk_pass") == "" and item.get("disk_pass"):
                    score_new += 5
                if existing.get("shared_time") == "" and item.get("shared_time"):
                    score_new += 3
                if score_new > score_old:
                    seen[key] = item
            else:
                seen[key] = item
        return list(seen.values())

    def _convert(self, items: List[Dict[str, Any]]) -> List[SearchResult]:
        results: List[SearchResult] = []
        for item in items:
            url = item.get("link", "")
            if not url:
                continue
            disk_type = self._disk_type(item.get("disk_type", ""))
            published_at = None
            if item.get("shared_time"):
                try:
                    published_at = datetime.strptime(item["shared_time"], "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass
            results.append(SearchResult(
                title=item["disk_name"] or "无标题",
                content=item.get("files", ""),
                links=[Link(
                    type=disk_type,
                    url=url,
                    password=item.get("disk_pass", ""),
                    note=item["disk_name"],
                    source=f"plugin:{self.name}",
                )],
                source=f"plugin:{self.name}",
                published_at=published_at,
            ))
        return results

    def _disk_type(self, value: str) -> str:
        mapping = {
            "BDY": "baidu", "ALY": "aliyun", "QUARK": "quark", "TIANYI": "tianyi",
            "UC": "uc", "CAIYUN": "mobile", "115": "115", "XUNLEI": "xunlei",
            "123PAN": "123", "PIKPAK": "pikpak",
        }
        return mapping.get(value.upper(), "others")

    def _clean(self, title: str) -> str:
        title = re.sub(r"<[^>]+>", "", title)
        for old, new in (("<em>", ""), ("</em>", ""), ("<b>", ""), ("</b>", "")):
            title = title.replace(old, new)
        return title.strip()
