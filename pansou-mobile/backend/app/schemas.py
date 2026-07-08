from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# --- Config ---
class ConfigOut(BaseModel):
    name: str
    value: str

    class Config:
        from_attributes = True


# --- Category ---
class CategoryOut(BaseModel):
    id: int
    name: str
    url: str
    is_show: int

    class Config:
        from_attributes = True


# --- Keyword ---
class KeywordOut(BaseModel):
    id: int
    keyword: str
    search_count: int

    class Config:
        from_attributes = True


# --- Resource ---
class ResourceBase(BaseModel):
    title: str
    content: Optional[str] = ""
    url: Optional[str] = ""
    code: Optional[str] = ""
    size: Optional[str] = ""
    category_id: Optional[int] = 0
    label: Optional[str] = ""
    created_at: Optional[datetime] = None


class ResourceCreate(ResourceBase):
    pass


class ResourceUpdate(ResourceBase):
    pass


class ResourceOut(ResourceBase):
    id: int
    updated_at: Optional[datetime] = None
    category_name: Optional[str] = ""

    class Config:
        from_attributes = True


# --- Search ---
class SearchRequest(BaseModel):
    kw: str = Field(..., min_length=1)
    category: Optional[int] = None
    sort: Optional[str] = "1"  # 1=all, 2=1month, 3=6months, 4=1year
    page: Optional[int] = 1
    page_size: Optional[int] = 15


class SearchResultItem(BaseModel):
    id: int
    title: str
    content: Optional[str] = ""
    url: Optional[str] = ""
    code: Optional[str] = ""
    size: Optional[str] = ""
    category_id: Optional[int] = 0
    category_name: Optional[str] = ""
    label: Optional[str] = ""
    created_at: Optional[datetime] = None
    source: Optional[str] = "local"


class SearchResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: List[SearchResultItem]


# --- MergedByType (Limitless-search compatible) ---
class MergedLink(BaseModel):
    url: str
    password: Optional[str] = ""
    note: Optional[str] = ""
    datetime: Optional[str] = ""
    source: Optional[str] = "local"


class SearchMergedResponse(BaseModel):
    total: int
    results: List[Dict[str, Any]] = []
    merged_by_type: Dict[str, List[MergedLink]] = {}


# --- Report ---
class ReportCreate(BaseModel):
    resource_id: int
    reason: str
    details: Optional[str] = ""
    contact: Optional[str] = ""


class ReportOut(ReportCreate):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Admin ---
class AdminLogin(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class StatsOut(BaseModel):
    total_resources: int
    total_categories: int
    total_keywords: int
    total_reports: int
