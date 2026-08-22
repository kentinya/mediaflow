from __future__ import annotations

import os
import tempfile
import unittest
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.domain.organizer import (
    ExecutionStatus,
    OrganizePlan,
    PlanOperation,
    StorageLocation,
)
from mediaflow.domain.storage import StorageEntryType, StorageError, StorageErrorCode
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.s3_storage import S3Provider, S3Storage, S3StorageConfig
from mediaflow.infrastructure.smb_storage import SMBStorage, SMBStorageConfig
from tests.test_openlist_real_acceptance import CONFIRMATION, write_acceptance_report


@dataclass(frozen=True)
class RealSMBEnvironment:
    host: str
    port: int
    share: str
    username: str
    password: str
    root: str
    report: Path


@dataclass(frozen=True)
class RealS3Environment:
    endpoint: str
    bucket: str
    access_key: str
    secret_key: str
    root: str
    report: Path


def _new_report(value: str) -> Path:
    report = Path(value)
    if (
        not report.is_absolute()
        or report.suffix.lower() != ".json"
        or report.exists()
        or report.is_symlink()
        or not report.parent.is_dir()
    ):
        raise ValueError("acceptance report must be a new absolute .json file")
    return report


def _safe_relative_root(value: str, provider: str) -> str:
    path = PurePosixPath(value.replace("\\", "/"))
    if (
        not value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or not path.name.startswith("mediaflow-acceptance-")
    ):
        raise ValueError(
            f"{provider} acceptance root must be a relative mediaflow-acceptance-* path"
        )
    return path.as_posix()


def resolve_real_smb_environment(environ: dict[str, str]) -> RealSMBEnvironment:
    names = (
        "TEST_REAL_SMB_HOST",
        "TEST_REAL_SMB_PORT",
        "TEST_REAL_SMB_SHARE",
        "TEST_REAL_SMB_USERNAME",
        "TEST_REAL_SMB_PASSWORD",
        "TEST_REAL_SMB_ROOT",
        "TEST_REAL_SMB_DESTRUCTIVE_CONFIRM",
        "TEST_REAL_SMB_REPORT",
    )
    if any(not environ.get(name) for name in names):
        raise ValueError("real SMB acceptance prerequisites are incomplete")
    if environ["TEST_REAL_SMB_DESTRUCTIVE_CONFIRM"] != CONFIRMATION:
        raise ValueError("real SMB destructive confirmation is invalid")
    try:
        port = int(environ["TEST_REAL_SMB_PORT"])
    except ValueError as error:
        raise ValueError("real SMB port is invalid") from error
    if not 1 <= port <= 65535:
        raise ValueError("real SMB port is invalid")
    return RealSMBEnvironment(
        environ["TEST_REAL_SMB_HOST"],
        port,
        environ["TEST_REAL_SMB_SHARE"],
        environ["TEST_REAL_SMB_USERNAME"],
        environ["TEST_REAL_SMB_PASSWORD"],
        _safe_relative_root(environ["TEST_REAL_SMB_ROOT"], "SMB"),
        _new_report(environ["TEST_REAL_SMB_REPORT"]),
    )


def resolve_real_s3_environment(environ: dict[str, str]) -> RealS3Environment:
    names = (
        "TEST_REAL_S3_ENDPOINT",
        "TEST_REAL_S3_BUCKET",
        "TEST_REAL_S3_ACCESS_KEY",
        "TEST_REAL_S3_SECRET_KEY",
        "TEST_REAL_S3_ROOT",
        "TEST_REAL_S3_DESTRUCTIVE_CONFIRM",
        "TEST_REAL_S3_REPORT",
    )
    if any(not environ.get(name) for name in names):
        raise ValueError("real S3 acceptance prerequisites are incomplete")
    if environ["TEST_REAL_S3_DESTRUCTIVE_CONFIRM"] != CONFIRMATION:
        raise ValueError("real S3 destructive confirmation is invalid")
    return RealS3Environment(
        environ["TEST_REAL_S3_ENDPOINT"],
        environ["TEST_REAL_S3_BUCKET"],
        environ["TEST_REAL_S3_ACCESS_KEY"],
        environ["TEST_REAL_S3_SECRET_KEY"],
        _safe_relative_root(environ["TEST_REAL_S3_ROOT"], "S3"),
        _new_report(environ["TEST_REAL_S3_REPORT"]),
    )


def _environment_or_skip(prefix: str, resolver):
    relevant = {key: value for key, value in os.environ.items() if key.startswith(prefix)}
    return resolver(dict(os.environ)) if relevant else None


SMB_ENVIRONMENT = _environment_or_skip("TEST_REAL_SMB_", resolve_real_smb_environment)
S3_ENVIRONMENT = _environment_or_skip("TEST_REAL_S3_", resolve_real_s3_environment)


class RealSMBS3AcceptanceGateTests(unittest.TestCase):
    def test_smb_and_s3_gates_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            smb = {
                "TEST_REAL_SMB_HOST": "127.0.0.1",
                "TEST_REAL_SMB_PORT": "445",
                "TEST_REAL_SMB_SHARE": "acceptance",
                "TEST_REAL_SMB_USERNAME": "tester",
                "TEST_REAL_SMB_PASSWORD": "secret",
                "TEST_REAL_SMB_ROOT": "mediaflow-acceptance-smb",
                "TEST_REAL_SMB_DESTRUCTIVE_CONFIRM": CONFIRMATION,
                "TEST_REAL_SMB_REPORT": str(Path(directory) / "smb.json"),
            }
            s3 = {
                "TEST_REAL_S3_ENDPOINT": "http://127.0.0.1:9000",
                "TEST_REAL_S3_BUCKET": "acceptance",
                "TEST_REAL_S3_ACCESS_KEY": "access",
                "TEST_REAL_S3_SECRET_KEY": "secret",
                "TEST_REAL_S3_ROOT": "mediaflow-acceptance-s3",
                "TEST_REAL_S3_DESTRUCTIVE_CONFIRM": CONFIRMATION,
                "TEST_REAL_S3_REPORT": str(Path(directory) / "s3.json"),
            }
            self.assertEqual(445, resolve_real_smb_environment(smb).port)
            self.assertEqual("acceptance", resolve_real_s3_environment(s3).bucket)
            for mutation in (
                {"TEST_REAL_SMB_PASSWORD": ""},
                {"TEST_REAL_SMB_PORT": "0"},
                {"TEST_REAL_SMB_ROOT": "../mediaflow-acceptance-smb"},
                {"TEST_REAL_SMB_DESTRUCTIVE_CONFIRM": "yes"},
                {"TEST_REAL_SMB_REPORT": "relative.json"},
            ):
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    resolve_real_smb_environment({**smb, **mutation})
            for mutation in (
                {"TEST_REAL_S3_SECRET_KEY": ""},
                {"TEST_REAL_S3_ROOT": "/mediaflow-acceptance-s3"},
                {"TEST_REAL_S3_ROOT": "prefix"},
                {"TEST_REAL_S3_DESTRUCTIVE_CONFIRM": "yes"},
                {"TEST_REAL_S3_REPORT": "relative.json"},
            ):
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    resolve_real_s3_environment({**s3, **mutation})


class _RealMatrixMixin:
    environment: object
    provider_name: str

    def _run_real_matrix(self, storage, report: Path, root_identifier: str) -> None:
        started = datetime.now(UTC)
        run = f"run-{uuid.uuid4().hex}"
        completed: list[str] = []
        cleanup_attempted = False
        cleanup_passed: bool | None = None
        failure: BaseException | None = None
        created = False
        with tempfile.TemporaryDirectory() as local_root:
            local = LocalStorage("local-acceptance", local_root)
            try:
                self.assertEqual(StorageEntryType.DIRECTORY, storage.stat("").entry_type)
                self.assertEqual((), storage.list(""))
                completed.append("empty_root_preflight")
                storage.create_directory(run)
                created = True
                self._adapter_lifecycle(storage, run)
                completed.append("adapter_lifecycle")
                self._transfer_matrix(storage, local, run)
                completed.append("transfer_matrix")
            except BaseException as error:
                failure = error
            finally:
                if created:
                    cleanup_attempted = True
                    try:
                        self._cleanup(storage, run)
                        cleanup_passed = True
                        completed.append("allowlisted_cleanup")
                    except BaseException as error:
                        cleanup_passed = False
                        if failure is None:
                            failure = error
                else:
                    cleanup_passed = True
                try:
                    storage.close()
                except BaseException as error:
                    if failure is None:
                        failure = error
        write_acceptance_report(
            report,
            {
                "schema": 1,
                "suite": f"phase-19.24-{self.provider_name.lower()}",
                "result": "FAIL" if failure else "PASS",
                "adapter": type(storage).__name__,
                "rootIdentifier": root_identifier,
                "startedAt": started.isoformat(),
                "finishedAt": datetime.now(UTC).isoformat(),
                "plannedOperations": [
                    "empty_root_preflight",
                    "adapter_lifecycle",
                    "transfer_matrix",
                    "allowlisted_cleanup",
                ],
                "completedOperations": completed,
                "cleanupAttempted": cleanup_attempted,
                "cleanupPassed": cleanup_passed,
                "errorCategory": self._error_category(failure),
            },
        )
        if failure is not None:
            raise failure

    def _adapter_lifecycle(self, storage, run: str) -> None:
        payload = b"mediaflow-real-storage-acceptance-v1"
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
        storage.delete(moved)
        storage.delete(source)

    def _transfer_matrix(self, remote, local, run: str) -> None:
        payload = b"mediaflow-real-transfer-v1"
        executor = OrganizerExecutor()
        storages = {"local-acceptance": local, "remote-acceptance": remote}
        local.write("local-copy-source.bin", payload)
        self._assert_execute(
            executor,
            storages,
            "local-acceptance",
            "local-copy-source.bin",
            "remote-acceptance",
            f"{run}/from-local-copy.bin",
            PlanOperation.COPY,
        )
        local.write("local-move-source.bin", payload)
        self._assert_execute(
            executor,
            storages,
            "local-acceptance",
            "local-move-source.bin",
            "remote-acceptance",
            f"{run}/from-local-move.bin",
            PlanOperation.MOVE,
        )
        self.assertFalse(local.exists("local-move-source.bin"))
        remote.write(f"{run}/remote-copy-source.bin", payload)
        self._assert_execute(
            executor,
            storages,
            "remote-acceptance",
            f"{run}/remote-copy-source.bin",
            "local-acceptance",
            "downloads/from-remote-copy.bin",
            PlanOperation.COPY,
        )
        remote.write(f"{run}/remote-move-source.bin", payload)
        self._assert_execute(
            executor,
            storages,
            "remote-acceptance",
            f"{run}/remote-move-source.bin",
            "local-acceptance",
            "downloads/from-remote-move.bin",
            PlanOperation.MOVE,
        )
        self.assertFalse(remote.exists(f"{run}/remote-move-source.bin"))
        remote.write(f"{run}/same-copy-source.bin", payload)
        self._assert_execute(
            executor,
            storages,
            "remote-acceptance",
            f"{run}/same-copy-source.bin",
            "remote-acceptance",
            f"{run}/same-copy-target.bin",
            PlanOperation.COPY,
        )
        remote.write(f"{run}/same-move-source.bin", payload)
        self._assert_execute(
            executor,
            storages,
            "remote-acceptance",
            f"{run}/same-move-source.bin",
            "remote-acceptance",
            f"{run}/same-move-target.bin",
            PlanOperation.MOVE,
        )
        for path in (
            f"{run}/from-local-copy.bin",
            f"{run}/from-local-move.bin",
            f"{run}/same-copy-target.bin",
            f"{run}/same-move-target.bin",
        ):
            with remote.read(path) as stream:
                self.assertEqual(payload, stream.read())
        with local.read("downloads/from-remote-copy.bin") as stream:
            self.assertEqual(payload, stream.read())
        with local.read("downloads/from-remote-move.bin") as stream:
            self.assertEqual(payload, stream.read())

    def _cleanup(self, storage, run: str) -> None:
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
        if {entry.path for entry in entries}.difference(allowed):
            raise AssertionError("acceptance run contains an unknown object")
        for entry in entries:
            storage.delete(entry.path)
        storage.delete(run)

    def _assert_execute(self, executor, storages, source_id, source, target_id, target, operation):
        plan = OrganizePlan(
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
        result = executor.execute(plan, storages, execute=True)
        self.assertEqual(ExecutionStatus.SUCCESS, result.status, result.errors)

    @staticmethod
    def _error_category(error: BaseException | None) -> str | None:
        if isinstance(error, StorageError):
            return error.code.value
        return type(error).__name__ if error else None


@unittest.skipIf(SMB_ENVIRONMENT is None, "BLOCKED: dedicated real SMB environment is absent")
class RealSMBAcceptanceMatrixTests(_RealMatrixMixin, unittest.TestCase):
    provider_name = "SMB"

    def test_real_smb_matrix(self) -> None:
        environment = SMB_ENVIRONMENT
        assert environment is not None
        storage = SMBStorage(
            SMBStorageConfig(
                "remote-acceptance",
                "SMB isolated acceptance",
                environment.host,
                environment.share,
                environment.username,
                environment.password,
                root_path=environment.root,
                port=environment.port,
            )
        )
        storage.connect()
        self._run_real_matrix(storage, environment.report, PurePosixPath(environment.root).name)


@unittest.skipIf(S3_ENVIRONMENT is None, "BLOCKED: dedicated real S3 environment is absent")
class RealS3AcceptanceMatrixTests(_RealMatrixMixin, unittest.TestCase):
    provider_name = "S3"

    def test_real_s3_matrix(self) -> None:
        environment = S3_ENVIRONMENT
        assert environment is not None
        storage = S3Storage(
            S3StorageConfig(
                "remote-acceptance",
                "MinIO isolated acceptance",
                S3Provider.S3_COMPATIBLE,
                environment.bucket,
                environment.access_key,
                environment.secret_key,
                endpoint=environment.endpoint,
                root_prefix=environment.root,
                force_path_style=True,
            )
        )
        storage.health_check()
        self._run_real_matrix(storage, environment.report, PurePosixPath(environment.root).name)
