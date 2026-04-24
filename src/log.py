import logging
import logging.handlers
import os
import sys
import tarfile
from typing import TextIO, override

from src.config import get_config
from src.definitions import ROOT_DIR

LOG_DIR = ROOT_DIR / "logs"

CONFIG = get_config()


# https://stackoverflow.com/a/56944256
class LogFormatter(logging.Formatter):
    def __init__(self, use_color: bool = False):
        super().__init__()

        white = "\033[0;37;49m"
        green = "\033[0;32;49m"
        bold_red = "\033[1;31;1m"
        bold_yellow = "\033[1;33;20m"
        bold_blue = "\033[1;34;49m"
        bold_magenta = "\033[1;35;49m"
        bold_grey = "\033[1;38;20m"
        reset = "\033[0m"

        format_ = f"{green}%(asctime)s{reset} - %(name)s{reset} - {{level_color}}%(levelname)s{reset} - %(message)s ({white}%(filename)s:%(lineno)d{reset})"
        format_no_color = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

        self.OS = "nt" if not use_color else os.name

        self.FORMATS = {
            logging.DEBUG: format_.format(level_color=bold_grey),
            logging.INFO: format_.format(level_color=bold_blue),
            logging.WARNING: format_.format(level_color=bold_yellow),
            logging.ERROR: format_.format(level_color=bold_red),
            logging.CRITICAL: format_.format(level_color=bold_magenta),
            "NORMAL": format_no_color,
        }

    def format(self, record):
        log_fmt = (
            self.FORMATS.get(record.levelno)
            if self.OS != "nt"
            else self.FORMATS.get("NORMAL")
        )
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class LogGZipRotatingFileHandler(logging.handlers.RotatingFileHandler):
    def __init__(
        self,
        filename: str | os.PathLike[str],
        mode: str = "a",
        maxBytes: int = 0,
        tarBackupCount: int = 0,
        backupCount: int = 0,
        encoding: str | None = None,
        delay: bool = False,
        errors: str | None = None,
    ) -> None:
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay, errors)
        self.tarBackupCount = tarBackupCount

    def make_tar_archive(self):
        if self.backupCount <= 0 or self.tarBackupCount <= 0:
            return

        for i in range(self.tarBackupCount - 1, 0, -1):
            sfn = self.rotation_filename("%s.%d.tar.gz" % (self.baseFilename, i))
            dfn = self.rotation_filename("%s.%d.tar.gz" % (self.baseFilename, i + 1))
            if os.path.exists(sfn):
                if os.path.exists(dfn):
                    os.remove(dfn)
                os.rename(sfn, dfn)
        dfn = self.rotation_filename(self.baseFilename + ".1.tar.gz")
        if os.path.exists(dfn):
            os.remove(dfn)

        with tarfile.open(dfn, "w|gz") as tar:
            for i in range(1, self.backupCount + 1):
                name = f"{self.baseFilename}.{i}"
                tar.add(name)
                # NOTE: this is ok, tar.add reads the file
                os.remove(name)

    @override
    def doRollover(self) -> None:
        if self.stream:
            self.stream.close()
            self.stream = None

        final = self.rotation_filename(self.baseFilename + f".{self.backupCount}")
        if os.path.exists(final):
            self.make_tar_archive()

        elif self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = self.rotation_filename("%s.%d" % (self.baseFilename, i))
                dfn = self.rotation_filename("%s.%d" % (self.baseFilename, i + 1))
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    os.rename(sfn, dfn)
            dfn = self.rotation_filename(self.baseFilename + ".1")
            if os.path.exists(dfn):
                os.remove(dfn)
            self.rotate(self.baseFilename, dfn)

        if not self.delay:
            self.stream = self._open()


_color_formatter_singleton: LogFormatter | None = None
_non_color_formatter_singleton: LogFormatter | None = None
_stderr_handler_singleton: logging.StreamHandler[TextIO] | None = None


def get_logger(name: str) -> logging.Logger:
    global _color_formatter_singleton
    global _non_color_formatter_singleton
    global _stderr_handler_singleton

    log = CONFIG.logging

    if _non_color_formatter_singleton is None or _stderr_handler_singleton is None:
        _color_formatter_singleton = LogFormatter(True)
        _non_color_formatter_singleton = LogFormatter(False)

        _stderr_handler_singleton = logging.StreamHandler(sys.stderr)
        _stderr_handler_singleton.setFormatter(_color_formatter_singleton)
        _stderr_handler_singleton.setLevel(log.stderr_level)

    if name in logging.Logger.manager.loggerDict:
        return logging.getLogger(name)

    logger = logging.getLogger(name)
    file_handler = LogGZipRotatingFileHandler(
        LOG_DIR / f"{name}.log",
        maxBytes=log.files.max_size,
        backupCount=log.files.backup_count,
        tarBackupCount=log.files.backup_count_tar,
    )

    file_handler.setFormatter(_non_color_formatter_singleton)

    logger.addHandler(_stderr_handler_singleton)
    logger.addHandler(file_handler)

    return logger
