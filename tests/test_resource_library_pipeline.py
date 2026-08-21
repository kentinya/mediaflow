from __future__ import annotations

import io
import json
import posixpath
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from mediaflow.application.library_pipeline import MediaLibraryResolver, ResourceLibraryScanner
from mediaflow.application.media_organizer import MediaOrganizerService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.scanner import StorageScanner
from mediaflow.application.strategy_test import (
    SyntheticMetadataProvider,
    strategy_runner_from_configuration,
)
from mediaflow.domain.classification import ClassificationResult
from mediaflow.domain.library import MediaLibrary, ResourceLibrary
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.organizer import ExecutionStatus
from mediaflow.domain.storage import StorageCapabilities, StorageEntry, StorageEntryType
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository
from mediaflow.infrastructure.memory_file_index import InMemoryFileIndexRepository
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration


class MemoryStorage:
    """Storage-protocol fake used as a remote/OpenList boundary, not a filesystem."""

    def __init__(self, storage_id: str, files: dict[str, bytes] | None = None) -> None:
        self.storage_id = storage_id
        self.name = storage_id
        self.read_only = False
        self.capabilities = StorageCapabilities(True, True, True, False, False)
        self.files = dict(files or {})
        self.directories = {""}
        self.mutations = 0
        for path in self.files:
            parent = posixpath.dirname(path)
            while parent:
                self.directories.add(parent)
                parent = posixpath.dirname(parent)

    def list(self, path):
        prefix = f"{path.rstrip('/')}/" if path else ""
        children = {}
        for candidate, content in self.files.items():
            if not candidate.startswith(prefix):
                continue
            remainder = candidate[len(prefix) :]
            name = remainder.split("/", 1)[0]
            child = f"{prefix}{name}".strip("/")
            is_directory = "/" in remainder
            children[name] = StorageEntry(
                name,
                child,
                StorageEntryType.DIRECTORY if is_directory else StorageEntryType.FILE,
                0 if is_directory else len(content),
                datetime(2020, 1, 1, tzinfo=UTC),
            )
        return tuple(children.values())

    def stat(self, path):
        if path in self.files:
            return StorageEntry(
                posixpath.basename(path),
                path,
                StorageEntryType.FILE,
                len(self.files[path]),
                datetime(2020, 1, 1, tzinfo=UTC),
            )
        if path in self.directories or any(
            item.startswith(f"{path.rstrip('/')}/") for item in self.files
        ):
            return StorageEntry(
                posixpath.basename(path),
                path,
                StorageEntryType.DIRECTORY,
                0,
                datetime(2020, 1, 1, tzinfo=UTC),
            )
        raise FileNotFoundError(path)

    def exists(self, path):
        return path in self.files or path in self.directories

    def read(self, path):
        return io.BytesIO(self.files[path])

    def write(self, path, data, *, overwrite=False):
        self.mutations += 1
        if path in self.files and not overwrite:
            raise FileExistsError(path)
        self.files[path] = bytes(data) if isinstance(data, bytes) else data.read()

    def create_directory(self, path):
        self.mutations += 1
        current = ""
        for part in path.split("/"):
            current = posixpath.join(current, part)
            self.directories.add(current)

    def move(self, source, target, *, overwrite=False):
        self.copy(source, target, overwrite=overwrite)
        self.delete(source)

    def copy(self, source, target, *, overwrite=False):
        self.mutations += 1
        self.files[target] = self.files[source]

    def delete(self, path):
        self.mutations += 1
        del self.files[path]

    def hard_link(self, source, target):
        raise NotImplementedError

    def soft_link(self, source, target):
        raise NotImplementedError


class ResourceLibraryPipelineTests(unittest.TestCase):
    def test_scan_cli_needs_no_path_or_metadata_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source_root = Path(temp, "source")
            target_root = Path(temp, "target")
            source_root.joinpath("Incoming").mkdir(parents=True)
            target_root.mkdir()
            source_root.joinpath("Incoming", "Movie.2024.mkv").write_bytes(b"movie")
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["storages"] = [
                {"id": "source", "type": "local", "rootPath": str(source_root)},
                {"id": "target", "type": "local", "rootPath": str(target_root)},
            ]
            document["resourceLibraries"] = [
                {
                    "id": "movies",
                    "storageId": "source",
                    "storagePath": "Incoming",
                    "rootPath": str(source_root / "Incoming"),
                }
            ]
            for policy in document["classificationPolicies"]:
                for rule in policy["rules"]:
                    rule["result"]["mediaLibraryId"] = "movies"
            document["mediaLibraries"] = [
                {
                    "id": "movies",
                    "storageId": "target",
                    "rootPath": "Movies",
                }
            ]
            config = Path(temp, "config.json")
            config.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            stdout, stderr = io.StringIO(), io.StringIO()
            code = final_main(
                ["--config", str(config), "scan", "--limit", "20"],
                stdout=stdout,
                stderr=stderr,
            )
            self.assertEqual(0, code, stderr.getvalue())
            self.assertIn("ResourceLibrary: movies", stdout.getvalue())
            self.assertIn("source:Incoming/Movie.2024.mkv", stdout.getvalue())
            self.assertTrue(source_root.joinpath("Incoming", "Movie.2024.mkv").exists())

    def test_scans_local_and_mock_openlist_without_mutation(self) -> None:
        local = MemoryStorage("local", {"Movies/Local.2024.mkv": b"local"})
        openlist = MemoryStorage("openlist", {"TV/Show.S01E01.mkv": b"remote"})
        libraries = (
            ResourceLibrary("movies", "Movies", "local", "Movies"),
            ResourceLibrary("tv", "TV", "openlist", "TV"),
        )
        found = []
        batch = ResourceLibraryScanner(
            StorageScanner({"local": local, "openlist": openlist}, InMemoryFileIndexRepository()),
            libraries,
            {"local": local, "openlist": openlist},
        ).scan_all(
            on_discovered=lambda library, file: found.append((library.library_id, file.path))
        )
        self.assertEqual(2, batch.discovered)
        self.assertEqual(
            {("movies", "Movies/Local.2024.mkv"), ("tv", "TV/Show.S01E01.mkv")},
            set(found),
        )
        self.assertEqual(0, local.mutations + openlist.mutations)

    def test_media_library_resolver_selects_storage_and_rejects_unknown(self) -> None:
        storage = MemoryStorage("target")
        resolver = MediaLibraryResolver(
            (
                MediaLibrary("movies", "Movies", "target", "Movies"),
                MediaLibrary("tv", "TV", "target", "TV"),
            ),
            {"target": storage},
        )
        resolved = resolver.resolve(ClassificationResult("tv", "Series"))
        self.assertEqual("target", resolved.storage_id)
        self.assertEqual("TV", resolved.root_path)
        with self.assertRaises(LookupError):
            resolver.resolve(ClassificationResult("missing", "Other"))

    def test_storage_aware_end_to_end_all_local_openlist_combinations(self) -> None:
        combinations = (
            ("local", "local-target"),
            ("local", "openlist-target"),
            ("openlist", "local-target"),
            ("openlist-a", "openlist-c"),
        )
        for source_id, target_id in combinations:
            with (
                self.subTest(source=source_id, target=target_id),
                tempfile.TemporaryDirectory() as temp,
            ):
                source_root = "b" if source_id == "openlist-a" else "Incoming"
                source_path = f"{source_root}/Spirited.Away.2001.mkv"
                destination_root = "分类/Movies" if target_id == "openlist-c" else "Movies"
                source = MemoryStorage(source_id, {source_path: b"movie"})
                target = MemoryStorage(target_id)
                storages = {source_id: source, target_id: target}
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
                service = MediaOrganizerService(
                    strategy_runner_from_configuration(
                        configuration, MetadataProviderRegistry((provider,))
                    ),
                    StorageScanner(storages, InMemoryFileIndexRepository()),
                    storages,
                    {"movies": MediaLibrary("movies", "Movies", target_id, destination_root)},
                    configuration.recognition_type_policies,
                    JsonLinesOperationHistoryRepository(Path(temp, "history.jsonl")),
                )
                library = ResourceLibrary("movies", "Movies", source_id, source_root)
                preview = service.process_all_libraries((library,))
                self.assertEqual(ExecutionStatus.DRY_RUN, preview.items[0].execution.status)
                self.assertEqual(0, source.mutations + target.mutations)
                plan = preview.items[0].plan
                self.assertEqual(source_id, plan.source_location.storage_id)
                self.assertEqual(source_path, plan.source_location.path)
                self.assertEqual(target_id, plan.destination_location.storage_id)
                self.assertTrue(
                    plan.destination_location.path.startswith(f"{destination_root}/Anime/")
                )
                executed = service.process_all_libraries((library,), execute=True)
                self.assertEqual(ExecutionStatus.SUCCESS, executed.items[0].execution.status)
                self.assertFalse(source.exists(source_path))
                self.assertTrue(target.exists(executed.items[0].plan.destination_location.path))


if __name__ == "__main__":
    unittest.main()
