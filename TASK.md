# Task 27.3 — Scoped Manual Scan and Durable Task

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

## Task 27.2 — B Review Result

```text
Reviewed: ebe31799a38d07e1dc02aa4a9a343739461e6123..75c64eb3f6d65a09211acdeaa232a1e6cbddf0ea
Decision: PASS
Slice Required Outcomes all satisfied: NO
Next: NEXT TASK
```

Task 27.2 satisfied the current-source lifecycle unit for RO-2 and its FileIndex projection needed
by RO-8. The implementation checkpoint is `75c64eb3f6d65a09211acdeaa232a1e6cbddf0ea`; the
Developer completion report was recorded at `eb675edcbd7a4b25f35f4fcc1b549950740f1ea`.

# Task 27.3 — Scoped Manual Scan and Durable Task

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 27.3
Parent Slice: 27 - Manual Operations and File Lifecycle
Status: PLANNED
Task Base: eb675edcbd7a4b25f35f4fcc1b549950740f1ea
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete Slice 27 RO-3: an authenticated operator can start a bounded manual Scan for either an
exact current FileIndex source item or a configured ResourceLibrary scope through the same Web/API
application behavior, observe a durable Task and per-item discovery state, cancel it safely, and
continue diagnosis from persisted outcomes. The Scan must preserve the existing full/incremental
discovery and reconciliation semantics, isolate one requested scope from unrelated scopes, and
perform no organization or other media mutation.

## Why This Task Exists

Slice 27.1 and 27.2 established the real Storage `Files` surface, indexed `FileIndex` lifecycle,
current source occurrence identity and processing disposition. The next missing vertical journey is
the operator action that refreshes that state: today the scanner can run through application/CLI
foundations, but the manual Web/API path does not yet admit a file- or ResourceLibrary-scoped,
durable, cancellable Scan with operator-visible Task state and recovery guidance.

This is the largest reasonable next unit because later Preview and Organize admission must consume a
known discovery boundary and durable current-occurrence state. It completes the discovery operation
without coupling analysis, metadata lookup, planning, execution authority or Worker readiness into
the same Task.

## Implementation Scope

```text
Domain/task scope -> persistence -> scan application runner -> versioned API -> Operator Web -> tests
```

- **Domain and application:** define a bounded manual Scan request for one exact current FileIndex
  source item or one configured ResourceLibrary, with explicit `FULL`/`INCREMENTAL` mode where the
  existing configuration allows it. Bind a file request to the current `fileId`, occurrence and
  fingerprint; stale or replaced sources fail closed with a durable next action. Reuse the
  Storage-port-only `StorageScanner` and existing Scanner cancellation/progress semantics.
- **Task persistence/runtime:** admit a durable Scan Task containing scope kind, scope identity,
  mode, configuration snapshot identity, status, progress, cancellation request, completion/error
  state and bounded per-scope/per-item outcomes. Reloaded Tasks must retain the original scope and
  must not silently broaden to a whole ResourceLibrary. A cancelled, failed or partial Scan must
  remain distinguishable from a completed full reconciliation.
- **Execution boundary:** run only discovery/index refresh for this Task. FileIndex updates must use
  the current-occurrence lifecycle from Task 27.2, and a file-scoped request must not reconcile
  unrelated FileIndex records as Missing. Do not invoke Metadata Providers, Preview, Planner,
  OrganizerExecutor, execution authority or mutating Storage methods.
- **API:** add explicit versioned Scan admission, Task read/detail and cancellation routes through
  the shared application service. Accept only bounded scope identifiers and declared mode; do not
  accept arbitrary paths, operations, Provider payloads or execution authority. Preserve RBAC,
  validation, audit, redaction, bounded errors and pagination. Viewer/read access must not admit or
  cancel work.
- **Operator Web:** expose Scan actions from the real `Files` and indexed `FileIndex` journeys for
  the selected exact item or ResourceLibrary scope. Show the durable Task, scope, mode, progress,
  per-item discovery result, cancellation state, failure stage, known effects, retry safety and one
  concrete next action. Keep successful or unaffected sibling scopes/items visible and independent.
- **Tests:** use temporary Local roots, fake Storage and isolated repositories. Cover file and
  ResourceLibrary scope, full/incremental behavior, stale occurrence rejection, bounded cancellation,
  reload, partial/failure reconciliation protection, concurrent scope isolation, API/Web parity,
  RBAC, redaction and zero Provider/Storage-mutation side effects.

Frozen unless a listed Acceptance Criterion cannot be met without a minimal compatible change:

- `SLICE.md`, its Base SHA, Required Outcomes, Required Surfaces, Safety Invariants and Explicitly
  Deferred entries;
- Task 27.1 real-Storage Files browser and Task 27.2 current-occurrence/disposition contracts;
- Preview findings and production-equivalent analysis/planning (RO-4);
- manual Organize admission/execution, attachment handling and mutation behavior (RO-5);
- conflict/review/recovery continuation (RO-6) and Worker registration/readiness/fencing (RO-7);
- OrganizerExecutor, Storage mutation/fallback policy, scheduled automation and configuration
  lifecycle behavior.

## Acceptance Criteria

- [ ] Authenticated operator/admin API and Web can admit a manual Scan for exactly one current
      FileIndex source item or one configured ResourceLibrary, with an explicit bounded mode and no
      arbitrary path or execution fields in the request.
- [ ] Admission validates the exact Active runtime binding and, for file scope, the current
      `fileId`/occurrence/fingerprint. Stale, missing, ambiguous, unready or replaced sources fail
      closed with bounded durable state and a concrete next action; no Task is created on rejected
      admission.
- [ ] Each accepted Scan creates a durable Task before execution, persists scope/mode/configuration
      identity, exposes status/progress/errors after reload, and preserves independent item outcomes
      without hiding or overwriting sibling state.
- [ ] ResourceLibrary-scoped Scan preserves existing configured FULL/INCREMENTAL discovery behavior;
      only a completed full-scope traversal may reconcile absence, while file-scoped and incomplete,
      failed or cancelled scans cannot fabricate `Missing` outside their observed boundary.
- [ ] Cancellation is an explicit persisted request with cooperative bounded behavior. A cancelled
      or partial Task is not reported as successful, does not claim full reconciliation, and exposes
      safe retry/recovery guidance. Repeating a safe discovery request does not duplicate or broaden
      the original scope.
- [ ] Scan execution performs zero organization, metadata/provider, planning, authority or
      mutating Storage operations. All reads and FileIndex writes remain behind existing interfaces;
      no hard-coded filesystem/network access or implicit Worker subprocess startup is introduced.
- [ ] API and Operator Web use matching application behavior, permissions, validation, status,
      audit, redaction, pagination and actionable failure semantics. Read-only access cannot admit,
      cancel or mutate a Scan Task.
- [ ] Focused and required T4 tests cover success, invalid/stale input, conflict/concurrency,
      cancellation, partial/failure, reload and sibling isolation; the checkpoint contains only
      this Task's coherent changes and no private config, credentials, endpoints or user media.

## Required Tests

Run from the repository root with the project environment. Add the Task-specific module once created:

```bash
.venv/bin/python -m unittest \
  tests.test_manual_scan \
  tests.test_scanner \
  tests.test_file_index_lifecycle \
  tests.test_task_persistence \
  tests.test_api_security \
  tests.test_operator_ui \
  tests.test_automation_api
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff format --check mediaflow tests
.venv/bin/ruff check mediaflow tests
.venv/bin/python -m compileall -q mediaflow tests
.venv/bin/pip check
git diff --check
```

Also run applicable configuration validation, migration/persistence checks, Markdown link
validation, private-config/secret scan and forbidden FFprobe/FFmpeg scan. Record unavailable
production SMB/OpenList/AWS S3/Cloudflare R2 and multi-process gates as `SKIP / UNAVAILABLE`; use no
production credentials, private endpoints or user media.

## Non-goals

- Analysis-only Preview, parse/recognition/metadata/naming/classification planning or Preview finding
  persistence (RO-4).
- Manual Organize admission/execution, one-shot authority, attachments or any Storage mutation
  (RO-5).
- Conflict/Review/Recovery continuation, automatic replay or batch recovery (RO-6).
- Worker registration/readiness/fencing, API health integration or implicit Worker supervision
  (RO-7).
- New Storage providers, arbitrary host-path browsing, recursive/unbounded scope expansion,
  configuration lifecycle changes, scheduled automation redesign, Docker release work or Slice 28
  administration.
- Changes to the closed Scanner/Parser/Recognition/Metadata/Naming/Classification/OrganizerExecutor
  semantics beyond the minimum bounded manual-Scan integration required here.
- Optional proof, broad UI redesign, test-only cleanup, P2/P3 polish or work outside Slice 27.

## Developer Completion Report

### Changed Files
- `mediaflow/domain/manual_scan.py`
- `mediaflow/application/manual_scan.py`
- `mediaflow/application/scanner.py`
- `mediaflow/application/storage_browser.py`
- `mediaflow/infrastructure/sqlite_runtime.py`
- `mediaflow/interfaces/service_api.py`
- `mediaflow/interfaces/operator_ui.py`
- `tests/test_manual_scan.py`

### Implemented
- Added bounded file- and ResourceLibrary-scoped manual Scan admission with exact current
  FileIndex occurrence/fingerprint validation, Active configuration snapshot pinning, strict
  request fields, and secret-free durable errors.
- Added durable generic Task and manual-Scan scope/per-item persistence, reloadable progress,
  cooperative cancellation, same-library concurrency isolation, and cancellation-wins
  finalization.
- Reused the Storage-port-only scanner for exact file refresh and configured full/incremental
  traversal; only a completed full ResourceLibrary traversal can reconcile absence, while
  file-scoped, partial, failed, and cancelled work cannot mark unrelated records Missing.
- Added shared authenticated API/Task detail/cancellation routes and Operator Web actions/state
  rendering. Execution stays discovery-only: no Provider, Preview, Planner, authority,
  OrganizerExecutor, or mutating Storage operation is invoked.

### Tests and Results
- `PASS` — `.venv/bin/python -m unittest tests.test_manual_scan tests.test_scanner tests.test_file_index_lifecycle tests.test_task_persistence tests.test_api_security tests.test_operator_ui tests.test_automation_api` — 118 tests.
- `PASS` — `.venv/bin/python -m unittest tests.test_manual_scan` — 9 tests.
- `PASS` — temporary LocalStorage + SQLite FileIndex/Task repository integration — exact file
  Scan completed, source bytes remained unchanged, and full reconciliation was not claimed.
- `FAIL / PRE-EXISTING / UNRELATED` — `.venv/bin/python -m unittest discover -s tests` — 1187
  tests, 9 failures, 7 skips, 0 errors. The failures reproduce the Task 27.2 baseline: two
  shared credential/configuration-environment assertions, one final-integration CLI assertion,
  three existing queue-full assertions, one shared ResourceLibrary CLI configuration assertion,
  and two shared runtime-Storage configuration assertions.
- `PASS` — `.venv/bin/ruff format --check mediaflow tests` — 245 files already formatted.
- `PASS` — `.venv/bin/ruff check mediaflow tests`.
- `PASS` — `.venv/bin/python -m compileall -q mediaflow tests`.
- `PASS` — `.venv/bin/pip check` — no broken requirements found.
- `PASS` — `git diff --check` and staged-diff check.
- `PASS` — `.venv/bin/mediaflow --config config/strategy.example.json config validate`.
- `PASS` — `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`.
- `PASS` — `.venv/bin/python -m unittest tests.test_migration_rehearsal tests.test_sqlite_backup tests.test_sqlite_restore tests.test_task_persistence` — 22 tests.
- `PASS` — Markdown local-link validator over tracked Markdown — 123 files, 38 local links,
  0 broken.
- `PASS` — `git check-ignore -v config/alist.json` plus staged/private-file scan — ignored,
  untracked, unstaged; no private credential file staged.
- `PASS` — forbidden FFprobe/FFmpeg scan over `mediaflow` and `pyproject.toml` — no matches.
- `SKIP / UNAVAILABLE` — production SMB, OpenList, AWS S3, Cloudflare R2, and multi-process
  concurrency gates; no production services or credentials were authorized, so only fake and
  temporary LocalStorage coverage was run.

### Decisions
- Kept the runtime schema marker at 32 and added idempotent manual-Scan companion tables without
  changing the existing Task/TaskItem column contract; migration/persistence checks remain green.
- Pinned the runner to the exact Active configuration snapshot and constructed only the selected
  Storage for a scan scope; a changed snapshot fails the persisted Task rather than broadening it.
- Used occurrence ID plus verified fingerprint as the file admission and execution boundary;
  scanner reads remain `stat`/`list` only and FileIndex writes remain behind the existing port.
- Kept cancellation cooperative and durable, with persisted item outcomes and explicit next
  actions instead of treating retry as recovery.

### Remaining In-Slice Work
- Slice 27 Preview, Organize, Recovery, and Worker outcomes remain outside this Task.

### Risks / Deviations
- Full regression is `FAIL / PRE-EXISTING / UNRELATED` as listed above; existing SQLite
  `ResourceWarning` messages about unclosed test connections were also emitted.
- Production remote-provider and multi-process behavior is unverified because the required
  services/credentials were unavailable and out of scope.
- Pre-existing `SLICE.md`, `docs/roadmap.md`, `nohup.out`, and `worker.log` changes were
  preserved and not included; `config/alist.json` was not accessed or staged.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 2222647b2b269a967a11e9904d32d76d48d978dd
```

## B Review Result

```text
Reviewed: [Head SHA or Task Base..Head]
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
