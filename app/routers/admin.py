from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Category, Resource, HotKeyword
from app.schemas import CategoryCreate, CategoryOut, ResourceCreate, ResourceOut, HotKeywordOut

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
