"""Task 42.2 P1 #1 fix: the reviewed Manual plan survives into run-item detail.

This module proves the AC-T4 repair end to end and at each boundary:

A. the **real managed journey** (reusing ``tests.test_v2_manual_organize``'s
   ``_JourneyFixtureMixin``: real ``LocalStorage`` roots, real scanner/FileIndex,
   managed snapshot pins, real intent/Preview/execution services, the real
   Worker and a real ``MediaFlowApi`` graph): after the Worker completes a
   Manual Organize execution, ``GET
   /api/v1/operations/runs/{taskId}/items/{taskItemId}`` publishes
   ``planEvidence`` — the durable reviewed plan (RecognitionType C with
   NamingPolicy A / ClassificationPolicy A stays C on every detail read), the
   analysis stages, the destination, the persisted per-step effects and the
   cleanup truth on the Result — while the read itself mutates nothing;

B. a coordinator-style item that never went through the Manual journey (no
   ``manual_execution_items`` linkage) gets the exact explicit
   ``{"available": False, "reason": "no_reviewed_manual_execution_plan"}`` —
   never a fabricated plan and never an erasure of its durable Result;

C. the repository join ``manual_execution_item_for_task_item`` returns the
   persisted raw plan (including the executor ``executionPlan`` input it keeps
   durably) for admitted work, ``None`` for unknown ids and ``ValueError`` for
   blank/oversized ids — while the operator projection drops ``executionPlan``
   everywhere;

D. the operator projection ``manual_execution_plan_evidence_operator`` is
   ``None`` for no document, and for a persisted plan whose raw
   ``executionPlan`` holds a host path and destructive authority it publishes
   only the bounded ``destructiveImplications`` — no ``executionPlan``, no
   ``/tmp/…`` path, no raw executor key — never leaking the executor input.

No production file is exercised by hand-written rows here except the isolated
fixture in test B, which uses exactly the repository object API the
coordinator path persists through.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from mediaflow.application.operations_lifecycle import (
    manual_execution_plan_evidence_operator,
    run_item_evidence_document,
)
from mediaflow.domain.manual_execution import ManualExecutionStatus
from mediaflow.domain.task_persistence import PersistentTaskStatus, TaskItemStatus
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_operations_run_detail import _item, _result
from tests.test_operations_run_inventory import OPERATOR, request, task
from tests.test_v2_manual_organize import (
    _FORBIDDEN_DOCUMENT_SUBSTRINGS,
    _JourneyFixtureMixin,
)

_UNAVAILABLE_PLAN_EVIDENCE = {
    "available": False,
    "reason": "no_reviewed_manual_execution_plan",
}


def _serialized(value: object) -> str:
    return json.dumps(value, sort_keys=True)


class RunItemPlanEvidenceJourneyTests(_JourneyFixtureMixin, unittest.TestCase):
    """A. The real managed journey: reviewed plan evidence on the run-item read."""

    def _complete_manual_journey(self, value):
        """Intent -> choice C -> preview -> execute -> Worker completion."""

        intent = self._create_reviewed_intent(value)
        preview = self._create_preview(value, intent)
        status, execution = self._execute(value, preview, intent)
        self.assertEqual(202, status, execution)
        self.assertEqual("admitted", execution["status"])
        self.assertTrue(execution["taskId"])
        completed = value.worker.run_next()
        self.assertIsNotNone(completed)
        self.assertEqual(ManualExecutionStatus.COMPLETED, completed.status)
        return intent, preview, execution, completed

    def test_completed_item_evidence_publishes_the_reviewed_plan(self) -> None:
        with self.journey() as value:
            _intent, preview, execution, completed = self._complete_manual_journey(value)

            # The source really moved and the mutation stages are durable facts.
            self.assertFalse((value.source_root / "One.2001.mkv").exists())
            self.assertTrue(value.source.mutations)

            # Resolve the (task_id, task_item_id) join from BOTH durable reads:
            # the outcome document the operator sees and the repository row.
            execution_id = execution["executionId"]
            status, outcome = self._request(
                value, f"/api/v1/operations/organize/executions/{execution_id}"
            )
            self.assertEqual(200, status, outcome)
            self.assertEqual("completed", outcome["status"])
            self.assertEqual(1, len(outcome["items"]))
            task_item_id = outcome["items"][0]["taskItemId"]
            durable = value.repository.get_manual_execution(execution_id)
            self.assertIsNotNone(durable)
            assert durable is not None
            self.assertEqual(completed.task_id, durable.task_id)
            self.assertEqual(task_item_id, durable.items[0].task_item_id)
            task_id = durable.task_id

            # Freeze the file layout and the recorded Storage mutations so the
            # evidence read can be proven side-effect free.
            source_layout = sorted(
                str(p.relative_to(value.source_root)) for p in value.source_root.rglob("*")
            )
            target_layout = sorted(
                str(p.relative_to(value.target_root)) for p in value.target_root.rglob("*")
            )
            mutations_before = list(value.source.mutations) + list(value.target.mutations)

            status, evidence = self._request(
                value, f"/api/v1/operations/runs/{task_id}/items/{task_item_id}"
            )
            self.assertEqual(200, status, evidence)
            self.assertEqual(task_id, evidence["task_id"])
            self.assertEqual(task_item_id, evidence["item_id"])
            self.assertEqual(task_id, evidence["run_id"])
            self.assertEqual("none", evidence["sideEffects"])

            plan_evidence = evidence["planEvidence"]
            self.assertTrue(plan_evidence["available"], plan_evidence)
            self.assertEqual(preview["previewId"], plan_evidence["previewId"])
            self.assertEqual(execution_id, plan_evidence["executionId"])
            # The durable execution-item row's own terminal facts (its status is
            # the item outcome "success"; the execution status is "completed").
            self.assertEqual("success", plan_evidence["status"])
            self.assertEqual("completed", plan_evidence["stage"])
            self.assertEqual("verified_complete", plan_evidence["effectCertainty"])

            # The completed/uncertain effect partition is the durable truth.
            self.assertEqual(["CREATE_DIRECTORY", "MOVE"], plan_evidence["completedOperations"])
            self.assertEqual([], plan_evidence["uncertainEffects"])
            self.assertTrue(plan_evidence["effects"])
            actions = {effect["action"] for effect in plan_evidence["effects"]}
            self.assertTrue({"CREATE_DIRECTORY", "MOVE"} <= actions, actions)
            verified = [
                effect
                for effect in plan_evidence["effects"]
                if effect["verified"] is True and effect["certainty"] == "verified_complete"
            ]
            self.assertTrue(verified, plan_evidence["effects"])

            # The reviewed plan survives every detail read: RecognitionType C
            # with NamingPolicy A / ClassificationPolicy A is still C.
            plan = plan_evidence["plan"]
            self.assertIsNotNone(plan)
            assert plan is not None
            self.assertEqual("C", plan["recognitionType"])
            self.assertEqual("A", plan["policies"]["namingPolicyId"])
            self.assertEqual("A", plan["policies"]["classificationPolicyId"])
            self.assertEqual("C", plan["policies"]["metadataPolicyId"])
            self.assertEqual("A", plan["policies"]["organizePolicyId"])
            self.assertEqual("type-C", plan["policies"]["recognitionTypePolicyId"])
            self.assertEqual("C", plan["analysis"]["recognition"]["recognitionTypeId"])
            self.assertEqual("C", plan["mediaIdentity"]["recognitionTypeId"])

            # The bounded analysis stages and the reviewed destination are all
            # published from the persisted plan — no Provider or planner re-run.
            self.assertIsNotNone(plan_evidence["plan"]["analysis"])
            self.assertEqual("One", plan["analysis"]["parse"]["titleCandidate"])
            self.assertEqual(2001, plan["analysis"]["parse"]["year"])
            self.assertIsNotNone(plan["destination"])
            self.assertEqual("target", plan["destination"]["storageId"])
            self.assertEqual(
                "Movies/Anime/One (2001)/One (2001).mkv", plan["destination"]["relativePath"]
            )
            self.assertIsInstance(plan["conflicts"], list)
            self.assertIsNotNone(plan["capabilities"])
            self.assertEqual("ok", plan["capabilities"]["verdict"])
            self.assertEqual("MOVE", plan["operation"])
            self.assertEqual("ready", plan["planStatus"])
            self.assertTrue(plan["zeroMutation"])
            self.assertTrue(plan["bounded"])
            self.assertTrue(plan["deterministic"])

            # The Result carries its durable cleanup truth (the manual journey
            # executes without source-cleanup authority: disabled, zero steps).
            self.assertEqual(1, len(evidence["results"]))
            result = evidence["results"][0]
            self.assertEqual("disabled", result["cleanup_status"])
            self.assertEqual(0, result["cleanup_step_count"])
            self.assertEqual("C", result["recognition_type"])
            self.assertEqual("verified_complete", result["effect_certainty"])
            self.assertEqual(durable.items[0].result_id, result["result_id"])

            # Missing pipeline evidence never erases the durable reviewed plan.
            self.assertEqual([], evidence["evidence"])
            self.assertTrue(evidence["planEvidence"]["available"])

            # Secret-free with the same forbidden-substring discipline as the
            # rest of the manual journey surfaces.
            encoded = _serialized(evidence)
            for forbidden in _FORBIDDEN_DOCUMENT_SUBSTRINGS:
                self.assertNotIn(forbidden, encoded, f"plan evidence leaked {forbidden!r}")
            self.assertNotIn("authorizationId", encoded)

            # Zero additional mutation: the reads above changed nothing.
            status, repeated = self._request(
                value, f"/api/v1/operations/runs/{task_id}/items/{task_item_id}"
            )
            self.assertEqual(200, status)
            self.assertEqual(evidence, repeated)
            self.assertEqual(
                source_layout,
                sorted(str(p.relative_to(value.source_root)) for p in value.source_root.rglob("*")),
            )
            self.assertEqual(
                target_layout,
                sorted(str(p.relative_to(value.target_root)) for p in value.target_root.rglob("*")),
            )
            self.assertEqual(
                mutations_before, list(value.source.mutations) + list(value.target.mutations)
            )

    def test_unexecuted_item_still_had_the_admitted_plan_durable_after_execution_row(self) -> None:
        """The plan join exists at admission; the Worker only finishes it.

        This keeps the read contract honest: the evidence read never invents
        plan data — an item whose execution has not run still reports the
        admitted reviewed plan, and one with no linkage reports unavailable.
        """

        with self.journey() as value:
            intent = self._create_reviewed_intent(value)
            preview = self._create_preview(value, intent)
            status, execution = self._execute(value, preview, intent)
            self.assertEqual(202, status, execution)
            durable = value.repository.get_manual_execution(execution["executionId"])
            assert durable is not None
            status, evidence = self._request(
                value,
                f"/api/v1/operations/runs/{durable.task_id}/items/{durable.items[0].task_item_id}",
            )
            self.assertEqual(200, status, evidence)
            plan_evidence = evidence["planEvidence"]
            self.assertTrue(plan_evidence["available"])
            self.assertEqual("admitted", plan_evidence["status"])
            self.assertEqual([], plan_evidence["completedOperations"])
            self.assertEqual([], plan_evidence["effects"])
            # The reviewed plan is already the durable C-with-A-policies truth.
            self.assertEqual("C", plan_evidence["plan"]["recognitionType"])
            self.assertEqual("A", plan_evidence["plan"]["policies"]["namingPolicyId"])
            self.assertEqual([], evidence["results"])


class UnlinkedRunItemPlanEvidenceTests(unittest.TestCase):
    """B. An item without Manual execution linkage reads explicitly unavailable."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name, "runtime.sqlite3")
        self.repository = SQLiteTaskRepository(self.database)
        self.addCleanup(self.repository.close)
        self.api = MediaFlowApi(self.repository, None, principals=(OPERATOR,))

    def test_standalone_task_item_without_manual_execution_is_unavailable(self) -> None:
        task_id = "task-42-2-unlinked"
        self.repository.create_task(
            task(task_id, command="organize", status=PersistentTaskStatus.COMPLETED)
        )
        self.repository.upsert_item(
            _item(task_id, "item-0", TaskItemStatus.SUCCESS, plan_id="plan-42")
        )
        self.repository.append_result(_result(task_id, "item-0"))

        # No manual_execution_items row exists for this exact linkage.
        self.assertIsNone(self.repository.manual_execution_item_for_task_item(task_id, "item-0"))

        code, evidence, _statuses = request(
            self.api,
            "GET",
            f"/api/v1/operations/runs/{task_id}/items/item-0",
            token=OPERATOR.token,
        )
        self.assertEqual(200, code, evidence)
        self.assertEqual(_UNAVAILABLE_PLAN_EVIDENCE, evidence["planEvidence"])
        # Explicit unavailability never erases the durable Result.
        self.assertEqual(1, len(evidence["results"]))
        self.assertEqual("C", evidence["results"][0]["recognition_type"])
        self.assertEqual("item-0", evidence["item_id"])
        self.assertEqual("none", evidence["sideEffects"])

    def test_compositor_publishes_the_same_explicit_unavailability(self) -> None:
        # The application composition itself is the source of the stable code.
        document = run_item_evidence_document(
            item=_item("task-x", "item-x", TaskItemStatus.SUCCESS),
            checkpoint_document={},
            results=[],
            evidence=[],
            logs=[],
            plan_evidence=manual_execution_plan_evidence_operator(None),
        )
        self.assertEqual(_UNAVAILABLE_PLAN_EVIDENCE, document["planEvidence"])


class ManualExecutionItemLookupRepositoryTests(_JourneyFixtureMixin, unittest.TestCase):
    """C. The repository join behind the plan evidence read."""

    def test_unknown_ids_return_none(self) -> None:
        with self.journey() as value:
            self.assertIsNone(
                value.repository.manual_execution_item_for_task_item(
                    "task-that-does-not-exist", "item-that-does-not-exist"
                )
            )

    def test_blank_and_oversized_ids_raise_value_error(self) -> None:
        with self.journey() as value:
            too_long = "x" * 129
            for bad_task, bad_item in (
                ("", "item-1"),
                ("   ", "item-1"),
                ("task-1", ""),
                ("task-1", " \t\n "),
                (too_long, "item-1"),
                ("task-1", too_long),
            ):
                with self.subTest(task=bad_task[:8], item=bad_item[:8]):
                    with self.assertRaises(ValueError):
                        value.repository.manual_execution_item_for_task_item(bad_task, bad_item)

    def test_admitted_item_returns_the_persisted_plan_and_operator_drops_execution_plan(
        self,
    ) -> None:
        with self.journey() as value:
            intent = self._create_reviewed_intent(value)
            preview = self._create_preview(value, intent)
            status, execution = self._execute(value, preview, intent)
            self.assertEqual(202, status, execution)
            durable = value.repository.get_manual_execution(execution["executionId"])
            assert durable is not None
            item = durable.items[0]

            raw = value.repository.manual_execution_item_for_task_item(
                durable.task_id, item.task_item_id
            )
            self.assertIsInstance(raw, dict)
            assert raw is not None
            self.assertEqual(item.execution_item_id, raw["execution_item_id"])
            self.assertEqual(durable.execution_id, raw["execution_id"])
            self.assertEqual(durable.preview_id, raw["preview_id"])
            self.assertEqual(durable.task_id, raw["task_id"])
            self.assertEqual(item.task_item_id, raw["task_item_id"])
            self.assertEqual("admitted", raw["status"])
            self.assertEqual((), raw["completed_operations"])
            self.assertEqual((), raw["uncertain_effects"])
            self.assertEqual((), raw["effects"])

            # The raw persisted plan keeps the exact reviewed executor input.
            plan = raw["plan"]
            self.assertIsInstance(plan, dict)
            self.assertEqual("C", plan["recognitionType"])
            self.assertEqual("A", plan["policies"]["namingPolicyId"])
            self.assertEqual("A", plan["policies"]["classificationPolicyId"])
            self.assertEqual("C", plan["policies"]["metadataPolicyId"])
            self.assertIn("executionPlan", plan)
            self.assertIsInstance(plan["executionPlan"], dict)

            # The operator projection publishes the reviewed plan WITHOUT the
            # raw executor input anywhere in its output.
            projected = manual_execution_plan_evidence_operator(raw)
            self.assertIsNotNone(projected)
            assert projected is not None
            encoded = _serialized(projected)
            self.assertNotIn("executionPlan", encoded)
            self.assertNotIn("sourcePath", encoded)
            self.assertNotIn("targetPath", encoded)
            self.assertNotIn("sourceLibraryRoot", encoded)
            self.assertEqual("C", projected["plan"]["recognitionType"])
            self.assertEqual(preview["previewId"], projected["previewId"])
            self.assertEqual(durable.execution_id, projected["executionId"])
            for forbidden in _FORBIDDEN_DOCUMENT_SUBSTRINGS:
                self.assertNotIn(forbidden, encoded, f"projection leaked {forbidden!r}")


class ManualExecutionPlanEvidenceOperatorTests(unittest.TestCase):
    """D. The bounded operator projection of the reviewed plan document."""

    def test_none_document_projects_none(self) -> None:
        self.assertIsNone(manual_execution_plan_evidence_operator(None))

    def test_host_paths_and_authority_never_leave_the_projection(self) -> None:
        document = {
            "execution_item_id": "ei-1",
            "execution_id": "execution-1",
            "preview_id": "preview-1",
            "preview_item_id": "preview-item-1",
            "task_id": "task-1",
            "task_item_id": "item-1",
            "status": "success",
            "stage": "completed",
            "result_id": "result-1",
            "effect_certainty": "verified_complete",
            "completed_operations": ("CREATE_DIRECTORY", "MOVE"),
            "uncertain_effects": (),
            "plan": {
                "recognitionType": "C",
                "mediaIdentity": None,
                "policies": {
                    "recognitionTypePolicyId": "type-C",
                    "metadataPolicyId": "C",
                    "namingPolicyId": "A",
                    "classificationPolicyId": "A",
                    "organizePolicyId": "A",
                },
                "analysis": None,
                "destination": None,
                "operation": "MOVE",
                "attachments": [],
                "capabilities": None,
                "conflicts": [],
                "warnings": [],
                "planStatus": "ready",
                "cleanupProjection": {
                    "mode": "empty_only",
                    "parent": "/srv/private/source/Season 1",
                    "ignorePatterns": ["*.nfo"],
                    "maxParentDirectories": 3,
                    "maxEntries": 24,
                    "matchedFiles": ["One.2001.mkv"],
                    "blockingEntries": [],
                    "expectedDirectoryOutcome": "remove_empty",
                    "permanentDelete": False,
                },
                # The exact executor input, written by a hostile or legacy
                # producer: host paths and destructive authority inside.
                "executionPlan": {
                    "sourcePath": "/tmp/secret.mkv",
                    "targetPath": "/tmp/Media/secret.mkv",
                    "mediaLibraryRoot": "/tmp/media-root",
                    "sourceLibraryRoot": "/tmp/library-root",
                    "overwriteAuthorized": True,
                    "sourceDirectoryCleanup": {"mode": "ignorable"},
                },
            },
            "effects": (),
        }

        projected = manual_execution_plan_evidence_operator(document)
        self.assertIsNotNone(projected)
        assert projected is not None
        encoded = _serialized(projected)
        self.assertNotIn("/tmp/secret.mkv", encoded)
        self.assertNotIn("/tmp/", encoded)
        self.assertNotIn("executionPlan", encoded)
        self.assertNotIn("overwriteAuthorized", encoded)
        self.assertNotIn("sourcePath", encoded)

        # The destructive implication is still explained, bounded and truthful.
        implications = projected["plan"]["destructiveImplications"]
        self.assertTrue(implications["overwriteRequired"])
        self.assertTrue(implications["sourceCleanupRequired"])
        self.assertIn("replace", implications["statement"])
        self.assertIn("delete the emptied source directories", implications["statement"])
        cleanup = projected["plan"]["cleanupProjection"]
        self.assertEqual("empty_only", cleanup["mode"])
        self.assertEqual("source/Season 1", cleanup["parent"])
        self.assertEqual(["*.nfo"], cleanup["ignorePatterns"])
        self.assertEqual(["One.2001.mkv"], cleanup["matchedFiles"])
        self.assertEqual("remove_empty", cleanup["expectedDirectoryOutcome"])
        self.assertFalse(cleanup["permanentDelete"])
        self.assertNotIn("/srv/private", _serialized(cleanup))

        # The bounded wrapper the run-evidence compositor applies keeps the
        # same guarantee even for the fully composed document.
        composed = run_item_evidence_document(
            item=_item("task-1", "item-1", TaskItemStatus.SUCCESS),
            checkpoint_document={},
            results=[],
            evidence=[],
            logs=[],
            plan_evidence=projected,
        )
        self.assertTrue(composed["planEvidence"]["available"])
        composed_encoded = _serialized(composed["planEvidence"])
        self.assertNotIn("/tmp/secret.mkv", composed_encoded)
        self.assertNotIn("executionPlan", composed_encoded)

    def test_projection_bounds_effect_and_operation_lists(self) -> None:
        occurred = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
        document = {
            "execution_item_id": "ei-2",
            "execution_id": "execution-2",
            "preview_id": "preview-2",
            "preview_item_id": "preview-item-2",
            "task_id": "task-2",
            "task_item_id": "item-2",
            "status": "partial_success",
            "stage": "organizing",
            "result_id": None,
            "effect_certainty": "attempted_unverified",
            "completed_operations": tuple(f"OP_{index}" for index in range(40)),
            "uncertain_effects": ("destination_state", "source_state"),
            "plan": {"recognitionType": "A", "executionPlan": None},
            "effects": tuple(
                {
                    "action": "MOVE",
                    "source_storage_id": "source",
                    "source_path": f"Media/part-{index}.mkv",
                    "destination_storage_id": "target",
                    "destination_path": f"Movies/part-{index}.mkv",
                    "verified": index == 0,
                    "certainty": "verified_complete" if index == 0 else "attempted_unverified",
                    "details": {"rollback": False},
                    "occurred_at": occurred.isoformat(),
                }
                for index in range(50)
            ),
        }
        projected = manual_execution_plan_evidence_operator(document)
        assert projected is not None
        self.assertLessEqual(len(projected["completedOperations"]), 32)
        self.assertLessEqual(len(projected["effects"]), 32)
        self.assertEqual(["destination_state", "source_state"], projected["uncertainEffects"])
        self.assertEqual("partial_success", projected["status"])
        self.assertTrue(
            any(effect["verified"] for effect in projected["effects"]), projected["effects"]
        )


if __name__ == "__main__":
    unittest.main()
