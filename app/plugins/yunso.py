import base64
import html
import re
from datetime import datetime
from typing import List
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.plugins.base import PluginBase
from app.schemas import SearchResult, Link


class YunsoPlugin(PluginBase):
    name = "yunso"
    enabled = settings.native_plugins_enabled
    timeout = settings.plugin_timeout
    search_api = "https://www.yunso.net/api/Core/search2"
    search_page = "https://www.yunso.net/index/user/s"
    decrypt_key = "pWz1vnL1fTkOvTMW3f9M1jJWfneUIh50"

    async def search(self, keyword: str, limit: int = 20) -> List[SearchResult]:
        results: List[SearchResult] = []
        seen = set()
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                for page in range(1, 4):
                    items = await self._search_page(client, keyword, page)
                    for item in items:
                        if not item.url:
                            continue
                        key = item.url
                        if key in seen:
                            continue
                        seen.add(key)
                        results.append(self._convert(item))
                    if len(results) >= limit * 2:
                        break
        except Exception:
            pass
        return results[:limit]

    async def _search_page(self, client: httpx.AsyncClient, keyword: str, page: int) -> List["YunsoItem"]:
        params = {
            "requestID": "",
            "mode": "90002",
            "scope_content": "0",
            "stype": "",
            "wd": keyword,
            "uk": "",
            "page": str(page),
            "limit": "20",
            "screen_filetype": "",
        }
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Origin": "https://www.yunso.net",
            "Referer": f"{self.search_page}?wd={keyword}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
        }
        resp = await client.post(f"{self.search_api}?{urlencode(params)}", headers=headers)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            return []
        return self._parse_items(data.get("data", ""))

    def _parse_items(self, fragment: str) -> List["YunsoItem"]:
        items: List[YunsoItem] = []
        soup = BeautifulSoup(f'<div id="yunso-root">{fragment}</div>', "html.parser")
        for card in soup.find_all("div", attrs={"data-qid": True}):
            anchor = card.find("a", href=re.compile("open_sid"))
            if not anchor:
                continue
            title = self._clean_text(anchor.get_text())
            if not title:
                continue

            encrypted_url = anchor.get("url", "")
            decrypted_url = self._decrypt_url(encrypted_url) if encrypted_url else ""

            body_span = card.select_one(".layui-card-body span")
            file_summary = self._clean_text(body_span.get_text()) if body_span else ""
            if "N/A" in file_summary.upper():
                file_summary = ""

            header = card.select_one(".layui-card-header")
            datetime_str = self._extract_datetime(header.get_text() if header else "")

            img = card.find("img", src=re.compile(r"/assets/xyso/"))
            type_code = ""
            type_name = ""
            if img:
                type_name = self._clean_text(img.get("alt", ""))
                m = re.search(r"/assets/xyso/(\d+)\.png", img.get("src", ""))
                if m:
                    type_code = m.group(1)

            password = self._clean_text(anchor.get("pa", ""))
            if not password and decrypted_url:
                password = self._extract_password_from_url(decrypted_url)

            items.append(YunsoItem(
                title=title,
                url=decrypted_url,
                password=password,
                type_code=type_code,
                type_name=type_name,
                preview=self._clean_text(card.select_one("p.result.container.p").get_text() if card.select_one("p.result.container.p") else ""),
                file_summary=file_summary,
                datetime=datetime_str,
                badges=[self._clean_text(b.get_text()) for b in card.find_all("span", class_="badge") if self._clean_text(b.get_text())],
            ))
        return items

    def _convert(self, item: "YunsoItem") -> SearchResult:
        content_parts = [p for p in (item.preview, item.file_summary, f"网盘: {item.type_name}" if item.type_name else "") if p]
        return SearchResult(
            title=item.title,
            content="\n".join(content_parts),
            links=[Link(type=self._map_type(item.type_code, item.url), url=item.url, password=item.password, source=f"plugin:{self.name}")],
            tags=item.badges,
            source=f"plugin:{self.name}",
            published_at=item.datetime,
        )

    def _map_type(self, type_code: str, raw_url: str) -> str:
        mapping = {
            "1": "baidu",
            "20100": "aliyun",
            "20500": "quark",
            "20000": "tianyi",
            "20300": "mobile",
            "20400": "xunlei",
            "20501": "uc",
            "20600": "lanzou",
        }
        t = mapping.get(type_code.strip())
        if t:
            return t
        lower = raw_url.lower()
        if "uc.cn" in lower or "fast.uc.cn" in lower:
            return "uc"
        if "pan.baidu.com" in lower:
            return "baidu"
        if "alipan.com" in lower or "aliyundrive.com" in lower:
            return "aliyun"
        if "pan.quark.cn" in lower:
            return "quark"
        if "cloud.189.cn" in lower:
            return "tianyi"
        if "pan.xunlei.com" in lower:
            return "xunlei"
        if "115.com" in lower:
            return "115"
        if "123pan" in lower:
            return "123"
        if "drive.uc.cn" in lower:
            return "uc"
        return "others"

    def _decrypt_url(self, value: str) -> str:
        try:
            decoded = self._decode_base64(value)
            raw = decoded.decode().strip()
            if raw.startswith("http://") or raw.startswith("https://"):
                return raw
            key = self.decrypt_key.encode()
            result = bytes(decoded[i] ^ key[i % len(key)] for i in range(len(decoded)))
            return result.decode().strip()
        except Exception:
            return ""

    @staticmethod
    def _decode_base64(value: str) -> bytes:
        value = value.strip()
        if not value:
            raise ValueError("empty encrypted url")
        try:
            return base64.b64decode(value)
        except Exception:
            if len(value) % 4:
                value += "=" * (4 - len(value) % 4)
            return base64.b64decode(value)

    @staticmethod
    def _extract_password_from_url(raw_url: str) -> str:
        try:
            qs = parse_qs(urlparse(raw_url).query)
            for key in ("pwd", "pass", "password"):
                if key in qs:
                    return qs[key][0]
        except Exception:
            pass
        return ""

    @staticmethod
    def _extract_datetime(text: str) -> datetime | None:
        m = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", text)
        if not m:
            return None
        try:
            return datetime.strptime(m.group(0), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    @staticmethod
    def _clean_text(value: str) -> str:
        if not value:
            return ""
        value = html.unescape(value)
        return " ".join(value.split()).strip()


class YunsoItem:
    def __init__(self, title: str, url: str, password: str, type_code: str, type_name: str, preview: str, file_summary: str, datetime: datetime | None, badges: List[str]):
        self.title = title
        self.url = url
        self.password = password
        self.type_code = type_code
        self.type_name = type_name
        self.preview = preview
        self.file_summary = file_summary
        self.datetime = datetime
        self.badges = badges
