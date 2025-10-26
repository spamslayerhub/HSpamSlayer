import sys
from enum import IntEnum
from typing import Any, NamedTuple, Protocol

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
    stderr: LoggingLevels
    files: LoggingFiles


class IndexableContainer(Protocol):
    def __getitem__(self, key: str, /) -> Any: ...


class DotIndexer:
    def __init__(self, obj: IndexableContainer) -> None:
        self.obj = obj

    def __getitem__(self, index_query: str) -> Any:
        indexes = index_query.split(".")
        result = self.obj
        for idx in indexes:
            result = result[idx]
        return result

    def get_inexable(self, index_query: str) -> IndexableContainer:
        return DotIndexer(self[index_query])


def parse_file_size(size_str: str | int) -> int:
    if isinstance(size_str, int):
        return size_str

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

        logging = data.get_inexable("logging")
        files = logging["files"]
        self.logging = Logging(
            stderr=LoggingLevels[logging["stderr.level"]],
            files=LoggingFiles(
                level=files["level"],
                max_size=parse_file_size(files["max_size"]),
                backup_count=files["backup_count"],
                backup_count_tar=files["backup_count_tar"],
            ),
        )


_config_singleton: HSSConfig | None = None


def get_config():
    global _config_singleton
    if _config_singleton is None:
        _config_singleton = HSSConfig()
    return _config_singleton


def main() -> int:
    config = HSSConfig()
    print(config.logging.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
