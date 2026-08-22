from __future__ import annotations

import math
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from mediaflow.infrastructure.sqlite_backup import SQLiteBackupService
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION

MINIMUM_PYTHON = (3, 11)
MAXIMUM_PYTHON = (3, 14)
MAXIMUM_BACKUP_AGE_HOURS = 24 * 365


@dataclass(frozen=True)
class UpgradePreflightResult:
    status: str
    application_version: str
    python_version: str
    python_supported: bool
    supported_schema: int
    runtime_schema: int
    backup_schema: int
    migration_required: bool
    backup_age_hours: float
    maximum_backup_age_hours: float
    backup_size_bytes: int
    backup_sha256: str
    checked_at: datetime


class UpgradePreflightService:
    def __init__(
        self,
        runtime_database: str | Path,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        application_version: str | None = None,
        python_version: tuple[int, int, int] | None = None,
    ) -> None:
        self._runtime = Path(runtime_database).absolute()
        self._clock = clock
        self._application_version = application_version or _application_version()
        self._python_version = python_version or tuple(sys.version_info[:3])

    def check(
        self, backup: str | Path, *, maximum_backup_age_hours: float = 24
    ) -> UpgradePreflightResult:
        if (
            isinstance(maximum_backup_age_hours, bool)
            or not isinstance(maximum_backup_age_hours, (int, float))
            or not math.isfinite(maximum_backup_age_hours)
            or not 0 < maximum_backup_age_hours <= MAXIMUM_BACKUP_AGE_HOURS
        ):
            raise ValueError(
                f"maximum backup age must be greater than zero and at most "
                f"{MAXIMUM_BACKUP_AGE_HOURS} hours"
            )
        backup_path = Path(backup).absolute()
        if self._runtime.resolve(strict=False) == backup_path.resolve(strict=False):
            raise ValueError("runtime database and backup must be different files")
        python_supported = MINIMUM_PYTHON <= self._python_version[:2] < MAXIMUM_PYTHON
        if not python_supported:
            raise ValueError(f"Python {_python_text(self._python_version)} is not supported")
        verifier = SQLiteBackupService(self._runtime)
        runtime = verifier.verify(self._runtime)
        backup_result = verifier.verify(backup_path)
        if runtime.schema_version != backup_result.schema_version:
            raise ValueError(
                "runtime and backup schema versions differ: "
                f"{runtime.schema_version} != {backup_result.schema_version}"
            )
        checked_at = self._clock()
        if checked_at.tzinfo is None:
            raise ValueError("preflight clock must return a timezone-aware UTC time")
        checked_at = checked_at.astimezone(UTC)
        modified_at = datetime.fromtimestamp(backup_path.stat().st_mtime, UTC)
        age_hours = (checked_at - modified_at).total_seconds() / 3600
        if age_hours < 0:
            raise ValueError("backup modification time is in the future")
        if age_hours > maximum_backup_age_hours:
            raise ValueError(
                f"backup is stale: {age_hours:.2f} hours exceeds {maximum_backup_age_hours:g} hours"
            )
        migration_required = runtime.schema_version < SCHEMA_VERSION
        return UpgradePreflightResult(
            "migration_required" if migration_required else "ready",
            self._application_version,
            _python_text(self._python_version),
            python_supported,
            SCHEMA_VERSION,
            runtime.schema_version,
            backup_result.schema_version,
            migration_required,
            age_hours,
            float(maximum_backup_age_hours),
            backup_result.size_bytes,
            backup_result.sha256,
            checked_at,
        )


def _application_version() -> str:
    try:
        return version("mediaflow")
    except PackageNotFoundError:
        return "development"


def _python_text(value: tuple[int, int, int]) -> str:
    return ".".join(str(item) for item in value)
