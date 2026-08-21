from enum import IntEnum
from typing import Protocol


class LogLevel(IntEnum):
    TRACE = 5
    DEBUG = 10
    INFO = 20
    WARN = 30
    ERROR = 40


class Logger(Protocol):
    def log(self, level: LogLevel, message: str, **context: object) -> None: ...
