from fastapi import APIRouter

from app.schemas import CheckRequest, CheckResponse
from app.services.check_service import perform_check

router = APIRouter(prefix="/api", tags=["check"])


@router.post("/check/links", response_model=CheckResponse)
async def check_links(payload: CheckRequest):
    return await perform_check(payload)
