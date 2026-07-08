import re
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc

from app.database import get_db
from app import models, schemas
from app.config import get_settings

router = APIRouter(prefix="/api", tags=["search"])

DRIVE_PATTERNS = {
    "baidu": re.compile(r"pan\.baidu\.com|yun\.baidu\.com|bdwp|bdpan", re.I),
    "aliyun": re.compile(r"aliyundrive\.com|alipan\.com|aliyun", re.I),
    "quark": re.compile(r"quark\.cn|quarkpan|quark", re.I),
    "tianyi": re.compile(r"189\.cn|cloud\.189\.cn|tianyi", re.I),
    "xunlei": re.compile(r"pan\.xunlei\.com|xunlei", re.I),
    "uc": re.compile(r"uc\.cn|drive\.uc\.cn|uc网盘|uc云盘", re.I),
    "pan115": re.compile(r"115\.com|115网盘|115云盘", re.I),
    "pan123": re.compile(r"123pan\.com|123云盘|123网盘", re.I),
    "pikpak": re.compile(r"pikpak", re.I),
    "yidong": re.compile(r"caiyun\.10086\.cn|移动云盘|彩云", re.I),
    "magnet": re.compile(r"^magnet:", re.I),
    "ed2k": re.compile(r"^ed2k://", re.I),
    "google": re.compile(r"drive\.google\.com|googledrive", re.I),
}

DRIVE_NAMES = {
    "baidu": "百度网盘",
    "aliyun": "阿里云盘",
    "quark": "夸克网盘",
    "tianyi": "天翼云盘",
    "xunlei": "迅雷网盘",
    "uc": "UC网盘",
    "pan115": "115网盘",
    "pan123": "123云盘",
    "pikpak": "PikPak",
    "yidong": "移动云盘",
    "magnet": "磁力链接",
    "ed2k": "电驴链接",
    "google": "谷歌云盘",
    "unknown": "其他链接",
}


def detect_drive_type(url: str) -> str:
    if not url:
        return "unknown"
    for drive, pattern in DRIVE_PATTERNS.items():
        if pattern.search(url):
            return drive
    return "unknown"


def build_time_condition(sort_value: str):
    now = datetime.now()
    if sort_value == "2":
        return now - timedelta(days=30)
    elif sort_value == "3":
        return now - timedelta(days=180)
    elif sort_value == "4":
        return now - timedelta(days=365)
    return None


def record_keyword(db: Session, keyword: str):
    keyword = keyword.strip()[:255]
    if not keyword:
        return
    existing = db.query(models.Keyword).filter(models.Keyword.keyword == keyword).first()
    if existing:
        existing.search_count = (existing.search_count or 0) + 1
        existing.created_at = func.current_timestamp()
    else:
        db.add(models.Keyword(keyword=keyword, search_count=1))
    db.commit()


@router.get("/search", response_model=schemas.SearchResponse)
def search_get(
    kw: str = Query(..., min_length=1),
    category: Optional[int] = Query(None),
    sort: str = Query("1"),
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return do_search(db, kw, category, sort, page, page_size)


@router.post("/search", response_model=schemas.SearchMergedResponse)
def search_post(payload: schemas.SearchRequest, db: Session = Depends(get_db)):
    result = do_search(db, payload.kw, payload.category, payload.sort, payload.page, payload.page_size)
    merged = {}
    for item in result.results:
        drive_type = detect_drive_type(item.url)
        entry = schemas.MergedLink(
            url=item.url or "",
            password=item.code or "",
            note=item.title,
            datetime=item.created_at.isoformat() if item.created_at else "",
            source="local",
        )
        if drive_type not in merged:
            merged[drive_type] = []
        merged[drive_type].append(entry)

    return schemas.SearchMergedResponse(
        total=result.total,
        results=[],
        merged_by_type=merged,
    )


def do_search(
    db: Session,
    keyword: str,
    category: Optional[int],
    sort: str,
    page: int,
    page_size: int,
) -> schemas.SearchResponse:
    record_keyword(db, keyword)

    query = db.query(models.Resource).filter(
        models.Resource.title.ilike(f"%{keyword}%")
    )

    since = build_time_condition(sort)
    if since:
        query = query.filter(models.Resource.created_at >= since)

    if category:
        query = query.filter(models.Resource.category_id == category)

    total = query.count()
    resources = (
        query.order_by(desc(models.Resource.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    categories = {c.id: c.name for c in db.query(models.Category).all()}

    results = []
    for r in resources:
        item = schemas.SearchResultItem(
            id=r.id,
            title=r.title or "",
            content=r.content or "",
            url=r.url or "",
            code=r.code or "",
            size=r.size or "",
            category_id=r.category_id or 0,
            category_name=categories.get(r.category_id, ""),
            label=r.label or "",
            created_at=r.created_at,
            source="local",
        )
        results.append(item)

    return schemas.SearchResponse(total=total, page=page, page_size=page_size, results=results)


@router.get("/resource/{resource_id}", response_model=schemas.ResourceOut)
def resource_detail(resource_id: int, db: Session = Depends(get_db)):
    r = db.query(models.Resource).filter(models.Resource.id == resource_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="资源不存在")
    category = db.query(models.Category).filter(models.Category.id == r.category_id).first()
    data = schemas.ResourceOut.from_orm(r)
    data.category_name = category.name if category else ""
    return data


@router.get("/categories", response_model=list[schemas.CategoryOut])
def list_categories(is_show: Optional[int] = Query(None), db: Session = Depends(get_db)):
    q = db.query(models.Category)
    if is_show is not None:
        q = q.filter(models.Category.is_show == is_show)
    return q.all()


@router.get("/hot-keywords", response_model=list[schemas.KeywordOut])
def hot_keywords(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return (
        db.query(models.Keyword)
        .filter(models.Keyword.is_audit == 1)
        .order_by(desc(models.Keyword.search_count))
        .limit(limit)
        .all()
    )


@router.get("/client-info")
def client_info():
    return {"ip": "unknown", "country": "unknown"}
