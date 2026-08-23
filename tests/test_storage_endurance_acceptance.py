from __future__ import annotations

import hashlib
import io
import os
import tempfile
import time
import unittest
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.domain.organizer import (
    ExecutionStatus,
    OrganizePlan,
    PlanOperation,
    StorageLocation,
)
from mediaflow.domain.storage import StorageEntryType
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.openlist_storage import OpenListStorage, OpenListStorageConfig
from mediaflow.infrastructure.s3_storage import S3Provider, S3Storage, S3StorageConfig
from mediaflow.infrastructure.smb_storage import SMBStorage, SMBStorageConfig
from tests.test_openlist_real_acceptance import CONFIRMATION, write_acceptance_report

MIB = 1024 * 1024


@dataclass(frozen=True)
class EnduranceProfile:
    provider: str
    batch_count: int
    large_bytes: int
    report: Path
    local_root: Path | None = None
    host: str | None = None
    port: int | None = None
    share: str | None = None
    username: str | None = None
    password: str | None = None
    remote_root: str | None = None
    endpoint: str | None = None
    bucket: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    token: str | None = None


def _positive_bounded(environ: dict[str, str], name: str, minimum: int, maximum: int) -> int:
    try:
        value = int(environ[name])
    except (KeyError, ValueError) as error:
        raise ValueError(f"{name} must be an integer") from error
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} is outside the acceptance bound")
    return value


def _new_report(environ: dict[str, str]) -> Path:
    value = environ.get("TEST_ENDURANCE_REPORT", "")
    report = Path(value)
    if (
        not value
        or not report.is_absolute()
        or report.suffix.lower() != ".json"
        or report.exists()
        or report.is_symlink()
        or not report.parent.is_dir()
    ):
        raise ValueError("endurance report must be a new absolute .json file")
    return report


def _common(environ: dict[str, str]) -> tuple[int, int, Path]:
    if environ.get("TEST_ENDURANCE_DESTRUCTIVE_CONFIRM") != CONFIRMATION:
        raise ValueError("endurance destructive confirmation is invalid")
    return (
        _positive_bounded(environ, "TEST_ENDURANCE_BATCH_COUNT", 8, 512),
        _positive_bounded(environ, "TEST_ENDURANCE_LARGE_BYTES", 6 * MIB, 1024 * MIB),
        _new_report(environ),
    )


def _relative_root(value: str) -> str:
    path = PurePosixPath(value.replace("\\", "/"))
    if (
        not value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or not path.name.startswith("mediaflow-acceptance-")
    ):
        raise ValueError("endurance remote root must be a relative mediaflow-acceptance-* path")
    return path.as_posix()


def _absolute_openlist_root(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or not path.is_absolute()
        or value == "/"
        or any(part in {"", ".", ".."} for part in path.parts[1:])
        or not path.name.startswith("mediaflow-acceptance-")
    ):
        raise ValueError("OpenList endurance root must be an absolute mediaflow-acceptance-* path")
    return path.as_posix()


def resolve_endurance_profile(provider: str, environ: dict[str, str]) -> EnduranceProfile:
    batch_count, large_bytes, report = _common(environ)
    normalized = provider.casefold()
    if normalized == "local":
        value = environ.get("TEST_ENDURANCE_LOCAL_ROOT", "")
        root = Path(value)
        if (
            not value
            or not root.is_absolute()
            or root.is_symlink()
            or not root.is_dir()
            or not root.name.startswith("mediaflow-acceptance-")
        ):
            raise ValueError(
                "Local endurance root must be an existing absolute acceptance directory"
            )
        return EnduranceProfile(normalized, batch_count, large_bytes, report, local_root=root)
    if normalized == "smb":
        required = (
            "TEST_ENDURANCE_SMB_HOST",
            "TEST_ENDURANCE_SMB_PORT",
            "TEST_ENDURANCE_SMB_SHARE",
            "TEST_ENDURANCE_SMB_USERNAME",
            "TEST_ENDURANCE_SMB_PASSWORD",
            "TEST_ENDURANCE_SMB_ROOT",
        )
        if any(not environ.get(name) for name in required):
            raise ValueError("SMB endurance prerequisites are incomplete")
        port = _positive_bounded(environ, "TEST_ENDURANCE_SMB_PORT", 1, 65535)
        return EnduranceProfile(
            normalized,
            batch_count,
            large_bytes,
            report,
            host=environ["TEST_ENDURANCE_SMB_HOST"],
            port=port,
            share=environ["TEST_ENDURANCE_SMB_SHARE"],
            username=environ["TEST_ENDURANCE_SMB_USERNAME"],
            password=environ["TEST_ENDURANCE_SMB_PASSWORD"],
            remote_root=_relative_root(environ["TEST_ENDURANCE_SMB_ROOT"]),
        )
    if normalized == "openlist":
        required = (
            "TEST_ENDURANCE_OPENLIST_URL",
            "TEST_ENDURANCE_OPENLIST_TOKEN",
            "TEST_ENDURANCE_OPENLIST_ROOT",
        )
        if any(not environ.get(name) for name in required):
            raise ValueError("OpenList endurance prerequisites are incomplete")
        return EnduranceProfile(
            normalized,
            batch_count,
            large_bytes,
            report,
            endpoint=environ["TEST_ENDURANCE_OPENLIST_URL"],
            token=environ["TEST_ENDURANCE_OPENLIST_TOKEN"],
            remote_root=_absolute_openlist_root(environ["TEST_ENDURANCE_OPENLIST_ROOT"]),
        )
    if normalized == "s3":
        required = (
            "TEST_ENDURANCE_S3_ENDPOINT",
            "TEST_ENDURANCE_S3_BUCKET",
            "TEST_ENDURANCE_S3_ACCESS_KEY",
            "TEST_ENDURANCE_S3_SECRET_KEY",
            "TEST_ENDURANCE_S3_ROOT",
        )
        if any(not environ.get(name) for name in required):
            raise ValueError("S3 endurance prerequisites are incomplete")
        return EnduranceProfile(
            normalized,
            batch_count,
            large_bytes,
            report,
            endpoint=environ["TEST_ENDURANCE_S3_ENDPOINT"],
            bucket=environ["TEST_ENDURANCE_S3_BUCKET"],
            access_key=environ["TEST_ENDURANCE_S3_ACCESS_KEY"],
            secret_key=environ["TEST_ENDURANCE_S3_SECRET_KEY"],
            remote_root=_relative_root(environ["TEST_ENDURANCE_S3_ROOT"]),
        )
    raise ValueError("unsupported endurance provider")


def _configured_profile(provider: str) -> EnduranceProfile | None:
    prefix = "TEST_ENDURANCE_"
    if not any(name.startswith(prefix) for name in os.environ):
        return None
    selected = os.environ.get("TEST_ENDURANCE_PROVIDER", "").casefold()
    if selected != provider:
        return None
    return resolve_endurance_profile(provider, dict(os.environ))


class PatternStream(io.RawIOBase):
    def __init__(self, size: int, *, fail_after: int | None = None) -> None:
        self.remaining = size
        self.position = 0
        self.fail_after = fail_after
        self.maximum_read = 0

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            raise AssertionError("acceptance streams forbid unbounded reads")
        if self.fail_after is not None and self.position >= self.fail_after:
            raise OSError("injected acceptance stream interruption")
        count = min(size, self.remaining)
        if self.fail_after is not None:
            count = min(count, self.fail_after - self.position)
        self.maximum_read = max(self.maximum_read, count)
        if count <= 0:
            return b""
        start = self.position
        self.position += count
        self.remaining -= count
        pattern = bytes(range(251))
        offset = start % len(pattern)
        repeats = (offset + count + len(pattern) - 1) // len(pattern)
        return (pattern * repeats)[offset : offset + count]


class InterruptedSource:
    def __init__(self, storage: LocalStorage, path: str, fail_after: int) -> None:
        self._storage = storage
        self.storage_id = storage.storage_id
        self.fail_after = fail_after

    @property
    def capabilities(self):
        return self._storage.capabilities

    def exists(self, path: str) -> bool:
        return self._storage.exists(path)

    def stat(self, path: str):
        return self._storage.stat(path)

    def read(self, path: str):
        return PatternStream(self._storage.stat(path).size, fail_after=self.fail_after)

    def __getattr__(self, name: str):
        return getattr(self._storage, name)


class ObservedReadStorage:
    def __init__(self, storage: LocalStorage) -> None:
        self._storage = storage
        self.storage_id = storage.storage_id
        self.maximum_read = 0

    @property
    def capabilities(self):
        return self._storage.capabilities

    def read(self, path: str):
        parent = self
        stream = self._storage.read(path)

        class ObservedStream:
            def read(self, size: int = -1) -> bytes:
                if size < 0:
                    raise AssertionError("acceptance transfers forbid unbounded reads")
                chunk = stream.read(size)
                parent.maximum_read = max(parent.maximum_read, len(chunk))
                return chunk

            def close(self) -> None:
                stream.close()

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback) -> None:
                self.close()

        return ObservedStream()

    def __getattr__(self, name: str):
        return getattr(self._storage, name)


class EnduranceGateTests(unittest.TestCase):
    def test_profiles_fail_closed_and_bounds_are_validated(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mediaflow-acceptance-local-") as root:
            report = str(Path(root).parent / f"mediaflow-endurance-{uuid.uuid4().hex}.json")
            base = {
                "TEST_ENDURANCE_DESTRUCTIVE_CONFIRM": CONFIRMATION,
                "TEST_ENDURANCE_BATCH_COUNT": "8",
                "TEST_ENDURANCE_LARGE_BYTES": str(6 * MIB),
                "TEST_ENDURANCE_REPORT": report,
                "TEST_ENDURANCE_LOCAL_ROOT": root,
            }
            profile = resolve_endurance_profile("local", base)
            self.assertEqual((8, 6 * MIB), (profile.batch_count, profile.large_bytes))
            for mutation in (
                {"TEST_ENDURANCE_DESTRUCTIVE_CONFIRM": "yes"},
                {"TEST_ENDURANCE_BATCH_COUNT": "7"},
                {"TEST_ENDURANCE_LARGE_BYTES": str(5 * MIB)},
                {"TEST_ENDURANCE_REPORT": "relative.json"},
                {"TEST_ENDURANCE_LOCAL_ROOT": "/tmp"},
            ):
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    resolve_endurance_profile("local", {**base, **mutation})

    def test_remote_roots_and_partial_configuration_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            common = {
                "TEST_ENDURANCE_DESTRUCTIVE_CONFIRM": CONFIRMATION,
                "TEST_ENDURANCE_BATCH_COUNT": "8",
                "TEST_ENDURANCE_LARGE_BYTES": str(6 * MIB),
                "TEST_ENDURANCE_REPORT": str(Path(directory) / "report.json"),
            }
            with self.assertRaises(ValueError):
                resolve_endurance_profile("smb", common)
            with self.assertRaises(ValueError):
                resolve_endurance_profile("openlist", common)
            with self.assertRaises(ValueError):
                resolve_endurance_profile("s3", common)
            self.assertEqual(
                "mediaflow-acceptance-safe", _relative_root("mediaflow-acceptance-safe")
            )
            self.assertEqual(
                "/qa/mediaflow-acceptance-safe",
                _absolute_openlist_root("/qa/mediaflow-acceptance-safe"),
            )
            for unsafe in ("root", "../mediaflow-acceptance-x", "/mediaflow-acceptance-x"):
                with self.subTest(unsafe=unsafe), self.assertRaises(ValueError):
                    _relative_root(unsafe)


class _EnduranceMixin:
    profile: EnduranceProfile

    def create_storage(self):
        raise NotImplementedError

    def test_endurance_profile(self) -> None:
        profile = self.profile
        storage = self.create_storage()
        started = time.monotonic()
        run = f"run-{uuid.uuid4().hex}"
        completed: list[str] = []
        observed_partial_target = False
        cleanup_passed = False
        failure: BaseException | None = None
        maximum_stream_read = 0
        with tempfile.TemporaryDirectory() as local_directory:
            local = LocalStorage("endurance-source", local_directory)
            try:
                self.assertEqual(StorageEntryType.DIRECTORY, storage.stat("").entry_type)
                self.assertEqual((), storage.list(""))
                completed.append("empty_root_preflight")
                storage.create_directory(run)
                self._run_batch(local, storage, run, profile.batch_count)
                completed.append("sustained_batch")
                maximum_stream_read = self._run_large(local, storage, run, profile.large_bytes)
                completed.append("large_streaming_object")
                observed_partial_target = self._run_interruption_and_retry(
                    local, storage, run, profile.large_bytes
                )
                completed.append("interruption_source_preserved")
                completed.append("explicit_retry_consistent")
            except BaseException as error:
                failure = error
            finally:
                try:
                    self._cleanup(storage, run, profile.batch_count)
                    cleanup_passed = True
                    completed.append("allowlisted_cleanup")
                except BaseException as error:
                    if failure is None:
                        failure = error
                close = getattr(storage, "close", None)
                if close is not None:
                    try:
                        close()
                    except BaseException as error:
                        if failure is None:
                            failure = error
        duration = time.monotonic() - started
        write_acceptance_report(
            profile.report,
            {
                "schema": 1,
                "suite": "phase-19.25-storage-endurance",
                "result": "FAIL" if failure else "PASS",
                "provider": profile.provider,
                "batchCount": profile.batch_count,
                "largeBytes": profile.large_bytes,
                "maximumStreamRead": maximum_stream_read,
                "durationSeconds": round(duration, 6),
                "plannedChecks": [
                    "empty_root_preflight",
                    "sustained_batch",
                    "large_streaming_object",
                    "interruption_source_preserved",
                    "explicit_retry_consistent",
                    "allowlisted_cleanup",
                ],
                "completedChecks": completed,
                "partialTargetObserved": observed_partial_target,
                "cleanupPassed": cleanup_passed,
                "errorCategory": type(failure).__name__ if failure else None,
            },
        )
        if failure is not None:
            raise failure

    def _run_batch(self, local, remote, run: str, count: int) -> None:
        executor = OrganizerExecutor()
        for index in range(count):
            payload = hashlib.sha256(f"mediaflow-batch-{index}".encode()).digest() * 128
            source = f"batch-source-{index:04d}.bin"
            target = f"{run}/batch-{index:04d}.bin"
            local.write(source, payload)
            result = executor.execute(
                _plan("endurance-source", source, "endurance-target", target, PlanOperation.COPY),
                {"endurance-source": local, "endurance-target": remote},
                execute=True,
            )
            self.assertEqual(ExecutionStatus.SUCCESS, result.status, result.errors)
            self.assertEqual(len(payload), remote.stat(target).size)
            with remote.read(target) as stream:
                self.assertEqual(payload, stream.read())

    def _run_large(self, local, remote, run: str, size: int) -> int:
        source = "large-source.bin"
        target = f"{run}/large.bin"
        generated = PatternStream(size)
        local.write(source, generated)
        observed = ObservedReadStorage(local)
        result = OrganizerExecutor().execute(
            _plan("endurance-source", source, "endurance-target", target, PlanOperation.COPY),
            {"endurance-source": observed, "endurance-target": remote},
            execute=True,
        )
        self.assertEqual(ExecutionStatus.SUCCESS, result.status, result.errors)
        self.assertEqual(size, remote.stat(target).size)
        self.assertEqual(_digest(local, source), _digest(remote, target))
        return max(generated.maximum_read, observed.maximum_read)

    def _run_interruption_and_retry(self, local, remote, run: str, size: int) -> bool:
        source = "interrupted-source.bin"
        target = f"{run}/interrupted.bin"
        local.write(source, PatternStream(size))
        interrupted = InterruptedSource(local, source, max(1, size // 3))
        plan = _plan("endurance-source", source, "endurance-target", target, PlanOperation.MOVE)
        result = OrganizerExecutor().execute(
            plan,
            {"endurance-source": interrupted, "endurance-target": remote},
            execute=True,
        )
        self.assertNotEqual(ExecutionStatus.SUCCESS, result.status)
        self.assertTrue(local.exists(source), "interrupted MOVE must preserve source")
        partial = remote.exists(target)
        if partial:
            self.assertLess(remote.stat(target).size, size)
            remote.delete(target)
        retry = OrganizerExecutor().execute(
            plan,
            {"endurance-source": local, "endurance-target": remote},
            execute=True,
        )
        self.assertEqual(ExecutionStatus.SUCCESS, retry.status, retry.errors)
        self.assertFalse(local.exists(source))
        self.assertEqual(size, remote.stat(target).size)
        return partial

    def _cleanup(self, storage, run: str, count: int) -> None:
        if not storage.exists(run):
            return
        allowed = {f"{run}/batch-{index:04d}.bin" for index in range(count)}
        allowed.update({f"{run}/large.bin", f"{run}/interrupted.bin"})
        entries = storage.list(run)
        unknown = {entry.path for entry in entries}.difference(allowed)
        if unknown:
            raise AssertionError("endurance root contains an unknown generated object")
        for entry in entries:
            storage.delete(entry.path)
        storage.delete(run)


def _plan(source_id: str, source: str, target_id: str, target: str, operation) -> OrganizePlan:
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


def _digest(storage, path: str) -> str:
    digest = hashlib.sha256()
    with storage.read(path) as stream:
        while chunk := stream.read(MIB):
            digest.update(chunk)
    return digest.hexdigest()


LOCAL_PROFILE = _configured_profile("local")
SMB_PROFILE = _configured_profile("smb")
OPENLIST_PROFILE = _configured_profile("openlist")
S3_PROFILE = _configured_profile("s3")


@unittest.skipIf(LOCAL_PROFILE is None, "BLOCKED: isolated Local endurance profile is absent")
class RealLocalEnduranceTests(_EnduranceMixin, unittest.TestCase):
    profile = LOCAL_PROFILE

    def create_storage(self):
        assert self.profile.local_root is not None
        return LocalStorage("endurance-target", self.profile.local_root)


@unittest.skipIf(SMB_PROFILE is None, "BLOCKED: isolated SMB endurance profile is absent")
class RealSMBEnduranceTests(_EnduranceMixin, unittest.TestCase):
    profile = SMB_PROFILE

    def create_storage(self):
        profile = self.profile
        assert profile.host and profile.port and profile.share and profile.username
        assert profile.password and profile.remote_root
        storage = SMBStorage(
            SMBStorageConfig(
                "endurance-target",
                "SMB endurance acceptance",
                profile.host,
                profile.share,
                profile.username,
                profile.password,
                root_path=profile.remote_root,
                port=profile.port,
            )
        )
        storage.connect()
        return storage


@unittest.skipIf(OPENLIST_PROFILE is None, "BLOCKED: isolated OpenList endurance profile is absent")
class RealOpenListEnduranceTests(_EnduranceMixin, unittest.TestCase):
    profile = OPENLIST_PROFILE

    def create_storage(self):
        profile = self.profile
        assert profile.endpoint and profile.token and profile.remote_root
        storage = OpenListStorage(
            OpenListStorageConfig(
                "endurance-target",
                "OpenList endurance acceptance",
                profile.endpoint,
                profile.token,
                root_path=profile.remote_root,
                request_timeout=120,
            )
        )
        storage.health_check()
        return storage


@unittest.skipIf(S3_PROFILE is None, "BLOCKED: isolated S3 endurance profile is absent")
class RealS3EnduranceTests(_EnduranceMixin, unittest.TestCase):
    profile = S3_PROFILE

    def create_storage(self):
        profile = self.profile
        assert profile.endpoint and profile.bucket and profile.access_key
        assert profile.secret_key and profile.remote_root
        storage = S3Storage(
            S3StorageConfig(
                "endurance-target",
                "MinIO endurance acceptance",
                S3Provider.S3_COMPATIBLE,
                profile.bucket,
                profile.access_key,
                profile.secret_key,
                endpoint=profile.endpoint,
                root_prefix=profile.remote_root,
                force_path_style=True,
                multipart_threshold=5 * MIB,
                multipart_part_size=5 * MIB,
            )
        )
        storage.health_check()
        return storage
