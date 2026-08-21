from __future__ import annotations

import json
import threading
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from mediaflow.domain.history import OperationHistoryRecord


class JsonLinesOperationHistoryRepository:
    """Append-only local history adapter; application code depends only on its domain port."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()

    def append(self, record: OperationHistoryRecord) -> None:
        payload = asdict(record)
        payload["timestamp"] = record.timestamp.isoformat()
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def list(self, *, limit: int | None = None) -> tuple[OperationHistoryRecord, ...]:
        if not self._path.exists():
            return ()
        with self._lock, self._path.open(encoding="utf-8") as handle:
            values = tuple(_record(json.loads(line)) for line in handle if line.strip())
        return values[-limit:] if limit is not None else values


def _record(value: dict) -> OperationHistoryRecord:
    return OperationHistoryRecord(
        value["record_id"],
        datetime.fromisoformat(value["timestamp"]),
        value["source"],
        value["destination"],
        value["operation"],
        value["status"],
        value.get("provider_id"),
        value.get("title"),
        value.get("error"),
    )
