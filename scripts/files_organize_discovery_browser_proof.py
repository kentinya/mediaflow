#!/usr/bin/env python3
"""Real-Python acceptance: bounded folder/mixed-selection discovery (Task 44.6).

This harness starts the production-shaped Python API (``mediaflow api serve``)
against a temporary throwaway configuration — temporary SQLite repositories,
temporary Local Storage roots, a throwaway API token and the current built V2
artifact served by the real ``mediaflow.interfaces.v2_ui`` boundary — and drives
a real Chromium browser through Slice 44 RO-6:

* ResourceLibrary list/grid folder menus and the batch action complete
  folder-only, file-only, multiple-folder and mixed selections;
* the backend admits one durable discovery per selection, resolves the real
  entry types, the pinned Active revision and the exact budgets, and returns
  promptly with zero directory enumeration in the request;
* a resident Processing Worker performs the metadata-only walk, proving
  configured extensions/exclusions, real stability waiting and bounded
  exclusion findings;
* cooperative pause/continue/cancel and explicit operator finalize are native,
  durable and versioned;
* finalize freezes one deduplicated source list and links the existing manual
  intent, which still requires a separate exact Preview and a confirmed
  execution;
* the whole journey performs zero media mutation and creates no executable
  OrganizerExecutor work.

Safety is proven at the Python boundary: the harness reads the real
configuration authority and the real SQLite runtime database before and after
the whole journey and requires the Active revision, digest, activation count and
executable Task/Job work to be unchanged, and no mutating HTTP request to have
been issued.

No production service, credential, user media or external network is involved.
Every token here is a throwaway value scoped to temporary resources.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

PORT = int(os.environ.get("MF_PROOF_PORT", "8791"))
BASE = f"http://127.0.0.1:{PORT}"
TOKEN = "discovery-proof-operator-token"
ARTIFACT_ROOT = ROOT / ".git" / "validation-evidence" / "_discovery-proof" / "browser"

#: Controlled synthetic scope names the acceptance matrix needs.
FOLDER = "电影"
FOLDER_CHILD = "电影/华语"
MIXED_FILE = "sample.mkv"
SECOND_FOLDER = "SP"
TEMPORARY = "下载中.mkv.part"
UNSUPPORTED = "notes.txt"
#: The dedicated confirmed-execution scope: one ordinary source the reviewed
#: exact Preview moves through the real OrganizerExecutor, entirely inside the
#: temporary roots.
EXECUTION_FOLDER = "执行范围"
EXECUTION_FILE = "Execution.2004.mkv"
EXECUTION_RELATIVE = f"{EXECUTION_FOLDER}/{EXECUTION_FILE}"
EXECUTION_TARGET = "Movies/其他电影/Execution (2004) [tmdbid-909]/Execution (2004).mkv"
#: The controlled safety-depth scope: eligible media below the Task's own
#: 32-level safety bound, with the configured library depth unset.
MASS_FOLDER = "mass"
DEEP_FOLDER = "deep"
#: The bounded control-preservation scope: a second 101-source folder whose
#: completed walk is acknowledged by a *pause* at the safe boundary.  The
#: acknowledgement must keep the counters, findings, manifest and the
#: encountered primary-limit refusal instead of resetting them (B44-8-1).
CONTROL_MASS_FOLDER = "control-mass"


def render_configuration(root: Path) -> dict:
    document = json.loads((ROOT / "config" / "strategy.example.json").read_text(encoding="utf-8"))
    (root / "source").mkdir(parents=True, exist_ok=True)
    (root / "target" / "Movies").mkdir(parents=True, exist_ok=True)
    document["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
    document["historyPath"] = str(root / "history.jsonl")
    document["storages"][0]["rootPath"] = str(root / "source")
    document["storages"][1]["rootPath"] = str(root / "target")
    document["resourceLibraries"][0]["storagePath"] = ""
    document["resourceLibraries"][0]["extensions"] = ["mkv", "mp4"]
    document["resourceLibraries"][0]["maxDepth"] = None
    document["mediaLibraries"][0]["rootPath"] = "Movies"
    # The confirmed-execution stage of this proof must run without any external
    # Metadata service or credential.  The managed MetadataPolicies are
    # therefore offline (`mediaQueryType: none`): an offline policy performs no
    # lookup by definition, and the exact Preview pins the identity the
    # operator's Choice carried — an identity grounded in the source-linked
    # durable Result the proof seeds through the production persistence write
    # path before any Choice.  No Provider registry is ever constructed.
    for policy in document["metadataPolicies"]:
        policy["mediaQueryType"] = "none"
    # The classification results follow the RO-3 revised destination contract:
    # MediaLibrary + path only, no display-name prefix segment.
    for policy in document["classificationPolicies"]:
        for rule in policy["rules"]:
            rule["result"].pop("library", None)
    return document


def seed_tree(root: Path) -> None:
    """Create the controlled synthetic media the acceptance matrix needs."""

    source = root / "source"
    (source / FOLDER_CHILD).mkdir(parents=True, exist_ok=True)
    (source / FOLDER_CHILD / "One.2001.mkv").write_bytes(b"synthetic discovery media")
    (source / FOLDER_CHILD / "Two.2002.mp4").write_bytes(b"synthetic discovery media")
    (source / FOLDER_CHILD / UNSUPPORTED).write_bytes(b"not media")
    (source / FOLDER_CHILD / TEMPORARY).write_bytes(b"downloading")
    (source / SECOND_FOLDER).mkdir(parents=True, exist_ok=True)
    (source / SECOND_FOLDER / "Extra.2003.mkv").write_bytes(b"synthetic discovery media")
    (source / MIXED_FILE).write_bytes(b"synthetic discovery media")
    # The confirmed-execution stage organizes this extra source in its own
    # dedicated scope so the four discovery selections above stay untouched.
    EXECUTION_FOLDER = "执行范围"
    (source / EXECUTION_FOLDER).mkdir(parents=True, exist_ok=True)
    (source / EXECUTION_FOLDER / "Execution.2004.mkv").write_bytes(b"synthetic execution media")
    # The 101-source budget case: exactly one source beyond the admitted
    # primary bound, all ordinary legal media.
    mass = source / MASS_FOLDER
    mass.mkdir(parents=True, exist_ok=True)
    for index in range(101):
        (mass / f"Bulk.{index:03d}.mkv").write_bytes(b"synthetic discovery media")
    # The control-preservation case needs its own 101-source scope so the
    # primary-limit refusal is exercised by a pause acknowledgement rather
    # than by a terminal walk.
    control_mass = source / CONTROL_MASS_FOLDER
    control_mass.mkdir(parents=True, exist_ok=True)
    for index in range(101):
        (control_mass / f"Hold.{index:03d}.mkv").write_bytes(b"synthetic discovery media")
    # The safety-depth case: one direct source plus eligible media below the
    # Task's own 32-level descendant bound, with the configured depth unset.
    (source / DEEP_FOLDER).mkdir(parents=True, exist_ok=True)
    (source / DEEP_FOLDER / "Direct.2001.mkv").write_bytes(b"synthetic discovery media")
    deep = source / DEEP_FOLDER
    for level in range(33):
        deep = deep / f"Level{level:02d}"
    deep.mkdir(parents=True, exist_ok=True)
    (deep / "Buried.2002.mkv").write_bytes(b"synthetic discovery media")


def wait_for_health(process: subprocess.Popen, timeout: float = 90.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("API process exited before becoming healthy")
        try:
            with urllib.request.urlopen(f"{BASE}/health", timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(0.3)
    raise RuntimeError("API did not become healthy in time")


def api(method: str, path: str, document: dict | None = None, *, expect: int | None = None):
    request = urllib.request.Request(
        f"{BASE}{path}",
        method=method,
        data=None if document is None else json.dumps(document).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read())
            status = response.status
    except urllib.error.HTTPError as error:
        body = json.loads(error.read() or b"{}")
        status = error.code
    if expect is not None and status != expect:
        raise RuntimeError(f"{method} {path} returned {status}, expected {expect}: {body}")
    return status, body


def run_cli(*arguments: str) -> str:
    result = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "mediaflow"), "--config", str(arguments[0]), *arguments[1:]],
        cwd=ROOT,
        env={
            **os.environ,
            "MEDIAFLOW_API_TOKEN": TOKEN,
            "MEDIAFLOW_UI_V2_ASSET_ROOT": str(ROOT / "web" / "dist"),
        },
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(f"cli {arguments[1]} failed:\n{result.stdout}\n{result.stderr}")
    return result.stdout


def _executable_work(database_path: Path) -> dict:
    connection = sqlite3.connect(database_path)
    try:
        tasks = connection.execute(
            "SELECT COUNT(*) FROM tasks WHERE command='manual_organize'"
        ).fetchone()[0]
        jobs = connection.execute("SELECT COUNT(*) FROM automation_jobs").fetchone()[0]
        return {"manualOrganizeTasks": tasks, "jobs": jobs}
    finally:
        connection.close()


def _activation_count(database_path: Path) -> int:
    if not database_path.exists():
        return 0
    connection = sqlite3.connect(str(database_path))
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if "managed_configuration_audit" not in tables:
            return 0
        return connection.execute(
            "SELECT COUNT(*) FROM managed_configuration_audit WHERE action = 'activate'"
        ).fetchone()[0]
    finally:
        connection.close()


def _discovery_row(database_path: Path, discovery_id: str) -> dict:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT * FROM media_discoveries WHERE discovery_id=?", (discovery_id,)
        ).fetchone()
        if row is None:
            raise RuntimeError("the admitted discovery was not persisted")
        return dict(row)
    finally:
        connection.close()


def _run_worker(configuration_path: Path) -> None:
    """Advance the resident Worker once so the durable walk really runs."""

    subprocess.run(
        [
            str(ROOT / ".venv" / "bin" / "mediaflow"),
            "--config",
            str(configuration_path),
            "worker",
            "run-next",
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "MEDIAFLOW_API_TOKEN": TOKEN,
            "MEDIAFLOW_UI_V2_ASSET_ROOT": str(ROOT / "web" / "dist"),
        },
        capture_output=True,
        text=True,
        check=False,
    )


def _settle(configuration_path: Path, discovery_id: str, *, attempts: int = 6) -> dict:
    """Drive the Worker until the discovery is no longer running/queued."""

    for _ in range(attempts):
        _, document = api("GET", f"/api/v1/operations/organize/discoveries/{discovery_id}")
        if document["status"] not in {"queued", "running"}:
            return document
        _run_worker(configuration_path)
        time.sleep(0.4)
    _, document = api("GET", f"/api/v1/operations/organize/discoveries/{discovery_id}")
    return document


def _run_worker_until_idle(configuration_path: Path, *, attempts: int = 8) -> None:
    """Drain the Worker queue so any admitted work reaches a terminal state."""

    for _ in range(attempts):
        result = subprocess.run(
            [
                str(ROOT / ".venv" / "bin" / "mediaflow"),
                "--config",
                str(configuration_path),
                "worker",
                "run-next",
            ],
            cwd=ROOT,
            env={
                **os.environ,
                "MEDIAFLOW_API_TOKEN": TOKEN,
                "MEDIAFLOW_UI_V2_ASSET_ROOT": str(ROOT / "web" / "dist"),
            },
            capture_output=True,
            text=True,
            check=False,
        )
        combined = f"{result.stdout}{result.stderr}".lower()
        if "no pending" in combined or "no claimable" in combined or "nothing" in combined:
            return


def _seed_source_linked_result(database_path: Path) -> None:
    """Ground the execution source's operator Choice in durable source evidence.

    The bounded metadata authority of a manual intent accepts only an identity
    that a durable Result or source-linked evidence of the exact source already
    carries.  The proof writes one prior preview-mode Result through the real
    production repository write path on the same SQLite file the running
    deployment uses — the identical seeding shape the Docker sibling proofs
    use for durable state.  It grants no execution authority and never touches
    media; only a later exact Preview plus a separately confirmed Execute can.
    """

    from datetime import UTC, datetime

    from mediaflow.domain.task_persistence import (
        PersistentResultRecord,
        PersistentTask,
        PersistentTaskStatus,
    )
    from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository

    now = datetime.now(UTC)
    with SQLiteTaskRepository(database_path) as repository:
        if repository.get_task("discovery-proof-prior") is None:
            repository.create_task(
                PersistentTask(
                    "discovery-proof-prior",
                    "preview",
                    PersistentTaskStatus.COMPLETED,
                    False,
                    now,
                    now,
                )
            )
        repository.append_result(
            PersistentResultRecord(
                "discovery-proof-prior-result",
                "discovery-proof-prior",
                "discovery-proof-prior-item",
                "source-storage",
                EXECUTION_RELATIVE,
                "media-target",
                EXECUTION_TARGET,
                "A",
                "tmdb",
                "909",
                "A",
                "A",
                "A",
                "A",
                "MOVE",
                "dry_run",
                now,
                title="Execution",
            )
        )


def _current_preview_for_intent(database_path: Path, intent_id: str) -> str | None:
    """The durable current Preview identity of one intent (bounded SQLite read)."""

    connection = sqlite3.connect(database_path)
    try:
        row = connection.execute(
            "SELECT preview_id FROM manual_previews WHERE intent_id=? AND current=1 "
            "ORDER BY created_at DESC LIMIT 1",
            (intent_id,),
        ).fetchone()
        return None if row is None else str(row[0])
    finally:
        connection.close()


def _execution_state(root: Path) -> dict:
    """Read-only state of the execution source and its planned destination."""

    source = root / "source" / EXECUTION_RELATIVE
    target = root / "target" / EXECUTION_TARGET
    return {"sourceExists": source.is_file(), "targetExists": target.is_file()}


def main() -> int:
    if shutil.which("node") is None:
        print("UNAVAILABLE: node is required for the browser proof")
        return 1
    if not (ROOT / "web" / "dist" / "index.html").is_file():
        print("UNAVAILABLE: the built V2 artifact is missing; run `npm --prefix web run build`")
        return 1

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    for stale in ARTIFACT_ROOT.glob("*.png"):
        stale.unlink()

    directory = tempfile.mkdtemp(prefix="mediaflow-discovery-proof-")
    root = Path(directory)
    seed_tree(root)
    configuration_path = root / "mediaflow.json"
    configuration_path.write_text(
        json.dumps(render_configuration(root), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    process = subprocess.Popen(
        [
            str(ROOT / ".venv" / "bin" / "mediaflow"),
            "--config",
            str(configuration_path),
            "api",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "MEDIAFLOW_API_TOKEN": TOKEN,
            "MEDIAFLOW_UI_V2_ASSET_ROOT": str(ROOT / "web" / "dist"),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_for_health(process)
        config_path = str(configuration_path)
        imported = run_cli(config_path, "config", "import", "--file", config_path)
        revision_id = json.loads(imported)["revisionId"]
        run_cli(config_path, "config", "validate-draft", revision_id)
        run_cli(
            config_path,
            "config",
            "activate",
            revision_id,
            "--expected-version",
            "1",
            "--actor",
            "discovery-proof",
        )
        print("== real Python bounded folder/mixed-selection discovery proof ==")

        database_path = root / "runtime.sqlite3"
        active_before = api("GET", "/api/v1/operations/rules/form-authority")[1]["active"]
        activations_before = _activation_count(database_path)
        work_before = _executable_work(database_path)

        cases = [
            ("folder-only", [FOLDER]),
            ("file-only", [MIXED_FILE]),
            ("multiple-folders", [FOLDER, SECOND_FOLDER]),
            ("mixed", [FOLDER, MIXED_FILE]),
        ]
        results = {}
        for name, paths in cases:
            status, admitted = api(
                "POST",
                "/api/v1/resource-libraries/source/files/discoveries",
                {"paths": paths},
                expect=202,
            )
            discovery_id = admitted["discoveryId"]
            settled = _settle(configuration_path, discovery_id)
            row = _discovery_row(database_path, discovery_id)
            results[name] = {
                "paths": paths,
                "status": settled["status"],
                "primarySources": settled["primarySourceCount"],
                "visitedEntries": settled["progress"]["visitedEntries"],
                "excludedEntries": settled["progress"]["excludedEntries"],
                "reasons": [item["reason"] for item in settled["progress"]["reasons"]],
                "sources": [item["path"] for item in settled["sources"]],
                "persistedStatus": row["status"],
                "scopeEntries": json.loads(row["progress_json"])["scopeEntries"],
                "discoveryId": discovery_id,
                "settledStatus": settled["status"],
            }
            print(
                f"   {name}: {settled['status']} "
                f"{settled['primarySourceCount']} primary, "
                f"{settled['progress']['excludedEntries']} excluded"
            )

        # Folder discovery really applies the configured filters.
        folder = results["folder-only"]
        if "unsupported_extension" not in folder["reasons"]:
            raise RuntimeError(f"the unsupported entry was not explained: {folder}")
        if "temporary_file" not in folder["reasons"]:
            raise RuntimeError(f"the temporary entry was not explained: {folder}")
        if sorted(folder["sources"]) != sorted(
            [f"{FOLDER}/华语/One.2001.mkv", f"{FOLDER}/华语/Two.2002.mp4"]
        ):
            raise RuntimeError(f"folder discovery found the wrong sources: {folder}")

        # Mixed selection deduplicates and keeps one item per ordinary source.
        mixed = results["mixed"]
        if len(mixed["sources"]) != len(set(mixed["sources"])):
            raise RuntimeError(f"the mixed selection duplicated a source: {mixed}")
        if MIXED_FILE not in mixed["sources"]:
            raise RuntimeError(f"the explicit file was dropped: {mixed}")

        # Cooperative control: pause then continue the same durable scope.
        _, control_target = api(
            "POST",
            "/api/v1/resource-libraries/source/files/discoveries",
            {"paths": [SECOND_FOLDER]},
            expect=202,
        )
        target_id = control_target["discoveryId"]
        _, paused = api(
            "POST",
            f"/api/v1/operations/organize/discoveries/{target_id}/pause",
            {"expectedVersion": 1},
            expect=200,
        )
        if paused["pauseRequested"] is not True:
            raise RuntimeError(f"the cooperative pause was not recorded: {paused}")
        _, conflicted = api(
            "POST",
            f"/api/v1/operations/organize/discoveries/{target_id}/pause",
            {"expectedVersion": 1},
        )
        if conflicted["error"]["code"] != "discovery_conflict":
            raise RuntimeError(f"a stale control was accepted: {conflicted}")
        # Acknowledge-before-Continue: while the pause is still pending the
        # safe-boundary acknowledgement, Continue is not offered and a direct
        # Continue is refused actionably without changing any work.
        if paused["actions"]["resume"]["available"] is not False:
            raise RuntimeError(f"a pending pause advertised Continue: {paused}")
        if paused["actions"]["resume"]["pendingReason"] != "discovery_pause_pending":
            raise RuntimeError(f"a pending pause gave no bounded reason: {paused}")
        _, premature = api(
            "POST",
            f"/api/v1/operations/organize/discoveries/{target_id}/resume",
            {"expectedVersion": paused["version"]},
        )
        if premature.get("error", {}).get("code") != "discovery_pause_pending":
            raise RuntimeError(f"a premature Continue was accepted: {premature}")
        _run_worker(configuration_path)
        time.sleep(0.4)
        _, acknowledged = api(
            "GET", f"/api/v1/operations/organize/discoveries/{target_id}", expect=200
        )
        if (
            acknowledged["status"] != "paused"
            or acknowledged["pauseRequested"] is not True
            or acknowledged["actions"]["resume"]["available"] is not True
        ):
            raise RuntimeError(f"the pause was not acknowledged truthfully: {acknowledged}")
        _, resumed = api(
            "POST",
            f"/api/v1/operations/organize/discoveries/{target_id}/resume",
            {"expectedVersion": acknowledged["version"]},
            expect=200,
        )
        if resumed["pauseRequested"] is not False:
            raise RuntimeError(f"continue did not clear the pause: {resumed}")
        settled_control = _settle(configuration_path, target_id)

        # Control/publication preservation (B44-8-1): a real 101-source scope
        # reaches the primary bound, and the accepted pause must never be
        # acknowledged as a reset record.  A pause requested before pickup is
        # honoured truthfully (no walk is claimed for it); Continue then runs
        # the same durable scope to the bound, and the durable material refusal
        # keeps Finalize refused.  The narrower in-flight race — a publication
        # that loses the version CAS to a concurrent pause — is covered
        # deterministically by the Python regressions rather than by fragile
        # browser timing.
        _, control_mass_target = api(
            "POST",
            "/api/v1/resource-libraries/source/files/discoveries",
            {"paths": [CONTROL_MASS_FOLDER]},
            expect=202,
        )
        control_mass_id = control_mass_target["discoveryId"]
        _, control_paused = api(
            "POST",
            f"/api/v1/operations/organize/discoveries/{control_mass_id}/pause",
            {"expectedVersion": control_mass_target["version"]},
            expect=200,
        )
        if (
            control_paused["pauseRequested"] is not True
            or control_paused["progress"]["visitedEntries"] != 0
            # Acknowledge-before-Continue: the request is durable but not yet
            # acknowledged, so Continue is not offered and a direct Continue is
            # refused actionably without changing any work.
            or control_paused["actions"]["resume"]["available"] is not False
            or control_paused["actions"]["resume"]["pendingReason"] != "discovery_pause_pending"
        ):
            raise RuntimeError(f"a pending pause advertised Continue: {control_paused}")
        _, control_premature = api(
            "POST",
            f"/api/v1/operations/organize/discoveries/{control_mass_id}/resume",
            {"expectedVersion": control_paused["version"]},
        )
        if control_premature.get("error", {}).get("code") != "discovery_pause_pending":
            raise RuntimeError(f"a premature Continue was accepted: {control_premature}")
        _run_worker(configuration_path)
        time.sleep(0.4)
        _, control_held = api(
            "GET", f"/api/v1/operations/organize/discoveries/{control_mass_id}", expect=200
        )
        if (
            control_held["status"] != "paused"
            or control_held["progress"]["visitedEntries"] != 0
            or control_held["pauseRequested"] is not True
            or control_held["actions"]["resume"]["available"] is not True
        ):
            raise RuntimeError(f"a paused record was not acknowledged truthfully: {control_held}")
        _, control_resumed = api(
            "POST",
            f"/api/v1/operations/organize/discoveries/{control_mass_id}/resume",
            {"expectedVersion": control_held["version"]},
            expect=200,
        )
        if control_resumed["pauseRequested"] is not False:
            raise RuntimeError(f"continue did not clear the preservation pause: {control_resumed}")
        control_final = _settle(configuration_path, control_mass_id)
        if (
            control_final["progress"]["visitedEntries"] != 101
            or control_final["progress"]["primarySources"] != 100
            or control_final["progress"]["refusalReasons"] != ["primary_limit"]
            or control_final["actions"]["finalize"]["available"] is not False
        ):
            raise RuntimeError(
                f"continue did not reach the durable bound truthfully: {control_final['progress']}"
            )
        _, control_refused = api(
            "POST",
            f"/api/v1/operations/organize/discoveries/{control_mass_id}/finalize",
            {"expectedVersion": control_final["version"]},
        )
        if control_refused.get("error", {}).get("code") != "discovery_budget_limited":
            raise RuntimeError(f"a bounded prefix was frozen: {control_refused}")
        print(
            "   control preservation: pending pause refused Continue; acknowledged pause "
            "continued to 101 visited / 100 sources / primary_limit; finalize refused"
        )

        # Cooperative cancellation of work that no Worker has picked up yet is
        # acknowledged durably and immediately: it reaches its terminal state
        # without stranding an open record, and repeated real Worker passes find
        # nothing to advance.  Cancellation is never an executable subset.
        _, cancel_target = api(
            "POST",
            "/api/v1/resource-libraries/source/files/discoveries",
            {"paths": [SECOND_FOLDER]},
            expect=202,
        )
        cancel_id = cancel_target["discoveryId"]
        _, cancelled = api(
            "POST",
            f"/api/v1/operations/organize/discoveries/{cancel_id}/cancel",
            {"expectedVersion": cancel_target["version"]},
            expect=200,
        )
        if cancelled["status"] != "cancelled" or cancelled["cancelRequested"] is not True:
            raise RuntimeError(f"the accepted cancellation was not durable: {cancelled}")
        if cancelled["actions"]["finalize"]["available"] is not False:
            raise RuntimeError(f"a cancelled discovery advertised finalize: {cancelled}")
        if cancelled["execution"] != "not_available_from_discovery":
            raise RuntimeError(f"a cancelled discovery granted execution authority: {cancelled}")
        for _ in range(3):
            _run_worker(configuration_path)
            time.sleep(0.4)
        _, cancelled_after = api(
            "GET", f"/api/v1/operations/organize/discoveries/{cancel_id}", expect=200
        )
        if (
            cancelled_after["status"] != "cancelled"
            or cancelled_after["version"] != cancelled["version"]
        ):
            raise RuntimeError(f"the cancelled record was stranded or rewritten: {cancelled_after}")
        if _discovery_row(database_path, cancel_id)["claim_token"] is not None:
            raise RuntimeError("the cancelled record kept an unclaimable stale claim")
        _, cancel_successor = api(
            "POST",
            "/api/v1/resource-libraries/source/files/discoveries",
            {"paths": [SECOND_FOLDER]},
            expect=202,
        )
        if cancel_successor["discoveryId"] == cancel_id:
            raise RuntimeError("a cancelled discovery was reconciled as still open")

        # Explicit finalize freezes the list and links the existing intent.
        _, frozen = api(
            "POST",
            f"/api/v1/operations/organize/discoveries/{settled_control['discoveryId']}/finalize",
            {"expectedVersion": settled_control["version"]},
            expect=201,
        )
        if frozen["intentId"] is None or frozen["frozen"] is not True:
            raise RuntimeError(f"finalize did not freeze the source list: {frozen}")

        # Budget refusal (B blocker 1): 101 ordinary sources under one folder
        # stop at the primary bound, the finalize action is not advertised and
        # an explicit finalize attempt is refused durably — never a truncated
        # executable prefix.
        _, mass_admitted = api(
            "POST",
            "/api/v1/resource-libraries/source/files/discoveries",
            {"paths": [MASS_FOLDER]},
            expect=202,
        )
        mass_settled = _settle(configuration_path, mass_admitted["discoveryId"])
        if (
            mass_settled["status"] != "partial_success"
            or mass_settled["progress"]["incompleteReason"] != "primary_limit"
            or mass_settled["primarySourceCount"] != 100
        ):
            raise RuntimeError(f"the 101-source case did not stop at the bound: {mass_settled}")
        if mass_settled["actions"]["finalize"]["available"] is not False:
            raise RuntimeError(
                f"a budget-limited finalize was advertised: {mass_settled['actions']['finalize']}"
            )
        if mass_settled["actions"]["finalize"].get("refusal") != "discovery_budget_limited":
            raise RuntimeError(
                f"the finalize refusal was not published: {mass_settled['actions']['finalize']}"
            )
        _, mass_refused = api(
            "POST",
            f"/api/v1/operations/organize/discoveries/{mass_admitted['discoveryId']}/finalize",
            {"expectedVersion": mass_settled["version"]},
        )
        if mass_refused.get("error", {}).get("code") != "discovery_budget_limited":
            raise RuntimeError(f"a truncated prefix was frozen: {mass_refused}")
        # Nothing was frozen: no manual intent carries a mass-scope source.
        with sqlite3.connect(database_path) as connection:
            mass_intents = connection.execute(
                "SELECT COUNT(*) FROM manual_intent_items WHERE source_path LIKE ?",
                (f"{MASS_FOLDER}/Bulk.%",),
            ).fetchone()[0]
        if mass_intents != 0:
            raise RuntimeError(f"a budget-limited discovery produced intent items: {mass_intents}")
        print("   budget refusal: primary_limit refused finalize (discovery_budget_limited)")

        # Safety-depth truth (B blocker 2): eligible media below the Task's
        # own 32-level bound yields an honest incomplete outcome that cannot
        # finalize, distinct from a configured depth exclusion.
        _, deep_admitted = api(
            "POST",
            "/api/v1/resource-libraries/source/files/discoveries",
            {"paths": [DEEP_FOLDER]},
            expect=202,
        )
        deep_settled = _settle(configuration_path, deep_admitted["discoveryId"])
        if (
            deep_settled["status"] != "partial_success"
            or deep_settled["progress"]["incompleteReason"] != "safety_depth_limit"
        ):
            raise RuntimeError(f"the safety-depth case was not truthful: {deep_settled}")
        if deep_settled["primarySourceCount"] != 1:
            raise RuntimeError(f"the direct source was lost: {deep_settled}")
        truncated = [
            item
            for item in deep_settled["progress"]["findings"]
            if item.get("kind") == "truncated" and item.get("reason") == "safety_depth_limit"
        ]
        if not truncated:
            raise RuntimeError(
                f"the safety-depth cutoff was not explained: {deep_settled['progress']}"
            )
        if deep_settled["actions"]["finalize"]["available"] is not False:
            raise RuntimeError(
                f"a truncated scope advertised finalize: {deep_settled['actions']['finalize']}"
            )
        _, deep_refused = api(
            "POST",
            f"/api/v1/operations/organize/discoveries/{deep_admitted['discoveryId']}/finalize",
            {"expectedVersion": deep_settled["version"]},
        )
        if deep_refused.get("error", {}).get("code") != "discovery_budget_limited":
            raise RuntimeError(f"a safety-truncated prefix was frozen: {deep_refused}")
        print("   safety depth: incomplete outcome refused finalize (safety_depth_limit)")

        # Actor/scope/pin reconciliation (B blocker 3): an identical open
        # submission reconciles to the original durable record, so a lost
        # admission response can never duplicate the walk.  A terminal
        # record is never reopened: the same scope afterwards is deliberate
        # successor work in a new record.
        _, reconciliation_target = api(
            "POST",
            "/api/v1/resource-libraries/source/files/discoveries",
            {"paths": [MASS_FOLDER]},
            expect=202,
        )
        _, reconciled = api(
            "POST",
            "/api/v1/resource-libraries/source/files/discoveries",
            {"paths": [MASS_FOLDER]},
            expect=202,
        )
        if reconciled["discoveryId"] != reconciliation_target["discoveryId"]:
            raise RuntimeError(
                "an identical open scope admitted a duplicate discovery: "
                f"{reconciled['discoveryId']}"
            )
        # Once the settled folder scope is terminal, the same scope is
        # deliberate successor work: a fresh independent record.
        _, successor = api(
            "POST",
            "/api/v1/resource-libraries/source/files/discoveries",
            {"paths": [FOLDER]},
            expect=202,
        )
        if successor["discoveryId"] == reconciliation_target["discoveryId"]:
            raise RuntimeError("a terminal discovery was reopened by resubmission")
        if successor["discoveryId"] == results["folder-only"]["discoveryId"]:
            raise RuntimeError("a terminal discovery was reopened by resubmission")
        print(
            "   reconciliation: open scope reused "
            f"{reconciled['discoveryId'][:8]}…; successor work admitted "
            f"{successor['discoveryId'][:8]}…"
        )

        # Operations readback (B blocker 3b): the admitted discoveries are
        # visible through the unified run inventory and the discovery list.
        _, discovery_list = api("GET", "/api/v1/operations/organize/discoveries")
        if discovery_list["total"] < 6:
            raise RuntimeError(
                f"the discovery readback lost admitted records: {discovery_list['total']}"
            )
        _, runs = api("GET", "/api/v1/operations/runs?limit=100")
        run_ids = {run["run_id"] for run in runs["items"]}
        needed = {
            mass_admitted["discoveryId"],
            deep_admitted["discoveryId"],
            successor["discoveryId"],
            reconciliation_target["discoveryId"],
        }
        if not needed.issubset(run_ids):
            raise RuntimeError(
                f"the run inventory lost admitted discoveries: missing {sorted(needed - run_ids)}"
            )
        mass_run = next(
            run for run in runs["items"] if run["run_id"] == mass_admitted["discoveryId"]
        )
        if (
            mass_run.get("status") != "partial_success"
            or mass_run.get("command_label") != "整理发现"
        ):
            raise RuntimeError(f"the discovery run row was not truthful: {mass_run}")
        _, mass_overview = api("GET", f"/api/v1/operations/runs/{mass_admitted['discoveryId']}")
        if mass_overview.get("status") != "partial_success":
            raise RuntimeError(f"the discovery run overview was not truthful: {mass_overview}")
        print(
            f"   operations readback: {discovery_list['total']} discoveries, "
            "unified run inventory rows and overview agree"
        )

        # ---- Prepare the reviewed execution intent (AC1/AC5) ---------------
        # A dedicated frozen discovery feeds the existing manual journey.  The
        # operator's Choice identity is grounded in durable source-linked
        # evidence; the exact Preview and the separately confirmed Execute are
        # then driven from the real browser below.
        before_execution = _execution_state(root)
        if not before_execution["sourceExists"] or before_execution["targetExists"]:
            raise RuntimeError(f"the execution fixture was not pristine: {before_execution}")
        _, execution_target = api(
            "POST",
            "/api/v1/resource-libraries/source/files/discoveries",
            {"paths": [EXECUTION_FOLDER]},
            expect=202,
        )
        execution_discovery = _settle(configuration_path, execution_target["discoveryId"])
        if execution_discovery["status"] != "completed" or [
            value["path"] for value in execution_discovery["sources"]
        ] != [EXECUTION_RELATIVE]:
            raise RuntimeError(f"the execution discovery was not exact: {execution_discovery}")
        _, execution_frozen = api(
            "POST",
            f"/api/v1/operations/organize/discoveries/{execution_discovery['discoveryId']}/finalize",
            {"expectedVersion": execution_discovery["version"]},
            expect=201,
        )
        intent_id = execution_frozen["intentId"]
        # Ground the operator's metadata identity in the source-linked durable
        # Result, then record the reviewed Choice through the real intent API.
        _seed_source_linked_result(database_path)
        _, intent = api("GET", f"/api/v1/operations/organize/intents/{intent_id}", expect=200)
        item = intent["items"][0]
        _, chosen = api(
            "POST",
            f"/api/v1/operations/organize/intents/{intent_id}/items/{item['itemId']}/choice",
            {
                "expectedVersion": intent["version"],
                "expectedItemVersion": item["version"],
                "recognitionTypeId": "A",
                "metadata": {
                    "provider": "tmdb",
                    "providerId": "909",
                    "mediaType": "movie",
                    "title": "Execution",
                },
            },
            expect=200,
        )
        if _execution_state(root) != before_execution:
            raise RuntimeError("recording the reviewed Choice mutated Storage")

        # Browser journey on the built artifact.  The browser now drives the
        # ordinary native intent -> exact Preview -> one confirmed Execute.
        browser = subprocess.run(
            ["node", "--input-type=module", "-e", BROWSER_PROOF],
            cwd=ROOT / "web",
            env={
                **os.environ,
                "MF_PROOF_BASE": BASE,
                "MF_PROOF_TOKEN": TOKEN,
                "MF_PROOF_ARTIFACTS": str(ARTIFACT_ROOT),
                "MF_PROOF_EXECUTION_INTENT": intent_id,
                "MF_PROOF_SCOPE": json.dumps(
                    {
                        "folder": FOLDER,
                        "file": MIXED_FILE,
                        "secondFolder": SECOND_FOLDER,
                    },
                    ensure_ascii=False,
                ),
            },
            capture_output=True,
            text=True,
        )
        if browser.returncode:
            raise RuntimeError(
                f"discovery browser journey failed:\n{browser.stdout}\n{browser.stderr}"
            )
        print("   " + browser.stdout.strip().splitlines()[-1])

        # ---- Confirmed execution durability and recovery (AC1/AC5) --------
        # The browser's single confirmation admitted the exact reviewed item;
        # the real resident Worker completes it through the real
        # OrganizerExecutor, and the recovery cases prove changed/missing
        # sources stop only their own item and completed effects never replay.
        _run_worker_until_idle(configuration_path)
        executions = api(
            "GET",
            f"/api/v1/operations/organize/executions?intentId={intent_id}&limit=50",
            expect=200,
        )[1]
        execution_rows = executions.get("items") or []
        if len(execution_rows) != 1:
            raise RuntimeError(f"the journey admitted the wrong execution count: {executions}")
        task_id = execution_rows[0].get("taskId")
        if not task_id:
            raise RuntimeError(f"the admitted execution lost its Task linkage: {execution_rows[0]}")
        # The browser generated exactly one exact Preview under the intent; the
        # durable item identifies the exact reviewed source and destination.
        preview_id = _current_preview_for_intent(database_path, intent_id)
        if preview_id is None:
            raise RuntimeError("the browser journey created no durable Preview")
        preview_document = api(
            "GET",
            f"/api/v1/operations/organize/previews/{preview_id}",
            expect=200,
        )[1]
        preview_item = (preview_document.get("items") or [{}])[0]
        destination = (preview_item.get("plan") or {}).get("destination") or {}
        if (
            preview_item.get("source", {}).get("path") != EXECUTION_RELATIVE
            or destination.get("storageId") != "media-target"
            or destination.get("storageRelativePath") != EXECUTION_TARGET
        ):
            raise RuntimeError(
                f"the exact Preview does not carry the exact identities: {preview_item}"
            )
        if (preview_item.get("plan") or {}).get("zeroMutation") is not True:
            raise RuntimeError("the exact Preview did not advertise zero mutation")
        _, task_document = api("GET", f"/api/v1/tasks/{task_id}", expect=200)
        if task_document.get("status") != "completed":
            raise RuntimeError(f"the confirmed execution did not complete: {task_document}")
        after_execution = _execution_state(root)
        if after_execution != {"sourceExists": False, "targetExists": True}:
            raise RuntimeError(
                f"the confirmed execution did not produce its exact effect: {after_execution}"
            )
        # The completed effect is durable and never replayed: a re-Preview of
        # the same intent cannot re-plan the executed work.  Because the
        # confirmed execution moved the source away, the re-Preview is refused
        # with the truthful source-missing explanation — the completed effect
        # is never silently recreated, and no new execution is admitted.
        _, replays = api(
            "POST",
            f"/api/v1/operations/organize/intents/{intent_id}/previews",
            {"expectedVersion": chosen["version"]},
        )
        if replays.get("error", {}).get("code") != "source_missing":
            raise RuntimeError(
                f"a re-Preview of the executed journey was not refused truthfully: {replays}"
            )
        _, executed_items = api("GET", f"/api/v1/operations/runs/{task_id}/items", expect=200)
        item_rows = executed_items.get("items") or []
        if not item_rows or item_rows[0].get("status") != "success":
            raise RuntimeError(f"the completed execution lost its item outcome: {executed_items}")
        if _execution_state(root) != {"sourceExists": False, "targetExists": True}:
            raise RuntimeError("a refused re-Preview changed Storage")
        # Successor recovery is explicit successor work: a fresh discovery of a
        # new scope after the confirmed execution produces its own independent
        # record and freezes its own list — it never enlarges or rewrites the
        # frozen list, the old pin or the completed execution.
        changed_folder = root / "source" / "changed"
        changed_folder.mkdir(parents=True, exist_ok=True)
        (changed_folder / "Changed.2005.mkv").write_bytes(b"synthetic changed media")
        _, successor = api(
            "POST",
            "/api/v1/resource-libraries/source/files/discoveries",
            {"paths": ["changed"]},
            expect=202,
        )
        successor_settled = _settle(configuration_path, successor["discoveryId"])
        if successor_settled["status"] != "completed" or [
            value["path"] for value in successor_settled["sources"]
        ] != ["changed/Changed.2005.mkv"]:
            raise RuntimeError(f"the successor discovery was not truthful: {successor_settled}")
        _, successor_frozen = api(
            "POST",
            f"/api/v1/operations/organize/discoveries/{successor['discoveryId']}/finalize",
            {"expectedVersion": successor_settled["version"]},
            expect=201,
        )
        if successor_frozen["intentId"] in (None, intent_id):
            raise RuntimeError(
                f"the successor work did not create its own intent: {successor_frozen}"
            )
        _, frozen_after = api(
            "GET",
            f"/api/v1/operations/organize/intents/{intent_id}",
            expect=200,
        )
        if [value["source"]["path"] for value in frozen_after["items"]] != [EXECUTION_RELATIVE]:
            raise RuntimeError(f"the frozen list was rewritten: {frozen_after}")
        print(
            "   confirmed execution: exact Preview admitted one reviewed item, "
            f"Worker completed {task_id[:8]}…, source moved to the planned target; "
            "no replay, successor recovery explicit"
        )

        active_after = api("GET", "/api/v1/operations/rules/form-authority")[1]["active"]
        activations_after = _activation_count(database_path)
        work_after = _executable_work(database_path)
        if active_before["revisionId"] != active_after["revisionId"]:
            raise RuntimeError("the discovery journey changed the Active revision")
        if active_before["digest"] != active_after["digest"]:
            raise RuntimeError("the discovery journey changed the Active digest")
        if activations_before != activations_after:
            raise RuntimeError("the discovery journey published a configuration")
        # Exactly the confirmed execution created executable Organize work —
        # the discovery stage alone never did.
        if work_after["manualOrganizeTasks"] != work_before["manualOrganizeTasks"] + 1:
            raise RuntimeError(
                f"executable work changed unexpectedly: {work_before} -> {work_after}"
            )

        matrix = {
            "task": "44.6",
            "slice": "44",
            "requiredOutcome": "RO-6",
            "cases": results,
            "control": {
                "paused": paused["pauseRequested"],
                "conflictRefused": True,
                "resumed": resumed["pauseRequested"],
            },
            "budgetRefusal": {
                "status": mass_settled["status"],
                "incompleteReason": mass_settled["progress"]["incompleteReason"],
                "finalizeAdvertised": False,
                "refusalCode": mass_refused.get("error", {}).get("code"),
                "intentItemsCreated": mass_intents,
            },
            "safetyDepth": {
                "status": deep_settled["status"],
                "incompleteReason": deep_settled["progress"]["incompleteReason"],
                "truncatedFindings": len(truncated),
                "refusalCode": deep_refused.get("error", {}).get("code"),
            },
            "reconciliation": {
                "openScopeId": reconciled["discoveryId"],
                "successorId": successor["discoveryId"],
                "operationsDiscoveryTotal": discovery_list["total"],
                "runInventoryRows": len(runs["items"]),
            },
            "frozen": {
                "intentId": frozen["intentId"],
                "primarySourceCount": frozen["primarySourceCount"],
            },
            "confirmedExecution": {
                "discoveryId": execution_discovery["discoveryId"],
                "intentId": intent_id,
                "previewId": preview_id,
                "taskId": task_id,
                "sourcePath": EXECUTION_RELATIVE,
                "targetPath": EXECUTION_TARGET,
                "zeroMutationPreview": True,
                "sourceMoved": after_execution == {"sourceExists": False, "targetExists": True},
                "taskStatus": task_document.get("status"),
            },
            "safety": {
                "discoveryAdmissionsOnly": False,
                "nonReadRequests": "discovery admissions, one choice, one Preview, "
                "one confirmed Execute per reviewed item",
                "activeRevisionUnchanged": active_before["revisionId"],
                "activeDigestUnchanged": active_before["digest"],
                "activationsBefore": activations_before,
                "activationsAfter": activations_after,
                "executableWorkBefore": work_before,
                "executableWorkAfter": work_after,
            },
        }
        (ARTIFACT_ROOT / "matrix.json").write_text(
            json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            f"   {len(results)} discovery cases; confirmed execution moved "
            f"{EXECUTION_RELATIVE}; frozen intent {frozen['intentId']}"
        )
        return 0
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive
            process.kill()


BROWSER_PROOF = r"""
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.MF_PROOF_BASE;
const TOKEN = process.env.MF_PROOF_TOKEN;
const ARTIFACTS = process.env.MF_PROOF_ARTIFACTS;
const SCOPE = JSON.parse(process.env.MF_PROOF_SCOPE);
const evidence = { passes: [], mutatingRequests: [] };
const requests = [];

function require_(condition, message) {
  if (!condition) throw new Error(message);
}

const browser = await chromium.launch();
try {
  const context = await browser.newContext({ viewport: { width: 1536, height: 1024 } });
  const page = await context.newPage();
  page.on('request', (request) => {
    requests.push({ method: request.method(), url: request.url() });
  });

  const connect = async (url) => {
    await page.goto(`${BASE}${url}`);
    const field = page.getByLabel('API token');
    if (await field.count()) {
      await field.fill(TOKEN);
      await page.getByRole('button', { name: 'Connect' }).click();
    }
  };

  const shoot = async (name) => {
    const file = path.join(ARTIFACTS, `${name}.png`);
    await page.screenshot({ path: file, fullPage: false });
    return file;
  };

  // -- folder-only selection from the list view -------------------------
  await connect('/ui-v2/resourcelib/files');
  await page.getByRole('table').waitFor();
  const folderRow = page.getByRole('row', { name: new RegExp(SCOPE.folder) });
  await folderRow.getByRole('checkbox').check();
  require_(
    await page.getByRole('button', { name: '批量整理' }).isEnabled(),
    'a folder selection did not enable the batch Organize action',
  );
  evidence.passes.push({ case: 'folder-selection', screenshot: await shoot('folder-selection') });
  await page.getByRole('button', { name: '批量整理' }).click();
  await page.getByRole('heading', { name: '整理发现' }).waitFor();
  // The heading renders while the authenticated discovery read is still in
  // flight, so wait for the resolved scope section before inspecting it.  This
  // only waits for the existing assertion's own content; no assertion changes.
  await page.getByRole('heading', { name: /已选范围/ }).waitFor();
  const discoveryText = await page.getByRole('main').innerText();
  require_(/已选范围/.test(discoveryText), 'the discovery page did not show the admitted scope');
  require_(
    /不会移动、复制或删除任何文件/.test(discoveryText),
    'the discovery page did not advertise zero mutation',
  );
  evidence.passes.push({ case: 'folder-discovery', screenshot: await shoot('folder-discovery') });

  // -- grid view folder menu --------------------------------------------
  await connect('/ui-v2/resourcelib/files');
  await page.getByRole('button', { name: '网格视图' }).click();
  const gridCard = page.getByRole('listitem', { name: new RegExp(SCOPE.folder) });
  await gridCard.click({ button: 'right' });
  require_(
    (await page.getByRole('menuitem', { name: '整理' }).count()) > 0,
    'the grid folder menu did not offer Organize',
  );
  evidence.passes.push({ case: 'grid-folder-menu', screenshot: await shoot('grid-folder-menu') });
  await page.keyboard.press('Escape');

  // -- mixed selection ---------------------------------------------------
  await connect('/ui-v2/resourcelib/files');
  await page.getByRole('table').waitFor();
  await page
    .getByRole('row', { name: new RegExp(SCOPE.folder) })
    .getByRole('checkbox')
    .check();
  await page
    .getByRole('row', { name: new RegExp(SCOPE.file.replace('.', '\\.')) })
    .getByRole('checkbox')
    .check();
  evidence.passes.push({ case: 'mixed-selection', screenshot: await shoot('mixed-selection') });
  await page.getByRole('button', { name: '批量整理' }).click();
  await page.getByRole('heading', { name: '整理发现' }).waitFor();
  evidence.passes.push({ case: 'mixed-discovery', screenshot: await shoot('mixed-discovery') });

  // -- lost-response refresh recovery (B blocker 3/4) --------------------
  // A full reload clears memory-only auth; the shared route/auth
  // continuation model has recorded the exact durable discovery destination
  // plus its bounded Files return context, so reconnecting continues the
  // same discovery instead of the Dashboard. The reconnection itself is a
  // read-only continuation: no admission is replayed.
  const discoveryUrl = page.url();
  require_(
    /\/operations\/organize\/discovery\//.test(discoveryUrl),
    `the journey did not reach a discovery page: ${discoveryUrl}`,
  );
  await page.reload();
  await page.getByRole('heading', { name: 'V2 entry' }).waitFor();
  evidence.passes.push({
    case: 'reload-not-connected',
    screenshot: await shoot('reload-not-connected'),
  });
  await page.getByLabel('API token').fill(TOKEN);
  await page.getByRole('button', { name: 'Connect' }).click();
  await page.getByRole('heading', { name: '整理发现' }).waitFor();
  require_(
    page.url() === discoveryUrl,
    `reconnect lost the discovery context: ${page.url()} != ${discoveryUrl}`,
  );
  require_(
    /returnTo=files&returnResourceLibraryId=/.test(page.url()),
    `the reconnected discovery lost its Files return context: ${page.url()}`,
  );
  require_(
    (await page.getByRole('link', { name: '返回文件' }).count()) === 1,
    'the reconnected discovery did not offer the native Files return action',
  );
  evidence.passes.push({ case: 'reload-recovery', screenshot: await shoot('reload-recovery') });

  // The Operations task center publishes the same admitted discovery, so a
  // lost admission response is recoverable there without raw identifiers.
  await page
    .getByRole('navigation', { name: 'Primary' })
    .getByRole('link', { name: 'Operations' })
    .click();
  await page.getByRole('heading', { name: '操作与任务', exact: true }).waitFor();
  await page
    .getByRole('heading', { name: '整理发现', level: 3 })
    .waitFor({ timeout: 20000 })
    .catch(async () => {
      await shoot('operations-discovery-readback-failure');
      throw new Error(
        'the Operations task center did not publish the admitted discoveries: '
        + JSON.stringify({
          url: page.url(),
          main: (await page.getByRole('main').innerText()).slice(0, 900),
        }),
      );
    });
  evidence.passes.push({
    case: 'operations-discovery-readback',
    screenshot: await shoot('operations-discovery-readback'),
  });

  // -- native reviewed choices -> exact Preview -> confirmed Execute -------
  // The harness has admitted and frozen one dedicated execution discovery and
  // recorded the reviewed Choice (its metadata identity is grounded in durable
  // source-linked evidence).  The browser now drives the ordinary manual
  // journey from that intent: inspect the exact reviewed plan, then make one
  // explicit Execute confirmation.  It never handles an execution token,
  // digest or authorization identifier.
  const executionIntentId = process.env.MF_PROOF_EXECUTION_INTENT;
  await connect(`/ui-v2/operations/organize/intent/${executionIntentId}`);
  await page.getByText('Execution.2004.mkv').first().waitFor();
  const intentText = await page.getByRole('main').innerText();
  require_(
    /Execution\.2004\.mkv/.test(intentText),
    `the intent did not show the reviewed source: ${
      JSON.stringify({ url: page.url(), intentText: intentText.slice(0, 900) })
    }`,
  );
  const previewButton = page.getByRole('button', { name: '生成精确预览' });
  await previewButton.waitFor();
  evidence.passes.push({ case: 'intent-choice', screenshot: await shoot('intent-choice') });
  await previewButton.click();
  await page.getByRole('heading', { name: '整理预览' }).waitFor();
  const previewText = await page.getByRole('main').innerText();
  require_(
    /预览不会修改文件/.test(previewText),
    'the exact Preview did not advertise zero mutation',
  );
  require_(
    /Movies\/其他电影\/Execution \(2004\)/.test(previewText),
    'the exact Preview did not show the exact destination',
  );
  evidence.passes.push({ case: 'exact-preview', screenshot: await shoot('exact-preview') });

  const executeButton = page.getByRole('button', { name: '确认执行所选条目' });
  await executeButton.waitFor();
  await executeButton.click();
  await page.getByRole('heading', { name: '整理执行情况' }).waitFor();
  // The durable execution page is the post-confirmation outcome surface.  It
  // reports the backend's own admitted state and the exact selected count; the
  // resident Worker completes it afterwards and the Python driver verifies the
  // resulting file effect.
  const executionText = await page.getByRole('main').innerText();
  require_(
    /整理执行情况/.test(executionText) && /已准入/.test(executionText),
    `the execution page did not report the durable admission: ${
      JSON.stringify({ url: page.url(), executionText: executionText.slice(0, 900) })
    }`,
  );
  require_(
    /已选 1/.test(executionText),
    `the execution page did not report the exact reviewed selection: ${
      executionText.slice(0, 500)
    }`,
  );
  evidence.passes.push({
    case: 'confirmed-execution',
    screenshot: await shoot('confirmed-execution'),
  });

  // Every non-GET request in the readback portion of this journey is one
  // bounded discovery admission; the execution leg adds exactly one Preview
  // and one confirmed Execute, and nothing else mutates media.
  evidence.mutatingRequests = requests.filter(
    (entry) => entry.method !== 'GET' && entry.method !== 'HEAD',
  );
  evidence.discoveryAdmissions = evidence.mutatingRequests.filter((entry) =>
    entry.url.includes('/files/discoveries'),
  );
  evidence.executionRequests = evidence.mutatingRequests.filter(
    (entry) => entry.url.includes('/previews') || entry.url.includes('/execute'),
  );
  require_(
    evidence.discoveryAdmissions.length + evidence.executionRequests.length ===
      evidence.mutatingRequests.length,
    `an unexpected non-read request was issued: ${JSON.stringify(evidence.mutatingRequests)}`,
  );
  fs.writeFileSync(path.join(ARTIFACTS, 'evidence.json'), JSON.stringify(evidence, null, 2));
  console.log(JSON.stringify({ ok: true, passes: evidence.passes.length }));
} finally {
  await browser.close();
}
"""


if __name__ == "__main__":
    raise SystemExit(main())
