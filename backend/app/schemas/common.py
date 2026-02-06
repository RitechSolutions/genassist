from typing import Generic, List, TypeVar

from pydantic import BaseModel

from app.schemas.filter import BaseFilterModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response for list endpoints"""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    @classmethod
    def from_filter(
        cls,
        items: List[T],
        total: int,
        filter_obj: BaseFilterModel
    ) -> "PaginatedResponse[T]":
        """
        Create a PaginatedResponse from items, total count, and filter object.
        Converts skip/limit to page/page_size for the response.
        """
        page_size = filter_obj.limit
        page = (filter_obj.skip // page_size) + 1 if page_size > 0 else 1
        total_pages = (total + page_size - 1) // page_size if total > 0 and page_size > 0 else 0

        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
