"""
Pagination utilities.

Why pagination?
  All list endpoints return paginated results rather than the full dataset.
  Without pagination, GET /drivers would return all 861 drivers at once —
  slow, memory-intensive, and unusable for clients.

  Standard pagination pattern:
    GET /drivers?page=1&limit=20
    → returns items 1-20 plus metadata:
      {
        "items": [...],
        "total": 861,
        "page": 1,
        "limit": 20,
        "pages": 44,
        "has_next": true,
        "has_prev": false
      }

  The `pages` and `has_next/has_prev` fields let clients build
  navigation UI without doing extra calculations.
"""

from typing import TypeVar, Generic, List
from pydantic import BaseModel, Field
from fastapi import Query

T = TypeVar("T")


class PaginationParams:
    """
    Reusable pagination query parameters.

    Used as a FastAPI dependency:
        async def list_drivers(pagination: PaginationParams = Depends()):

    FastAPI automatically reads `page` and `limit` from the query string.
    Pydantic validates the types and ranges.

    gt=0: page must be > 0 (no page 0)
    ge=1, le=100: limit between 1 and 100 (prevents ?limit=999999)
    """

    def __init__(
        self,
        page: int = Query(default=1, ge=1, description="Page number (1-based)"),
        limit: int = Query(default=20, ge=1, le=100, description="Items per page (max 100)"),
    ):
        self.page = page
        self.limit = limit

    @property
    def offset(self) -> int:
        """Calculate the SQL OFFSET for this page."""
        return (self.page - 1) * self.limit


class PagedResponse(BaseModel, Generic[T]):
    """
    Generic paginated response wrapper.

    Generic[T] means this works for any item type:
        PagedResponse[DriverResponse]
        PagedResponse[TeamResponse]
        etc.

    FastAPI uses this to generate correct OpenAPI documentation
    showing the full schema including the nested item type.
    """

    items: List[T]
    total: int = Field(description="Total number of items matching the query")
    page: int = Field(description="Current page number")
    limit: int = Field(description="Items per page")
    pages: int = Field(description="Total number of pages")
    has_next: bool = Field(description="Whether there is a next page")
    has_prev: bool = Field(description="Whether there is a previous page")

    @classmethod
    def create(cls, items: List[T], total: int, pagination: PaginationParams) -> "PagedResponse[T]":
        """Factory method to build a PagedResponse from query results."""
        pages = max(1, -(-total // pagination.limit))  # ceiling division
        return cls(
            items=items,
            total=total,
            page=pagination.page,
            limit=pagination.limit,
            pages=pages,
            has_next=pagination.page < pages,
            has_prev=pagination.page > 1,
        )
