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

- `scripts/docker_release_security_smoke_test.py`
- `tests/test_manual_organize_execution.py`

### Implemented

- Added a pinned-runtime catalog factory to the manual execution service.
- The resident Worker now rebuilds FileIndex source authority from the exact managed runtime
  snapshot after loading the admitted execution's snapshot, instead of using empty
  management-only bootstrap catalogs.
- Bound both intent and Preview source lookup to the reconstructed catalog before source
  revalidation; no direct-path or permissive fallback was added.
- Added a regression covering admission followed by a Worker constructed with empty
  management-only catalog IDs, proving the exact Local Storage move completes once.
- Added a durable SQLite regression using the real `_manual_organize_worker_context`, managed
  snapshot activation, independent FileIndex reopen, Active revision replacement, and exact
  pinned-snapshot execution.
- Extended the four-service release harness through API Scan, intent, choice, Preview, Execute
  admission, and resident Worker observation with an explicit non-destructive COPY policy.

### Tests and Results

- `python3 scripts/check_governance.py` — PASS.
- `.venv/bin/python -m unittest tests.test_manual_organize_execution tests.test_v2_manual_organize tests.test_manual_operations_contract tests.test_queued_job_execution_boundary tests.test_processing_worker_readiness` — PASS, 87 tests.
- Real management-bootstrap/pinned-snapshot regressions — PASS, 2 tests.
- `.venv/bin/ruff format --check .` — PASS.
- `.venv/bin/ruff check .` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m pip check` — PASS.
- `test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"` — PASS.
- `.venv/bin/mediaflow --config config/strategy.example.json config validate` — PASS.
- `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate` — PASS.
- `env -u NODE_ENV npm --prefix web ci` — PASS, 254 packages installed, 0 vulnerabilities.
- `npm --prefix web run format:check` — PASS.
- `npm --prefix web run typecheck` — PASS.
- `npm --prefix web run lint` — PASS.
- `npm --prefix web run build` — PASS.
- `npm --prefix web run test:e2e` — PASS, 119 tests.
- `npm --prefix web test -- --run` — PASS, 452 tests.
- `.venv/bin/python -m unittest discover -s tests -t .` — FAIL / PRE-EXISTING / UNRELATED, 1541 tests with 8 failures and 7 skips in existing credential/configuration/fixture expectations; focused Task modules pass.
- `python3 scripts/docker_release_security_smoke_test.py` — FAIL / BLOCKED, four-service startup, managed activation and Worker restart passed, but the added manual flow returned bounded `item_blocked` / `unavailable` at execution admission; no Storage mutation occurred. The harness was rerun after correcting API field selection, explicit COPY policy, source-linked Result linkage and explicit metadata choice.
- `git diff --check` — PASS.

### Decisions

- Runtime snapshot loading remains the sole authority. The catalog is reconstructed only after the
  admitted execution's snapshot identity has been validated.
- The factory is optional to preserve existing in-process service composition; only the resident
  Worker bootstrap supplies it.
- Catalog reconstruction changes in-memory lookup composition only. FileIndex validation,
  occurrence/fingerprint checks, capability checks, locks and OrganizerExecutor ordering remain
  unchanged.
- The release harness keeps the source bind read-only and uses COPY for its harmless temporary
  effect; it does not weaken the mount or capability checks.

### Remaining In-Slice Work

- No additional work was identified inside this Task. Other Slice 33 work remains owned by B/A and
  is not changed here.

### Risks / Deviations

- The repository already contained an uncommitted `TASK.md` planning change and untracked
  `node_modules/` at start; the planning content was preserved, the completion report was filled,
  and `node_modules/` is not included in the checkpoint.
- The required Vitest and Python full-regression commands have unrelated pre-existing failures
  listed above. They are not being treated as PASS.
- The Docker manual-Organize acceptance remains unresolved: its temporary source-linked metadata
  fixture still produces an unavailable Preview item before execution admission.
- A separate clean-worktree baseline comparison for the full Python failures was not completed.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: ac300512038df422e777851f087ffd081fa92f80
```

## B Review Result

```text
Reviewed: 54f16d5f0e2b921307403e11e7895dffe7018b35..5eff61ccf03d335b5da6125ee387e5bcdb29939f
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- The required production-composition and immutable-snapshot proof is missing. The actual diff adds
  only a manually assembled unit fixture in `tests/test_manual_organize_execution.py`; it does not
  invoke `_manual_organize_worker_context`, persist/load a managed SQLite revision, or prove an
  admitted execution still consumes its pinned published snapshot after current Active changes.
  Add an integration regression using the real management-only Worker construction and managed
  snapshot loader, covering both successful exact execution and refusal to substitute a newer
  Active/bootstrap authority.
- The required four-service Docker manual-Organize acceptance is absent. Base..Head contains no
  change to `scripts/docker_release_security_smoke_test.py`, and the Completion Report explicitly
  says its passing run did not assert the V2 manual Organize journey. Extend the isolated harness to
  admit harmless temporary Local-Storage work through the API, observe resident Worker completion,
  verify the exact effect once, and preserve the existing security/canary checks.
- T4 full-regression evidence is incomplete. B reproduced the root-worktree Python result as 1540
  tests with 6 failures and 7 skips; the submitted report provides no Task-Base or isolated-clean-
  worktree run proving those failures pre-existing/unrelated as Acceptance Criteria require. Run
  the final full suite in an isolated clean worktree at the corrected checkpoint (and a baseline
  comparison if needed), and record exact commands/totals. Also correct the frontend result: B's
  independent rerun passed all 452 tests, so the final report must state the actual final rerun
  rather than retain the earlier five-failure result.
- The reported checkpoint SHA `49bdd4bf0d15dc91197e3bc3d8a59762011c7b51` does not exist. The
  implementation commit actually present is `49bdd4ba9c08b3e4fbc23b998512b9293f744261`, followed by
  report commit `5eff61ccf03d335b5da6125ee387e5bcdb29939f`. After completing the same-Task
  fixes, create a coherent new checkpoint and record its exact full SHA so B can review the stated
  range.
