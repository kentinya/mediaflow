"""Task45.6 RO-8 acceptance: independent Preview retirement and shared analysis.

These tests exercise the real application boundary for the retired independent
Preview product:

* the old CLI commands, API routes and Web destinations are gone and answer as
  ordinary unsupported/not-found results rather than compatibility shims;
* a fresh runtime database has no independent Preview-only tables, while the
  shared organize plan evidence (``manual_previews``) is retained;
* the shared Organize DryRun analysis (public ``organize`` without
  ``--execute`` and the Web preparation chain) produces the same complete fixed
  plan, records conflicts/unready branches as findings only, creates no formal
  execution backlog, grants no execution authority and mutates no Storage;
* the retained Automation grant binds definition/config/permission bounds
  without depending on the retired product.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.manual_organize import (
    ManualOrganizeIntentService,
    ManualSourceIdentity,
)
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.strategy_test import SyntheticMetadataProvider
from mediaflow.domain.manual_organize_preview import ManualPreviewItemStatus
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.source_evidence import (
    OccurrenceState,
    occurrence_id_for,
    source_fingerprint,
)
from mediaflow.domain.storage import StorageEntryType
from mediaflow.domain.task_persistence import TaskItemStatus
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.runtime_configuration import (
    load_runtime_configuration,
    with_managed_snapshot,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

EXAMPLES = Path("config/strategy.example.json")

#: Every module that made up the retired independent Preview product.  Importing
#: any of them must now fail: there is no durable analysis service, no definition
#: Preview service and no dedicated domain model left behind under a new name.
RETIRED_MODULES = (
    "mediaflow.application.preview_analysis",
    "mediaflow.application.automation_task_definition_preview",
    "mediaflow.domain.automation_task_definition_preview",
)

#: The independent Preview-only schema a fresh runtime must never create.
RETIRED_TABLES = (
    "preview_analyses",
    "automation_task_definition_previews",
    "automation_task_definition_preview_items",
)


def _request(api, method, path, *, token="admin-token", body=None, query=""):
    raw = b"" if body is None else json.dumps(body).encode()
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(raw)),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
        "wsgi.input": io.BytesIO(raw),
    }
    payload = b"".join(api(environ, lambda status, _headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(payload)


def _cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = final_main(argv, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


class RetiredPreviewModuleTests(unittest.TestCase):
    def test_retired_modules_cannot_be_imported(self):
        for module in RETIRED_MODULES:
            with self.subTest(module=module):
                with self.assertRaises(ModuleNotFoundError):
                    __import__(module)


class RetiredPreviewCliTests(unittest.TestCase):
    def test_old_cli_preview_commands_are_ordinary_usage_errors(self):
        for argv in (
            ["preview"],
            ["batch", "preview"],
            ["jobs", "submit", "preview"],
        ):
            with self.subTest(argv=argv):
                out, err = io.StringIO(), io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    with self.assertRaises(SystemExit) as raised:
                        final_main(argv, stdout=out, stderr=err)
                self.assertEqual(2, raised.exception.code)
                self.assertIn("invalid choice", err.getvalue())

    def test_cli_help_does_not_advertise_the_retired_product(self):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit):
            final_main(["--help"], stdout=io.StringIO(), stderr=io.StringIO())
        rendered = out.getvalue()
        self.assertNotIn("preview", rendered)
        self.assertIn("organize", rendered)


class RetiredPreviewApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.repository = SQLiteTaskRepository(Path(self.directory.name, "runtime.sqlite3"))
        self.api = MediaFlowApi(
            self.repository,
            None,
            principals=(
                ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ})),
            ),
        )

    def tearDown(self):
        self.repository.close()
        self.directory.cleanup()

    def test_old_preview_routes_are_ordinary_not_found(self):
        for method, path, body in (
            ("POST", "/api/v1/operations/previews", {"scopeKind": "resource_library"}),
            ("GET", "/api/v1/operations/previews", None),
            ("GET", "/api/v1/operations/previews/p-1", None),
            (
                "POST",
                "/api/v1/automation/task-definitions/definition/preview",
                {},
            ),
            ("GET", "/api/v1/automation/task-definitions/definition/previews", None),
            (
                "GET",
                "/api/v1/automation/task-definitions/definition/previews/p-1",
                None,
            ),
            (
                "POST",
                "/api/v1/automation/task-definitions/definition/preview-analyses",
                {},
            ),
            (
                "POST",
                "/api/v1/operations/organize/intents/intent-1/preview-analyses",
                {"expectedVersion": 1},
            ),
            ("GET", "/api/v1/operations/automation/preview-analyses", None),
            ("GET", "/api/v1/operations/automation/preview-analyses/a-1", None),
        ):
            with self.subTest(method=method, path=path):
                status, document = _request(self.api, method, path, body=body, token="admin-token")
                self.assertIn(status, (404, 503), document)
                self.assertNotIn("previewId", document)

    def test_retired_routes_create_no_durable_work(self):
        _request(
            self.api,
            "POST",
            "/api/v1/automation/task-definitions/definition/preview",
            body={},
        )
        _request(
            self.api,
            "POST",
            "/api/v1/operations/previews",
            body={"scopeKind": "resource_library"},
        )
        self.assertEqual((), self.repository.list_jobs())
        self.assertEqual((), self.repository.list_tasks())

    def test_fresh_schema_has_no_independent_preview_tables(self):
        tables = {
            row[0]
            for row in self.repository._connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for retired in RETIRED_TABLES:
            with self.subTest(table=retired):
                self.assertNotIn(retired, tables)
        # The shared organize plan evidence is retained.
        self.assertIn("manual_previews", tables)
        self.assertIn("manual_preview_items", tables)


class RetainedRunOncePlanTests(unittest.TestCase):
    """The Run once page keeps its exact plan across a reload and a reopen.

    The retired independent Preview was where an operator reviewed a plan.  The
    retained shared journey is the definition-bound Run once: it freezes the
    complete bounded manifest and the resident Worker runs the shared
    zero-mutation analysis over its linked intent on this same durable run.
    The plan identity must be re-readable from an ordinary Run once GET and
    from a reopened runtime store, so a reload, reconnect or restart restores
    the same plan instead of losing it or re-running the analysis.
    """

    def test_frozen_run_once_plan_is_reread_from_the_durable_intent(self):
        from tests.test_v2_automation_operations import (
            _DEFINITION,
            AutomationOperatorJourneyTests,
            _request,
        )

        journey = AutomationOperatorJourneyTests()
        with journey._journey() as value:
            api = value.api
            status, admitted = _request(
                api,
                f"/api/v1/operations/automation/task-definitions/{_DEFINITION['id']}/run-once",
                method="POST",
                body={},
            )
            self.assertEqual(202, status, admitted)
            discovery_id = admitted["discoveryId"]
            path = f"/api/v1/operations/automation/run-once/{discovery_id}"
            for index in range(16):
                worked = api._media_discovery.claim_and_run(
                    worker_id=f"plan-worker-{index}",
                    claim_token=f"plan-token-{index}",
                )
                self.assertIsNotNone(worked)
                if worked.terminal:
                    break
            else:
                self.fail("the Run once did not settle in the step budget")
            status, ready = _request(api, path)
            self.assertEqual(200, status)
            self.assertTrue(ready["actions"]["finalize"]["available"])
            # Before the freeze there is no plan identity and no linked intent.
            self.assertIsNone(ready["previewId"])
            self.assertIsNone(ready["intentId"])

            status, frozen = _request(
                api,
                f"{path}/finalize",
                method="POST",
                body={"expectedVersion": ready["version"]},
            )
            self.assertEqual(201, status, frozen)
            # Finalize defers the plan to the durable analysis stage on this
            # same run; no plan or analysis identity is produced inline.
            self.assertEqual("analyzing", frozen["phase"])
            self.assertIsNone(frozen["previewId"])
            self.assertNotIn("preview", frozen)
            self.assertIsNone(frozen["analysisId"])
            # The resident Worker links the exact plan on the same run.
            analyzed = api._media_discovery.claim_and_run(
                worker_id="plan-analysis-worker", claim_token="plan-analysis-token"
            )
            self.assertIsNotNone(analyzed)
            preview_id = analyzed.preview_id
            self.assertIsNotNone(preview_id)

            # An ordinary read of the same durable run resolves the exact plan.
            status, reread = _request(api, path)
            self.assertEqual(200, status)
            self.assertEqual("frozen", reread["phase"])
            self.assertEqual(preview_id, reread["previewId"])
            self.assertEqual(frozen["intentId"], reread["intentId"])
            self.assertTrue(reread["actions"]["preview"]["available"])
            self.assertEqual(
                f"/api/v1/operations/organize/previews/{preview_id}",
                reread["actions"]["preview"]["path"],
            )
            # The frozen manifest offers no second freeze, and the whole read
            # stayed zero-mutation.
            self.assertFalse(reread["actions"]["finalize"]["available"])
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            # The same association survives a reopen of the runtime store.
            intent_id = frozen["intentId"]
            database = Path(value.root, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as reopened:
                latest = reopened.get_latest_manual_preview(intent_id)
                self.assertEqual(preview_id, latest.preview_id)
                self.assertEqual(intent_id, latest.intent_id)
                self.assertTrue(latest.zero_mutation)


class RetainedAuthorizationPrecedentTests(unittest.TestCase):
    """The unattended grant keeps its analysis precedent without the product.

    The retired independent Preview used to be the required evidence before an
    unattended grant.  That role is now carried by the shared zero-mutation
    organize analysis a definition-bound Run once produces.  This proves the
    real API/Run-once assembly refuses a confirmed grant until that shared
    analysis exists, then admits it — with zero Storage mutation throughout and
    no grant row before the analysis is real.
    """

    def test_grant_requires_the_shared_analysis_then_admits_it(self):
        from tests.test_v2_automation_operations import (
            _DEFINITION,
            OPERATIONS_ROUTE,
            AutomationOperatorJourneyTests,
            _request,
        )

        journey = AutomationOperatorJourneyTests()
        with journey._journey() as value:
            api = value.api
            # A confirmed grant with no shared analysis is refused before any
            # grant row, audit row or Storage effect.
            status, refused = _request(
                api,
                f"/api/v1/automation/task-definitions/{_DEFINITION['id']}/grant",
                method="POST",
                body={"revisionId": value.active.revision_id, "confirmation": True},
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("unattended_execution_analysis_required", refused["error"]["code"])
            self.assertEqual((), value.repository.list_unattended_execution_grants())
            self.assertEqual(value.source.mutations, [])
            self.assertEqual(value.target.mutations, [])

            # The eligibility projection agrees with the durable admission.
            status, detail = _request(api, f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}")
            self.assertEqual(200, status)
            eligibility = detail["definition"]["grantEligibility"]
            self.assertFalse(eligibility["eligible"])
            self.assertNotIn("previewId", eligibility)

            # A real definition-bound Run once produces the shared analysis.
            preview_id = journey._run_shared_analysis(value)
            self.assertTrue(preview_id)
            status, detail = _request(api, f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}")
            self.assertEqual(200, status)
            self.assertTrue(detail["definition"]["grantEligibility"]["eligible"])

            # The same confirmed grant now succeeds, still with zero mutation.
            status, granted = _request(
                api,
                f"/api/v1/automation/task-definitions/{_DEFINITION['id']}/grant",
                method="POST",
                body={"revisionId": value.active.revision_id, "confirmation": True},
            )
            self.assertEqual(201, status, granted)
            self.assertEqual("active", granted["grant"]["status"])
            self.assertEqual(value.source.mutations, [])
            self.assertEqual(value.target.mutations, [])
            self.assertEqual(1, len(value.repository.list_unattended_execution_grants()))


class RetiredPreviewScheduleTests(unittest.TestCase):
    def test_preview_schedule_command_is_rejected(self):
        from mediaflow.domain.automation import AutomationCommand, CronSchedule, IntervalSchedule

        self.assertNotIn("preview", {item.value for item in AutomationCommand})
        with self.assertRaises(ValueError):
            IntervalSchedule("legacy", "preview", 60)
        with self.assertRaises(ValueError):
            CronSchedule("legacy", "preview", "* * * * *", "UTC")

    def test_old_schedule_document_value_is_rejected_not_defaulted(self):
        from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration

        document = json.loads(EXAMPLES.read_text(encoding="utf-8"))
        document["automation"] = {
            "schedules": [{"id": "legacy", "command": "preview", "intervalSeconds": 60}]
        }
        with self.assertRaisesRegex(ValueError, "must be organize"):
            load_runtime_configuration(document)


if __name__ == "__main__":
    unittest.main()


SNAPSHOT = ("revision-1", "a" * 64)


#: Every durable table that could carry an execution right.  An analysis must
#: leave all of them empty: it has no single-shot or unattended authority.
_AUTHORITY_TABLES = (
    "manual_executions",
    "manual_execution_authorizations",
    "unattended_execution_grants",
)


def _authority_rows(repository) -> dict[str, int]:
    """Non-zero execution-authority rows, so an empty dict proves none exist."""

    counts: dict[str, int] = {}
    for table in _AUTHORITY_TABLES:
        # Fixed table names from ``_AUTHORITY_TABLES``, never operator input.
        total = repository._connection.execute(
            f"SELECT COUNT(*) FROM {table}"  # noqa: S608
        ).fetchone()[0]
        if total:
            counts[table] = total
    return counts


class _AnalysisEnvironment:
    """One temporary local ResourceLibrary/MediaLibrary with a real config file."""

    def __init__(
        self,
        directory: str,
        *,
        subdir: str = "电影",
        filename: str = "Film.1999.mkv",
        attachments: bool = True,
        document_patch=None,
        existing_target: bool = False,
    ) -> None:
        root = Path(directory)
        self.root = root
        self.media = root / "HDD" / "Media" / subdir
        self.media.mkdir(parents=True)
        self.source_file = self.media / filename
        self.source_file.write_bytes(b"source-bytes")
        self.sidecar = self.media / f"{self.source_file.stem}.zh.srt"
        self.sidecar.write_bytes(b"subtitle-bytes")
        self.target_root = root / "HDD" / "Organized"
        self.target_root.mkdir(parents=True)
        self.target_file = (
            self.target_root
            / "Movies"
            / "Movies"
            / "其他电影"
            / "Film (1999) [tmdbid-603]"
            / "Film (1999).mkv"
        )
        if existing_target:
            self.target_file.parent.mkdir(parents=True)
            self.target_file.write_bytes(b"existing-target")
        self.database = root / "runtime.sqlite3"
        document = json.loads(EXAMPLES.read_text(encoding="utf-8"))
        document["storages"][0]["rootPath"] = str(root / "HDD")
        document["storages"][1]["rootPath"] = str(self.target_root)
        document["resourceLibraries"][0]["displayRootPath"] = str(root / "HDD" / "Media")
        for policy in document["organizePolicies"]:
            policy["attachments"]["enabled"] = attachments
        if document_patch is not None:
            document_patch(document)
        document["historyPath"] = str(root / "history.jsonl")
        document["persistence"] = {"databasePath": str(self.database)}
        self.document = document
        self.config = root / "config.json"
        self.config.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")

    def tree(self, root: Path) -> tuple[tuple[str, bytes | None], ...]:
        values = []
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root).as_posix()
            values.append((relative, None if path.is_dir() else path.read_bytes()))
        return tuple(values)

    def runtime_configuration(self):
        return with_managed_snapshot(
            load_runtime_configuration(json.loads(json.dumps(self.document))),
            snapshot_id=SNAPSHOT[0],
            digest=SNAPSHOT[1],
        )


def _candidates(*titles: str) -> tuple[MediaCandidate, ...]:
    return tuple(
        MediaCandidate("tmdb", str(602 + position), MediaType.MOVIE, title, None, 1999)
        for position, title in enumerate(titles, start=1)
    )


def _run_analysis_cli(environment: _AnalysisEnvironment, provider) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with patch(
        "mediaflow.final_cli.metadata_provider_registry_from_environment",
        return_value=MetadataProviderRegistry((provider,)),
    ):
        code = final_main(
            ["--config", str(environment.config), "organize", str(environment.media)],
            stdout=out,
            stderr=err,
        )
    return code, out.getvalue(), err.getvalue()


class SharedAnalysisCliTests(unittest.TestCase):
    """The public ``organize`` analysis records findings, never execution backlog.

    Every assertion runs the real CLI entry against a temporary local
    ResourceLibrary/MediaLibrary and a fake Provider, then reads the durable
    runtime: the analysis item, its persisted Result/evidence, the confirmation
    and review tables and the media bytes on both sides.
    """

    def test_conflict_analysis_records_the_full_plan_without_execution_backlog(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = _AnalysisEnvironment(directory, existing_target=True)
            source_before = environment.tree(environment.media)
            target_before = environment.tree(environment.target_root)
            code, out, err = _run_analysis_cli(
                environment, SyntheticMetadataProvider(_candidates("Film"))
            )
            self.assertEqual(0, code, f"{err}\n{out}")
            self.assertIn("ANALYSIS", out)
            self.assertNotIn("NEED_CONFIRM", out)

            with SQLiteTaskRepository(environment.database) as repository:
                tasks = repository.list_tasks()
                self.assertEqual(1, len(tasks))
                task = tasks[0]
                # Analysis carries no execution authority of any kind.
                self.assertFalse(task.execute_authorized)
                items = repository.list_items(task.task_id)
                self.assertEqual(1, len(items))
                self.assertEqual(TaskItemStatus.DRY_RUN, items[0].status)
                self.assertEqual("completed", items[0].stage)
                # No formal execution backlog item was created anywhere.
                self.assertEqual((), repository.list_confirmations())
                self.assertEqual((), repository.list_metadata_reviews())
                self.assertEqual((), repository.list_classification_reviews())
                self.assertEqual((), repository.list_recognition_reviews())
                self.assertEqual({}, _authority_rows(repository))
                self.assertEqual((), repository.list_unattended_execution_grants())
                # The complete fixed plan evidence is retained.
                results = repository.list_results(task.task_id)
                self.assertEqual(1, len(results))
                result = results[0]
                self.assertEqual("dry_run", result.status)
                self.assertEqual(TaskItemStatus.DRY_RUN.value, result.status)
                self.assertEqual("MOVE", result.operation)
                self.assertEqual(
                    "Movies/Movies/其他电影/Film (1999) [tmdbid-603]/Film (1999).mkv",
                    result.destination_path,
                )
                self.assertEqual(1, result.attachment_count)
                evidence = repository.list_evidence_for_item(items[0].item_id)
                self.assertEqual(1, len(evidence))
                plan = evidence[0].section("plan")
                self.assertTrue(plan.available)
                self.assertEqual(
                    "Movies/Movies/其他电影/Film (1999) [tmdbid-603]/Film (1999).mkv",
                    plan.value["target"],
                )
                self.assertEqual("conflict", plan.value["status"])
                self.assertEqual(
                    ["DESTINATION_EXISTS"],
                    [value["type"] for value in plan.value["conflicts"]],
                )
                self.assertEqual(1, len(plan.value["attachments"]))
                self.assertEqual("subtitle", plan.value["attachments"][0]["type"])
                self.assertTrue(plan.value["nextAction"])
                # A conflict finding is analysis evidence, not a decision item.
                self.assertNotIn("waiting_confirm", out)
            self.assertEqual(source_before, environment.tree(environment.media))
            self.assertEqual(target_before, environment.tree(environment.target_root))

    def test_each_unready_branch_records_a_finding_and_no_execution_backlog(self):
        cases = (
            (
                "recognition",
                {"subdir": "Unknown"},
                (),
                "waiting_recognition",
            ),
            (
                "metadata-selection",
                {"subdir": "电影", "filename": "Double.1999.mkv"},
                _candidates("Double", "Double"),
                "waiting_metadata",
            ),
            (
                "metadata-correction",
                {"subdir": "电影", "filename": "Missing.1999.mkv"},
                (),
                "waiting_metadata_correction",
            ),
            (
                "classification",
                {"subdir": "电影", "filename": "Unfiled.1999.mkv"},
                _candidates("Unfiled"),
                "waiting_classification",
            ),
        )

        def tv_only(document) -> None:
            document["classificationPolicies"][0]["rules"] = [
                {
                    "id": "tv-only",
                    "priority": 100,
                    "conditions": {"mediaType": ["tv"]},
                    "result": {"mediaLibraryId": "tv", "library": "TV", "path": ["TV"]},
                }
            ]

        for name, options, candidates, expected_outcome in cases:
            with self.subTest(branch=name), tempfile.TemporaryDirectory() as directory:
                if name == "classification":
                    options = {**options, "document_patch": tv_only}
                environment = _AnalysisEnvironment(directory, **options)
                source_before = environment.tree(environment.media)
                target_before = environment.tree(environment.target_root)
                code, out, err = _run_analysis_cli(
                    environment, SyntheticMetadataProvider(candidates)
                )
                self.assertEqual(0, code, f"{err}\n{out}")
                self.assertIn(f"outcome={expected_outcome}", out)
                with SQLiteTaskRepository(environment.database) as repository:
                    task = repository.list_tasks()[0]
                    items = repository.list_items(task.task_id)
                    self.assertEqual(1, len(items))
                    self.assertEqual(TaskItemStatus.DRY_RUN, items[0].status)
                    self.assertEqual((), repository.list_confirmations())
                    self.assertEqual((), repository.list_metadata_reviews())
                    self.assertEqual((), repository.list_metadata_corrections())
                    self.assertEqual((), repository.list_classification_reviews())
                    self.assertEqual((), repository.list_recognition_reviews())
                    evidence = repository.list_evidence_for_item(items[0].item_id)
                    self.assertEqual(1, len(evidence))
                    self.assertEqual(expected_outcome, evidence[0].outcome)
                    # The finding carries the exact correction the operator can
                    # make before an explicit re-analysis.
                    unavailable = evidence[0].section("plan").unavailable_reason
                    self.assertIn("next action:", unavailable)
                self.assertEqual(source_before, environment.tree(environment.media))
                self.assertEqual(target_before, environment.tree(environment.target_root))

    def test_analysis_cannot_be_promoted_to_execution_without_new_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = _AnalysisEnvironment(directory, existing_target=True)
            _run_analysis_cli(environment, SyntheticMetadataProvider(_candidates("Film")))
            with SQLiteTaskRepository(environment.database) as repository:
                task = repository.list_tasks()[0]
            out_buffer, err_buffer = io.StringIO(), io.StringIO()
            with patch(
                "mediaflow.final_cli.metadata_provider_registry_from_environment",
                return_value=MetadataProviderRegistry(
                    (SyntheticMetadataProvider(_candidates("Film")),)
                ),
            ):
                code = final_main(
                    [
                        "--config",
                        str(environment.config),
                        "tasks",
                        "retry-failed",
                        task.task_id,
                        "--execute",
                    ],
                    stdout=out_buffer,
                    stderr=err_buffer,
                )
            err = err_buffer.getvalue()
            # The analysis Task holds no execution authority, so retrying it
            # with --execute is refused before any Storage or Provider work.
            self.assertEqual(2, code)
            self.assertIn("not execute-authorized", err)
            with SQLiteTaskRepository(environment.database) as repository:
                self.assertEqual(1, len(repository.list_tasks()))
                self.assertEqual((), repository.list_confirmations())

    def test_shared_analysis_matches_web_preparation_for_the_same_source(self):
        """One source, one pin, one policy set: both entries agree exactly.

        The public CLI analysis and the Web preparation chain (the durable
        intent + fixed plan the Files/create pages render) are driven over the
        same temporary source and the same pinned strategy. Their target,
        operation, attachment set and conflict finding must be equivalent; only
        volatile identities may differ.
        """
        with tempfile.TemporaryDirectory() as directory:
            environment = _AnalysisEnvironment(directory, existing_target=True)
            provider = SyntheticMetadataProvider(_candidates("Film"))
            code, out, err = _run_analysis_cli(environment, provider)
            self.assertEqual(0, code, f"{err}\n{out}")
            with SQLiteTaskRepository(environment.database) as repository:
                task = repository.list_tasks()[0]
                item = repository.list_items(task.task_id)[0]
                evidence = repository.list_evidence_for_item(item.item_id)[0]
                cli_plan = evidence.section("plan").value
                cli_target = cli_plan["target"]
                cli_operation = cli_plan["operation"]
                cli_conflicts = sorted(
                    (value["type"], value["destination"]) for value in cli_plan["conflicts"]
                )
                cli_attachments = sorted(
                    (value["type"], value["operation"], value["suffix"])
                    for value in cli_plan["attachments"]
                )
                cli_result = repository.list_results(task.task_id)[0]
                cli_policies = {
                    "recognitionType": cli_result.recognition_type,
                    "metadataPolicyId": cli_result.metadata_policy_id,
                    "namingPolicyId": cli_result.naming_policy_id,
                    "classificationPolicyId": cli_result.classification_policy_id,
                    "organizePolicyId": cli_result.organize_policy_id,
                }
                runtime = environment.runtime_configuration()
                intent_service = ManualOrganizeIntentService(
                    repository,
                    configuration_resolver=lambda: runtime,
                    runtime_resolver=lambda *_: runtime,
                    storage_factory=lambda configuration, ids: configuration.create_storages(
                        storage_ids=ids
                    ),
                )
                # Exactly the Files path: observe the live Storage entry and
                # derive the immutable source identity from that observation.
                source_storage = LocalStorage("source-storage", environment.root / "HDD")
                storage_path = f"Media/电影/{environment.source_file.name}"
                entry = source_storage.stat(storage_path)
                self.assertIs(StorageEntryType.FILE, entry.entry_type)
                observed = source_fingerprint("source-storage", "source", entry)
                self.assertIs(OccurrenceState.VERIFIED, observed.state)
                occurrence = occurrence_id_for(
                    "source-storage", "source", entry.path, observed.value
                )
                identity = ManualSourceIdentity(
                    source_id=occurrence,
                    storage_id="source-storage",
                    resource_library_id="source",
                    path=entry.path,
                    filename=entry.name,
                    extension=entry.name.rsplit(".", 1)[-1].lower(),
                    size=entry.size,
                    modified_at=entry.modified_at,
                    observed_at=entry.modified_at,
                    stable_since=None,
                    occurrence_id=occurrence,
                    fingerprint=observed.value,
                    fingerprint_algorithm=observed.algorithm,
                    fingerprint_evidence=observed.evidence,
                    occurrence_state=observed.state.value,
                )
                intent = intent_service.create_from_sources((identity,), actor="operator")
                preview_service = ManualOrganizePreviewService(
                    repository,
                    intent_service,
                    runtime_resolver=lambda *_: runtime,
                    providers=MetadataProviderRegistry((provider,)),
                    storage_factory=lambda configuration, ids: configuration.create_storages(
                        storage_ids=ids
                    ),
                )
                preview = preview_service.create(
                    intent.intent_id,
                    actor="operator",
                    expected_version=intent.version,
                )
                self.assertEqual(ManualPreviewItemStatus.BLOCKED, preview.items[0].status)
                web_plan = preview.items[0].plan
                self.assertEqual(cli_target, web_plan["destination"]["path"])
                self.assertEqual(cli_operation, web_plan["operation"])
                self.assertEqual(
                    cli_conflicts,
                    sorted(
                        (value["type"], value["destination"]) for value in web_plan["conflicts"]
                    ),
                )
                self.assertEqual(
                    cli_attachments,
                    sorted(
                        (value["type"], value["operation"], value["suffix"])
                        for value in web_plan["attachments"]
                    ),
                )
                self.assertEqual(cli_policies["recognitionType"], web_plan["recognitionType"])
                for name in (
                    "metadataPolicyId",
                    "namingPolicyId",
                    "classificationPolicyId",
                    "organizePolicyId",
                ):
                    self.assertEqual(cli_policies[name], web_plan["policies"][name])
                # The Web preparation is also analysis only: durable plan
                # evidence, no execution backlog and no authority.
                self.assertEqual((), repository.list_confirmations())
                self.assertEqual({}, _authority_rows(repository))
                self.assertEqual((), repository.list_unattended_execution_grants())
                self.assertTrue(web_plan["zeroMutation"])
                # Both entries saw the same one primary file and one sidecar.
                self.assertEqual(1, len(web_plan["attachments"]))
