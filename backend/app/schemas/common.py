from typing import Generic, List, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response for list endpoints"""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
