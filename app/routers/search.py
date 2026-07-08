from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import SearchRequest, SearchResponse
from app.services.search_service import perform_search

router = APIRouter(prefix="/api", tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search_post(payload: SearchRequest, req: Request, db: Session = Depends(get_db)):
    return await perform_search(db, payload, client_ip=req.client.host if req.client else "")


@router.get("/search", response_model=SearchResponse)
async def search_get(
    kw: str,
    res: str = "merge",
    src: str = "all",
    limit: int = 50,
    req: Request = None,
    db: Session = Depends(get_db),
):
    payload = SearchRequest(kw=kw, res=res, src=src, limit=limit)
    return await perform_search(db, payload, client_ip=req.client.host if req and req.client else "")
