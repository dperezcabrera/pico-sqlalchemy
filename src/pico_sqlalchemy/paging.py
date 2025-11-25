from dataclasses import dataclass, field
from typing import Generic, Sequence, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Sort:
    field: str
    direction: str = "ASC"


@dataclass(frozen=True)
class PageRequest:
    page: int
    size: int
    sorts: list[Sort] = field(default_factory=list)

    @property
    def offset(self) -> int:
        return self.page * self.size


@dataclass(frozen=True)
class Page(Generic[T]):
    content: Sequence[T]
    total_elements: int
    page: int
    size: int

    @property
    def total_pages(self) -> int:
        if self.size <= 0:
            return 0
        return (self.total_elements + self.size - 1) // self.size

    @property
    def is_first(self) -> bool:
        return self.page == 0

    @property
    def is_last(self) -> bool:
        return self.page + 1 >= self.total_pages