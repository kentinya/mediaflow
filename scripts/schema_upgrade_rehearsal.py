#!/usr/bin/env python3
"""Rehearse a genuine old-schema -> candidate schema upgrade from a git revision.

The rehearsal never trusts the working tree for the *base* side.  It extracts the
requested immutable revision with ``git archive`` into a temporary directory
outside the working tree, creates a database with that revision's own
``SQLiteTaskRepository`` and seeds a small but representative population through
that revision's own repository API.  Only then does it reopen the *same*
database with the candidate (this working tree) so the candidate's additive
migrations run over genuine legacy rows, and it proves every seeded row is still
readable with its original identity and pin values.

Both phases run in subprocesses with an explicit ``PYTHONPATH`` so the base
phase can never import candidate code and the candidate phase can never import
base code.

Usage::

    python scripts/schema_upgrade_rehearsal.py \\
        --base-sha 853973dbbf8289fa2ad40657033e94e870a690e4 --expect-schema 44

Exit codes: 0 every assertion passed, 1 an assertion failed, 2 the rehearsal
could not be set up or run at all.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")

#: The runtime schema the candidate is expected to report after its additive
#: upgrade.  When the flag is omitted the candidate's own ``SCHEMA_VERSION`` is
#: discovered from this working tree, so an ordinary schema bump never needs this
#: rehearsal to be edited.  Passing the flag pins the expectation explicitly and
#: makes an unexpected bump a hard failure instead of a silent retarget.
DEFAULT_CANDIDATE_SCHEMA: int | None = None

BASE_SEED_SCRIPT = '''
"""Create and seed one genuine base-schema database with the base revision code."""

from __future__ import annotations

import json
import hashlib
import sqlite3
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

DATABASE = Path(sys.argv[1])
EXPECTED_SCHEMA = int(sys.argv[2])
REPORT_PATH = Path(sys.argv[3])

from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationDefinitionOccurrence,
    AutomationJob,
    AutomationJobStatus,
    AutomationTaskRunMode,
)
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)
from mediaflow.domain.unattended_execution import (
    UnattendedExecutionGrant,
    UnattendedExecutionGrantAudit,
    UnattendedExecutionGrantStatus,
)
from mediaflow.domain.configuration_management import (
    ManagedConfigurationRevision,
    ManagedConfigurationStatus,
)
from mediaflow.domain.manual_organize import (
    ManualChoice,
    ManualConfigurationSnapshot,
    ManualIntentAudit,
    ManualIntentItem,
    ManualIntentItemStatus,
    ManualIntentStatus,
    ManualOrganizeIntent,
    ManualSourceIdentity,
)
from mediaflow.domain.manual_organize_preview import (
    ManualOrganizePreview,
    ManualPreviewItem,
    ManualPreviewItemStatus,
    ManualPreviewStatus,
)
from mediaflow.domain.recognition_review import (
    RecognitionReview,
    RecognitionReviewChoice,
    RecognitionReviewStatus,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository

NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
FINGERPRINT = "b" * 64
CONFIG_DOCUMENT = {"schemaVersion": 1, "rehearsal": "immutable-base-pin"}
DIGEST = hashlib.sha256(
    json.dumps(
        CONFIG_DOCUMENT, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
).hexdigest()
REQUEST_ID = "11111111-1111-4111-8111-111111111111"
TASK_ID = "rehearsal-task"
DEFINITION_ID = "rehearsal-definition"

REPORT = {"inapplicable": [], "failures": [], "seeded": {}, "facts": {}}


def inapplicable(name, reason):
    REPORT["inapplicable"].append({"family": name, "reason": reason})


def skip(name, reason):
    REPORT["failures"].append({"seed": name, "error": reason})


def table_exists(repository, name):
    row = repository._connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def table_columns(repository, name):
    return {row["name"] for row in repository._connection.execute(f"PRAGMA table_info({name})")}


with SQLiteTaskRepository(DATABASE) as repository:
    REPORT["base_schema"] = repository.schema_version
    REPORT["base_schema_constant"] = SCHEMA_VERSION
    if repository.schema_version != EXPECTED_SCHEMA:
        raise SystemExit(
            f"base schema {repository.schema_version} != expected {EXPECTED_SCHEMA}"
        )

    try:
        with SQLiteConfigurationRepository(DATABASE) as configuration_repository:
            revision = ManagedConfigurationRevision(
                "snap-base",
                7,
                ManagedConfigurationStatus.SUPERSEDED,
                1,
                DIGEST,
                CONFIG_DOCUMENT,
                NOW,
                NOW,
                activated_at=NOW,
            )
            stored_revision = configuration_repository.create_revision(revision)
        REPORT["seeded"]["configuration_revisions"] = 1
        REPORT["facts"]["configuration_revision"] = {
            "revision_id": stored_revision.revision_id,
            "version": stored_revision.version,
            "status": stored_revision.status.value,
            "schema_version": stored_revision.schema_version,
            "digest": stored_revision.digest,
            "document": stored_revision.document,
        }
    except Exception as error:
        skip("configuration revision", f"{type(error).__name__}: {error}")

    try:
        repository.create_task(
            PersistentTask(
                TASK_ID,
                "organize",
                PersistentTaskStatus.COMPLETED,
                True,
                NOW,
                NOW,
                started_at=NOW,
                completed_at=NOW,
                total_items=2,
                completed_items=1,
                failed_items=1,
                scope_path="Movies",
                item_limit=10,
                configuration_snapshot_id="snap-base",
                configuration_snapshot_digest=DIGEST,
            )
        )
        REPORT["seeded"]["tasks"] = 1
        REPORT["facts"]["task"] = {
            "task_id": TASK_ID,
            "command": "organize",
            "status": "completed",
            "execute_authorized": True,
            "configuration_snapshot_id": "snap-base",
            "configuration_snapshot_digest": DIGEST,
            "total_items": 2,
            "completed_items": 1,
            "failed_items": 1,
            "scope_path": "Movies",
            "item_limit": 10,
        }
    except Exception as error:
        skip("persistent task", f"{type(error).__name__}: {error}")

    try:
        seeded_items = []
        for index, status in enumerate((TaskItemStatus.SUCCESS, TaskItemStatus.FAILED)):
            item_id = f"rehearsal-item-{index}"
            repository.upsert_item(
                PersistentTaskItem(
                    item_id,
                    TASK_ID,
                    "storage-base",
                    "library-base",
                    f"Movies/source-{index}.mkv",
                    f"source-{index}.mkv",
                    status,
                    "organize",
                    1,
                    NOW + timedelta(minutes=index),
                    NOW + timedelta(minutes=index),
                    plan_id=f"plan-{index}",
                )
            )
            seeded_items.append(
                {
                    "item_id": item_id,
                    "status": status.value,
                    "stage": "organize",
                    "attempts": 1,
                    "source_path": f"Movies/source-{index}.mkv",
                    "storage_id": "storage-base",
                    "resource_library_id": "library-base",
                    "plan_id": f"plan-{index}",
                }
            )
        REPORT["seeded"]["task_items"] = len(seeded_items)
        REPORT["facts"]["items"] = seeded_items
    except Exception as error:
        skip("persistent task items", f"{type(error).__name__}: {error}")

    if table_exists(repository, "task_results") and hasattr(repository, "append_result"):
        try:
            result = PersistentResultRecord(
                "rehearsal-result",
                TASK_ID,
                "rehearsal-item-0",
                "storage-base",
                "Movies/source-0.mkv",
                "storage-base",
                "Movies/organized-0.mkv",
                "C",
                "tmdb",
                "12345",
                "metadata-c",
                "naming-a",
                "classification-a",
                "organize-move",
                "MOVE",
                "success",
                NOW,
                title="Rehearsal Movie",
                completed_operations=("MOVE",),
                effect_certainty="confirmed",
            )
            repository.append_result(result)
            REPORT["seeded"]["task_results"] = 1
            REPORT["facts"]["result"] = {
                "result_id": result.result_id,
                "task_id": result.task_id,
                "item_id": result.item_id,
                "source_storage_id": result.source_storage_id,
                "source_path": result.source_path,
                "destination_storage_id": result.destination_storage_id,
                "destination_path": result.destination_path,
                "recognition_type": result.recognition_type,
                "provider": result.provider,
                "provider_id": result.provider_id,
                "operation": result.operation,
                "status": result.status,
                "effect_certainty": result.effect_certainty,
            }
        except Exception as error:
            skip("task Result", f"{type(error).__name__}: {error}")
    else:
        inapplicable("task Results", "task_results table or append_result API is absent")

    if table_exists(repository, "manual_intents") and hasattr(repository, "create_manual_intent"):
        try:
            source = ManualSourceIdentity(
                "rehearsal-manual-file",
                "storage-base",
                "library-base",
                "Movies/manual-source.mkv",
                "manual-source.mkv",
                ".mkv",
                123,
                NOW,
                NOW,
                NOW,
                NOW,
                "completed",
                "rehearsal-scan",
            )
            choice = ManualChoice("C", None, "naming-a", "classification-a", "organize-a")
            manual_item = ManualIntentItem(
                "rehearsal-manual-item",
                "rehearsal-manual-intent",
                0,
                source,
                choice,
                ManualIntentItemStatus.READY,
                created_at=NOW,
                updated_at=NOW,
            )
            options = ManualConfigurationSnapshot("snap-base", DIGEST, (), (), (), (), ())
            manual_intent = ManualOrganizeIntent(
                "rehearsal-manual-intent",
                "operator",
                "snap-base",
                DIGEST,
                ManualIntentStatus.OPEN,
                1,
                NOW,
                NOW,
                (manual_item,),
                options,
            )
            manual_audit = ManualIntentAudit(
                "rehearsal-manual-audit",
                manual_intent.intent_id,
                None,
                "operator",
                "created",
                {},
                {"version": 1},
                NOW,
            )
            repository.create_manual_intent(manual_intent, (manual_item,), manual_audit)
            REPORT["seeded"]["manual_intents"] = 1
            REPORT["facts"]["manual_intent"] = {
                "intent_id": manual_intent.intent_id,
                "actor": manual_intent.actor,
                "snapshot_id": manual_intent.snapshot_id,
                "snapshot_digest": manual_intent.snapshot_digest,
                "status": manual_intent.status.value,
                "version": manual_intent.version,
                "item_id": manual_item.item_id,
                "source_path": source.path,
                "recognition_type_id": choice.recognition_type_id,
            }
            if hasattr(repository, "create_manual_preview"):
                preview_id = "rehearsal-manual-preview"
                preview_item = ManualPreviewItem(
                    "rehearsal-manual-preview-item",
                    preview_id,
                    manual_intent.intent_id,
                    manual_item.item_id,
                    0,
                    manual_intent.version,
                    manual_item.version,
                    source,
                    choice,
                    "snap-base",
                    DIGEST,
                    "a" * 64,
                    input_fingerprint="d" * 64,
                    status=ManualPreviewItemStatus.FAILED,
                    error="synthetic rehearsal analysis evidence",
                    next_action="request a fresh Preview after the upgrade rehearsal",
                    created_at=NOW,
                    updated_at=NOW,
                )
                preview = ManualOrganizePreview(
                    preview_id,
                    manual_intent.intent_id,
                    "operator",
                    manual_intent.version,
                    "snap-base",
                    DIGEST,
                    ManualPreviewStatus.FAILED,
                    (preview_item,),
                    NOW,
                    NOW,
                )
                repository.create_manual_preview(preview, (preview_item,))
                REPORT["seeded"]["manual_previews"] = 1
                REPORT["facts"]["manual_preview"] = {
                    "preview_id": preview.preview_id,
                    "intent_id": preview.intent_id,
                    "actor": preview.actor,
                    "intent_version": preview.intent_version,
                    "configuration_snapshot_id": preview.configuration_snapshot_id,
                    "configuration_snapshot_digest": preview.configuration_snapshot_digest,
                    "status": preview.status.value,
                    "zero_mutation": preview.zero_mutation,
                    "item_id": preview_item.item_id,
                    "item_status": preview_item.status.value,
                }
        except Exception as error:
            skip("manual intent and Preview", f"{type(error).__name__}: {error}")
    else:
        inapplicable("manual intent and Preview", "manual_intents table or API is absent")

    if table_exists(repository, "recognition_reviews") and hasattr(
        repository, "create_recognition_review"
    ):
        try:
            review_task_id = "rehearsal-review-task"
            review_item_id = "rehearsal-review-item"
            review_task = PersistentTask(
                review_task_id,
                "organize",
                PersistentTaskStatus.RUNNING,
                True,
                NOW,
                NOW,
                started_at=NOW,
                total_items=1,
                scope_path="Movies",
                item_limit=1,
                configuration_snapshot_id="snap-base",
                configuration_snapshot_digest=DIGEST,
            )
            repository.create_task(review_task)
            processing_item = PersistentTaskItem(
                review_item_id,
                review_task_id,
                "storage-base",
                "library-base",
                "Movies/review-source.mkv",
                "review-source.mkv",
                TaskItemStatus.PROCESSING,
                "recognition",
                1,
                NOW,
                NOW,
            )
            repository.upsert_item(processing_item)
            review = RecognitionReview(
                "rehearsal-recognition-review",
                review_task_id,
                review_item_id,
                "storage-base",
                "Movies/review-source.mkv",
                RecognitionReviewStatus.PENDING,
                NOW,
                NOW,
            )
            choices = (
                RecognitionReviewChoice(review.review_id, "A", "Movie"),
                RecognitionReviewChoice(review.review_id, "B", "TV"),
            )
            waiting_item = replace(processing_item, status=TaskItemStatus.WAITING_RECOGNITION)
            repository.create_recognition_review(review, choices, waiting_item)
            REPORT["seeded"]["recognition_reviews"] = 1
            REPORT["facts"]["review"] = {
                "review_id": review.review_id,
                "task_id": review.task_id,
                "item_id": review.item_id,
                "source_storage_id": review.source_storage_id,
                "source_path": review.source_path,
                "status": review.status.value,
                "choices": ["A", "B"],
            }
        except Exception as error:
            skip("recognition review", f"{type(error).__name__}: {error}")
    else:
        inapplicable("recognition reviews", "recognition_reviews table or API is absent")

    try:
        repository.create_job(
            AutomationJob(
                "rehearsal-job",
                AutomationCommand.ORGANIZE,
                AutomationJobStatus.COMPLETED,
                NOW,
                NOW,
                limit=5,
                task_id=TASK_ID,
                schedule_id="schedule-base",
                configuration_snapshot_id="snap-base",
                configuration_snapshot_digest=DIGEST,
                definition_id=DEFINITION_ID,
                definition_fingerprint=FINGERPRINT,
                definition_version=3,
                occurrence_at=NOW,
                run_mode=AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
                resource_library_id="library-base",
                source_scope="Movies",
                configuration_snapshot_version=7,
            )
        )
        REPORT["seeded"]["automation_jobs"] = 1
        REPORT["facts"]["job"] = {
            "job_id": "rehearsal-job",
            "command": "organize",
            "status": "completed",
            "task_id": TASK_ID,
            "limit": 5,
            "definition_id": DEFINITION_ID,
            "definition_fingerprint": FINGERPRINT,
            "definition_version": 3,
            "run_mode": "automatic-organization",
            "resource_library_id": "library-base",
            "source_scope": "Movies",
            "configuration_snapshot_id": "snap-base",
            "configuration_snapshot_digest": DIGEST,
            "configuration_snapshot_version": 7,
        }
    except Exception as error:
        skip("automation job", f"{type(error).__name__}: {error}")

    if table_exists(repository, "unattended_execution_grants"):
        try:
            repository.create_unattended_execution_grant(
                UnattendedExecutionGrant(
                    "rehearsal-grant",
                    DEFINITION_ID,
                    "library-base",
                    "Movies",
                    AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
                    5,
                    UnattendedExecutionGrantStatus.ACTIVE,
                    "operator",
                    NOW,
                    FINGERPRINT,
                    "snap-base",
                    DIGEST,
                    7,
                    preview_id="rehearsal-preview",
                ),
                UnattendedExecutionGrantAudit(
                    "rehearsal-grant-audit",
                    "rehearsal-grant",
                    "granted",
                    NOW,
                    "operator",
                    {"reason": "schema upgrade rehearsal"},
                ),
            )
            REPORT["seeded"]["unattended_execution_grants"] = 1
            REPORT["seeded"]["unattended_execution_grant_audit"] = 1
            REPORT["facts"]["grant"] = {
                "grant_id": "rehearsal-grant",
                "definition_id": DEFINITION_ID,
                "resource_library_id": "library-base",
                "source_scope": "Movies",
                "run_mode": "automatic-organization",
                "max_items_per_run": 5,
                "status": "active",
                "granting_principal": "operator",
                "definition_fingerprint": FINGERPRINT,
                "configuration_snapshot_id": "snap-base",
                "configuration_snapshot_digest": DIGEST,
                "configuration_snapshot_version": 7,
                "preview_id": "rehearsal-preview",
            }
            REPORT["facts"]["grant_audit"] = {
                "audit_id": "rehearsal-grant-audit",
                "grant_id": "rehearsal-grant",
                "action": "granted",
                "actor": "operator",
            }
        except Exception as error:
            skip("unattended execution grant", f"{type(error).__name__}: {error}")
    else:
        inapplicable("unattended execution grant", "table is absent in this revision")

    if table_exists(repository, "automation_definition_due_state"):
        try:
            repository.initialize_automation_definition_due_state(
                DEFINITION_ID,
                NOW + timedelta(hours=1),
                NOW,
                definition_fingerprint=FINGERPRINT,
            )
            REPORT["seeded"]["automation_definition_due_state"] = 1
        except Exception as error:
            skip("automation definition due state", f"{type(error).__name__}: {error}")
    else:
        inapplicable("automation definition due state", "table is absent in this revision")

    if table_exists(repository, "automation_definition_occurrences"):
        try:
            occurrence_job_id = "rehearsal-occurrence-job"
            occurrence_at = NOW + timedelta(hours=1)
            repository.enqueue_due_automation_definition(
                DEFINITION_ID,
                AutomationJob(
                    occurrence_job_id,
                    AutomationCommand.ORGANIZE,
                    AutomationJobStatus.PENDING,
                    NOW,
                    NOW,
                    limit=5,
                    definition_id=DEFINITION_ID,
                    definition_fingerprint=FINGERPRINT,
                    definition_version=3,
                    occurrence_at=occurrence_at,
                    run_mode=AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
                    resource_library_id="library-base",
                    source_scope="Movies",
                    configuration_snapshot_id="snap-base",
                    configuration_snapshot_digest=DIGEST,
                    configuration_snapshot_version=7,
                ),
                AutomationDefinitionOccurrence(
                    "rehearsal-occurrence",
                    DEFINITION_ID,
                    occurrence_at,
                    NOW,
                    occurrence_job_id,
                    FINGERPRINT,
                    3,
                    "snap-base",
                    7,
                    DIGEST,
                    AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
                    "library-base",
                    "Movies",
                    5,
                    "emitted",
                    "due",
                    "none",
                ),
                NOW + timedelta(hours=2),
                occurrence_at + timedelta(minutes=1),
                4,
            )
            REPORT["seeded"]["automation_definition_occurrences"] = 1
            REPORT["facts"]["occurrence"] = {
                "occurrence_id": "rehearsal-occurrence",
                "definition_id": DEFINITION_ID,
                "job_id": occurrence_job_id,
                "definition_fingerprint": FINGERPRINT,
                "definition_version": 3,
                "configuration_revision_id": "snap-base",
                "configuration_revision_version": 7,
                "configuration_revision_digest": DIGEST,
                "run_mode": "automatic-organization",
                "resource_library_id": "library-base",
                "source_scope": "Movies",
                "item_limit": 5,
                "outcome": "emitted",
            }
        except Exception as error:
            skip("automation definition occurrence", f"{type(error).__name__}: {error}")
    else:
        inapplicable("automation definition occurrence", "table is absent in this revision")

    if REPORT["seeded"].get("automation_definition_due_state"):
        try:
            due_state = repository.get_automation_definition_due_state(DEFINITION_ID)
            if due_state is None:
                raise LookupError("due state disappeared after seeding")
            REPORT["facts"]["due_state"] = {
                "definition_id": due_state.definition_id,
                "next_run_at": due_state.next_run_at.isoformat(),
                "last_job_id": due_state.last_job_id,
                "last_outcome": due_state.last_outcome,
                "definition_fingerprint": due_state.definition_fingerprint,
            }
        except Exception as error:
            skip("automation definition due state facts", f"{type(error).__name__}: {error}")

    if table_exists(repository, "media_discoveries"):
        try:
            from mediaflow.domain.media_discovery import (
                DiscoveryBudgets,
                DiscoveryCounters,
                DiscoveryEntryKind,
                DiscoveryIncompleteReason,
                DiscoveryProgress,
                DiscoveryScopeEntry,
                DiscoveryStatus,
                MediaDiscovery,
            )

            discovery_kwargs = {"admission_request_id": REQUEST_ID}
            origin_document = None
            if "definition_origin_json" in table_columns(repository, "media_discoveries"):
                from mediaflow.domain.media_discovery import DefinitionRunOnceOrigin

                origin = DefinitionRunOnceOrigin(
                    DEFINITION_ID,
                    "Rehearsal Definition",
                    FINGERPRINT,
                    "snap-base",
                    7,
                    DIGEST,
                    "library-base",
                    "Movies",
                    5,
                    5,
                    "automatic-organization",
                    REQUEST_ID,
                )
                discovery_kwargs["definition_origin"] = origin
                origin_document = origin.document()
                REPORT["definition_origin_seeded"] = True
            else:
                REPORT["definition_origin_seeded"] = False
                inapplicable(
                    "media discovery definition origin",
                    "media_discoveries has no definition_origin_json column in this revision",
                )
            repository.create_media_discovery(
                MediaDiscovery(
                    "rehearsal-discovery",
                    "operator",
                    "library-base",
                    "storage-base",
                    "snap-base",
                    DIGEST,
                    DiscoveryStatus.COMPLETED,
                    1,
                    DiscoveryBudgets(),
                    DiscoveryProgress(
                        "completed",
                        (DiscoveryScopeEntry("Movies", DiscoveryEntryKind.DIRECTORY),),
                        DiscoveryCounters(),
                        DiscoveryIncompleteReason.NONE,
                        (),
                        (),
                    ),
                    NOW,
                    NOW,
                    **discovery_kwargs,
                )
            )
            REPORT["seeded"]["media_discoveries"] = 1
            REPORT["facts"]["discovery"] = {
                "discovery_id": "rehearsal-discovery",
                "actor": "operator",
                "resource_library_id": "library-base",
                "storage_id": "storage-base",
                "snapshot_id": "snap-base",
                "snapshot_digest": DIGEST,
                "status": "completed",
                "admission_request_id": REQUEST_ID,
                "definition_origin": origin_document,
            }
        except Exception as error:
            skip("media discovery", f"{type(error).__name__}: {error}")
    else:
        inapplicable("media discovery", "table is absent in this revision")

REPORT["raw_counts"] = {}
with sqlite3.connect(str(DATABASE)) as connection:
    for name in (
        "tasks",
        "task_items",
        "automation_jobs",
        "unattended_execution_grants",
        "unattended_execution_grant_audit",
        "automation_definition_due_state",
        "automation_definition_occurrences",
        "media_discoveries",
        "task_results",
        "manual_intents",
        "manual_previews",
        "recognition_reviews",
        "managed_configuration_revisions",
    ):
        try:
            row = connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()
        except sqlite3.Error:
            continue
        REPORT["raw_counts"][name] = int(row[0])

REPORT_PATH.write_text(json.dumps(REPORT, indent=2, sort_keys=True), encoding="utf-8")
print(json.dumps(REPORT, indent=2, sort_keys=True))
if REPORT["failures"]:
    raise SystemExit(1)
'''

CANDIDATE_VERIFY_SCRIPT = '''
"""Verify an upgraded database with the candidate revision code."""

from __future__ import annotations

import json
import hashlib
import sys
from pathlib import Path

from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository

DATABASE = Path(sys.argv[1])
REPORT = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
EXPECTED_SCHEMA = int(sys.argv[3])

SEEDED = REPORT.get("seeded", {})
FACTS = REPORT.get("facts", {})
ASSERTIONS = []


def normalize(value):
    return getattr(value, "value", value)


def check(name, condition, detail=None):
    ASSERTIONS.append({"assertion": name, "ok": bool(condition), "detail": detail})


def compare(prefix, record, expected):
    for field, wanted in sorted(expected.items()):
        actual = normalize(getattr(record, field, None))
        check(f"{prefix}.{field}", actual == wanted, {"expected": wanted, "actual": actual})


def guard(name, function):
    try:
        function()
    except Exception as error:
        check(name, False, f"{type(error).__name__}: {error}")


with SQLiteTaskRepository(DATABASE) as repository:
    check(
        "candidate_schema_version",
        repository.schema_version == EXPECTED_SCHEMA,
        {"expected": EXPECTED_SCHEMA, "actual": repository.schema_version},
    )

    if SEEDED.get("configuration_revisions"):

        def verify_configuration_revision():
            with SQLiteConfigurationRepository(DATABASE) as configuration_repository:
                revision = configuration_repository.get_revision(
                    FACTS["configuration_revision"]["revision_id"]
                )
            check("configuration_revision.readable", revision is not None)
            if revision is not None:
                expected = FACTS["configuration_revision"]
                for field in (
                    "revision_id",
                    "version",
                    "status",
                    "schema_version",
                    "digest",
                    "document",
                ):
                    actual = normalize(getattr(revision, field, None))
                    wanted = expected[field]
                    check(
                        f"configuration_revision.{field}",
                        actual == wanted,
                        {"expected": wanted, "actual": actual},
                    )
                encoded = json.dumps(
                    revision.document,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                check(
                    "configuration_revision.digest_matches_document",
                    hashlib.sha256(encoded.encode("utf-8")).hexdigest() == revision.digest,
                )

        guard("configuration_revision.readable", verify_configuration_revision)
    check(
        "candidate_schema_constant",
        SCHEMA_VERSION == EXPECTED_SCHEMA,
        {"expected": EXPECTED_SCHEMA, "actual": SCHEMA_VERSION},
    )

    if SEEDED.get("tasks"):

        def verify_task():
            task = repository.get_task(FACTS["task"]["task_id"])
            check("task.readable", task is not None, FACTS["task"]["task_id"])
            if task is not None:
                compare("task", task, FACTS["task"])

        guard("task.readable", verify_task)

    if SEEDED.get("task_items"):

        def verify_items():
            items = {item.item_id: item for item in repository.list_items(FACTS["task"]["task_id"])}
            for expected in FACTS["items"]:
                item = items.get(expected["item_id"])
                check(f"item.{expected['item_id']}.readable", item is not None, None)
                if item is not None:
                    compare(f"item.{expected['item_id']}", item, expected)

        guard("items.readable", verify_items)

    if SEEDED.get("task_results"):

        def verify_result():
            expected = FACTS["result"]
            values = repository.list_results_for_item(expected["item_id"])
            match = [value for value in values if value.result_id == expected["result_id"]]
            check("result.readable", len(match) == 1, len(values))
            if match:
                for field, wanted in expected.items():
                    actual = normalize(getattr(match[0], field, None))
                    check(
                        f"result.{field}",
                        actual == wanted,
                        {"expected": wanted, "actual": actual},
                    )

        guard("result.readable", verify_result)

    if SEEDED.get("manual_intents"):

        def verify_manual_records():
            expected_intent = FACTS["manual_intent"]
            intent = repository.get_manual_intent(expected_intent["intent_id"])
            check("manual_intent.readable", intent is not None)
            if intent is not None:
                for field, wanted in expected_intent.items():
                    if field in {"item_id", "source_path", "recognition_type_id"}:
                        continue
                    actual = normalize(getattr(intent, field, None))
                    check(
                        f"manual_intent.{field}",
                        actual == wanted,
                        {"expected": wanted, "actual": actual},
                    )
                item = next(
                    (
                        value
                        for value in intent.items
                        if value.item_id == expected_intent["item_id"]
                    ),
                    None,
                )
                check("manual_intent.item.readable", item is not None)
                if item is not None:
                    check(
                        "manual_intent.item.source_path",
                        item.source.path == expected_intent["source_path"],
                    )
                    check(
                        "manual_intent.item.recognition_type",
                        item.choice.recognition_type_id == expected_intent["recognition_type_id"],
                    )
            if SEEDED.get("manual_previews"):
                expected_preview = FACTS["manual_preview"]
                preview = repository.get_manual_preview(expected_preview["preview_id"])
                check("manual_preview.readable", preview is not None)
                if preview is not None:
                    for field, wanted in expected_preview.items():
                        if field in {"item_id", "item_status"}:
                            continue
                        actual = normalize(getattr(preview, field, None))
                        check(
                            f"manual_preview.{field}",
                            actual == wanted,
                            {"expected": wanted, "actual": actual},
                        )
                    item = next(
                        (
                            value
                            for value in preview.items
                            if value.item_id == expected_preview["item_id"]
                        ),
                        None,
                    )
                    check("manual_preview.item.readable", item is not None)
                    if item is not None:
                        check(
                            "manual_preview.item.status",
                            item.status.value == expected_preview["item_status"],
                        )

        guard("manual_intent.readable", verify_manual_records)

    if SEEDED.get("recognition_reviews"):

        def verify_review():
            expected = FACTS["review"]
            review = repository.get_recognition_review(expected["review_id"])
            check("review.readable", review is not None)
            if review is not None:
                for field, wanted in expected.items():
                    if field == "choices":
                        continue
                    actual = normalize(getattr(review, field, None))
                    check(
                        f"review.{field}",
                        actual == wanted,
                        {"expected": wanted, "actual": actual},
                    )
                choices = repository.list_recognition_review_choices(review.review_id)
                check(
                    "review.choices",
                    sorted(value.recognition_type_id for value in choices) == expected["choices"],
                )

        guard("review.readable", verify_review)

    if SEEDED.get("automation_jobs"):

        def verify_job():
            job = repository.get_job(FACTS["job"]["job_id"])
            check("job.readable", job is not None, FACTS["job"]["job_id"])
            if job is not None:
                compare("job", job, FACTS["job"])

        guard("job.readable", verify_job)

    if SEEDED.get("unattended_execution_grants"):

        def verify_grant():
            grant = repository.get_unattended_execution_grant(FACTS["grant"]["grant_id"])
            check("grant.readable", grant is not None, FACTS["grant"]["grant_id"])
            if grant is not None:
                compare("grant", grant, FACTS["grant"])
                check(
                    "grant.still_active",
                    normalize(grant.status) == "active",
                    normalize(grant.status),
                )

        guard("grant.readable", verify_grant)

    if SEEDED.get("unattended_execution_grant_audit"):

        def verify_grant_audit():
            audits = repository.list_unattended_execution_grant_audit(
                FACTS["grant_audit"]["grant_id"]
            )
            wanted_audit = FACTS["grant_audit"]["audit_id"]
            match = [value for value in audits if value.audit_id == wanted_audit]
            check("grant_audit.readable", len(match) == 1, len(audits))
            if match:
                compare("grant_audit", match[0], FACTS["grant_audit"])

        guard("grant_audit.readable", verify_grant_audit)

    if SEEDED.get("automation_definition_due_state"):

        def verify_due_state():
            due = repository.get_automation_definition_due_state(
                FACTS["due_state"]["definition_id"]
            )
            check("due_state.readable", due is not None, FACTS["due_state"]["definition_id"])
            if due is not None:
                actual = {
                    "definition_id": due.definition_id,
                    "next_run_at": due.next_run_at.isoformat(),
                    "last_job_id": due.last_job_id,
                    "last_outcome": due.last_outcome,
                    "definition_fingerprint": due.definition_fingerprint,
                }
                for field, wanted in sorted(FACTS["due_state"].items()):
                    check(
                        f"due_state.{field}",
                        actual.get(field) == wanted,
                        {"expected": wanted, "actual": actual.get(field)},
                    )

        guard("due_state.readable", verify_due_state)

    if SEEDED.get("automation_definition_occurrences"):

        def verify_occurrence():
            occurrences = repository.list_automation_definition_occurrences(
                FACTS["occurrence"]["definition_id"]
            )
            match = [
                value
                for value in occurrences
                if value.occurrence_id == FACTS["occurrence"]["occurrence_id"]
            ]
            check("occurrence.readable", len(match) == 1, len(occurrences))
            if match:
                compare("occurrence", match[0], FACTS["occurrence"])

        guard("occurrence.readable", verify_occurrence)

    if SEEDED.get("media_discoveries"):

        def verify_discovery():
            discovery = repository.get_media_discovery(FACTS["discovery"]["discovery_id"])
            check("discovery.readable", discovery is not None, FACTS["discovery"]["discovery_id"])
            if discovery is None:
                return
            expected = {
                key: value
                for key, value in FACTS["discovery"].items()
                if key != "definition_origin"
            }
            compare("discovery", discovery, expected)
            wanted_origin = FACTS["discovery"].get("definition_origin")
            if wanted_origin is None:
                check(
                    "discovery.definition_origin_absent",
                    discovery.definition_origin is None,
                    None,
                )
            else:
                check(
                    "discovery.definition_origin_present",
                    discovery.definition_origin is not None,
                    None,
                )
                if discovery.definition_origin is not None:
                    actual_origin = discovery.definition_origin.document()
                    for field, value in sorted(wanted_origin.items()):
                        check(
                            f"discovery.definition_origin.{field}",
                            actual_origin.get(field) == value,
                            {"expected": value, "actual": actual_origin.get(field)},
                        )

            # The additive 46 migration must leave the new column *usable* on this
            # legacy row, not merely present.  A legacy discovery keeps no
            # invented origin, and the definition-bound lookup must still be able
            # to reconcile a real origin written after the upgrade.
            columns = {
                row["name"]
                for row in repository._connection.execute(
                    "PRAGMA table_info(media_discoveries)"
                ).fetchall()
            }
            check("discovery.definition_origin_column_present", "definition_origin_json" in columns)
            if wanted_origin is None:
                check(
                    "discovery.legacy_origin_never_backfilled",
                    discovery.definition_origin is None,
                    "no definition identity may be guessed for a legacy admission",
                )
                check(
                    "discovery.definition_origin_lookup_usable",
                    repository.find_open_definition_run_once(
                        actor="operator",
                        definition_id="absent-definition",
                        definition_fingerprint="a" * 64,
                        snapshot_id="snap-base",
                        snapshot_digest="d" * 64,
                    )
                    is None,
                )

        guard("discovery.readable", verify_discovery)

print(
    json.dumps(
        {
            "candidate_schema": SCHEMA_VERSION,
            "assertions": ASSERTIONS,
            "passed": all(value["ok"] for value in ASSERTIONS),
        },
        indent=2,
        sort_keys=True,
    )
)
'''


def _run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, **kwargs)  # noqa: S603


def _archive(revision: str, project: Path) -> subprocess.CompletedProcess:
    """``git archive`` produces a binary tar stream, never decoded text."""

    return subprocess.run(  # noqa: S603
        ["git", "archive", revision], cwd=str(project), capture_output=True
    )


def _subprocess_environment(source: Path) -> dict[str, str]:
    """The real environment with ``PYTHONPATH`` pinned to one revision.

    The base phase must never import candidate code and the candidate phase must
    never import base code, whatever the developer's shell already exported, so
    an inherited ``PYTHONPATH`` is deliberately replaced rather than extended.
    """

    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(source)
    return environment


def _fail(message: str, *, code: int = 2) -> int:
    print(json.dumps({"ok": False, "error": message}, indent=2, sort_keys=True))
    return code


def _discover_candidate_schema(project: Path) -> int:
    """Read the candidate's own ``SCHEMA_VERSION`` with the candidate code only."""

    probe = (
        "from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION; print(SCHEMA_VERSION)"
    )
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", probe],
        cwd=str(project),
        env=_subprocess_environment(project),
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "could not read the candidate schema version: "
            + (completed.stderr or completed.stdout).strip()
        )
    return int(completed.stdout.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-sha", required=True, help="immutable 40-hex git revision")
    parser.add_argument("--expect-schema", required=True, type=int, help="base schema version")
    parser.add_argument("--keep", action="store_true", help="keep the temporary rehearsal dir")
    parser.add_argument(
        "--project",
        default=str(Path(__file__).resolve().parents[1]),
        help="repository root containing the script's parent (default: script's parent)",
    )
    parser.add_argument(
        "--expect-candidate-schema",
        type=int,
        default=DEFAULT_CANDIDATE_SCHEMA,
        help=(
            "pin the schema the candidate must report after upgrading; by default the "
            "candidate's own SCHEMA_VERSION is discovered from --project"
        ),
    )
    arguments = parser.parse_args(argv)

    if not SHA_PATTERN.fullmatch(arguments.base_sha):
        return _fail("--base-sha must be exactly 40 lowercase hex characters")
    project = Path(arguments.project).resolve()
    if not (project / ".git").exists():
        return _fail(f"{project} is not a git working tree")

    expected_candidate_schema = arguments.expect_candidate_schema
    if expected_candidate_schema is None:
        try:
            expected_candidate_schema = _discover_candidate_schema(project)
        except RuntimeError as error:
            return _fail(str(error))

    root = Path(tempfile.mkdtemp(prefix="mediaflow-schema-rehearsal-"))
    keep = bool(arguments.keep)
    try:
        base_source = root / "base-source"
        base_source.mkdir()
        archive = _archive(arguments.base_sha, project)
        if archive.returncode != 0:
            return _fail("git archive failed: " + archive.stderr.decode("utf-8", "replace").strip())
        extract = subprocess.run(  # noqa: S603
            ["tar", "-x", "-C", str(base_source)],
            input=archive.stdout,
            capture_output=True,
        )
        if extract.returncode != 0:
            return _fail(
                "tar extraction failed: " + extract.stderr.decode("utf-8", "replace").strip()
            )

        database = root / "runtime.sqlite3"
        seed_report_path = root / "base-report.json"
        seed_script = root / "base_seed.py"
        verify_script = root / "candidate_verify.py"
        seed_script.write_text(BASE_SEED_SCRIPT, encoding="utf-8")
        verify_script.write_text(CANDIDATE_VERIFY_SCRIPT, encoding="utf-8")

        commands: list[dict[str, object]] = [
            {
                "step": "extract-base",
                "command": f"git archive {arguments.base_sha} | tar -x -C {base_source}",
                "cwd": str(project),
            },
            {
                "step": "seed-base",
                "command": (
                    f"PYTHONPATH={base_source} {sys.executable} {seed_script} "
                    f"{database} {arguments.expect_schema} {seed_report_path}"
                ),
                "cwd": str(base_source),
            },
        ]
        seeded = _run(
            [
                sys.executable,
                str(seed_script),
                str(database),
                str(arguments.expect_schema),
                str(seed_report_path),
            ],
            cwd=str(base_source),
            env=_subprocess_environment(base_source),
        )
        if seeded.returncode != 0:
            return _fail(
                "base seeding failed:\n" + (seeded.stderr or seeded.stdout).strip(),
            )
        base_report = json.loads(seed_report_path.read_text(encoding="utf-8"))

        commands.append(
            {
                "step": "upgrade-and-verify-candidate",
                "command": (
                    f"PYTHONPATH={project} {sys.executable} {verify_script} "
                    f"{database} {seed_report_path} {expected_candidate_schema}"
                ),
                "cwd": str(project),
            }
        )
        verified = _run(
            [
                sys.executable,
                str(verify_script),
                str(database),
                str(seed_report_path),
                str(expected_candidate_schema),
            ],
            cwd=str(project),
            env=_subprocess_environment(project),
        )
        if verified.returncode != 0:
            return _fail(
                "candidate verification failed:\n" + (verified.stderr or verified.stdout).strip()
            )
        verification = json.loads(verified.stdout)

        assertions = verification["assertions"]
        failures = [value for value in assertions if not value["ok"]]
        summary = {
            "ok": not failures,
            "base_sha": arguments.base_sha,
            "expected_schema": arguments.expect_schema,
            "observed_base_schema": base_report.get("base_schema"),
            "base_schema_constant": base_report.get("base_schema_constant"),
            "expected_candidate_schema": expected_candidate_schema,
            "candidate_schema": verification.get("candidate_schema"),
            "seeded_row_counts": base_report.get("seeded", {}),
            "raw_base_counts": base_report.get("raw_counts", {}),
            "seed_failures": base_report.get("failures", []),
            "inapplicable_families": base_report.get("inapplicable", []),
            "definition_origin_seeded": base_report.get("definition_origin_seeded", False),
            "preserved_row_assertions": assertions,
            "failed_assertions": failures,
            "commands": commands,
        }
        if keep:
            summary["kept_temp_dir"] = str(root)
            summary["kept_database"] = str(database)
        print(json.dumps(summary, indent=2, sort_keys=True))
        if failures:
            print(
                "FAILED ASSERTIONS: " + ", ".join(str(value["assertion"]) for value in failures),
                file=sys.stderr,
            )
            return 1
        return 0
    finally:
        if keep:
            print(f"kept temporary rehearsal directory: {root}", file=sys.stderr)
        else:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
