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
import contextlib
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

#: The one fixture file the mixed-batch journey asks the *real* LocalStorage
#: adapter to refuse, so durable outcome truth comes from the production Worker
#: rather than from a fabricated Task row.  ``None`` means no fault is armed.
REFUSED_DELETE_NAME: str | None = None

#: The one fixture file refused inside a large-directory Delete.  It is chosen
#: from the end of the directory listing so its durable result settles beyond
#: the first local item page — exactly the B-reproduced case where a fixed
#: prefix hid the failed child.
REFUSED_BULK_DELETE_NAME: str | None = None

#: Set by ``/__harness__/disable-resource-library``: the exact ResourceLibrary
#: this run disabled through the managed configuration service, so the browser
#: journey can prove a historical origin stays readable after the live list lost
#: it.  ``None`` means nothing was disabled by the harness.
DISABLED_ORIGIN: dict[str, object] | None = None


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


def _refresh_managed_active(state) -> None:
    """Re-read the harness context's Active revision after a real publication.

    ``ManagedHarnessContext`` is a frozen value, so the whole context is
    replaced with the same paths/service and the newly published Active.  This
    mirrors what a real process does on its next configuration refresh.
    """

    active = state.managed.configuration_service.active()
    if active is None:
        return
    state.managed = replace(state.managed, active=active)


def _null_context():
    """A no-op context manager for a journey with no armed fault."""

    return contextlib.nullcontext()


def _request_document(environ) -> dict[str, object]:
    """Read one bounded test-only JSON request body."""

    length = str(environ.get("CONTENT_LENGTH", "")).strip()
    if not length:
        return {}
    try:
        payload = int(length)
    except ValueError:
        return {}
    if payload <= 0 or payload > 65536:
        return {}
    raw = environ["wsgi.input"].read(payload)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _refused_delete_matcher():
    """The one real-LocalStorage Delete refusal armed for this run, if any."""

    if REFUSED_DELETE_NAME is not None:
        wanted = REFUSED_DELETE_NAME

        def refuse_named(_storage, target, *args, **kwargs):
            if Path(str(target)).name == wanted:
                raise RuntimeError("isolated provider refusal")
            return None

        return refuse_named
    if REFUSED_BULK_DELETE_NAME is not None:
        wanted = REFUSED_BULK_DELETE_NAME

        def refuse_bulk(_storage, target, *args, **kwargs):
            if Path(str(target)).name == wanted:
                raise RuntimeError("isolated provider refusal")
            return None

        return refuse_bulk
    return None


def _start_gated_files_worker(start_response, *, mode: str = "write"):
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
    #: How many real per-entry mutations of the paused folder must happen first.
    gate_after = 3
    folder_writes = 0
    folder = "Browser-Paused-Move-Resource-Directory"

    def gated_write(storage, path, data, *, overwrite: bool = False):
        nonlocal folder_writes
        name = Path(path).name
        if mode == "move":
            # A cross-Storage folder Move writes each child into the destination
            # provider; gate the third one so the transfer pauses with three
            # children already durably moved.
            if folder in str(path) and not entered.is_set():
                folder_writes += 1
                if folder_writes == gate_after:
                    entered.set()
                    if not release.wait(timeout=30):
                        raise TimeoutError("test Worker move gate was not released")
        elif (
            name in {"Browser-Move-Resource-Second.txt", "Browser-Move-Media-Second.txt"}
            and not entered.is_set()
        ):
            entered.set()
            if not release.wait(timeout=30):
                raise TimeoutError("test Worker write gate was not released")
        return original_write(storage, path, data, overwrite=overwrite)

    gate = patch.object(LocalStorage, "write", gated_write)

    def run_worker() -> None:
        try:
            with gate:
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
    global REFUSED_DELETE_NAME, REFUSED_BULK_DELETE_NAME, DISABLED_ORIGIN
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
        document = _request_document(environ)
        mode = document.get("mode")
        return _start_gated_files_worker(start_response, mode=mode if mode == "move" else "write")
    if (
        path == "/__harness__/release-gated-files-worker"
        and environ.get("REQUEST_METHOD") == "POST"
    ):
        return _release_gated_files_worker(start_response)
    if path == "/__harness__/run-files-worker" and environ.get("REQUEST_METHOD") == "POST":
        state = inventory.STATE
        if state is None:
            return _json_response(start_response, "503 Service Unavailable", {"ran": False})
        fault = REFUSED_DELETE_NAME or REFUSED_BULK_DELETE_NAME
        original_delete = LocalStorage.delete
        matcher = _refused_delete_matcher()

        def refuse_named(storage, target, *args, **kwargs):
            # A real provider refusal on exactly one selected fixture: the
            # durable item outcome, its effect certainty and the safe next
            # action are produced by the production Worker path.
            if matcher is not None:
                matcher(storage, target)
            return original_delete(storage, target, *args, **kwargs)

        with patch.object(LocalStorage, "delete", refuse_named) if fault else _null_context():
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
    if path == "/__harness__/arm-files-delete-fault" and environ.get("REQUEST_METHOD") == "POST":
        document = _request_document(environ)
        name = document.get("name")
        bulk = document.get("bulkName")
        REFUSED_DELETE_NAME = name if isinstance(name, str) and name else None
        REFUSED_BULK_DELETE_NAME = bulk if isinstance(bulk, str) and bulk else None
        return _json_response(
            start_response,
            "200 OK",
            {
                "armed": REFUSED_DELETE_NAME is not None,
                "bulkArmed": REFUSED_BULK_DELETE_NAME is not None,
            },
        )
    if path == "/__harness__/add-unreferenced-origin" and environ.get("REQUEST_METHOD") == "POST":
        # Admit a real unreferenced ResourceLibrary through the same supported
        # Add command the operator's drawer uses.  It references nothing (no
        # Automation definition, no recipe), which is exactly what makes it
        # disableable later — that is the B-reproduced historical origin.
        state = inventory.STATE
        if state is None:
            return _json_response(start_response, "503 Service Unavailable", {"added": False})
        document = _request_document(environ)
        library_id = document.get("libraryId")
        if not isinstance(library_id, str) or not library_id:
            return _json_response(
                start_response, "400 Bad Request", {"added": False, "reason": "libraryId"}
            )
        objects = state.api._configuration_objects
        if objects is None:
            return _json_response(start_response, "503 Service Unavailable", {"added": False})
        storage_path = str(document.get("storagePath") or library_id)
        # The configured root must exist on the isolated fixture Storage, exactly
        # as an operator's chosen directory would.
        (state.managed.root / "source" / storage_path).mkdir(parents=True, exist_ok=True)
        try:
            objects.save_resource_library(
                {
                    "id": library_id,
                    "name": str(document.get("name") or library_id),
                    "storageId": "source-storage",
                    "storagePath": storage_path,
                    "enabled": True,
                },
                actor="harness-unreferenced-origin",
            )
        except Exception as error:
            return _json_response(
                start_response,
                "409 Conflict",
                {"added": False, "reason": type(error).__name__},
            )
        _refresh_managed_active(state)
        state.restart()
        return _json_response(start_response, "200 OK", {"added": True, "libraryId": library_id})
    if path == "/__harness__/disable-resource-library" and environ.get("REQUEST_METHOD") == "POST":
        state = inventory.STATE
        if state is None:
            return _json_response(start_response, "503 Service Unavailable", {"disabled": False})
        document = _request_document(environ)
        library_id = document.get("libraryId")
        if not isinstance(library_id, str) or not library_id:
            return _json_response(
                start_response, "400 Bad Request", {"disabled": False, "reason": "libraryId"}
            )
        service = state.managed.configuration_service
        _refresh_managed_active(state)
        current = state.managed.active
        successor = json.loads(json.dumps(current.document))
        found = False
        for library in successor.get("resourceLibraries", []):
            if isinstance(library, dict) and library.get("id") == library_id:
                library["enabled"] = False
                found = True
        if not found:
            return _json_response(
                start_response, "404 Not Found", {"disabled": False, "reason": "not_found"}
            )
        # Publish a real successor through the managed lifecycle (draft → edit →
        # validate → activate), the same path the operator's configuration Save
        # uses.  Nothing is seeded directly into Active.
        draft = service.create_successor_draft(
            actor="harness-disabled-origin",
            expected_active_revision_id=current.revision_id,
            expected_active_version=current.revision_sequence or current.version,
            expected_active_digest=current.digest,
            verified_active=current,
        )
        edited = service.edit_draft(
            draft.revision_id,
            successor,
            expected_version=draft.version,
            actor="harness-disabled-origin",
            audit_context={
                "kind": "resourceLibrary",
                "objectId": library_id,
                "action": "disable",
                "before": None,
                "after": None,
            },
        )
        validated = service.validate(edited.revision_id, actor="harness-disabled-origin")
        if getattr(validated.status, "value", "") != "validated":
            return _json_response(
                start_response,
                "409 Conflict",
                {
                    "disabled": False,
                    "reason": "validation_failed",
                    "errors": list(validated.validation_errors),
                },
            )
        activated = service.activate(
            validated.revision_id,
            expected_version=validated.version,
            actor="harness-disabled-origin",
        )
        _refresh_managed_active(state)
        DISABLED_ORIGIN = {"libraryId": library_id, "revisionId": activated.revision_id}
        state.restart()
        return _json_response(start_response, "200 OK", {"disabled": True, **DISABLED_ORIGIN})
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
                "resourceStatusOneExists": (
                    root / "source" / "Browser-StatusOne-Resource.txt"
                ).exists(),
                "resourceStatusTwoExists": (
                    root / "source" / "Browser-StatusTwo-Resource.txt"
                ).exists(),
                "mediaStatusOneExists": (
                    root / "destination" / "Movies" / "Browser-StatusOne-Media.txt"
                ).exists(),
                "mediaStatusTwoExists": (
                    root / "destination" / "Movies" / "Browser-StatusTwo-Media.txt"
                ).exists(),
                "resourceMixedKeepExists": (
                    root / "source" / "Browser-Mixed-Keep-Resource.txt"
                ).exists(),
                "resourceMixedRemoveExists": (
                    root / "source" / "Browser-Mixed-Remove-Resource.txt"
                ).exists(),
                "mediaMixedKeepExists": (
                    root / "destination" / "Movies" / "Browser-Mixed-Keep-Media.txt"
                ).exists(),
                "mediaMixedRemoveExists": (
                    root / "destination" / "Movies" / "Browser-Mixed-Remove-Media.txt"
                ).exists(),
                "resourceBulkDirectoryExists": (
                    root / "source" / "Browser-Bulk-Resource-Directory"
                ).is_dir(),
                "resourceBulkSurvivingFiles": sorted(
                    entry.name
                    for entry in (root / "source" / "Browser-Bulk-Resource-Directory").glob("*.txt")
                )
                if (root / "source" / "Browser-Bulk-Resource-Directory").is_dir()
                else [],
                "mediaBulkDirectoryExists": (
                    root / "destination" / "Movies" / "Browser-Bulk-Media-Directory"
                ).is_dir(),
                "mediaBulkSurvivingFiles": sorted(
                    entry.name
                    for entry in (
                        root / "destination" / "Movies" / "Browser-Bulk-Media-Directory"
                    ).glob("*.txt")
                )
                if (root / "destination" / "Movies" / "Browser-Bulk-Media-Directory").is_dir()
                else [],
                "resourcePausedMoveMoved": sorted(
                    entry.name
                    for entry in (
                        root / "destination" / "Browser-Paused-Move-Resource-Directory"
                    ).glob("*.txt")
                ),
                "resourcePausedMoveRemaining": sorted(
                    entry.name
                    for entry in (root / "source" / "Browser-Paused-Move-Resource-Directory").glob(
                        "*.txt"
                    )
                )
                if (root / "source" / "Browser-Paused-Move-Resource-Directory").is_dir()
                else [],
                "disabledOrigin": DISABLED_ORIGIN,
                "refusedDeleteName": REFUSED_DELETE_NAME,
                "refusedBulkDeleteName": REFUSED_BULK_DELETE_NAME,
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
        # Dedicated fixtures for the current-page operation-status journey, so
        # its own batch Delete never consumes another journey's source files.
        for suffix in ("StatusOne", "StatusTwo"):
            (library_root / f"Browser-{suffix}-{kind}.txt").write_text(
                f"{kind.lower()} status fixture {suffix}", encoding="utf-8"
            )
        # The mixed/uncertain batch journey's own two sources: the operator
        # selects both and the harness refuses exactly one real Storage Delete.
        for suffix in ("Keep", "Remove"):
            (library_root / f"Browser-Mixed-{suffix}-{kind}.txt").write_text(
                f"{kind.lower()} mixed batch fixture {suffix}", encoding="utf-8"
            )
        # A 120-file directory for the "every admitted item stays reachable"
        # journey: one selected directory legitimately admits 121 items, and the
        # refused child is chosen from the end of the listing so its result
        # settles beyond the first local item page.
        bulk = library_root / f"Browser-Bulk-{kind}-Directory"
        bulk.mkdir()
        for index in range(120):
            (bulk / f"bulk-{index:03d}.txt").write_text(
                f"{kind.lower()} bulk fixture {index}", encoding="utf-8"
            )
    # A folder whose Move is paused at the shared cooperative boundary after
    # some children already moved: the local status read must show the moved
    # children, not one opaque directory with "no change".
    paused_folder = managed_root / "source" / "Browser-Paused-Move-Resource-Directory"
    paused_folder.mkdir()
    for index in range(6):
        (paused_folder / f"paused-{index:02d}.txt").write_text(
            f"resource paused move fixture {index}", encoding="utf-8"
        )
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
        storage_adapters=storage_adapters,
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
