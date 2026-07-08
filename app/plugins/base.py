from abc import ABC, abstractmethod
from typing import List

from app.schemas import SearchResult


class PluginBase(ABC):
    name: str = ""
    enabled: bool = True
    timeout: float = 5.0

    @abstractmethod
    async def search(self, keyword: str, limit: int = 20) -> List[SearchResult]:
        pass
