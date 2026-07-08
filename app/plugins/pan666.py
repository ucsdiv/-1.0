import re
from datetime import datetime
from typing import List, Dict, Any
from urllib.parse import quote

import httpx

from app.config import settings
from app.plugins.base import PluginBase
from app.schemas import SearchResult, Link
from app.utils.link_parser import detect_disk_type


class Pan666Plugin(PluginBase):
    name = "pan666"
    enabled = settings.native_plugins_enabled
    timeout = settings.plugin_timeout
    base_url = "https://pan666.net"
    api_base = "https://pan666.net/api/discussions"

    async def search(self, keyword: str, limit: int = 20) -> List[SearchResult]:
        results: List[SearchResult] = []
        seen: Dict[str, bool] = {}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                for page in range(0, 2):
                    offset = page * 50
                    url = f"{self.api_base}?filter[q]={quote(keyword)}&include=mostRelevantPost&page[offset]={offset}&page[limit]=50"
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                    page_results = self._parse(data)
                    for r in page_results:
                        if r.links and r.title and (r.title not in seen):
                            seen[r.title] = True
                            results.append(r)
                    if not data.get("links", {}).get("next"):
                        break
        except Exception:
            pass
        return results[:limit]

    def _parse(self, data: Dict[str, Any]) -> List[SearchResult]:
        results: List[SearchResult] = []
        included = {p["id"]: p for p in data.get("included", []) if p.get("type") == "posts" and p.get("id")}

        for discussion in data.get("data", []):
            post_id = discussion.get("relationships", {}).get("mostRelevantPost", {}).get("data", {}).get("id")
            post = included.get(post_id)
            if not post:
                continue

            title = discussion.get("attributes", {}).get("title", "").strip()
            content_html = post.get("attributes", {}).get("contentHtml", "")
            content = self._clean_html(content_html)
            links = self._extract_links(content_html)
            if not links:
                continue

            published_at = None
            created = discussion.get("attributes", {}).get("createdAt")
            if created:
                try:
                    published_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except ValueError:
                    pass

            results.append(SearchResult(
                title=title,
                content=content,
                links=links,
                source=f"plugin:{self.name}",
                published_at=published_at,
            ))
        return results

    def _extract_links(self, html: str) -> List[Link]:
        text = self._clean_html(html)
        patterns = [
            r"https?://pan\.baidu\.com/s/[a-zA-Z0-9_-]+(?:\?pwd=[a-zA-Z0-9]+)?",
            r"https?://www\.alipan\.com/s/[a-zA-Z0-9_-]+",
            r"https?://aliyundrive\.com/s/[a-zA-Z0-9_-]+",
            r"https?://cloud\.189\.cn/[a-zA-Z0-9_/-]+",
            r"https?://pan\.quark\.cn/s/[a-zA-Z0-9_-]+",
            r"https?://pan\.xunlei\.com/s/[a-zA-Z0-9_-]+",
            r"https?://drive\.uc\.cn/s/[a-zA-Z0-9_-]+",
            r"https?://www\.123pan\.com/s/[a-zA-Z0-9_-]+",
            r"https?://115\.com/s/[a-zA-Z0-9_-]+",
        ]
        seen = set()
        links: List[Link] = []
        for pattern in patterns:
            for url in re.findall(pattern, text):
                if url in seen:
                    continue
                seen.add(url)
                t = detect_disk_type(url)
                if t:
                    password = self._extract_password(text, url)
                    links.append(Link(type=t, url=url, password=password, note="", source=f"plugin:{self.name}"))
        return links

    def _extract_password(self, text: str, url: str) -> str:
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        for key in ("pwd", "password", "pass", "code"):
            if key in qs:
                return qs[key][0]
        idx = text.find(url)
        if idx == -1:
            return ""
        snippet = text[max(0, idx - 30):idx + len(url) + 100]
        for pattern in (r"提取码[：:]\s*([A-Za-z0-9]+)", r"密码[：:]\s*([A-Za-z0-9]+)", r"访问码[：:]\s*([A-Za-z0-9]+)"):
            m = re.search(pattern, snippet)
            if m:
                return m.group(1)
        return ""

    def _clean_html(self, value: str) -> str:
        if not value:
            return ""
        text = value.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        for old, new in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&nbsp;", " ")):
            text = text.replace(old, new)
        return text
