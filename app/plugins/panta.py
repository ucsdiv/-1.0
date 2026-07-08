import asyncio
import re
from datetime import datetime
from typing import List, Dict, Any
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.plugins.base import PluginBase
from app.schemas import SearchResult, Link
from app.utils.link_parser import detect_disk_type


class PantaPlugin(PluginBase):
    name = "panta"
    enabled = settings.native_plugins_enabled
    timeout = settings.plugin_timeout
    base_url = "https://www.91panta.cn"
    search_url_template = "https://www.91panta.cn/search?keyword={}"
    thread_url_template = "https://www.91panta.cn/thread?topicId={}"

    _link_patterns = [
        re.compile(r"https?://pan\.baidu\.com/s/[a-zA-Z0-9_-]+(?:\?pwd=[a-zA-Z0-9]+)?"),
        re.compile(r"https?://pan\.quark\.cn/s/[a-zA-Z0-9_-]+"),
        re.compile(r"https?://www\.aliyundrive\.com/s/[a-zA-Z0-9_-]+"),
        re.compile(r"https?://alipan\.com/s/[a-zA-Z0-9_-]+"),
        re.compile(r"https?://pan\.xunlei\.com/s/[a-zA-Z0-9_-]+(?:\?pwd=[a-zA-Z0-9]+)?"),
        re.compile(r"https?://cloud\.189\.cn/t/[a-zA-Z0-9_-]+"),
        re.compile(r"https?://caiyun\.139\.com/[mw]/i\?[a-zA-Z0-9_-]+"),
        re.compile(r"https?://www\.caiyun\.139\.com/[mw]/i\?[a-zA-Z0-9_-]+"),
        re.compile(r"https?://115\.com/s/[a-zA-Z0-9_-]+"),
        re.compile(r"https?://115cdn\.com/s/[a-zA-Z0-9_-]+"),
    ]

    _pwd_patterns = [
        re.compile(r"提取码[：:]\s*([a-zA-Z0-9]+)"),
        re.compile(r"密码[：:]\s*([a-zA-Z0-9]+)"),
        re.compile(r"pwd[：:=]\s*([a-zA-Z0-9]+)"),
        re.compile(r"password[：:=]\s*([a-zA-Z0-9]+)"),
    ]

    async def search(self, keyword: str, limit: int = 20) -> List[SearchResult]:
        results: List[SearchResult] = []
        seen = set()
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                search_url = self.search_url_template.format(quote(keyword))
                resp = await client.get(
                    search_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Referer": "https://www.91panta.cn/index",
                    },
                )
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                items = soup.select("div.topicItem")[:limit]

                sem = asyncio.Semaphore(4)
                tasks = [self._fetch_topic(client, sem, item, idx) for idx, item in enumerate(items)]
                gathered = await asyncio.gather(*tasks, return_exceptions=True)

                for item in gathered:
                    if isinstance(item, tuple):
                        result = item[1]
                        if result and result.links:
                            key = f"{result.title}|{result.links[0].url}"
                            if key in seen:
                                continue
                            seen.add(key)
                            results.append(result)
        except Exception:
            pass
        return results[:limit]

    async def _fetch_topic(self, client: httpx.AsyncClient, sem: asyncio.Semaphore, item: Any, index: int):
        async with sem:
            title_el = item.select_one("a.topic-title")
            if not title_el:
                return index, None
            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            topic_id_match = re.search(r"topicId=(\d+)", href)
            if not topic_id_match:
                return index, None
            topic_id = topic_id_match.group(1)

            try:
                thread_url = self.thread_url_template.format(topic_id)
                resp = await client.get(
                    thread_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Referer": "https://www.91panta.cn/search",
                    },
                )
                resp.raise_for_status()
                text = resp.text
            except Exception:
                return index, None

            links = self._extract_links(text)
            if not links:
                return index, None

            content = self._clean_html(text)
            published_at = self._extract_time(text)
            return index, SearchResult(
                title=title,
                content=content,
                links=links,
                source=f"plugin:{self.name}",
                published_at=published_at,
            )

    def _extract_links(self, html: str) -> List[Link]:
        links: List[Link] = []
        seen = set()
        for pattern in self._link_patterns:
            for url in pattern.findall(html):
                if url in seen:
                    continue
                seen.add(url)
                disk_type = detect_disk_type(url)
                if not disk_type:
                    continue
                password = self._extract_password(html, url)
                links.append(Link(type=disk_type, url=url, password=password, source=f"plugin:{self.name}"))
        return links

    def _extract_password(self, text: str, url: str) -> str:
        parsed = __import__("urllib.parse").urlparse(url)
        qs = __import__("urllib.parse").parse_qs(parsed.query)
        for key in ("pwd", "password"):
            if key in qs:
                return qs[key][0]
        idx = text.find(url)
        if idx == -1:
            return ""
        snippet = text[max(0, idx - 50):idx + len(url) + 100]
        for pattern in self._pwd_patterns:
            m = pattern.search(snippet)
            if m:
                return m.group(1)
        return ""

    def _extract_time(self, text: str) -> datetime | None:
        m = re.search(r"发表时间：(.+?)</", text)
        if not m:
            return None
        value = m.group(1).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    def _clean_html(self, html: str) -> str:
        if not html:
            return ""
        text = html.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
