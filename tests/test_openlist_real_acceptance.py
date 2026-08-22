from __future__ import annotations

import os
import tempfile
import unittest
import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath

from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.domain.organizer import (
    ExecutionStatus,
    OrganizePlan,
    PlanOperation,
    StorageLocation,
)
from mediaflow.domain.storage import StorageError, StorageErrorCode
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.openlist_storage import OpenListStorage, OpenListStorageConfig

CONFIRMATION = "DELETE_ONLY_GENERATED_MEDIAFLOW_ACCEPTANCE_DATA"


@dataclass(frozen=True)
class RealOpenListEnvironment:
    url: str
    token: str
    root: str


def resolve_real_openlist_environment(environ: dict[str, str]) -> RealOpenListEnvironment:
    names = (
        "TEST_OPENLIST_URL",
        "TEST_OPENLIST_TOKEN",
        "TEST_OPENLIST_ROOT",
        "TEST_OPENLIST_DESTRUCTIVE_CONFIRM",
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
    return RealOpenListEnvironment(
        environ["TEST_OPENLIST_URL"], environ["TEST_OPENLIST_TOKEN"], root
    )


def _real_environment_or_skip() -> RealOpenListEnvironment | None:
    relevant = {key: value for key, value in os.environ.items() if key.startswith("TEST_OPENLIST_")}
    if not relevant:
        return None
    return resolve_real_openlist_environment(dict(os.environ))


REAL_ENVIRONMENT = _real_environment_or_skip()


class RealOpenListAcceptanceGateTests(unittest.TestCase):
    def test_requires_every_field_exact_confirmation_and_dedicated_root(self) -> None:
        valid = {
            "TEST_OPENLIST_URL": "https://openlist.example.invalid",
            "TEST_OPENLIST_TOKEN": "secret",
            "TEST_OPENLIST_ROOT": "/qa/mediaflow-acceptance-openlist",
            "TEST_OPENLIST_DESTRUCTIVE_CONFIRM": CONFIRMATION,
        }
        self.assertEqual(
            "/qa/mediaflow-acceptance-openlist", resolve_real_openlist_environment(valid).root
        )
        for mutation in (
            {"TEST_OPENLIST_TOKEN": ""},
            {"TEST_OPENLIST_DESTRUCTIVE_CONFIRM": "yes"},
            {"TEST_OPENLIST_ROOT": "/"},
            {"TEST_OPENLIST_ROOT": "/media"},
            {"TEST_OPENLIST_ROOT": "relative/mediaflow-acceptance-openlist"},
            {"TEST_OPENLIST_ROOT": "/qa/../mediaflow-acceptance-openlist"},
        ):
            candidate = {**valid, **mutation}
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                resolve_real_openlist_environment(candidate)


@unittest.skipIf(
    REAL_ENVIRONMENT is None,
    "BLOCKED: dedicated real OpenList acceptance environment and confirmation are absent",
)
class RealOpenListAcceptanceMatrixTests(unittest.TestCase):
    def test_real_adapter_and_transfer_matrix(self) -> None:
        environment = REAL_ENVIRONMENT
        assert environment is not None
        config = OpenListStorageConfig(
            "openlist-acceptance",
            "OpenList isolated acceptance",
            environment.url,
            environment.token,
            root_path=environment.root,
        )
        run = f"run-{uuid.uuid4().hex}"
        payload = b"mediaflow-openlist-acceptance-v1"
        with OpenListStorage(config) as openlist, tempfile.TemporaryDirectory() as local_root:
            local = LocalStorage("local-acceptance", local_root)
            openlist.health_check()
            self.assertFalse(openlist.exists(run), "generated run child unexpectedly exists")
            openlist.create_directory(run)
            try:
                self._adapter_lifecycle(openlist, run, payload)
                self._transfer_matrix(openlist, local, run, payload)
            finally:
                self._cleanup_generated_child(openlist, run)
            self.assertFalse(openlist.exists(run))

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
