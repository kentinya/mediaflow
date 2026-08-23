from __future__ import annotations

import io
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from mediaflow.application.media_organizer import MediaOrganizerService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.scanner import StorageScanner
from mediaflow.application.strategy_test import (
    SyntheticMetadataProvider,
    strategy_runner_from_configuration,
)
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.cli import main
from mediaflow.domain.duplicates import DuplicateStatus, HashMode, HashPolicy
from mediaflow.domain.library import MediaLibrary, ResourceLibrary
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.organizer import ConflictType, ExecutionStatus
from mediaflow.domain.task_persistence import PersistentTaskStatus, TaskItemStatus
from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.memory_file_index import InMemoryFileIndexRepository
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration


class FinalIntegrationTests(unittest.TestCase):
    def test_configured_full_hash_adds_duplicate_conflict_without_execution(self) -> None:
        with (
            tempfile.TemporaryDirectory() as source_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            source_path = Path(source_root, "Spirited.Away.2001.mkv")
            source_path.write_bytes(b"same-media-content")
            source_storage = LocalStorage("source", source_root)
            target_storage = LocalStorage("target", target_root)
            storages = {"source": source_storage, "target": target_storage}
            base = development_strategy_configuration()
            full_hash = HashPolicy(HashMode.FULL, full_max_file_size=1024, chunk_size=4)
            type_policies = tuple(
                replace(
                    item,
                    organize_policy=replace(item.organize_policy, duplicate_detection=full_hash),
                )
                if item.organize_policy.policy_id == "A"
                else item
                for item in base.recognition_type_policies
            )
            configuration = replace(
                base,
                recognition_type_policies=type_policies,
            )
            provider = SyntheticMetadataProvider(
                (
                    MediaCandidate(
                        "tmdb",
                        "129",
                        MediaType.MOVIE,
                        "Spirited Away",
                        year=2001,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                )
            )
            service = MediaOrganizerService(
                strategy_runner_from_configuration(
                    configuration,
                    MetadataProviderRegistry((provider,)),
                    storages=storages,
                ),
                StorageScanner(storages, InMemoryFileIndexRepository()),
                storages,
                {"movies": MediaLibrary("movies", "Movies", "target", "Movies")},
                configuration.recognition_type_policies,
                JsonLinesOperationHistoryRepository(Path(source_root, "history.jsonl")),
                source_display_roots={"movies": source_root},
            )
            library = ResourceLibrary("movies", "Movies", "source", "")
            initial = service.process_file(
                source_path.as_posix(), resource_library=library, storage_path=source_path.name
            )
            self.assertEqual(initial.execution.status, ExecutionStatus.DRY_RUN)
            target_path = Path(target_root, initial.plan.target)
            target_path.parent.mkdir(parents=True)
            target_path.write_bytes(source_path.read_bytes())

            duplicate = service.process_file(
                source_path.as_posix(), resource_library=library, storage_path=source_path.name
            )
            self.assertIsNone(duplicate.execution)
            self.assertEqual(duplicate.plan.duplicate_comparison.status, DuplicateStatus.DUPLICATE)
            self.assertIn(
                ConflictType.DUPLICATE_MEDIA, {item.type for item in duplicate.plan.conflicts}
            )
            self.assertTrue(source_path.exists())
            self.assertEqual(target_path.read_bytes(), b"same-media-content")

    def test_runtime_configuration_and_final_analyze_cli(self) -> None:
        with (
            tempfile.TemporaryDirectory() as source_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            source = Path(source_root, "Movie.2024.mkv")
            source.write_bytes(b"movie")
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["resourceLibraries"] = [
                {
                    "id": "movies",
                    "name": "Movies",
                    "storageId": "source",
                    "rootPath": source_root,
                }
            ]
            document["storages"] = [
                {"id": "source", "type": "local", "rootPath": source_root},
                {"id": "target", "type": "local", "rootPath": target_root},
            ]
            document["mediaLibraries"] = [
                {
                    "id": "movies",
                    "name": "Movies",
                    "storageId": "target",
                    "rootPath": "Movies",
                },
                {
                    "id": "tv",
                    "name": "TV Shows",
                    "storageId": "target",
                    "rootPath": "TV Shows",
                },
            ]
            document["historyPath"] = str(Path(source_root, "history.jsonl"))
            runtime = load_runtime_configuration(document)
            self.assertEqual({"source", "target"}, set(runtime.create_storages()))
            self.assertEqual(
                {"movies", "tv"}, {item.library_id for item in runtime.media_libraries}
            )
            self.assertTrue(runtime.strategy.naming_policies)
            self.assertTrue(runtime.strategy.classification_policies)
            config_path = Path(source_root, "runtime.json")
            config_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            output, errors = io.StringIO(), io.StringIO()
            code = main(
                ["--config", str(config_path), "analyze", str(source), "--offline"],
                stdout=output,
                stderr=errors,
            )
            self.assertEqual(0, code)
            self.assertEqual("", errors.getvalue())
            self.assertIn("PARSER", output.getvalue())
            self.assertTrue(source.exists())

    def test_complete_batch_dryrun_execute_history_and_failure_isolation(self) -> None:
        with (
            tempfile.TemporaryDirectory() as source_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            source_path = Path(source_root, "Spirited.Away.2001.mkv")
            unknown_path = Path(source_root, "Unknown.Release.2024.mkv")
            source_path.write_bytes(b"movie")
            unknown_path.write_bytes(b"unknown")
            source_storage = LocalStorage("source", source_root)
            target_storage = LocalStorage("target", target_root)
            storages = {"source": source_storage, "target": target_storage}
            configuration = development_strategy_configuration()
            provider = SyntheticMetadataProvider(
                (
                    MediaCandidate(
                        "tmdb",
                        "129",
                        MediaType.MOVIE,
                        "Spirited Away",
                        year=2001,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                )
            )
            history = JsonLinesOperationHistoryRepository(Path(source_root, "history.jsonl"))
            library = ResourceLibrary("movies", "Movies", "source", "")
            task_repository = SQLiteTaskRepository(Path(source_root, "runtime.sqlite3"))
            coordinator = PersistentTaskCoordinator(task_repository, task_repository)
            task = coordinator.create("organize", execute_authorized=True)
            service = MediaOrganizerService(
                strategy_runner_from_configuration(
                    configuration, MetadataProviderRegistry((provider,))
                ),
                StorageScanner(storages, InMemoryFileIndexRepository()),
                storages,
                {"movies": MediaLibrary("movies", "Movies", "target", "Movies")},
                configuration.recognition_type_policies,
                history,
                source_display_roots={"movies": source_root},
                task_coordinator=coordinator,
                task_id=task.task_id,
            )

            preview = service.process_file(
                source_path.as_posix(),
                resource_library=library,
                storage_path=source_path.name,
            )
            self.assertEqual(ExecutionStatus.DRY_RUN, preview.execution.status)
            self.assertTrue(source_path.exists())
            self.assertFalse(Path(target_root, preview.plan.target).exists())

            progress = []
            batch = service.process_library(
                library,
                execute=True,
                progress=lambda done, total, source: progress.append((done, source)),
            )
            self.assertEqual(2, batch.total)
            self.assertEqual(1, batch.matched)
            self.assertEqual(1, batch.moved)
            self.assertEqual(1, batch.failed)
            self.assertEqual(2, len(progress))
            successful = next(item for item in batch.items if item.execution)
            self.assertEqual(ExecutionStatus.SUCCESS, successful.execution.status)
            self.assertFalse(source_path.exists())
            self.assertTrue(Path(target_root, successful.plan.target).exists())
            self.assertTrue(unknown_path.exists())
            self.assertEqual(3, len(history.list()))
            self.assertEqual("129", history.list()[1].provider_id)
            persisted = coordinator.finish(task.task_id, batch)
            self.assertEqual(persisted.status, PersistentTaskStatus.PARTIAL_SUCCESS)
            self.assertEqual(
                {item.status for item in task_repository.list_items(task.task_id)},
                {TaskItemStatus.SUCCESS, TaskItemStatus.FAILED},
            )
            task_repository.close()

    def test_history_persists_unicode_and_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = JsonLinesOperationHistoryRepository(Path(directory, "history.jsonl"))
            from mediaflow.domain.history import OperationHistoryRecord

            repository.append(
                OperationHistoryRecord.now(
                    "one",
                    "/电影/千与千寻.mkv",
                    "Movies/Anime/千与千寻.mkv",
                    "MOVE",
                    "FAILED",
                    provider_id="129",
                    title="千与千寻",
                    error="conflict",
                )
            )
            loaded = repository.list()
            self.assertEqual("千与千寻", loaded[0].title)
            self.assertEqual("conflict", loaded[0].error)

    def test_workflow_emits_stage_and_failure_logs(self) -> None:
        class RecordingLogger:
            def __init__(self):
                self.messages = []

            def log(self, level, message, **context):
                self.messages.append((level, message, context))

        with (
            tempfile.TemporaryDirectory() as source_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            source = Path(source_root, "Unknown.mkv")
            source.write_bytes(b"unknown")
            source_storage = LocalStorage("source", source_root)
            target_storage = LocalStorage("target", target_root)
            configuration = development_strategy_configuration()
            logger = RecordingLogger()
            service = MediaOrganizerService(
                strategy_runner_from_configuration(
                    configuration,
                    MetadataProviderRegistry((SyntheticMetadataProvider(()),)),
                ),
                StorageScanner({"source": source_storage}, InMemoryFileIndexRepository()),
                {"source": source_storage, "target": target_storage},
                {"movies": MediaLibrary("movies", "Movies", "target", "Movies")},
                configuration.recognition_type_policies,
                JsonLinesOperationHistoryRepository(Path(source_root, "history.jsonl")),
                source_display_roots={"movies": source_root},
                logger=logger,
            )
            result = service.process_file(
                source.as_posix(),
                resource_library=ResourceLibrary("movies", "Movies", "source", ""),
                storage_path=source.name,
            )
            self.assertIsNotNone(result.error)
            self.assertIn("media parsed and recognized", [item[1] for item in logger.messages])
            self.assertIn("media workflow failed", [item[1] for item in logger.messages])
