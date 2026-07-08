import asyncio
import hashlib
import time
from datetime import datetime, timezone
from typing import List, Dict, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Resource, SearchLog
from app.schemas import SearchRequest, SearchResponse, SearchResult, Link
from app.services.plugin_manager import plugin_manager


_SORT_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _to_sort_dt(value: datetime | None) -> datetime:
    """Normalize aware/naive datetimes for stable sorting."""
    if value is None:
        return _SORT_EPOCH
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


# Simple in-memory cache with TTL for search plugin results
_search_cache: Dict[str, Tuple[float, List[SearchResult]]] = {}


def _cache_key(keyword: str, plugins: Tuple[str, ...], cloud_types: Tuple[str, ...] | None) -> str:
    raw = f"{keyword}|{plugins}|{cloud_types}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cached(keyword: str, plugins: Tuple[str, ...], cloud_types: Tuple[str, ...] | None) -> List[SearchResult] | None:
    if settings.cache_ttl <= 0:
        return None
    key = _cache_key(keyword, plugins, cloud_types)
    entry = _search_cache.get(key)
    if not entry:
        return None
    cached_at, results = entry
    if time.time() - cached_at > settings.cache_ttl:
        _search_cache.pop(key, None)
        return None
    return results


def _set_cached(keyword: str, plugins: Tuple[str, ...], cloud_types: Tuple[str, ...] | None, results: List[SearchResult]) -> None:
    if settings.cache_ttl <= 0:
        return
    key = _cache_key(keyword, plugins, cloud_types)
    _search_cache[key] = (time.time(), results)


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

    cache_plugins = tuple(sorted(p.name for p in plugins))
    cached = _get_cached(keyword, cache_plugins, None)
    if cached is not None:
        return cached

    per_plugin_limit = max(10, min(20, limit // max(1, len(plugins)) + 5))
    fast_threshold = 20  # collect more results before early return to support pagination

    async def run_plugin(plugin):
        try:
            return await asyncio.wait_for(plugin.search(keyword, per_plugin_limit), timeout=min(plugin.timeout, settings.plugin_timeout))
        except Exception:
            return []

    # Limit concurrent plugins to avoid overwhelming the event loop / network
    semaphore = asyncio.Semaphore(max(1, settings.max_concurrent_plugins))

    async def run_with_semaphore(plugin):
        async with semaphore:
            return await run_plugin(plugin)

    tasks = [asyncio.create_task(run_with_semaphore(p)) for p in plugins]

    results: List[SearchResult] = []
    pending = set(tasks)
    deadline = time.time() + settings.search_timeout
    started = time.time()
    min_fast_wait = 2.0  # seconds: let more plugins finish before returning early

    while pending and time.time() < deadline:
        done, pending = await asyncio.wait(
            pending, return_when=asyncio.FIRST_COMPLETED, timeout=max(0.1, deadline - time.time())
        )
        for task in done:
            try:
                item = task.result()
            except (Exception, asyncio.CancelledError):
                continue
            if isinstance(item, list):
                results.extend(item)
            if len(results) >= limit * 2:
                for t in pending:
                    t.cancel()
                _set_cached(keyword, cache_plugins, None, results[:limit * 3])
                return results[:limit * 3]
        if len(results) >= fast_threshold and (time.time() - started) >= min_fast_wait:
            for t in pending:
                t.cancel()
            _set_cached(keyword, cache_plugins, None, results[:limit * 3])
            return results[:limit * 3]

    for t in pending:
        t.cancel()
        try:
            await t
        except (Exception, asyncio.CancelledError):
            pass

    if results:
        _set_cached(keyword, cache_plugins, None, results)
    return results


def merge_by_type(results: List[SearchResult]) -> Dict[str, List[Link]]:
    merged: Dict[str, List[Link]] = {}
    seen_urls = set()
    for result in results:
        source = result.source or ""
        published_at = result.published_at
        for link in result.links:
            if not link.url or link.url in seen_urls:
                continue
            seen_urls.add(link.url)
            link.source = link.source or source
            if published_at and not link.published_at:
                link.published_at = published_at
            merged.setdefault(link.type, []).append(link)
    return merged


def filter_cloud_types(results: List[SearchResult], cloud_types: List[str] | None) -> List[SearchResult]:
    if not cloud_types:
        return results
    filtered = []
    for r in results:
        links = [l for l in r.links if l.type in cloud_types]
        if links:
            filtered.append(r.model_copy(update={"links": links}))
    return filtered


def deduplicate_results(results: List[SearchResult]) -> List[SearchResult]:
    seen = set()
    out: List[SearchResult] = []
    for r in results:
        if not r.links:
            continue
        key = (r.title or "") + "|" + r.links[0].url
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


async def perform_search(db: Session, request: SearchRequest, client_ip: str = "") -> SearchResponse:
    start = time.time()
    keyword = request.kw.strip()

    # page/offset normalization: page takes precedence when explicitly set > 1 with default offset
    offset = request.offset
    if request.page > 1 and request.offset == 0:
        offset = (request.page - 1) * request.limit

    tasks = []
    if request.src in ("all", "local"):
        tasks.append(search_local(db, keyword, request.cloud_types, request.limit + offset))

    plugin_task = None
    if request.src in ("all", "upstream", "plugin"):
        plugin_task = search_plugins(keyword, request.plugins, request.limit + offset)
        tasks.append(plugin_task)

    gathered = await asyncio.gather(*tasks)
    all_results: List[SearchResult] = []
    for item in gathered:
        all_results.extend(item)

    all_results = filter_cloud_types(all_results, request.cloud_types)
    all_results = deduplicate_results(all_results)
    all_results.sort(key=lambda x: _to_sort_dt(x.published_at), reverse=True)

    total = len(all_results)
    paged = all_results[offset:offset + request.limit]
    merged = merge_by_type(paged if request.res != "merge" else all_results)

    log = SearchLog(keyword=keyword, ip=client_ip, results_count=total)
    db.add(log)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    elapsed_ms = round((time.time() - start) * 1000, 2)
    has_more = offset + request.limit < total

    if request.res == "results":
        return SearchResponse(total=total, results=paged, merged_by_type={}, elapsed_ms=elapsed_ms, has_more=has_more)
    elif request.res == "merge":
        return SearchResponse(total=sum(len(v) for v in merged.values()), results=[], merged_by_type=merged, elapsed_ms=elapsed_ms, has_more=has_more)
    else:
        return SearchResponse(total=total, results=paged, merged_by_type=merged, elapsed_ms=elapsed_ms, has_more=has_more)
