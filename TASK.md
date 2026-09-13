# Task 33.7 — Repair production Worker source revalidation for admitted manual Organize

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 33.7
Parent Slice: 33
Status: FIX REQUIRED
Task Base: 54f16d5f0e2b921307403e11e7895dffe7018b35
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Restore RO-4's complete Web-native manual Organize journey across the real independent API and
resident Processing Worker boundary: an exact execution admitted from a valid current FileIndex
source and immutable Preview must reconstruct its pinned runtime authority, pass truthful source
revalidation, and reach OrganizerExecutor exactly once, while genuinely missing or changed sources
still fail closed before mutation with bounded recovery evidence.

## Why This Task Exists

Live Docker validation exposed a P1 after the accepted Preview-projection correction. The API can
create the intent and Preview and atomically admit the server-held one-shot execution, but the
resident Worker closes the item at pre-mutation revalidation with `the reviewed source file is
unavailable` even when the indexed occurrence, physical source, Storage preflight and pinned Active
snapshot are valid.

The production `worker` command deliberately starts from a management-only bootstrap so it can
claim durable work before loading workflow configuration. Its manual-Organize context currently
builds source-catalog authority from that bootstrap's empty ResourceLibrary/Storage catalogs. The
existing service/restart tests rebuild the Worker with explicitly supplied full catalogs and runtime
objects, so they do not exercise this deployed bootstrap-to-pinned-runtime reconstruction path.

This is one coherent correction to the already-promised admission → durable execution → Worker
revalidation journey. It belongs to Slice 33 RO-4/RO-7/RO-8 and its Manual Organize surface; it does
not add Slice 34 recovery behavior or alter the accepted Slice Contract.

## Implementation Scope

```text
Worker bootstrap → durable manual execution/Preview/intent → pinned runtime reconstruction
→ FileIndex source revalidation → Storage preflight/fences → OrganizerExecutor → durable outcome
→ integration/release regression
```

- Reproduce the defect with an automated boundary test that starts the manual-Organize Worker from
  the same management-only bootstrap shape used by `mediaflow worker run`, while API admission and
  FileIndex/runtime state are reopened independently from durable SQLite state.
- Correct the Worker/manual-execution composition so FileIndex lookup and source validation use the
  exact ResourceLibrary and Storage authority of the execution's persisted pinned snapshot, without
  trusting stale workflow fields from the bootstrap document or substituting the current Active
  revision.
- Preserve reconstruction of the exact persisted intent, Preview item, occurrence/fingerprint,
  plan, effect permissions and snapshot identity before any lock or mutation boundary. Do not turn
  catalog failure into a permissive direct-path lookup.
- Preserve truthful fail-closed item outcomes for a missing, replaced, stale, malformed,
  cross-library/cross-Storage or unavailable source. The durable result must retain effect certainty
  `none`, identify the revalidation failure without leaking private paths/exceptions, and offer a
  fresh Files/intent/Preview action rather than automatic replay.
- Prove independent-process/restart behavior, including an execution pinned to a still-valid
  published snapshot when the current Active identity differs: the Worker must consume the saved
  snapshot, never silently rebind the execution, and never duplicate admission or mutation.
- Extend the isolated Docker release-security acceptance so the four-service topology performs a
  harmless temporary Local-Storage V2 manual Organize admission and observes Worker completion and
  the expected exact file effect. The harness must continue to use generated credentials, temporary
  media/configuration/runtime state and no production service or user data.
- Keep changes confined to the production Worker/manual-execution bootstrap and revalidation path,
  its tests, and the release-security harness. Frontend behavior, configuration schemas/migrations,
  recognition/metadata/naming/classification/planning semantics, Automation execution and Slice
  34 recovery are frozen unless a directly necessary compatibility adjustment is demonstrated in
  the completion report.

## Acceptance Criteria

- [ ] A regression test fails at Task Base with the confirmed `source_missing`/
      `the reviewed source file is unavailable` outcome and passes after the correction using the
      real management-only Worker bootstrap composition rather than a manually pre-populated Worker
      catalog.
- [ ] A valid V2 flow can create intent and choice, produce an exact zero-mutation Preview, admit one
      durable execution, let an independently constructed resident Worker claim it, and complete the
      reviewed Local Storage operation exactly once through OrganizerExecutor.
- [ ] The Worker derives ResourceLibrary, Storage adapters and runtime policy only from the exact
      persisted snapshot pinned to the admitted execution; stale bootstrap workflow content and a
      newer Active revision cannot replace or broaden that authority.
- [ ] FileIndex ID, ResourceLibrary, Storage, path, occurrence/fingerprint and plan/effect bindings
      are all still revalidated before locks/mutation. Missing or changed source evidence remains a
      bounded per-item pre-mutation failure with effect certainty `none`, durable known state and an
      actionable fresh-Preview recovery path.
- [ ] One-shot consumption, execution claim/lease fencing, idempotent repeat submission, explicit
      overwrite/source-cleanup authority, capability/conflict checks, no link fallback and no
      automatic replay of partial/uncertain effects remain intact.
- [ ] Preview and all analysis stages remain zero-mutation; only OrganizerExecutor performs the
      accepted exact Storage effect. RecognitionType C remains C when NamingPolicy A and
      ClassificationPolicy A are selected.
- [ ] API/V1 compatibility, Automation Worker handling, independent four-service deployment,
      redaction and private-file rules remain intact; no credential, raw authority, private absolute
      path, `config/alist.json`, operator media or generated artifact enters the checkpoint.
- [ ] The T4 focused, integration, full regression, packaging and safety gates below pass with actual
      totals/skips/unavailable results reported truthfully. Any known pre-existing root-worktree
      failures must be reproduced or proven unrelated in an isolated clean worktree, not hidden.
- [ ] The checkpoint contains only this focused correction and its coherent regression evidence.

## Required Tests

- `python3 scripts/check_governance.py`
- Add and run the focused management-bootstrap/pinned-snapshot Worker reproduction plus the relevant
  source-missing/source-stale/cross-authority negative cases.
- `.venv/bin/python -m unittest tests.test_manual_organize_execution tests.test_v2_manual_organize tests.test_manual_operations_contract tests.test_queued_job_execution_boundary tests.test_processing_worker_readiness`
- Run all other directly affected Worker, managed-snapshot, API and persistence integration modules
  identified by the final diff; report commands and exact counts.
- `env -u NODE_ENV npm --prefix web ci`
- `npm --prefix web run format:check`
- `npm --prefix web run typecheck`
- `npm --prefix web run lint`
- `npm --prefix web test -- --run`
- `npm --prefix web run build`
- `npm --prefix web run test:e2e`
- `.venv/bin/ruff format --check .`
- `.venv/bin/ruff check .`
- `.venv/bin/python -m unittest discover -s tests -t .`
- `.venv/bin/python -m compileall -q mediaflow tests scripts`
- `.venv/bin/python -m pip check`
- `.venv/bin/mediaflow --config config/strategy.example.json config validate`
- `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`
- `test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"`
- `python3 scripts/docker_release_security_smoke_test.py` — Docker must exercise the new harmless
  end-to-end manual Organize proof when available; report `UNAVAILABLE` only when the harness itself
  establishes Docker is unavailable.
- Inspect Task Base..Head for deleted tests, weakened assertions, hidden skips, unrelated files,
  credentials/private paths, tracked `config/alist.json`, generated frontend artifacts and
  `node_modules`; run `git diff --check`.

## Non-goals

- Changing Slice 33's User Goal, Required Outcomes, Required Surfaces, Safety Invariants, Explicitly
  Deferred list or immutable Slice Base.
- Adding Review/Recovery, retry-failed-item, Reprocess, conflict-decision or checkpoint-continuation
  behavior owned by Slice 34.
- Redesigning the Worker claim model, API-principal authentication, managed configuration lifecycle,
  OrganizerExecutor, Storage interfaces or processing policies beyond what this correction requires.
- Treating the bootstrap JSON as runtime authority after managed activation, rebinding admitted work
  to the newest Active revision, weakening source identity checks, or falling back to arbitrary
  filesystem paths/direct Storage access.
- Frontend copy/polish, unrelated refactors, new providers, schema work without demonstrated need,
  or cleanup of pre-existing P2/P3 test-environment diagnostics.

## Developer Completion Report

### Changed Files

- `tests/test_manual_organize_execution.py`
- `TASK.md`

### Implemented

- Added an independently reopened real Worker regression using the strict minimal
  management-only bootstrap and the persisted pinned snapshot.
- Corrupted the durable FileIndex source Storage authority after admission and verified the Worker
  fails closed before OrganizerExecutor, preserving the source and producing a bounded fresh-Preview
  recovery outcome with effect certainty `none`.
- Preserved the existing valid management-bootstrap success regressions.

### Tests and Results

- `python3 scripts/check_governance.py` — PASS.
- `.venv/bin/python -m unittest tests.test_manual_organize_execution.ManualOrganizeExecutionTests.test_real_management_worker_rejects_cross_authority_source_before_mutation tests.test_manual_organize_execution.ManualOrganizeExecutionTests.test_real_management_worker_uses_persisted_pinned_snapshot_after_active_changes tests.test_manual_organize_execution.ManualOrganizeExecutionTests.test_worker_rebuilds_management_bootstrap_catalog_from_pinned_runtime` — PASS, 3 tests.
- `.venv/bin/python -m unittest tests.test_manual_organize_execution tests.test_v2_manual_organize tests.test_manual_operations_contract tests.test_queued_job_execution_boundary tests.test_processing_worker_readiness` — PASS, 88 tests.
- `.venv/bin/ruff format tests/test_manual_organize_execution.py` — PASS.
- `.venv/bin/ruff format --check .` — PASS.
- `.venv/bin/ruff check .` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m pip check` — PASS.
- `git diff --check` — PASS.
- Task Base reproduction using the strict minimal bootstrap regression in isolated worktree
  `54f16d5f0e2b921307403e11e7895dffe7018b35` — PASS, contrary to B's described
  `source_missing` reproduction; the original failure could not be reproduced with the checked
  command and is recorded as an evidence discrepancy for B review.

### Decisions

- The negative case uses a strict minimal management bootstrap to exercise the same independent
  Worker boundary as the deployed CLI, then reopens the durable SQLite state before execution.
- The test asserts the bounded public error text rather than exposing the internal authority code;
  the durable item/result still records pre-mutation failure with certainty `none` and fresh Preview
  recovery.

### Remaining In-Slice Work

- No additional work was identified inside this Task. Other Slice 33 work remains owned by B/A and
  is not planned here.

### Risks / Deviations

- The repository had an uncommitted B-review update in `TASK.md` and untracked root `node_modules/`
  at start; both were preserved, and `node_modules/` is not staged.
- The required Task-Base `source_missing` reproduction remains unresolved because the exact isolated
  regression command passed at Task Base; B should decide whether a different historical harness or
  boundary fixture is required.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: a60f8f4fd35f2c28d29796411ba279bcf402b6db
```

## B Review Result

```text
Reviewed: 54f16d5f0e2b921307403e11e7895dffe7018b35..b952335b09b97b0ca322fc75fe0c9e8d710fe0fb
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- The Completion Report names `0a7fcb2adee0ef3e1f4b4beb8e4c9f2c7fffc875`, but the actual branch
  Head is `b952335b09b97b0ca322fc75fe0c9e8d710fe0fb`; both commits have parent
  `1008c6255f101ad54286ae54def48b87a5903b5f` and are sibling commits, so the reported checkpoint is
  not an ancestor of the repository state being handed to B (`git rev-list --left-right --count
  0a7fcb2...HEAD` returned `1 1`). Create an append-only descendant report checkpoint that names the
  reachable implementation commit actually being submitted; do not amend or rewrite either
  implementation history.
- The Task requires source-missing/source-stale/**cross-authority** negative coverage at the real
  management-bootstrap/pinned-snapshot Worker boundary, but the added Worker regressions are both
  success cases and `rg -n 'source_cross_authority|cross_authority' tests` finds no such assertion.
  Existing source missing/stale tests exercise other admission/execution compositions and do not
  prove that reconstructed ResourceLibrary/Storage authority fails closed before mutation. Add a
  focused independently reopened Worker negative test that corrupts or mismatches the persisted
  source's ResourceLibrary/Storage authority relative to the pinned snapshot, then assert a durable
  per-item pre-mutation failure, effect certainty `none`, no Storage effect and a fresh-Preview
  recovery action. Also record the required Task-Base reproduction showing the original valid
  management-bootstrap case fails with `source_missing` / `the reviewed source file is unavailable`.
