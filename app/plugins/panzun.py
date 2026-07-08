import asyncio
import re
import time
from datetime import datetime
from typing import List, Dict, Any
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.plugins.base import PluginBase
from app.schemas import SearchResult, Link
from app.utils.link_parser import detect_disk_type


class PanzunPlugin(PluginBase):
    name = "panzun"
    enabled = settings.native_plugins_enabled
    timeout = settings.plugin_timeout
    base_url = "https://www.panzun.cc"
    api_base = "https://www.panzun.cc/api"

    async def search(self, keyword: str, limit: int = 20) -> List[SearchResult]:
        results: List[SearchResult] = []
        seen: Dict[str, bool] = {}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                for page in range(1, 4):
                    offset = (page - 1) * 20
                    url = f"{self.api_base}/discussions?filter[q]={quote(keyword)}&page[offset]={offset}"
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                    page_results = await self._convert_discussions(client, data.get("data", []))
                    for r in page_results:
                        if r.links and r.title and (r.title not in seen):
                            seen[r.title] = True
                            results.append(r)
                    if not data.get("links", {}).get("next"):
                        break
                    await asyncio.sleep(0.3)
        except Exception:
            pass
        return results[:limit]

    async def _convert_discussions(self, client: httpx.AsyncClient, discussions: List[Dict[str, Any]]) -> List[SearchResult]:
        if not discussions:
            return []
        sem = asyncio.Semaphore(4)
        tasks = [self._fetch_one(client, sem, idx, item) for idx, item in enumerate(discussions)]
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        ordered = [None] * len(discussions)
        for item in gathered:
            if isinstance(item, tuple):
                ordered[item[0]] = item[1]
        return [r for r in ordered if r]

    async def _fetch_one(self, client: httpx.AsyncClient, sem: asyncio.Semaphore, index: int, item: Dict[str, Any]):
        async with sem:
            disc_id = str(item.get("id", "")).strip()
            title = str(item.get("attributes", {}).get("title", "")).strip()
            if not disc_id or not title:
                return index, None
            links, content, tags, published_at = await self._fetch_links(client, disc_id)
            if not links:
                return index, None
            return index, SearchResult(
                title=title,
                content=content,
                links=links,
                tags=tags,
                source=f"plugin:{self.name}",
                published_at=published_at,
            )

    async def _fetch_links(self, client: httpx.AsyncClient, discussion_id: str):
        url = f"{self.api_base}/discussions/{discussion_id}"
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return [], "", [], None

        included = {f"{i.get('type')}:{i.get('id')}": i for i in data.get("included", []) if i.get("type") and i.get("id")}
        rel = data.get("data", {}).get("relationships", {})
        post_id = ""
        posts = rel.get("posts", {})
        if posts:
            refs = posts.get("data", [])
            if refs:
                post_id = refs[0].get("id", "")

        content_html = ""
        if post_id and f"posts:{post_id}" in included:
            content_html = included[f"posts:{post_id}"].get("attributes", {}).get("contentHtml", "")

        content = self._clean_html(content_html)
        links = self._extract_links(content_html)

        tags = []
        tags_raw = rel.get("tags", {}).get("data", [])
        for tag_ref in tags_raw:
            tid = tag_ref.get("id")
            tag = included.get(f"tags:{tid}")
            if tag:
                name = tag.get("attributes", {}).get("name")
                if name:
                    tags.append(name)

        published_at = None
        created = data.get("data", {}).get("attributes", {}).get("createdAt")
        if created:
            try:
                published_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except ValueError:
                pass

        return links, content, tags, published_at

    def _extract_links(self, html: str) -> List[Link]:
        soup = BeautifulSoup(html or "", "html.parser")
        seen = set()
        links: List[Link] = []
        for a in soup.find_all("a", href=True):
            url = a["href"]
            if url in seen:
                continue
            seen.add(url)
            if "a.7u9.cn/s/" in url:
                url = self._resolve_short(url)
            t = detect_disk_type(url)
            if t:
                links.append(Link(type=t, url=url, note=a.get_text(strip=True), source=f"plugin:{self.name}"))
        for url in re.findall(r"https?://[^\s<>\"]+", html):
            if url in seen:
                continue
            seen.add(url)
            if "a.7u9.cn/s/" in url:
                url = self._resolve_short(url)
            t = detect_disk_type(url)
            if t:
                links.append(Link(type=t, url=url, source=f"plugin:{self.name}"))
        return links

    def _resolve_short(self, url: str) -> str:
        try:
            resp = httpx.get(url, follow_redirects=False, timeout=10, headers={"User-Agent": "python-requests/2.31.0"})
            location = resp.headers.get("location", "")
            if location:
                return location
        except Exception:
            pass
        return url

    def _clean_html(self, value: str) -> str:
        if not value:
            return ""
        text = value.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
