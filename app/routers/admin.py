from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Category, Resource, HotKeyword
from app.schemas import (
    CategoryCreate, CategoryOut, ResourceCreate, ResourceOut,
    HotKeywordOut, BulkImportRequest, BulkImportResponse,
)
from app.services.plugin_manager import plugin_manager
from app.utils.link_parser import detect_disk_type

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/categories", response_model=CategoryOut)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)):
    cat = Category(**payload.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.get("/categories", response_model=List[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.sort_order).all()


@router.post("/resources", response_model=ResourceOut)
def create_resource(payload: ResourceCreate, db: Session = Depends(get_db)):
    resource = Resource(**payload.model_dump())
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource


@router.get("/resources", response_model=List[ResourceOut])
def list_resources(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Resource).order_by(Resource.created_at.desc()).offset(skip).limit(limit).all()


@router.delete("/resources/{resource_id}")
def delete_resource(resource_id: int, db: Session = Depends(get_db)):
    r = db.query(Resource).filter(Resource.id == resource_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Resource not found")
    db.delete(r)
    db.commit()
    return {"message": "deleted"}


@router.get("/hot-keywords", response_model=List[HotKeywordOut])
def list_hot_keywords(limit: int = 20, db: Session = Depends(get_db)):
    return db.query(HotKeyword).order_by(HotKeyword.count.desc()).limit(limit).all()


@router.post("/import", response_model=BulkImportResponse)
def bulk_import(payload: BulkImportRequest, db: Session = Depends(get_db)):
    imported = 0
    skipped = 0
    errors: List[str] = []
    for idx, item in enumerate(payload.items):
        url = item.url.strip()
        title = item.title.strip() or "未命名资源"
        if not url:
            skipped += 1
            continue
        disk_type = item.disk_type.strip() or detect_disk_type(url) or "others"
        existing = db.query(Resource).filter(Resource.url == url).first()
        if existing:
            skipped += 1
            continue
        try:
            resource = Resource(
                title=title,
                content=item.content,
                disk_type=disk_type,
                url=url,
                password=item.password,
                category_id=item.category_id,
                tags=item.tags,
                source="import",
            )
            db.add(resource)
            imported += 1
        except Exception as e:
            errors.append(f"第 {idx + 1} 行导入失败: {str(e)}")
    db.commit()
    return BulkImportResponse(imported=imported, skipped=skipped, errors=errors)


@router.get("/plugins")
def list_plugins():
    return {"plugins": plugin_manager.list_plugin_names()}
