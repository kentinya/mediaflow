import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from mediaflow.application.organizer import OrganizePlanner, OrganizerExecutor, PlanningError
from mediaflow.domain.classification import ClassificationResult
from mediaflow.domain.library import MediaLibrary
from mediaflow.domain.metadata import MediaIdentity, MediaType
from mediaflow.domain.naming import NamingResult
from mediaflow.domain.organizer import (
    Conflict,
    ConflictType,
    ExecutionStatus,
    OrganizeOperation,
    OrganizeOperationType,
    OrganizePlan,
    OrganizePolicy,
    PlanOperation,
    PlanStatus,
)
from mediaflow.domain.recognition import RecognitionResult, RecognitionType, RecognitionTypePolicy
from mediaflow.infrastructure.local_storage import LocalStorage


class OrganizePlannerTest(unittest.TestCase):
    @staticmethod
    def _inputs(
        *, source="source.mkv", root="Movies", relative="Animation", directory="Movie (2001)"
    ):
        recognition_type = RecognitionType("A", "A")
        policy = RecognitionTypePolicy(
            "type-a",
            recognition_type,
            "A",
            "A",
            "A",
            OrganizePolicy("A", OrganizeOperationType.MOVE),
        )
        return dict(
            source_storage_id="local",
            source=source,
            recognition=RecognitionResult(recognition_type, "rule-a"),
            type_policy=policy,
            media_library=MediaLibrary("movies", "Movies", "local", root),
            naming=NamingResult(directory, "Movie (2001).mkv", "A", "A"),
            classification=ClassificationResult("movies", relative, "A", "A"),
            media_identity=MediaIdentity("tmdb", "129", MediaType.MOVIE, "Movie", year=2001),
        )

    def test_planning_produces_target_without_mutating_filesystem(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "Special.C.2025.mkv"
            source.write_bytes(b"media")
            target_directory = root / "Media" / "A" / "Special C (2025)"
            target = target_directory / "Special C (2025).mkv"
            before = sorted(path.relative_to(root) for path in root.rglob("*"))
            type_c = RecognitionType("C", "C")
            type_policy = RecognitionTypePolicy(
                "type-c",
                type_c,
                "metadata-c",
                "naming-a",
                "classification-a",
                OrganizePolicy("move", OrganizeOperationType.MOVE),
            )
            plan = OrganizePlanner().plan(
                source_storage_id="local",
                source="Special.C.2025.mkv",
                recognition=RecognitionResult(type_c, "rule-c"),
                type_policy=type_policy,
                media_library=MediaLibrary("main", "Main", "local", "Media"),
                naming=NamingResult("Special C (2025)", "Special C (2025).mkv"),
                classification=ClassificationResult("main", "A"),
            )
            after = sorted(path.relative_to(root) for path in root.rglob("*"))
            self.assertEqual(before, after)
            self.assertTrue(source.exists())
            self.assertEqual(b"media", source.read_bytes())
            self.assertFalse(target.exists())
            self.assertFalse(target_directory.exists())
            self.assertEqual("C", plan.recognition_type_id)
            self.assertEqual("Media/A/Special C (2025)/Special C (2025).mkv", plan.target)
            self.assertEqual(PlanOperation.MOVE, plan.operation)
            self.assertEqual((), plan.operations)

    def test_movie_and_tv_destination_include_classification_and_naming(self) -> None:
        movie = OrganizePlanner().plan(**self._inputs())
        tv_inputs = self._inputs(relative="Series", directory="Show (2024)/Season 01")
        tv_inputs["naming"] = NamingResult(
            "Show (2024)/Season 01",
            "Show - S01E01.mkv",
            directory_segments=("Show (2024)", "Season 01"),
        )
        tv = OrganizePlanner().plan(**tv_inputs)
        self.assertEqual("Movies/Animation/Movie (2001)/Movie (2001).mkv", movie.destination)
        self.assertEqual("Movies/Series/Show (2024)/Season 01/Show - S01E01.mkv", tv.destination)

    def test_same_source_destination_is_noop(self) -> None:
        values = self._inputs(source="Movies/Animation/Movie (2001)/Movie (2001).mkv")
        plan = OrganizePlanner().plan(**values)
        self.assertEqual(PlanOperation.NOOP, plan.operation)
        self.assertEqual(PlanStatus.NOOP, plan.status)
        self.assertEqual((), plan.conflicts)

    def test_read_only_conflict_detection(self) -> None:
        class ExistsOnlyStorage:
            storage_id = "local"

            def exists(self, path):
                return True

        values = self._inputs()
        destination = "Movies/Animation/Movie (2001)/Movie (2001).mkv"
        plan = OrganizePlanner().plan(
            **values,
            target_storage=ExistsOnlyStorage(),
            claimed_destinations={destination: "other.mkv"},
            known_media={("tmdb", "129"): "existing/movie.mkv"},
        )
        self.assertEqual(PlanStatus.CONFLICT, plan.status)
        self.assertEqual(
            {
                ConflictType.DESTINATION_EXISTS,
                ConflictType.TARGET_COLLISION,
                ConflictType.DUPLICATE_MEDIA,
            },
            {item.type for item in plan.conflicts},
        )

    def test_invalid_destination_is_skipped_without_exposing_unsafe_target(self) -> None:
        values = self._inputs(relative="../escape")
        plan = OrganizePlanner().plan(**values)
        self.assertEqual(PlanOperation.SKIP, plan.operation)
        self.assertEqual(PlanStatus.INVALID, plan.status)
        self.assertEqual("", plan.destination)
        self.assertEqual(ConflictType.INVALID_DESTINATION, plan.conflicts[0].type)

    def test_absolute_configured_root_is_allowed_and_normalized(self) -> None:
        values = self._inputs(root="/media/Movies/", relative="Animation")
        plan = OrganizePlanner().plan(**values)
        self.assertEqual(PlanStatus.READY, plan.status)
        self.assertEqual(
            "/media/Movies/Animation/Movie (2001)/Movie (2001).mkv",
            plan.destination,
        )
        self.assertEqual((), plan.operations)
        self.assertEqual("/media/Movies/", plan.media_library_root)
        self.assertEqual("Animation/Movie (2001)/Movie (2001).mkv", plan.relative_destination)

    def test_plan_preserves_absolute_source_and_portable_relative_destination(self) -> None:
        source = "/mnt/HDD_2/Media/电影/千与千寻 (2001)/千与千寻 (2001).mkv"
        plan = OrganizePlanner().plan(**self._inputs(source=source))
        self.assertEqual(source, plan.source)
        self.assertEqual("Movies/Animation/Movie (2001)/Movie (2001).mkv", plan.destination)
        self.assertFalse(plan.destination.startswith("/"))

    def test_absolute_classification_relative_path_is_rejected(self) -> None:
        plan = OrganizePlanner().plan(**self._inputs(relative="/Animation"))
        self.assertEqual(PlanStatus.INVALID, plan.status)
        self.assertEqual(PlanOperation.SKIP, plan.operation)
        self.assertEqual("", plan.destination)
        self.assertEqual(ConflictType.INVALID_DESTINATION, plan.conflicts[0].type)

    def test_naming_traversal_is_rejected(self) -> None:
        values = self._inputs()
        values["naming"] = NamingResult("..", "movie.mkv", directory_segments=("..",))
        plan = OrganizePlanner().plan(**values)
        self.assertEqual(PlanStatus.INVALID, plan.status)
        self.assertEqual("", plan.destination)
        self.assertEqual(ConflictType.INVALID_DESTINATION, plan.conflicts[0].type)

    def test_c_identity_is_preserved_when_a_policies_are_reused(self) -> None:
        values = self._inputs()
        type_c = RecognitionType("C", "C")
        values["recognition"] = RecognitionResult(type_c, "rule-c")
        values["type_policy"] = RecognitionTypePolicy(
            "type-c", type_c, "C", "A", "A", OrganizePolicy("A", OrganizeOperationType.MOVE)
        )
        values["naming"] = NamingResult("Movie (2001)", "Movie (2001).mkv", "A", "C")
        values["classification"] = ClassificationResult("movies", "Animation", "A", "C")
        plan = OrganizePlanner().plan(**values)
        self.assertEqual("C", plan.recognition_type_id)
        self.assertEqual("A", plan.naming_policy_id)
        self.assertEqual("A", plan.classification_policy_id)

    def test_copy_link_and_forbidden_policy_operations_map_to_plan_vocabulary(self) -> None:
        for policy_operation, expected in (
            (OrganizeOperationType.COPY, PlanOperation.COPY),
            (OrganizeOperationType.HARD_LINK, PlanOperation.LINK),
            (OrganizeOperationType.SOFT_LINK, PlanOperation.LINK),
            (OrganizeOperationType.DELETE, PlanOperation.SKIP),
        ):
            with self.subTest(operation=policy_operation):
                values = self._inputs()
                recognition_type = values["recognition"].recognition_type
                values["type_policy"] = RecognitionTypePolicy(
                    "type-a",
                    recognition_type,
                    "A",
                    "A",
                    "A",
                    OrganizePolicy("operation", policy_operation),
                )
                self.assertEqual(expected, OrganizePlanner().plan(**values).operation)

    def test_mismatched_recognition_policy_is_rejected(self) -> None:
        type_a, type_c = RecognitionType("A", "A"), RecognitionType("C", "C")
        policy = RecognitionTypePolicy(
            "type-a",
            type_a,
            "metadata-a",
            "naming-a",
            "classification-a",
            OrganizePolicy("move", OrganizeOperationType.MOVE),
        )
        with self.assertRaises(PlanningError):
            OrganizePlanner().plan(
                source_storage_id="source",
                source="file.mkv",
                recognition=RecognitionResult(type_c, "rule-c"),
                type_policy=policy,
                media_library=MediaLibrary("main", "Main", "target", "/Media"),
                naming=NamingResult("Movie", "Movie.mkv"),
                classification=ClassificationResult("main", "A"),
            )

    def test_executor_defaults_to_dry_run_for_legacy_mutation_operations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.mkv").write_bytes(b"source")
            storage = LocalStorage("local", root)
            base = {
                "source_storage_id": "local",
                "target_storage_id": "local",
                "source": "source.mkv",
                "target": "target.mkv",
                "recognition_type_id": "A",
                "naming_policy_id": "A",
                "classification_policy_id": "A",
                "organize_policy_id": "move",
            }
            delete_plan = OrganizePlan(
                **base,
                operations=(OrganizeOperation(OrganizeOperationType.DELETE, None, "source.mkv"),),
            )
            overwrite_plan = OrganizePlan(
                **base,
                operations=(
                    OrganizeOperation(
                        OrganizeOperationType.MOVE, "source.mkv", "target.mkv", overwrite=True
                    ),
                ),
            )

            delete_result = OrganizerExecutor().execute(delete_plan, {"local": storage})
            overwrite_result = OrganizerExecutor().execute(overwrite_plan, {"local": storage})
            self.assertEqual(ExecutionStatus.DRY_RUN, delete_result.status)
            self.assertEqual(ExecutionStatus.DRY_RUN, overwrite_result.status)
            self.assertEqual(b"source", (root / "source.mkv").read_bytes())
            self.assertFalse((root / "target.mkv").exists())

    def test_dry_run_move_copy_and_link_have_zero_mutations(self) -> None:
        class ExplodingStorage:
            def __getattr__(self, name):
                raise AssertionError(f"dry-run accessed Storage.{name}")

        base = OrganizePlanner().plan(**self._inputs())
        for operation in (PlanOperation.MOVE, PlanOperation.COPY, PlanOperation.LINK):
            result = OrganizerExecutor().execute(
                replace(base, operation=operation), {"local": ExplodingStorage()}
            )
            self.assertEqual(ExecutionStatus.DRY_RUN, result.status)
            self.assertEqual((), result.created_directories)
            self.assertEqual((), result.completed_operations)

    def test_local_move_copy_and_hard_link_execution(self) -> None:
        for operation in (PlanOperation.MOVE, PlanOperation.COPY, PlanOperation.LINK):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "source.mkv").write_bytes(b"media")
                storage = LocalStorage("local", root)
                plan = replace(
                    OrganizePlanner().plan(**self._inputs(source="source.mkv", root="Media")),
                    operation=operation,
                    target="Media/Animation/Movie (2001)/Movie (2001).mkv",
                    link_operation=OrganizeOperationType.HARD_LINK,
                )
                result = OrganizerExecutor().execute(plan, {"local": storage}, execute=True)
                self.assertEqual(ExecutionStatus.SUCCESS, result.status)
                target = root / plan.target
                self.assertEqual(b"media", target.read_bytes())
                self.assertEqual(
                    operation is not PlanOperation.MOVE, (root / "source.mkv").exists()
                )

    def test_execute_rejects_missing_source_invalid_plan_and_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = LocalStorage("local", directory)
            base = OrganizePlanner().plan(**self._inputs(source="missing.mkv"))
            missing = OrganizerExecutor().execute(base, {"local": storage}, execute=True)
            invalid = OrganizerExecutor().execute(
                replace(base, status=PlanStatus.INVALID, target=""),
                {"local": storage},
                execute=True,
            )
            conflict = OrganizerExecutor().execute(
                replace(
                    base,
                    status=PlanStatus.CONFLICT,
                    conflicts=(
                        Conflict(
                            ConflictType.DESTINATION_EXISTS,
                            base.source,
                            base.target,
                            "exists",
                        ),
                    ),
                ),
                {"local": storage},
                execute=True,
            )
            self.assertEqual(ExecutionStatus.FAILED, missing.status)
            self.assertEqual(ExecutionStatus.FAILED, invalid.status)
            self.assertEqual(ExecutionStatus.FAILED, conflict.status)

    def test_failure_after_directory_creation_is_partial(self) -> None:
        class PartialStorage:
            storage_id = "local"

            def __init__(self):
                self.created = []

            def exists(self, path):
                return path == "source.mkv"

            def stat(self, path):
                return type("Entry", (), {"size": 5})()

            def create_directory(self, path):
                self.created.append(path)

            def copy(self, source, target, *, overwrite=False):
                raise RuntimeError("copy failed")

        storage = PartialStorage()
        plan = replace(
            OrganizePlanner().plan(**self._inputs(source="source.mkv")),
            operation=PlanOperation.COPY,
        )
        result = OrganizerExecutor().execute(plan, {"local": storage}, execute=True)
        self.assertEqual(ExecutionStatus.PARTIAL, result.status)
        self.assertEqual(("CREATE_DIRECTORY",), result.completed_operations)

    def test_execution_result_is_logged_with_plan_context(self) -> None:
        class RecordingLogger:
            def __init__(self):
                self.records = []

            def log(self, level, message, **context):
                self.records.append((level, message, context))

        logger = RecordingLogger()
        plan = OrganizePlanner().plan(**self._inputs())
        result = OrganizerExecutor(logger).execute(plan, {})
        self.assertEqual(ExecutionStatus.DRY_RUN, result.status)
        self.assertEqual(plan.plan_id, logger.records[0][2]["plan_id"])
        self.assertEqual("MOVE", logger.records[0][2]["operation"])
        self.assertIn("timestamp", logger.records[0][2])

    def test_cross_storage_move_delete_failure_records_partial_copy(self) -> None:
        class DeleteFailingStorage:
            def __init__(self, delegate):
                self._delegate = delegate

            def __getattr__(self, name):
                return getattr(self._delegate, name)

            def delete(self, path):
                raise RuntimeError("delete failed")

        with (
            tempfile.TemporaryDirectory() as source_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            Path(source_root, "source.mkv").write_bytes(b"media")
            source = DeleteFailingStorage(LocalStorage("source", source_root))
            target = LocalStorage("target", target_root)
            plan = replace(
                OrganizePlanner().plan(**self._inputs(source="source.mkv")),
                source_storage_id="source",
                target_storage_id="target",
            )
            result = OrganizerExecutor().execute(
                plan, {"source": source, "target": target}, execute=True
            )
            self.assertEqual(ExecutionStatus.PARTIAL, result.status)
            self.assertIn("COPY", result.completed_operations)
            self.assertTrue(Path(source_root, "source.mkv").exists())
            self.assertTrue(Path(target_root, plan.target).exists())

    def test_cross_storage_move_size_mismatch_never_deletes_source_or_reports_success(self) -> None:
        class TruncatingTarget:
            storage_id = "target"

            def __init__(self, delegate):
                self._delegate = delegate

            def __getattr__(self, name):
                return getattr(self._delegate, name)

            def write(self, path, data, *, overwrite=False):
                data.read()
                self._delegate.write(path, b"x", overwrite=overwrite)

        with (
            tempfile.TemporaryDirectory() as source_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            source_path = Path(source_root, "source.mkv")
            source_path.write_bytes(b"complete-media")
            source = LocalStorage("source", source_root)
            target = TruncatingTarget(LocalStorage("target", target_root))
            plan = replace(
                OrganizePlanner().plan(**self._inputs(source="source.mkv")),
                source_storage_id="source",
                target_storage_id="target",
            )
            result = OrganizerExecutor().execute(
                plan, {"source": source, "target": target}, execute=True
            )
            self.assertEqual(ExecutionStatus.PARTIAL, result.status)
            self.assertIn("size mismatch", result.errors[0])
            self.assertTrue(source_path.exists())
            self.assertEqual(b"complete-media", source_path.read_bytes())
            self.assertEqual(b"x", Path(target_root, plan.target).read_bytes())

    def test_cross_storage_write_failure_never_deletes_source(self) -> None:
        class WriteFailingTarget:
            storage_id = "target"

            def exists(self, path):
                return False

            def create_directory(self, path):
                pass

            def write(self, path, data, *, overwrite=False):
                data.read(2)
                raise RuntimeError("injected target write failure")

        with tempfile.TemporaryDirectory() as source_root:
            source_path = Path(source_root, "source.mkv")
            source_path.write_bytes(b"complete-media")
            source = LocalStorage("source", source_root)
            plan = replace(
                OrganizePlanner().plan(**self._inputs(source="source.mkv")),
                source_storage_id="source",
                target_storage_id="target",
            )
            result = OrganizerExecutor().execute(
                plan, {"source": source, "target": WriteFailingTarget()}, execute=True
            )
            self.assertNotEqual(ExecutionStatus.SUCCESS, result.status)
            self.assertTrue(source_path.exists())
            self.assertEqual(b"complete-media", source_path.read_bytes())

    def test_executor_rejects_tampered_destination_before_storage_access(self) -> None:
        class ExplodingStorage:
            def __getattr__(self, name):
                raise AssertionError(f"tampered plan accessed Storage.{name}")

        plan = OrganizePlanner().plan(**self._inputs())
        result = OrganizerExecutor().execute(
            replace(plan, target="Movies/Tampered.mkv"),
            {"local": ExplodingStorage()},
            execute=True,
        )
        self.assertEqual(ExecutionStatus.FAILED, result.status)
        self.assertIn("does not match", result.errors[0])

    def test_permission_failure_is_failed_without_source_deletion(self) -> None:
        with (
            tempfile.TemporaryDirectory() as source_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            source_path = Path(source_root, "source.mkv")
            source_path.write_bytes(b"media")
            source = LocalStorage("source", source_root)
            target = LocalStorage("target", target_root, read_only=True)
            plan = replace(
                OrganizePlanner().plan(**self._inputs(source="source.mkv")),
                source_storage_id="source",
                target_storage_id="target",
                operation=PlanOperation.COPY,
            )
            result = OrganizerExecutor().execute(
                plan, {"source": source, "target": target}, execute=True
            )
            self.assertEqual(ExecutionStatus.FAILED, result.status)
            self.assertTrue(source_path.exists())
