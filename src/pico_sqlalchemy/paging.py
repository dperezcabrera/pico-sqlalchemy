"""Pagination and sorting data types.

* ``Sort`` -- specifies a single sort clause (field + direction).
* ``PageRequest`` -- carries page number, page size, and optional sorts.
* ``Page[T]`` -- generic, frozen result container with computed
  ``total_pages``, ``is_first``, and ``is_last`` properties.

All three are frozen dataclasses, safe to use as dict keys or in sets.
"""

from dataclasses import dataclass, field
from typing import Generic, Sequence, TypeVar

T = TypeVar("T")


_VALID_DIRECTIONS = {"ASC", "DESC"}


@dataclass(frozen=True)
class Sort:
    """A single sort specification: field name and direction.

    The ``direction`` is validated on construction and must be
    ``"ASC"`` or ``"DESC"`` (case-insensitive).

    Attributes:
        field: The column name to sort by.
        direction: ``"ASC"`` (default) or ``"DESC"``.

    Raises:
        ValueError: ``"Invalid sort direction: <value> (expected 'ASC'
            or 'DESC')"`` if *direction* is not valid.

    Example::

        Sort("name")                  # ascending
        Sort("created_at", "DESC")    # descending
    """

    field: str
    direction: str = "ASC"

    def __post_init__(self):
        """Validate that ``direction`` is ``"ASC"`` or ``"DESC"``."""
        if self.direction.upper() not in _VALID_DIRECTIONS:
            raise ValueError(f"Invalid sort direction: {self.direction!r} (expected 'ASC' or 'DESC')")


@dataclass(frozen=True)
class PageRequest:
    """Request parameters for a paginated query.

    Attributes:
        page: Zero-based page number.
        size: Number of items per page.
        sorts: Optional list of ``Sort`` specifications.

    Example::

        req = PageRequest(page=0, size=20, sorts=[Sort("name")])
        assert req.offset == 0
        req2 = PageRequest(page=2, size=20)
        assert req2.offset == 40
    """

    page: int
    size: int
    sorts: list[Sort] = field(default_factory=list)

    @property
    def offset(self) -> int:
        """Compute the SQL ``OFFSET`` value (``page * size``)."""
        return self.page * self.size


@dataclass(frozen=True)
class Page(Generic[T]):
    """Generic container for a page of query results.

    Attributes:
        content: The items on this page.
        total_elements: Total number of matching rows across all pages.
        page: Zero-based page number of this page.
        size: Requested page size.

    Example::

        page = Page(content=[u1, u2], total_elements=55, page=0, size=20)
        assert page.total_pages == 3
        assert page.is_first is True
        assert page.is_last is False
    """

    content: Sequence[T]
    total_elements: int
    page: int
    size: int

    @property
    def total_pages(self) -> int:
        """Total number of pages (ceiling division)."""
        if self.size <= 0:
            return 0
        return (self.total_elements + self.size - 1) // self.size

    @property
    def is_first(self) -> bool:
        """``True`` if this is the first page (page 0)."""
        return self.page == 0

    @property
    def is_last(self) -> bool:
        """``True`` if this is the last page."""
        return self.page + 1 >= self.total_pages
