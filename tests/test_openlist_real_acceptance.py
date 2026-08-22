from __future__ import annotations

import json
import os
import tempfile
import unittest
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from unittest.mock import Mock

from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.domain.organizer import (
    ExecutionStatus,
    OrganizePlan,
    PlanOperation,
    StorageLocation,
)
from mediaflow.domain.storage import StorageEntryType, StorageError, StorageErrorCode
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.openlist_storage import OpenListStorage, OpenListStorageConfig

CONFIRMATION = "DELETE_ONLY_GENERATED_MEDIAFLOW_ACCEPTANCE_DATA"


@dataclass(frozen=True)
class RealOpenListEnvironment:
    url: str
    token: str
    root: str
    report: Path


def resolve_real_openlist_environment(environ: dict[str, str]) -> RealOpenListEnvironment:
    names = (
        "TEST_OPENLIST_URL",
        "TEST_OPENLIST_TOKEN",
        "TEST_OPENLIST_ROOT",
        "TEST_OPENLIST_DESTRUCTIVE_CONFIRM",
        "TEST_OPENLIST_REPORT",
    )
    missing = [name for name in names if not environ.get(name)]
    if missing:
        raise ValueError("real OpenList acceptance prerequisites are incomplete")
    if environ["TEST_OPENLIST_DESTRUCTIVE_CONFIRM"] != CONFIRMATION:
        raise ValueError("real OpenList destructive confirmation is invalid")
    root = environ["TEST_OPENLIST_ROOT"]
    path = PurePosixPath(root)
    if (
        not path.is_absolute()
        or root == "/"
        or "\\" in root
        or "\x00" in root
        or any(part in {"", ".", ".."} for part in path.parts[1:])
        or not path.name.startswith("mediaflow-acceptance-")
    ):
        raise ValueError(
            "TEST_OPENLIST_ROOT must be a dedicated absolute mediaflow-acceptance-* path"
        )
    report = Path(environ["TEST_OPENLIST_REPORT"])
    if (
        not report.is_absolute()
        or report.suffix.lower() != ".json"
        or report.exists()
        or report.is_symlink()
        or not report.parent.is_dir()
    ):
        raise ValueError(
            "TEST_OPENLIST_REPORT must be a new absolute .json file in an existing directory"
        )
    return RealOpenListEnvironment(
        environ["TEST_OPENLIST_URL"], environ["TEST_OPENLIST_TOKEN"], root, report
    )


def assert_empty_acceptance_root(storage) -> None:
    root = storage.stat("")
    if root.entry_type is not StorageEntryType.DIRECTORY:
        raise AssertionError("approved OpenList acceptance root is not a directory")
    if storage.list(""):
        raise AssertionError("approved OpenList acceptance root is not empty")


def _package_version() -> str:
    try:
        return version("mediaflow")
    except PackageNotFoundError:
        return "source-tree"


def write_acceptance_report(destination: Path, record: dict[str, object]) -> None:
    forbidden = ("token", "authorization", "cookie", "password", "url")
    encoded = json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2)
    lowered = encoded.lower()
    if any(name in lowered for name in forbidden):
        raise ValueError("acceptance report contains a forbidden secret-bearing field")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".mediaflow-openlist-acceptance-", suffix=".json.tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(encoded)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError as error:
            raise ValueError("acceptance report destination already exists") from error
        temporary.unlink()
    finally:
        if temporary.exists():
            temporary.unlink()


def _real_environment_or_skip() -> RealOpenListEnvironment | None:
    relevant = {key: value for key, value in os.environ.items() if key.startswith("TEST_OPENLIST_")}
    if not relevant:
        return None
    return resolve_real_openlist_environment(dict(os.environ))


REAL_ENVIRONMENT = _real_environment_or_skip()


class RealOpenListAcceptanceGateTests(unittest.TestCase):
    def test_requires_every_field_exact_confirmation_and_dedicated_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "openlist-acceptance.json"
            valid = {
                "TEST_OPENLIST_URL": "https://openlist.example.invalid",
                "TEST_OPENLIST_TOKEN": "secret",
                "TEST_OPENLIST_ROOT": "/qa/mediaflow-acceptance-openlist",
                "TEST_OPENLIST_DESTRUCTIVE_CONFIRM": CONFIRMATION,
                "TEST_OPENLIST_REPORT": str(report),
            }
            environment = resolve_real_openlist_environment(valid)
            self.assertEqual("/qa/mediaflow-acceptance-openlist", environment.root)
            self.assertEqual(report, environment.report)
            for mutation in (
                {"TEST_OPENLIST_TOKEN": ""},
                {"TEST_OPENLIST_DESTRUCTIVE_CONFIRM": "yes"},
                {"TEST_OPENLIST_ROOT": "/"},
                {"TEST_OPENLIST_ROOT": "/media"},
                {"TEST_OPENLIST_ROOT": "relative/mediaflow-acceptance-openlist"},
                {"TEST_OPENLIST_ROOT": "/qa/../mediaflow-acceptance-openlist"},
                {"TEST_OPENLIST_REPORT": "relative.json"},
                {"TEST_OPENLIST_REPORT": str(Path(directory) / "report.txt")},
                {"TEST_OPENLIST_REPORT": str(Path(directory) / "missing" / "report.json")},
            ):
                candidate = {**valid, **mutation}
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    resolve_real_openlist_environment(candidate)
            report.write_text("existing", encoding="utf-8")
            with self.assertRaises(ValueError):
                resolve_real_openlist_environment(valid)

    def test_report_is_atomic_non_overwriting_and_secret_free(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.json"
            record = {
                "schema": 1,
                "result": "PASS",
                "adapter": "OpenListStorage",
                "rootIdentifier": "mediaflow-acceptance-openlist",
            }
            write_acceptance_report(target, record)
            self.assertEqual(record, json.loads(target.read_text(encoding="utf-8")))
            with self.assertRaises(ValueError):
                write_acceptance_report(target, record)
            self.assertEqual(record, json.loads(target.read_text(encoding="utf-8")))
            with self.assertRaises(ValueError):
                write_acceptance_report(
                    Path(directory) / "unsafe.json", {"authorization": "secret"}
                )
            failed = Path(directory) / "failed.json"
            write_acceptance_report(
                failed,
                {
                    "schema": 1,
                    "result": "FAIL",
                    "errorCategory": StorageErrorCode.PERMISSION_DENIED.value,
                },
            )
            self.assertEqual(
                "permission_denied",
                json.loads(failed.read_text(encoding="utf-8"))["errorCategory"],
            )

    def test_empty_root_preflight_is_read_only_and_fail_closed(self) -> None:
        storage = Mock()

        def assert_zero_mutations() -> None:
            for mutation in (
                storage.write,
                storage.create_directory,
                storage.move,
                storage.copy,
                storage.delete,
                storage.hard_link,
                storage.soft_link,
            ):
                mutation.assert_not_called()

        storage.stat.return_value = SimpleNamespace(entry_type=StorageEntryType.DIRECTORY)
        storage.list.return_value = ()
        assert_empty_acceptance_root(storage)
        storage.stat.assert_called_once_with("")
        storage.list.assert_called_once_with("")
        assert_zero_mutations()

        storage.reset_mock()
        storage.stat.return_value = SimpleNamespace(entry_type=StorageEntryType.FILE)
        with self.assertRaisesRegex(AssertionError, "not a directory"):
            assert_empty_acceptance_root(storage)
        storage.list.assert_not_called()
        assert_zero_mutations()

        storage.reset_mock()
        storage.stat.return_value = SimpleNamespace(entry_type=StorageEntryType.DIRECTORY)
        storage.list.return_value = (SimpleNamespace(path="unknown"),)
        with self.assertRaisesRegex(AssertionError, "not empty"):
            assert_empty_acceptance_root(storage)
        assert_zero_mutations()

        storage.reset_mock()
        storage.stat.side_effect = StorageError(
            StorageErrorCode.PERMISSION_DENIED, "stat", "", "denied"
        )
        with self.assertRaises(StorageError):
            assert_empty_acceptance_root(storage)
        assert_zero_mutations()


@unittest.skipIf(
    REAL_ENVIRONMENT is None,
    "BLOCKED: dedicated real OpenList acceptance environment and confirmation are absent",
)
class RealOpenListAcceptanceMatrixTests(unittest.TestCase):
    def test_real_adapter_and_transfer_matrix(self) -> None:
        environment = REAL_ENVIRONMENT
        assert environment is not None
        started = datetime.now(UTC)
        completed: list[str] = []
        preflight_passed = False
        cleanup_attempted = False
        cleanup_passed: bool | None = None
        run_created = False
        failure: BaseException | None = None
        config = OpenListStorageConfig(
            "openlist-acceptance",
            "OpenList isolated acceptance",
            environment.url,
            environment.token,
            root_path=environment.root,
        )
        run = f"run-{uuid.uuid4().hex}"
        payload = b"mediaflow-openlist-acceptance-v1"
        with tempfile.TemporaryDirectory() as local_root:
            openlist = OpenListStorage(config)
            local = LocalStorage("local-acceptance", local_root)
            try:
                openlist.health_check()
                assert_empty_acceptance_root(openlist)
                preflight_passed = True
                completed.append("empty_root_preflight")
                self.assertFalse(openlist.exists(run), "generated run child unexpectedly exists")
                openlist.create_directory(run)
                run_created = True
                self._adapter_lifecycle(openlist, run, payload)
                completed.append("adapter_lifecycle")
                self._transfer_matrix(openlist, local, run, payload)
                completed.append("transfer_matrix")
            except BaseException as error:
                failure = error
            finally:
                if run_created:
                    cleanup_attempted = True
                    try:
                        self._cleanup_generated_child(openlist, run)
                        cleanup_passed = True
                        completed.append("allowlisted_cleanup")
                    except BaseException as error:
                        cleanup_passed = False
                        if failure is None:
                            failure = error
                else:
                    cleanup_passed = True
                try:
                    openlist.close()
                except BaseException as error:
                    if failure is None:
                        failure = error

        error_category = None
        if failure is not None:
            error_category = (
                failure.code.value if isinstance(failure, StorageError) else type(failure).__name__
            )
        write_acceptance_report(
            environment.report,
            {
                "schema": 1,
                "suite": "phase-19.23-openlist",
                "result": "FAIL" if failure else "PASS",
                "adapter": "OpenListStorage",
                "packageVersion": _package_version(),
                "rootIdentifier": PurePosixPath(environment.root).name,
                "startedAt": started.isoformat(),
                "finishedAt": datetime.now(UTC).isoformat(),
                "plannedOperations": [
                    "empty_root_preflight",
                    "adapter_lifecycle",
                    "transfer_matrix",
                    "allowlisted_cleanup",
                ],
                "completedOperations": completed,
                "emptyRootPreflight": preflight_passed,
                "cleanupAttempted": cleanup_attempted,
                "cleanupPassed": cleanup_passed,
                "errorCategory": error_category,
            },
        )
        if failure is not None:
            raise failure

    def _adapter_lifecycle(self, storage, run: str, payload: bytes) -> None:
        source = f"{run}/adapter-source.bin"
        copied = f"{run}/adapter-copy.bin"
        moved = f"{run}/adapter-moved.bin"
        storage.write(source, payload)
        self.assertEqual(len(payload), storage.stat(source).size)
        with storage.read(source) as stream:
            self.assertEqual(payload, stream.read())
        with self.assertRaises(StorageError) as raised:
            storage.write(source, b"must-not-overwrite")
        self.assertEqual(StorageErrorCode.ALREADY_EXISTS, raised.exception.code)
        storage.copy(source, copied)
        storage.move(copied, moved)
        self.assertFalse(storage.exists(copied))
        self.assertEqual({source, moved}, {entry.path for entry in storage.list(run)})
        storage.delete(moved)
        storage.delete(source)

    def _transfer_matrix(self, openlist, local, run: str, payload: bytes) -> None:
        executor = OrganizerExecutor()

        local.write("local-copy-source.bin", payload)
        result = executor.execute(
            self._plan(
                "local-acceptance",
                "local-copy-source.bin",
                "openlist-acceptance",
                f"{run}/from-local-copy.bin",
                PlanOperation.COPY,
            ),
            {"local-acceptance": local, "openlist-acceptance": openlist},
            execute=True,
        )
        self.assertEqual(ExecutionStatus.SUCCESS, result.status)

        local.write("local-move-source.bin", payload)
        result = executor.execute(
            self._plan(
                "local-acceptance",
                "local-move-source.bin",
                "openlist-acceptance",
                f"{run}/from-local-move.bin",
                PlanOperation.MOVE,
            ),
            {"local-acceptance": local, "openlist-acceptance": openlist},
            execute=True,
        )
        self.assertEqual(ExecutionStatus.SUCCESS, result.status)
        self.assertFalse(local.exists("local-move-source.bin"))

        openlist.write(f"{run}/remote-copy-source.bin", payload)
        result = executor.execute(
            self._plan(
                "openlist-acceptance",
                f"{run}/remote-copy-source.bin",
                "local-acceptance",
                "downloads/from-openlist-copy.bin",
                PlanOperation.COPY,
            ),
            {"local-acceptance": local, "openlist-acceptance": openlist},
            execute=True,
        )
        self.assertEqual(ExecutionStatus.SUCCESS, result.status)

        openlist.write(f"{run}/remote-move-source.bin", payload)
        result = executor.execute(
            self._plan(
                "openlist-acceptance",
                f"{run}/remote-move-source.bin",
                "local-acceptance",
                "downloads/from-openlist-move.bin",
                PlanOperation.MOVE,
            ),
            {"local-acceptance": local, "openlist-acceptance": openlist},
            execute=True,
        )
        self.assertEqual(ExecutionStatus.SUCCESS, result.status)
        self.assertFalse(openlist.exists(f"{run}/remote-move-source.bin"))

        openlist.write(f"{run}/same-copy-source.bin", payload)
        result = executor.execute(
            self._plan(
                "openlist-acceptance",
                f"{run}/same-copy-source.bin",
                "openlist-acceptance",
                f"{run}/same-copy-target.bin",
                PlanOperation.COPY,
            ),
            {"openlist-acceptance": openlist},
            execute=True,
        )
        self.assertEqual(ExecutionStatus.SUCCESS, result.status)

        openlist.write(f"{run}/same-move-source.bin", payload)
        result = executor.execute(
            self._plan(
                "openlist-acceptance",
                f"{run}/same-move-source.bin",
                "openlist-acceptance",
                f"{run}/same-move-target.bin",
                PlanOperation.MOVE,
            ),
            {"openlist-acceptance": openlist},
            execute=True,
        )
        self.assertEqual(ExecutionStatus.SUCCESS, result.status)
        self.assertFalse(openlist.exists(f"{run}/same-move-source.bin"))

        for path in (
            f"{run}/from-local-copy.bin",
            f"{run}/from-local-move.bin",
            f"{run}/same-copy-target.bin",
            f"{run}/same-move-target.bin",
        ):
            with openlist.read(path) as stream:
                self.assertEqual(payload, stream.read())
        with local.read("downloads/from-openlist-copy.bin") as stream:
            self.assertEqual(payload, stream.read())
        with local.read("downloads/from-openlist-move.bin") as stream:
            self.assertEqual(payload, stream.read())

    @staticmethod
    def _plan(source_id, source, target_id, target, operation) -> OrganizePlan:
        return OrganizePlan(
            source_id,
            target_id,
            source,
            target,
            "A",
            "A",
            "A",
            "A",
            operation=operation,
            source_location=StorageLocation(source_id, source),
            destination_location=StorageLocation(target_id, target),
        )

    @staticmethod
    def _cleanup_generated_child(storage, run: str) -> None:
        if not storage.exists(run):
            return
        allowed = {
            f"{run}/{name}"
            for name in (
                "adapter-source.bin",
                "adapter-copy.bin",
                "adapter-moved.bin",
                "from-local-copy.bin",
                "from-local-move.bin",
                "remote-copy-source.bin",
                "remote-move-source.bin",
                "same-copy-source.bin",
                "same-copy-target.bin",
                "same-move-source.bin",
                "same-move-target.bin",
            )
        }
        entries = storage.list(run)
        unknown = {entry.path for entry in entries}.difference(allowed)
        if unknown:
            raise AssertionError("generated acceptance child contains an unknown object")
        for entry in entries:
            storage.delete(entry.path)
        storage.delete(run)
