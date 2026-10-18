#!/usr/bin/env python3
"""Real-Python browser harness for direct Files journeys on both library kinds.

The harness reuses the temporary checked Active/SQLite setup from
``operations_inventory_harness`` and adds throwaway direct-maintenance fixtures. Product
requests go through MediaFlowApi; the test-only Worker route starts the
production FilesTransferWorker with the pinned runtime factory. No production
configuration, media, Storage or credentials are involved.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import threading
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from wsgiref.simple_server import make_server

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mediaflow.domain.storage import StoragePage  # noqa: E402
from mediaflow.domain.task_persistence import (  # noqa: E402
    FILES_DELETE_TASK_COMMAND,
    FILES_TRANSFER_TASK_COMMAND,
    direct_command_task_command,
)
from mediaflow.final_cli import _files_transfer_worker_context  # noqa: E402
from mediaflow.infrastructure.local_storage import LocalStorage  # noqa: E402
from mediaflow.interfaces.v2_ui import asset_root  # noqa: E402
from scripts import operations_inventory_harness as inventory  # noqa: E402

GATED_WORKER_STATE: dict[str, object] | None = None


class QuietHandler(inventory.QuietHandler):
    pass


class ThreadingWSGIServer(inventory.ThreadingWSGIServer):
    pass


class FingerprintlessStorage:
    """Local test Storage that exposes the metadata-only provider contract."""

    def __init__(self, storage_id: str, root: Path) -> None:
        self._delegate = LocalStorage(storage_id, root)

    def __getattr__(self, name: str):
        return getattr(self._delegate, name)

    @staticmethod
    def _without_fingerprint(entry):
        return replace(entry, fingerprint=None)

    def list(self, path: str):
        return tuple(self._without_fingerprint(entry) for entry in self._delegate.list(path))

    def list_page(self, path: str, *, limit: int, cursor: str | None = None):
        page = self._delegate.list_page(path, limit=limit, cursor=cursor)
        return StoragePage(
            entries=tuple(self._without_fingerprint(entry) for entry in page.entries),
            next_cursor=page.next_cursor,
        )

    def stat(self, path: str):
        return self._without_fingerprint(self._delegate.stat(path))


def _json_response(start_response, status: str, document: dict[str, object]):
    body = json.dumps(document).encode("utf-8")
    start_response(
        status,
        [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
        ],
    )
    return [body]


def _start_gated_files_worker(start_response):
    global GATED_WORKER_STATE
    state = inventory.STATE
    if state is None:
        return _json_response(start_response, "503 Service Unavailable", {"started": False})
    if GATED_WORKER_STATE is not None:
        thread = GATED_WORKER_STATE.get("thread")
        if isinstance(thread, threading.Thread) and thread.is_alive():
            return _json_response(start_response, "409 Conflict", {"started": False})

    entered = threading.Event()
    release = threading.Event()
    worker_state: dict[str, object] = {"entered": entered, "release": release}
    original_write = LocalStorage.write

    def gated_write(storage, path, data, *, overwrite: bool = False):
        if (
            Path(path).name
            in {
                "Browser-Move-Resource-Second.txt",
                "Browser-Move-Media-Second.txt",
            }
            and not entered.is_set()
        ):
            entered.set()
            if not release.wait(timeout=30):
                raise TimeoutError("test Worker write gate was not released")
        return original_write(storage, path, data, overwrite=overwrite)

    def run_worker() -> None:
        try:
            with patch.object(LocalStorage, "write", gated_write):
                with _files_transfer_worker_context(
                    state.managed.runtime,
                    str(state.managed.config_path),
                    state.repository,
                ) as worker:
                    worker_state["result"] = worker.run_next()
        except Exception as error:  # pragma: no cover - surfaced to the browser response
            worker_state["error"] = type(error).__name__
        finally:
            worker_state["done"] = True

    thread = threading.Thread(target=run_worker, name="direct-files-gated-worker", daemon=True)
    worker_state["thread"] = thread
    GATED_WORKER_STATE = worker_state
    thread.start()
    if not entered.wait(timeout=10):
        release.set()
        thread.join(timeout=30)
        GATED_WORKER_STATE = None
        return _json_response(
            start_response,
            "503 Service Unavailable",
            {"started": False, "reason": worker_state.get("error", "write_not_reached")},
        )
    return _json_response(start_response, "200 OK", {"started": True})


def _release_gated_files_worker(start_response):
    global GATED_WORKER_STATE
    worker_state = GATED_WORKER_STATE
    if worker_state is None:
        return _json_response(start_response, "409 Conflict", {"released": False})
    release = worker_state.get("release")
    thread = worker_state.get("thread")
    if not isinstance(release, threading.Event) or not isinstance(thread, threading.Thread):
        GATED_WORKER_STATE = None
        return _json_response(start_response, "500 Internal Server Error", {"released": False})
    release.set()
    thread.join(timeout=30)
    if thread.is_alive():
        return _json_response(start_response, "504 Gateway Timeout", {"released": True})
    if "error" in worker_state:
        result = {"released": True, "error": worker_state["error"]}
    else:
        transfer = worker_state.get("result")
        status = getattr(getattr(transfer, "status", None), "value", None)
        result = {"released": True, "ran": transfer is not None, "status": status}
    GATED_WORKER_STATE = None
    return _json_response(start_response, "200 OK", result)


def application(environ, start_response):
    path = str(environ.get("PATH_INFO", ""))
    if path == "/__harness__/register-files-worker" and environ.get("REQUEST_METHOD") == "POST":
        state = inventory.STATE
        if state is None:
            return _json_response(start_response, "503 Service Unavailable", {"registered": False})
        active = state.managed.active
        commands = tuple(
            direct_command_task_command(command, media_library=media_library)
            for media_library in (False, True)
            for command in (FILES_TRANSFER_TASK_COMMAND, FILES_DELETE_TASK_COMMAND)
        )
        state.api._worker_service.register_worker(
            "harness-files-worker",
            "Harness Files Worker",
            3600.0,
            commands,
            configuration_snapshot_id=active.revision_id,
            configuration_snapshot_digest=active.digest,
            runtime_schema_version=inventory.SCHEMA_VERSION,
        )
        return _json_response(start_response, "200 OK", {"registered": True})
    if path == "/__harness__/start-gated-files-worker" and environ.get("REQUEST_METHOD") == "POST":
        return _start_gated_files_worker(start_response)
    if (
        path == "/__harness__/release-gated-files-worker"
        and environ.get("REQUEST_METHOD") == "POST"
    ):
        return _release_gated_files_worker(start_response)
    if path == "/__harness__/run-files-worker" and environ.get("REQUEST_METHOD") == "POST":
        state = inventory.STATE
        if state is None:
            return _json_response(start_response, "503 Service Unavailable", {"ran": False})
        with _files_transfer_worker_context(
            state.managed.runtime,
            str(state.managed.config_path),
            state.repository,
        ) as worker:
            result = worker.run_next()
        status = getattr(getattr(result, "status", None), "value", None)
        return _json_response(
            start_response, "200 OK", {"ran": result is not None, "status": status}
        )
    if path == "/__harness__/files-state" and environ.get("REQUEST_METHOD") == "GET":
        state = inventory.STATE
        if state is None:
            return _json_response(start_response, "503 Service Unavailable", {"ready": False})
        root = state.managed.root
        source = root / "source" / "Browser-Delete-Resource.txt"
        media = root / "destination" / "Movies" / "Browser-Delete-Media.txt"
        resource_http_delete = root / "source" / "Browser-Delete-HTTP-Resource.txt"
        resource_http_unknown_delete = root / "source" / "Browser-Delete-HTTP-Unknown-Resource.txt"
        media_http_delete = root / "destination" / "Movies" / "Browser-Delete-HTTP-Media.txt"
        media_http_unknown_delete = (
            root / "destination" / "Movies" / "Browser-Delete-HTTP-Unknown-Media.txt"
        )
        resource_move = root / "source" / "Browser-Move-Resource.txt"
        resource_move_second = root / "source" / "Browser-Move-Resource-Second.txt"
        media_move = root / "destination" / "Movies" / "Browser-Move-Media.txt"
        media_move_second = root / "destination" / "Movies" / "Browser-Move-Media-Second.txt"
        adapters = state.api._storage_adapters
        resource_fingerprint_available = (
            adapters["source-storage"].stat("Browser-Move-Resource.txt").fingerprint is not None
            if resource_move.exists()
            else None
        )
        resource_second_fingerprint_available = (
            adapters["source-storage"].stat("Browser-Move-Resource-Second.txt").fingerprint
            is not None
            if resource_move_second.exists()
            else None
        )
        media_fingerprint_available = (
            adapters["media-target"].stat("Movies/Browser-Move-Media.txt").fingerprint is not None
            if media_move.exists()
            else None
        )
        media_second_fingerprint_available = (
            adapters["media-target"].stat("Movies/Browser-Move-Media-Second.txt").fingerprint
            is not None
            if media_move_second.exists()
            else None
        )
        return _json_response(
            start_response,
            "200 OK",
            {
                "ready": True,
                "resourceExists": source.exists(),
                "mediaExists": media.exists(),
                "resourceHttpDeleteExists": resource_http_delete.exists(),
                "resourceHttpUnknownDeleteExists": resource_http_unknown_delete.exists(),
                "mediaHttpDeleteExists": media_http_delete.exists(),
                "mediaHttpUnknownDeleteExists": media_http_unknown_delete.exists(),
                "resourceMoveSource": (root / "source" / "Browser-Move-Resource.txt").exists(),
                "resourceMoveTarget": (root / "destination" / "Browser-Move-Resource.txt").exists(),
                "resourceMoveSecondSource": resource_move_second.exists(),
                "resourceMoveSecondTarget": (
                    root / "destination" / "Browser-Move-Resource-Second.txt"
                ).exists(),
                "mediaMoveSource": (
                    root / "destination" / "Movies" / "Browser-Move-Media.txt"
                ).exists(),
                "mediaMoveTarget": (
                    root / "source" / "Archive" / "Browser-Move-Media.txt"
                ).exists(),
                "mediaMoveSecondSource": media_move_second.exists(),
                "mediaMoveSecondTarget": (
                    root / "source" / "Archive" / "Browser-Move-Media-Second.txt"
                ).exists(),
                "resourceMoveFingerprintAvailable": resource_fingerprint_available,
                "resourceMoveSecondFingerprintAvailable": resource_second_fingerprint_available,
                "mediaMoveFingerprintAvailable": media_fingerprint_available,
                "mediaMoveSecondFingerprintAvailable": media_second_fingerprint_available,
                "resourceRecursiveExists": (
                    root / "source" / "Browser-Recursive-Resource-Directory"
                ).exists(),
                "mediaRecursiveExists": (
                    root / "destination" / "Movies" / "Browser-Recursive-Media-Directory"
                ).exists(),
                "resourceBatchOneExists": (
                    root / "source" / "Browser-Batch-Resource-One.txt"
                ).exists(),
                "resourceBatchTwoExists": (
                    root / "source" / "Browser-Batch-Resource-Two.txt"
                ).exists(),
                "mediaBatchOneExists": (
                    root / "destination" / "Movies" / "Browser-Batch-Media-One.txt"
                ).exists(),
                "mediaBatchTwoExists": (
                    root / "destination" / "Movies" / "Browser-Batch-Media-Two.txt"
                ).exists(),
            },
        )
    return inventory.application(environ, start_response)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4185)
    args = parser.parse_args(argv)
    if not (asset_root() / "index.html").is_file():
        print(
            "harness: built V2 artifact is missing; run `npm --prefix web run build` first",
            file=sys.stderr,
        )
        return 2

    temporary_root = Path(tempfile.mkdtemp(prefix="mediaflow-direct-files-browser-"))
    database = temporary_root / "direct-files.sqlite3"
    managed_root = temporary_root / "managed"
    (managed_root / "source").mkdir(parents=True)
    (managed_root / "destination").mkdir(parents=True)
    storage_adapters = {
        "source-storage": FingerprintlessStorage("source-storage", managed_root / "source"),
        "media-target": FingerprintlessStorage("media-target", managed_root / "destination"),
    }
    repository, managed, api = inventory.build_managed_fixture(
        database,
        managed_root,
        include_cross_storage_destinations=True,
        storage_adapters=storage_adapters,
    )
    (managed_root / "source" / "Browser-Delete-Resource.txt").write_text(
        "resource browser fixture", encoding="utf-8"
    )
    (managed_root / "destination" / "Movies" / "Browser-Delete-Media.txt").write_text(
        "media browser fixture", encoding="utf-8"
    )
    (managed_root / "source" / "Browser-Delete-HTTP-Resource.txt").write_text(
        "resource insecure HTTP delete fixture", encoding="utf-8"
    )
    (managed_root / "source" / "Browser-Delete-HTTP-Unknown-Resource.txt").write_text(
        "resource uncertain HTTP delete fixture", encoding="utf-8"
    )
    (managed_root / "destination" / "Movies" / "Browser-Delete-HTTP-Media.txt").write_text(
        "media insecure HTTP delete fixture", encoding="utf-8"
    )
    (managed_root / "destination" / "Movies" / "Browser-Delete-HTTP-Unknown-Media.txt").write_text(
        "media uncertain HTTP delete fixture", encoding="utf-8"
    )
    for kind in ("Resource", "Media"):
        library_root = (
            managed_root / "source"
            if kind == "Resource"
            else managed_root / "destination" / "Movies"
        )
        for suffix in ("One", "Two"):
            (library_root / f"Browser-Batch-{kind}-{suffix}.txt").write_text(
                f"{kind.lower()} batch fixture {suffix}", encoding="utf-8"
            )
        recursive = library_root / f"Browser-Recursive-{kind}-Directory"
        recursive.mkdir()
        (recursive / "child.txt").write_text("recursive child", encoding="utf-8")
    (managed_root / "source" / "Browser-Move-Resource.txt").write_text(
        "resource cross-storage move fixture", encoding="utf-8"
    )
    (managed_root / "source" / "Browser-Move-Resource-Second.txt").write_text(
        "resource second cross-storage move fixture", encoding="utf-8"
    )
    (managed_root / "destination" / "Movies" / "Browser-Move-Media.txt").write_text(
        "media cross-storage move fixture", encoding="utf-8"
    )
    (managed_root / "destination" / "Movies" / "Browser-Move-Media-Second.txt").write_text(
        "media second cross-storage move fixture", encoding="utf-8"
    )
    (managed_root / "source" / "Browser-Rename-Resource.txt").write_text(
        "resource rename fixture", encoding="utf-8"
    )
    resource_directory = managed_root / "source" / "Browser-Rename-Resource-Directory"
    resource_directory.mkdir()
    (resource_directory / "child.txt").write_text("child", encoding="utf-8")
    media_root = managed_root / "destination" / "Movies"
    (media_root / "Browser-Rename-Media.txt").write_text("media rename fixture", encoding="utf-8")
    media_directory = media_root / "Browser-Rename-Media-Directory"
    media_directory.mkdir()
    (media_directory / "child.txt").write_text("child", encoding="utf-8")
    inventory.STATE = inventory.AppState(
        database,
        repository=repository,
        api=api,
        managed=managed,
    )
    with make_server(
        args.host,
        args.port,
        application,
        server_class=ThreadingWSGIServer,
        handler_class=QuietHandler,
    ) as server:
        print(f"direct Files browser harness: http://{args.host}:{args.port}/ui-v2/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            repository.close()
            managed.configuration_repository.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
