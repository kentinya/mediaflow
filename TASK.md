# Task 40.5 — First-Draft validation and exact-version activation recovery

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
[Slice 40](SLICE.md).

```text
Task ID: 40.5
Parent Slice: 40
Status: PLANNED
Task Base: 0bfcc25ce5dadf2be504239cdae6a67d1c7cb880
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Restore Slice RO-1 and AC-3 by making the ordinary native V2 first-Draft journey carry the exact
post-validation Draft version into checked activation, without a reload workaround, overlapping
writes or any relaxation of backend concurrency and publication safety.

## Why This Task Exists

A's 2026-09-28 Final Review rejected the Slice 40 Closure Packet for one production-reachable P1.
On a legal management-only deployment, the operator created/resumed the first Draft and clicked
`验证 Draft`; the backend advanced the mutable Draft version and returned a validated revision, but
`ConfigurationPage` ignored that success result and retained its earlier `selectedVersion`. The
next `checked-activate` submitted the stale token and the backend correctly returned a conflict.
The actual durable state remained a valid version-3 Draft with no Active, so the operator's data was
safe but the required first-activation journey was blocked.

The existing component test does not cover the real contract: it sources the activation token from
a prior settings-save response and mocks validation without the production version transition. The
largest coherent correction is the Settings mutation lifecycle plus production-shaped tests and a
real Python-served browser proof. Backend optimistic concurrency is working and must remain strict.

## Implementation Scope

Managed configuration response contract → V2 Settings mutation state → real served browser journey
→ focused and T4 regression evidence.

- Make successful first-Draft validation update the page to the exact authoritative validated Draft
  identity and mutable version before checked activation becomes available. Use the bounded backend
  response and/or an exact revision/System Settings reread; never infer or increment a version in the
  browser.
- Serialize create/save/validate/activate actions. While a configuration mutation or its required
  authoritative refresh is pending, conflicting write controls must be disabled so validation and
  activation cannot overlap. Reads and navigation remain side-effect-free.
- Keep activation bound to the selected exact revision. A stale/concurrent response must preserve
  the Draft and any previous Active, report the durable winner/current version and require an
  explicit retry after refresh; unknown outcomes remain blocked pending explicit state verification.
- Preserve correctable System Settings input during the post-validation authoritative refresh where
  safe. Do not expose raw revision ceremony beyond the existing diagnostic state or put Bearer
  authority in URLs, browser storage, logs or errors.
- Correct the Web tests to model the real first-Draft transition with no prior settings save:
  create/resume version N, validate to N+1, then activate with exactly N+1. Cover delayed validation
  so a second write cannot race it, plus stale/concurrent and unknown-outcome recovery regressions.
- Extend or reuse the existing Docker empty-baseline Playwright path so a browser against the real
  Python-served built application performs the actual first-Draft validate → checked-activate
  sequence and observes the empty Active success state. The proof must use isolated fake credentials
  and temporary data and must verify that activation starts no media work, delivery or Storage
  mutation.
- Backend production behavior is frozen unless a minimal response-contract correction is proven
  necessary. Do not weaken expectedVersion checks, checked evidence, atomic runtime binding or RBAC.

## Acceptance Criteria

- [ ] From a fresh management-only deployment, Admin can create or resume the first Draft, validate
      it and immediately checked-activate it through native V2 Settings. The activation request uses
      the exact version produced by validation and succeeds without refresh, repeated validation,
      CLI/API fallback or manual revision/token handling.
- [ ] Validation and activation cannot overlap: all conflicting mutation controls remain disabled
      until the current mutation and authoritative state refresh complete. Double-clicks or delayed
      responses produce at most the explicitly requested safe mutation and never bypass concurrency.
- [ ] The success view reports the actual immutable empty Active and
      `Active 已激活,媒体业务尚未配置`; runtime consumption agrees with that exact revision. Creation,
      validation and activation start no Scan, Job, Task, notification, Provider call or Storage
      mutation.
- [ ] Stale/concurrent validation or activation preserves the current Draft and previous Active,
      exposes bounded recovery and never automatically replays. Unknown outcomes still require
      explicit authoritative verification before another write.
- [ ] Viewer/read-only behavior, safe return routing, memory-only Bearer handling, labelled JSON/
      export, System Settings input recovery and existing command-readiness behavior remain intact.
- [ ] Production-shaped component/integration tests fail on the reviewed implementation and pass on
      the correction. A real Python-served browser proves the exact first-Draft button sequence, not
      a direct API activation substituted for the Web journey.
- [ ] Assigned T4 gates pass, and the checkpoint changes only this focused correction, its tests and
      acceptance harness. No test/assertion is weakened and no skip is hidden.

## Required Tests

- Focused Web:
  `cd web && npm test -- --run src/features/configuration/ConfigurationPage.test.tsx`.
- Focused Python/API contract:
  `.venv/bin/python -m unittest tests.test_management_setup tests.test_configuration_objects`.
- Full Python regression:
  `.venv/bin/python -m unittest discover -s tests`.
- Full Web and quality:
  `cd web && npm test -- --run && npm run typecheck && npm run lint && npm run format:check && npm run build`.
- Python quality:
  `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/python -m compileall -q mediaflow tests scripts`.
- Real Python-served browser plus empty-baseline/resident acceptance:
  `TMPDIR=/root MEDIAFLOW_SMOKE_TEMP_DIR=/root .venv/bin/python scripts/docker_empty_baseline_smoke_test.py`.
  The browser portion must perform create/resume → validate with a real version advance → checked
  activation and observe the exact empty Active; a direct HTTP activation alone is insufficient.
- Safety/packaging regression:
  `TMPDIR=/root .venv/bin/python scripts/docker_release_security_smoke_test.py`,
  `TMPDIR=/root .venv/bin/python scripts/docker_health_smoke_test.py`, and
  `TMPDIR=/root .venv/bin/python scripts/docker_restart_fault_smoke_test.py`.
- Transfer/pinning regression:
  `TMPDIR=/root .venv/bin/python scripts/docker_files_transfer_lifecycle_smoke_test.py`.
- If persistence/schema changes unexpectedly, also run
  `.venv/bin/python -m unittest tests.test_upgrade_preflight` and
  `TMPDIR=/root .venv/bin/python scripts/docker_upgrade_recovery_smoke_test.py`.
- `python3 scripts/check_governance.py`, `git diff --check`, changed Markdown local-link checks and
  exact Task Base..Head scope/private-file/credential/dependency audit. Preserve the pre-existing
  untracked `docs/pics/*.png` and ignored `config/alist.json`.

## Non-goals

- Changing Slice Base, Required Outcomes/Surfaces, Safety Invariants, Explicitly Deferred work,
  Roadmap scope or A's blocker; declaring the Slice PASS/CLOSED.
- Weakening or removing backend optimistic concurrency, checked activation, exact evidence,
  immutable Active binding, RBAC, redaction or unknown-outcome recovery.
- Automatically activating after validation, automatically retrying a conflict, or operating on the
  user's current Draft/deployment as part of tests.
- Redesigning Settings, general configuration editing, business-object forms, resident services,
  deployment mounts, policy workspaces or unrelated readiness/copy wording.
- Fixing unrelated ResourceWarnings, jsdom diagnostics, bundle-size advice, Markdown cleanup or
  root-level parser issues.

## Developer Completion Report

### Changed Files

- `web/src/features/configuration/ConfigurationPage.tsx`
- `web/src/features/configuration/ConfigurationPage.test.tsx`
- `scripts/docker_empty_baseline_smoke_test.py`
- `TASK.md`

### Implemented

- Made successful validation adopt the exact backend-returned Draft identity and version, then wait
  for the exact revision/System Settings refresh before checked activation is available. Missing or
  unreadable authoritative results enter the existing explicit verification gate instead of
  guessing a version or publishing.
- Serialized create/save/validate/activate/export writes through the existing mutation lifecycle;
  conflicting write controls remain disabled through the mutation and its authoritative refresh.
  System Settings input is preserved during post-validation refresh when its field remains valid.
- Added production-shaped component coverage for first-Draft version N validation returning N+1,
  activation with exactly N+1, and delayed validation preventing overlapping validation,
  activation, or settings save.
- Replaced the media-free smoke suite's direct API first activation with a real Python-served
  Playwright journey that clicks Create, Validate, and checked-activate, verifies the request uses
  the validation response version, observes the empty Active state, and confirms zero durable work.

### Tests and Results

- `cd web && npm test -- --run src/features/configuration/ConfigurationPage.test.tsx` — PASS
  (1 file, 13 tests).
- `.venv/bin/python -m unittest tests.test_management_setup tests.test_configuration_objects` —
  PASS (89 tests).
- `.venv/bin/python -m unittest discover -s tests` — PASS (1902 tests, 7 skips).
- `cd web && npm test -- --run && npm run typecheck && npm run lint && npm run format:check && npm run build`
  — PASS on the final formatted candidate (50 files, 752 tests).
- `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/python -m compileall -q mediaflow tests scripts`
  — PASS (323 files already formatted; Ruff and compileall passed).
- `TMPDIR=/root MEDIAFLOW_SMOKE_TEMP_DIR=/root .venv/bin/python scripts/docker_empty_baseline_smoke_test.py`
  — PASS (real Python-served Web first activation, empty and optional-media stacks, zero activation
  work, unchanged resident process identities).
- `TMPDIR=/root .venv/bin/python scripts/docker_release_security_smoke_test.py` — PASS.
- `TMPDIR=/root .venv/bin/python scripts/docker_health_smoke_test.py` — PASS.
- `TMPDIR=/root .venv/bin/python scripts/docker_restart_fault_smoke_test.py` — PASS.
- `TMPDIR=/root .venv/bin/python scripts/docker_files_transfer_lifecycle_smoke_test.py` — PASS.
- Persistence/schema gates — SKIP (this Task made no persistence or schema change, so the Task's
  conditional upgrade gates were not applicable).
- `python3 scripts/check_governance.py` and `git diff --check` — PASS.
- Real external SMB/OpenList/S3/TMDB services — UNAVAILABLE / not used; all acceptance data,
  credentials, media, metadata and receivers were isolated fixtures as required.

### Decisions

- The validation response version is the exact optimistic-concurrency token for the next explicit
  activation. The subsequent read refreshes presentation and preserves input but never infers,
  increments, or silently substitutes a different version.
- A failed post-validation authoritative refresh blocks further writes pending explicit
  verification, even though validation itself succeeded; this avoids presenting stale state or
  publishing without the required refreshed view.
- Backend concurrency, checked evidence, atomic activation, RBAC and immutable Active binding remain
  unchanged.

### Remaining In-Slice Work

- None known outside this Task; B must reevaluate the Slice Required Outcomes after review.

### Risks / Deviations

- The first full Web chain reached `format:check` with two changed TypeScript files needing Prettier;
  they were formatted and the complete Web chain was rerun successfully on the final candidate.
- Existing Python `ResourceWarning` output, jsdom `scrollTo` diagnostics and the Vite bundle-size
  advisory remain pre-existing and were not changed by this focused correction.
- No production credentials or real external services were used.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 7805fa09d540fdeb5f0b39a5e3ac39c8c5ff7bb7
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: NO
Next: PENDING
```
