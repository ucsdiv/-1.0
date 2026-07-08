import asyncio
import time
from datetime import datetime
from typing import List, Dict

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Resource, SearchLog
from app.schemas import SearchRequest, SearchResponse, SearchResult, Link
from app.services.plugin_manager import plugin_manager


async def search_local(db: Session, keyword: str, cloud_types: List[str] | None, limit: int) -> List[SearchResult]:
    q = db.query(Resource).filter(
        or_(
            Resource.title.ilike(f"%{keyword}%"),
            Resource.content.ilike(f"%{keyword}%"),
            Resource.url.ilike(f"%{keyword}%"),
        )
    )
    if cloud_types:
        q = q.filter(Resource.disk_type.in_(cloud_types))

    resources = q.order_by(Resource.created_at.desc()).limit(limit).all()
    results: List[SearchResult] = []
    for r in resources:
        results.append(SearchResult(
            title=r.title,
            content=r.content,
            links=[Link(
                type=r.disk_type, url=r.url, password=r.password,
                note=r.title, source=r.source, images=r.images or [],
            )],
            tags=r.tags or [],
            images=r.images or [],
            source=r.source,
            published_at=r.created_at,
        ))
    return results


async def search_plugins(keyword: str, plugin_names: List[str] | None, limit: int) -> List[SearchResult]:
    plugins = plugin_manager.plugins
    if plugin_names:
        plugins = [p for p in plugins if p.name in plugin_names]

    if not plugins:
        return []

    per_plugin_limit = max(1, limit // max(1, len(plugins)) + 5)

    async def run_plugin(plugin):
        try:
            return await asyncio.wait_for(plugin.search(keyword, per_plugin_limit), timeout=plugin.timeout)
        except Exception:
            return []

    tasks = [run_plugin(p) for p in plugins]
    gathered = await asyncio.gather(*tasks, return_exceptions=True)

    results: List[SearchResult] = []
    for item in gathered:
        if isinstance(item, list):
            results.extend(item)
    return results


def merge_by_type(results: List[SearchResult]) -> Dict[str, List[Link]]:
    merged: Dict[str, List[Link]] = {}
    seen_urls = set()
    for result in results:
        for link in result.links:
            if not link.url or link.url in seen_urls:
                continue
            seen_urls.add(link.url)
            merged.setdefault(link.type, []).append(link)
    return merged


def filter_cloud_types(results: List[SearchResult], cloud_types: List[str] | None) -> List[SearchResult]:
    if not cloud_types:
        return results
    filtered = []
    for r in results:
        links = [l for l in r.links if l.type in cloud_types]
        if links:
            filtered.append(SearchResult(**{**r.model_dump(), "links": links}))
    return filtered


async def perform_search(db: Session, request: SearchRequest, client_ip: str = "") -> SearchResponse:
    start = time.time()
    keyword = request.kw.strip()

    tasks = []
    if request.src in ("all", "local"):
        tasks.append(search_local(db, keyword, request.cloud_types, request.limit))

    plugin_task = None
    if request.src in ("all", "upstream", "plugin"):
        plugin_task = search_plugins(keyword, request.plugins, request.limit)
        tasks.append(plugin_task)

    gathered = await asyncio.gather(*tasks)
    all_results: List[SearchResult] = []
    for item in gathered:
        all_results.extend(item)

    all_results = filter_cloud_types(all_results, request.cloud_types)
    all_results.sort(key=lambda x: x.published_at or datetime.min, reverse=True)
    merged = merge_by_type(all_results)

    log = SearchLog(keyword=keyword, ip=client_ip, results_count=len(all_results))
    db.add(log)
    db.commit()

    elapsed_ms = round((time.time() - start) * 1000, 2)

    if request.res == "results":
        return SearchResponse(total=len(all_results), results=all_results, merged_by_type={}, elapsed_ms=elapsed_ms)
    elif request.res == "merge":
        return SearchResponse(total=sum(len(v) for v in merged.values()), results=[], merged_by_type=merged, elapsed_ms=elapsed_ms)
    else:
        return SearchResponse(total=len(all_results), results=all_results, merged_by_type=merged, elapsed_ms=elapsed_ms)
