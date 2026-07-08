import re
import gzip
from datetime import datetime
from typing import List
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.plugins.base import PluginBase
from app.schemas import SearchResult, Link
from app.utils.link_parser import detect_disk_type


class QuPanShePlugin(PluginBase):
    name = "qupanshe"
    enabled = settings.native_plugins_enabled
    timeout = settings.plugin_timeout
    base_url = "https://www.qupanshe.com"

    async def search(self, keyword: str, limit: int = 20) -> List[SearchResult]:
        results: List[SearchResult] = []
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                formhash = await self._get_formhash(client)
                if not formhash:
                    return results
                search_url = await self._post_search(client, keyword, formhash)
                if not search_url:
                    return results
                results = await self._get_results(client, search_url, keyword, limit)
        except Exception:
            pass
        return results

    async def _get_formhash(self, client: httpx.AsyncClient) -> str:
        headers = {
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": self.base_url + "/",
        }
        resp = await client.get(self.base_url, headers=headers)
        resp.raise_for_status()
        text = _decode(resp)
        soup = BeautifulSoup(text, "html.parser")
        el = soup.find("input", {"name": "formhash"})
        return el.get("value", "").strip() if el else ""

    async def _post_search(self, client: httpx.AsyncClient, keyword: str, formhash: str) -> str:
        await __import__("asyncio").sleep(1)
        data = urlencode({
            "formhash": formhash,
            "srchtxt": keyword,
            "searchsubmit": "yes",
        })
        headers = {
            "User-Agent": _UA,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": self.base_url + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        resp = await client.post(f"{self.base_url}/search.php?mod=forum", content=data, headers=headers)
        location = resp.headers.get("location", "")
        if location:
            if location.startswith("http"):
                return location
            return self.base_url + "/" + location.lstrip("/")
        return ""

    async def _get_results(self, client: httpx.AsyncClient, search_url: str, keyword: str, limit: int) -> List[SearchResult]:
        headers = {
            "User-Agent": _UA,
            "Referer": self.base_url + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
        }
        resp = await client.get(search_url, headers=headers)
        resp.raise_for_status()
        text = _decode(resp)
        soup = BeautifulSoup(text, "html.parser")

        results: List[SearchResult] = []
        seen = set()
        for li in soup.select("li.pbw")[:limit]:
            title_link = li.select_one("h3.xs3 a")
            if not title_link:
                continue
            title = self._clean_title(title_link.get_text(strip=True))
            detail_path = title_link.get("href", "")
            detail_url = ""
            if detail_path:
                detail_url = detail_path if detail_path.startswith("http") else self.base_url + "/" + detail_path.lstrip("/")

            ps = li.find_all("p")
            content = ps[1].get_text(strip=True) if len(ps) > 1 else ""

            links: List[Link] = []
            for a in ps[1].find_all("a", href=True) if len(ps) > 1 else []:
                url = a["href"]
                t = detect_disk_type(url)
                if t:
                    links.append(self._make_link(t, url, content))

            text_links = _extract_text_links(content)
            for link in text_links:
                if not any(l.url == link.url for l in links):
                    links.append(link)

            if not links:
                continue

            last_p = ps[-1] if ps else None
            spans = last_p.find_all("span") if last_p else []
            time_str = spans[0].get_text(strip=True) if len(spans) > 0 else ""
            author = spans[1].find("a").get_text(strip=True) if len(spans) > 1 and spans[1].find("a") else ""
            category = spans[2].find("a").get_text(strip=True) if len(spans) > 2 and spans[2].find("a") else ""

            published_at = _parse_time(time_str)
            unique_key = title + "|" + links[0].url
            if unique_key in seen:
                continue
            seen.add(unique_key)

            enriched = content
            if detail_url:
                enriched = f"{content} | 作者: {author} | 分类: {category} | 详情: {detail_url}"

            results.append(SearchResult(
                title=title,
                content=enriched,
                links=links,
                source=f"plugin:{self.name}",
                published_at=published_at or datetime.utcnow(),
            ))
        return results

    def _make_link(self, disk_type: str, url: str, content: str) -> Link:
        password = ""
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        for key in ("pwd", "password", "pass", "code"):
            if key in qs:
                password = qs[key][0]
                qs.pop(key)
                break
        if not password:
            password = _extract_password(content, url)
        clean_url = urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))
        return Link(type=disk_type, url=clean_url, password=password, note="", source=f"plugin:{self.name}")

    def _clean_title(self, html: str) -> str:
        text = re.sub(r"<[^>]+>", "", html)
        for old, new in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"')):
            text = text.replace(old, new)
        return text.strip()


def _decode(resp: httpx.Response) -> str:
    data = resp.content
    if resp.headers.get("content-encoding") == "gzip":
        data = gzip.decompress(data)
    return data.decode("utf-8", errors="ignore")


def _extract_text_links(text: str) -> List[Link]:
    patterns = [
        r"https?://pan\.quark\.cn/s/[a-zA-Z0-9_-]+",
        r"https?://pan\.baidu\.com/s/[a-zA-Z0-9_-]+(?:\?pwd=[a-zA-Z0-9]+)?",
        r"https?://www\.alipan\.com/s/[a-zA-Z0-9_-]+",
        r"https?://aliyundrive\.com/s/[a-zA-Z0-9_-]+",
        r"https?://pan\.xunlei\.com/s/[a-zA-Z0-9_-]+",
        r"https?://cloud\.189\.cn/[a-zA-Z0-9_/-]+",
        r"https?://pan\.uc\.cn/s/[a-zA-Z0-9_-]+",
        r"https?://www\.123pan\.com/s/[a-zA-Z0-9_-]+",
        r"https?://www\.123684\.com/s/[a-zA-Z0-9_-]+",
        r"https?://115cdn\.com/[a-zA-Z0-9_/-]+",
        r"https?://115\.com/[a-zA-Z0-9_/-]+",
        r"https?://pan\.pikpak\.com/s/[a-zA-Z0-9_-]+",
        r"https?://mypikpak\.com/s/[a-zA-Z0-9_-]+",
        r"https?://caiyun\.139\.com/[a-zA-Z0-9_/-]+",
    ]
    links: List[Link] = []
    seen = set()
    for pattern in patterns:
        for url in re.findall(pattern, text):
            if url in seen:
                continue
            seen.add(url)
            t = detect_disk_type(url)
            if t:
                password = _extract_password(text, url)
                parsed = urlparse(url)
                qs = parse_qs(parsed.query)
                for key in ("pwd", "password", "pass", "code"):
                    if key in qs:
                        password = qs[key][0]
                        qs.pop(key)
                        break
                clean_url = urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))
                links.append(Link(type=t, url=clean_url, password=password, source="plugin:qupanshe"))
    return links


def _extract_password(content: str, url: str) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    for key in ("pwd", "password", "pass", "code"):
        if key in qs:
            return qs[key][0]
    idx = content.find(url)
    if idx == -1:
        return ""
    snippet = content[max(0, idx - 20):idx + len(url) + 100]
    for pattern in (r"提取码[：:]\s*([A-Za-z0-9]+)", r"密码[：:]\s*([A-Za-z0-9]+)", r"pwd[：:=]\s*([A-Za-z0-9]+)", r"password[：:=]\s*([A-Za-z0-9]+)"):
        m = re.search(pattern, snippet)
        if m:
            return m.group(1)
    return ""


def _parse_time(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
