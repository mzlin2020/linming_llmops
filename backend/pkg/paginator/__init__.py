from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class Paginator:
    """简单分页器：调用方传 page/page_size，自身负责 offset/limit 计算"""
    page: int = 1
    page_size: int = 20
    total_record: int = 0
    items: List[Any] = field(default_factory=list)

    @property
    def offset(self) -> int:
        return max(0, (self.page - 1) * self.page_size)

    @property
    def total_page(self) -> int:
        if self.page_size <= 0:
            return 0
        return (self.total_record + self.page_size - 1) // self.page_size

    def to_dict(self) -> dict:
        return {
            "list": self.items,
            "paginator": {
                "current_page": self.page,
                "page_size": self.page_size,
                "total_page": self.total_page,
                "total_record": self.total_record,
            },
        }
