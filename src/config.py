from enum import IntEnum
from typing import Any, NamedTuple, Protocol, TypeVar

import tomllib

from .definitions import ROOT_DIR

CONFIG_PATH = ROOT_DIR / "config/config.toml"


class LoggingLevels(IntEnum):
    CRITICAL = 50
    FATAL = CRITICAL
    ERROR = 40
    WARNING = 30
    WARN = WARNING
    INFO = 20
    DEBUG = 10


class LoggingFiles(NamedTuple):
    level: LoggingLevels
    max_size: int
    backup_count: int
    backup_count_tar: int


class Logging(NamedTuple):
    stderr_level: LoggingLevels
    files: LoggingFiles


class IndexableContainer(Protocol):
    def __getitem__(self, key: str, /) -> Any: ...


T = TypeVar("T")


class DotIndexer:
    def __init__(
        self, obj: IndexableContainer, current_query: str | None = None
    ) -> None:
        self.obj = obj
        self.current_query = current_query

    def get_full_query(self, index_query: str | None) -> str:
        assert (index_query is not None) or (self.current_query is not None)
        if self.current_query is None:
            # NOTE: pyright freaks out if I don't add this
            assert index_query is not None
            return index_query
        if index_query is None:
            return self.current_query
        return f"{self.current_query}.{index_query}"

    def __getitem__(self, index_query: str) -> "DotIndexer":
        indexes = index_query.split(".")
        result = self.obj
        for idx in indexes:
            result = result[idx]

        full_query = self.get_full_query(index_query)
        return DotIndexer(result, full_query)

    def get(
        self,
        index_query: str | None = None,
        expected_type: type[T] = type[Any],
    ) -> T:
        val: Any = (
            self.obj
            if index_query is None or len(index_query) == 0
            else self[index_query].obj
        )

        full_query = self.get_full_query(index_query)

        if not isinstance(val, expected_type):
            raise ValueError(
                f"expected key '{full_query}' to be of type '{expected_type.__name__}' but got value '{val}' of type '{type(val).__name__}'"
            )

        return val


def parse_file_size(size_str: str) -> int:
    size_str = size_str.strip().casefold()

    byte_conversion_table = {
        "b": 1,
        "k": 1024,
        "kb": 1024,
        "m": 1024**2,
        "mb": 1024**2,
        "g": 1024**3,
        "gb": 1024**3,
    }

    for unit in sorted(byte_conversion_table.keys(), key=len, reverse=True):
        if size_str.endswith(unit):
            num = size_str[: -len(unit)]
            if num.isdigit():
                return int(num) * byte_conversion_table[unit]

    if size_str.isdigit():
        return int(size_str)

    raise ValueError(f"invalid size format: {size_str}")


class HSSConfig:
    def __init__(self, path=CONFIG_PATH) -> None:
        with open(path, "rb") as f:
            data = DotIndexer(tomllib.load(f))

        logging = data["logging"]
        files = logging["files"]

        self.logging = Logging(
            stderr_level=LoggingLevels[logging.get("stderr.level", expected_type=str)],
            files=LoggingFiles(
                level=LoggingLevels[files.get("level", str)],
                max_size=parse_file_size(files.get("max_size", str)),
                backup_count=files.get("backup_count", int),
                backup_count_tar=files.get("backup_count_tar", int),
            ),
        )


_config_singleton: HSSConfig | None = None


def get_config():
    global _config_singleton
    if _config_singleton is None:
        _config_singleton = HSSConfig()
    return _config_singleton
