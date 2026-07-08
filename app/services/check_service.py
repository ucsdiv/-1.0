import time
from typing import List

import httpx

from app.config import settings
from app.schemas import CheckRequest, CheckResponse, CheckResult, CheckItem
from app.utils.link_parser import detect_disk_type


def _normalize_url(item: CheckItem) -> str:
    url = item.url.strip()
    if item.password and "?" not in url and "#" not in url:
        url = f"{url}?pwd={item.password}"
    return url


async def check_upstream(items: List[CheckItem]) -> List[CheckResult]:
    if not settings.upstream_pansou_enabled:
        return []

    url = f"{settings.upstream_pansou_base_url.rstrip('/')}/api/check/links"
    payload = {"items": [{"disk_type": i.disk_type, "url": i.url, "password": i.password} for i in items]}

    try:
        async with httpx.AsyncClient(timeout=settings.upstream_pansou_timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    results = []
    for r in data.get("results", []):
        results.append(CheckResult(
            disk_type=r.get("disk_type", ""),
            url=r.get("url", ""),
            normalized_url=r.get("normalized_url", ""),
            state=r.get("state", "uncertain"),
            summary=r.get("summary", "上游检测返回"),
            checked_at=r.get("checked_at", int(time.time() * 1000)),
        ))
    return results


async def check_local(items: List[CheckItem]) -> List[CheckResult]:
    results = []
    now = int(time.time() * 1000)
    for item in items:
        normalized = _normalize_url(item)
        if detect_disk_type(item.url):
            results.append(CheckResult(
                disk_type=item.disk_type, url=item.url, normalized_url=normalized,
                state="uncertain", summary="本地仅做格式校验，未检测有效性", checked_at=now,
            ))
        else:
            results.append(CheckResult(
                disk_type=item.disk_type, url=item.url, normalized_url=normalized,
                state="unsupported", summary="不支持的网盘类型", checked_at=now,
            ))
    return results


async def perform_check(request: CheckRequest) -> CheckResponse:
    upstream_results = await check_upstream(request.items)
    if upstream_results:
        return CheckResponse(results=upstream_results)
    local_results = await check_local(request.items)
    return CheckResponse(results=local_results)
