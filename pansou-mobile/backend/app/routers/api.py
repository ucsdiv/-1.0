from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api", tags=["public"])


@router.post("/report", response_model=schemas.ReportOut)
def report(payload: schemas.ReportCreate, db: Session = Depends(get_db)):
    if not payload.resource_id or not payload.reason:
        raise HTTPException(status_code=400, detail="请填写完整的举报信息")

    one_hour_ago = datetime.now() - timedelta(hours=1)
    existing = (
        db.query(models.Report)
        .filter(
            models.Report.resource_id == payload.resource_id,
            models.Report.created_at >= one_hour_ago,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="您已经举报过该资源")

    report = models.Report(
        resource_id=payload.resource_id,
        reason=payload.reason,
        details=payload.details or "",
        contact=payload.contact or "",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("/config")
def get_configs(db: Session = Depends(get_db)):
    items = db.query(models.ConfigItem).all()
    return {item.name: item.value for item in items}
