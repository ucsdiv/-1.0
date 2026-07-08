from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


class Link(BaseModel):
    type: str
    url: str
    password: str = ""
    note: str = ""
    published_at: Optional[datetime] = None
    source: str = ""
    images: List[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    title: str
    content: str = ""
    links: List[Link] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    images: List[str] = Field(default_factory=list)
    source: str = ""
    published_at: Optional[datetime] = None


class SearchRequest(BaseModel):
    kw: str = Field(..., min_length=1)
    res: str = Field(default="merge", pattern="^(all|results|merge)$")
    src: str = Field(default="all", pattern="^(all|local|upstream|plugin)$")
    plugins: Optional[List[str]] = None
    cloud_types: Optional[List[str]] = None
    limit: int = Field(default=50, ge=1, le=200)


class SearchResponse(BaseModel):
    total: int
    results: List[SearchResult]
    merged_by_type: Dict[str, List[Link]]
    elapsed_ms: float


class CheckItem(BaseModel):
    disk_type: str
    url: str
    password: str = ""


class CheckResult(BaseModel):
    disk_type: str
    url: str
    normalized_url: str
    state: str
    summary: str
    checked_at: int


class CheckRequest(BaseModel):
    items: List[CheckItem]


class CheckResponse(BaseModel):
    results: List[CheckResult]


class CategoryBase(BaseModel):
    name: str
    icon: str = ""
    sort_order: int = 0


class CategoryCreate(CategoryBase):
    pass


class CategoryOut(CategoryBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ResourceBase(BaseModel):
    title: str
    content: str = ""
    disk_type: str = "others"
    url: str
    password: str = ""
    category_id: int = 0
    tags: List[str] = Field(default_factory=list)
    images: List[str] = Field(default_factory=list)
    source: str = "local"


class ResourceCreate(ResourceBase):
    pass


class ResourceOut(ResourceBase):
    id: int
    is_valid: bool
    checked_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class HotKeywordOut(BaseModel):
    id: int
    keyword: str
    count: int

    class Config:
        from_attributes = True
