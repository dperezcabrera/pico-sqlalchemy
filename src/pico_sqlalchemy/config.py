from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from pico_ioc import configured


@runtime_checkable
class DatabaseConfigurer(Protocol):
    @property
    def priority(self) -> int:
        return 0

    def configure(self, engine) -> None:
        raise NotImplementedError


@configured(target="self", prefix="database", mapping="tree")
@dataclass
class DatabaseSettings:
    url: str = "sqlite:///./app.db"
    echo: bool = False
    pool_size: int = 5
    pool_pre_ping: bool = True
    pool_recycle: int = 3600
