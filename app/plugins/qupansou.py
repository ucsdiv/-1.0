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
    api_url = "https://v.funletu.com/search"

    async def search(self, keyword: str, limit: int = 20) -> List[SearchResult]:
        results: List[SearchResult] = []
        seen = set()
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                body = {
                    "style": "get",
                    "datasrc": "search",
                    "query": {
                        "id": "",
                        "datetime": "",
                        "courseid": 1,
                        "categoryid": "",
                        "filetypeid": "",
                        "filetype": "",
                        "reportid": "",
                        "validid": "",
                        "searchtext": keyword,
                    },
                    "page": {"pageSize": 1000, "pageIndex": 1},
                    "order": {"prop": "sort", "order": "desc"},
                    "message": "请求资源列表数据",
                }
                resp = await client.post(
                    self.api_url,
                    json=body,
                    headers={
                        "Content-Type": "application/json",
                        "Referer": "https://pan.funletu.com/",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("status") != 200:
                    return results

                for item in data.get("data", [])[:limit]:
                    title = self._clean_html(item.get("title", "")).strip()
                    url = item.get("url", "").strip()
                    if not url:
                        continue
                    disk_type = detect_disk_type(url)
                    if not disk_type:
                        continue
                    key = f"{title}|{url}"
                    if key in seen:
                        continue
                    seen.add(key)

                    published_at = None
                    time_str = item.get("updatetime", "")
                    if time_str:
                        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                            try:
                                published_at = datetime.strptime(time_str, fmt)
                                break
                            except ValueError:
                                continue

                    content = f"类别: {item.get('category', '')}, 文件类型: {item.get('filetype', '')}, 大小: {item.get('size', '')}"
                    results.append(SearchResult(
                        title=title or "无标题",
                        content=content,
                        links=[Link(type=disk_type, url=url, source=f"plugin:{self.name}")],
                        source=f"plugin:{self.name}",
                        published_at=published_at or datetime.utcnow(),
                    ))
        except Exception:
            pass
        return results

    def _clean_html(self, html: str) -> str:
        import re
        text = html
        for tag in ("<em>", "</em>", "<b>", "</b>", "<strong>", "</strong>", "<i>", "</i>"):
            text = text.replace(tag, "")
        text = re.sub(r"<[^>]+>", "", text)
        return text.strip()
