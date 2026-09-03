# Task 26.3 — Read-only Storage Checks and Capability Evidence

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 26.3
Parent Slice: 26 — Web-first Fresh Setup and Storage Completion
Status: READY FOR B REVIEW
Task Base: b81729f74742d38d5ec61d641c4a2ca13b5a8a40
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the read-only Storage test part of Slice 26 RO-4 and advance RO-8: for every configured
Storage kind, an authenticated configuration administrator can run an exact-revision connection/root
check, inspect declared capabilities and bounded outcome evidence, and recover from a named failure
without any Storage mutation. API and Operator Web use the same application behavior, permissions,
evidence currentness and recovery semantics.

The check covers Local, SMB, OpenList, AWS S3, Cloudflare R2 and generic S3-compatible definitions.
It may construct the configured adapter and contact only the explicitly requested fake/local test
service during the check; configuration reads and mutations remain side-effect free.

## Why This Task Exists

Task 26.2 made all six V1 Storage definitions manageable in a Draft and preserved deployment-owned
credential references, but it intentionally stopped before proving that a configured Storage root can
be reached. Slice 26 cannot provide a safe first-runtime setup or checked activation while the
operator cannot distinguish a valid definition from an unavailable path, credential, endpoint or
permission.

The existing Storage adapters already expose read operations, health checks and capability metadata,
and the existing configuration system already persists exact-revision evidence. The next largest
independent unit is therefore one shared, provider-neutral read-only check journey, including the
durable evidence and recovery surface needed by later activation and the Storage Browser.

## Implementation Scope

Implement one provider-neutral vertical path:

```text
Storage-check evidence model and bounded failure categories
→ managed revision evidence persistence and stale-state invalidation
→ shared Application read-only check behavior
→ authenticated typed API action and evidence reads
→ Operator Web action, evidence, blockers and recovery guidance
→ focused provider-neutral, safety, integration and full regression
```

Required behavior:

- Provide a typed read-only check for one selected Storage in a Draft/Validated setup revision, with
  expected version and digest admission. The evidence must identify the revision, Storage, check
  time, status, bounded failure category/message, completed read operations, declared capabilities,
  `sideEffects=none`, retry safety and the explicit next action.
- Exercise the configured root using only the Storage abstraction and provider read/health behavior:
  Local root validation/listing, SMB/OpenList/S3/R2 root reachability and authentication/permission
  handling. Do not implement mutation probes, recursive scans, writes, rename/move/copy/link/delete,
  or a second provider-specific check path in the application layer.
- Persist success and failure evidence against the exact immutable revision identity. A changed Draft,
  stale version/digest, disabled or missing definition, changed secret-reference readiness, or
  concurrent edit must not produce current evidence or permit a later checked activation; the Draft
  and prior Active remain intact.
- Normalize adapter errors into stable, bounded categories such as invalid path, not found,
  permission denied, authentication failed, connection failed, timeout, rate limited and unknown.
  Responses and logs must not expose credentials, authorization data, raw provider payloads or
  unbounded exception text.
- Expose the same action and evidence through authenticated API and Operator Web. Configuration
  administrators can run the check; read-only principals can inspect bounded evidence but cannot
  start it or mutate configuration. The Web must show the affected Storage, current/stale state,
  completed operations, capability summary, side-effect statement, failure recovery and safe retry
  action after reload.
- Prove read-only enforcement at the application boundary. A check must not create a Job, Task,
  Automation occurrence or Provider request, and must not call any Storage mutator. Tests must prove
  adapter constructors and fake services see only the intended read calls, and that missing
  environment references fail closed before an external operation.
- Keep production-service acceptance honest: unavailable real SMB, OpenList, AWS S3 or Cloudflare R2
  checks remain explicitly `SKIP / UNAVAILABLE`; fakes/local services prove software behavior only.

Frozen:

- `SLICE.md` User Goal, Required Outcomes, Required Surfaces, Safety Invariants and Base.
- Task 26.2 Storage normalization, lifecycle, adapter implementations and capability definitions,
  except for the minimum compatibility hook required to invoke an existing adapter read operation.
- Storage Browser, breadcrumbs, pagination/cursors, directory selection, path picker and Local
  execution-environment mount guidance.
- ResourceLibrary/MediaLibrary binding, complete policy-graph setup, exact activation orchestration,
  scan/Preview/organize execution and all media mutation behavior.
- `config/alist.json`, real credentials, production endpoints and user media.

## Acceptance Criteria

- [ ] Each of the six supported Storage kinds has one shared authenticated read-only check journey
      through Application, API and Operator Web, with no provider-specific UI or business-code fork.
- [ ] A successful check records the exact revision/version/digest and Storage identity, bounded
      completed read operations, declared capabilities, `sideEffects=none`, retry-safe status and a
      useful recovery/next-action projection; the evidence remains visible after reload.
- [ ] Failed checks preserve the Draft and prior Active, record a stable safe failure category and
      affected Storage, and state what was attempted, what is durable, whether retry is safe and the
      explicit correction or recovery action.
- [ ] Stale expected version/digest, changed Draft, missing or unset required secret reference,
      disabled/missing Storage and concurrent edit cannot yield current evidence or bypass later
      checked-activation requirements.
- [ ] The check performs no Storage mutation, recursive scan, Job/Task/Automation creation or
      Provider request. Mutation guards and fake clients prove writes, directory creation, move,
      copy, delete, hard-link and soft-link are never reached.
- [ ] Capability summaries are taken from the configured Storage abstraction, respect read-only
      intent, distinguish unsupported operations from failed connectivity, and never imply that a
      capability was proven by a mutation probe.
- [ ] API and Web enforce the existing RBAC and return bounded, deterministic, secret-free evidence
      and errors with matching state, validation, audit and recovery semantics.
- [ ] The checkpoint contains only this Task and all assigned T4 validation passes, with any
      unavailable production service explicitly reported as `SKIP / UNAVAILABLE`.

## Required Tests

Add focused automated coverage in a new `tests/test_storage_setup_check.py` or the repository's
equivalent test module for:

- Local, SMB, OpenList, AWS S3, Cloudflare R2 and generic S3-compatible success paths using temporary
  Local storage, fake adapters and fake/local services;
- permission, authentication, timeout, connection, not-found, invalid-root and malformed-response
  failures with stable categories, bounded messages, retry safety and recovery guidance;
- exact revision/version/digest evidence, evidence persistence/reload, stale invalidation after Draft
  edits, concurrent version conflicts and preservation of prior Active;
- missing/unset environment-reference handling and full credential/error/log/payload redaction;
- capability projection, read-only intent and mutation-guard counters proving no mutator or mutation
  probe is called;
- API/Web parity, RBAC, audit, bounded response behavior and no Job/Task/Automation/Provider side
  effects.

Run and report:

```bash
.venv/bin/python -m unittest tests.test_storage_setup_check \
  tests.test_guided_storage_lifecycle tests.test_configuration_objects \
  tests.test_configuration_snapshot tests.test_configuration_status \
  tests.test_configuration_destination_precheck tests.test_configuration_destination_activation \
  tests.test_api_security tests.test_operator_ui tests.test_management_setup
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests scripts
.venv/bin/python -m pip check
.venv/bin/mediaflow --config config/strategy.example.json config validate
.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate
test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"
git diff --check
```

For the changed configuration/API/Web package surface, also run an isolated wheel build and smoke
test using a temporary output directory:

```bash
release_dir=$(mktemp -d /tmp/mediaflow-task-26-3.XXXXXX)
.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w "$release_dir"
.venv/bin/python scripts/wheel_smoke_test.py "$release_dir"/mediaflow-*.whl
```

Use temporary Local directories, temporary SQLite databases, fake adapters/local test services and
fake environment references only. Production Storage, TMDB, SMB, OpenList, S3/R2 credentials and
user media are forbidden.

## Non-goals

- Storage Browser listings, breadcrumbs, pagination/cursors, path selection, path picker or arbitrary
  host filesystem access.
- ResourceLibrary/MediaLibrary guided binding and complete first-runtime policy graph setup.
- Checked activation orchestration, first complete Draft completion, scans, Preview, organize
  execution, Task/Automation work or any media mutation.
- Docker/Compose, production WSGI serving, built-in identity, a general Secret Store or Provider
  switching.
- Mutation-based capability probes, recursive Storage scans, production-service acceptance without an
  isolated approved environment, unrelated adapter rewrites or P2 cleanup.
- Changing Slice boundaries, Required Outcomes, Required Surfaces, Safety Invariants or the Slice
  Base.

## Previous Task Review

Task 26.2 — Guided Storage Lifecycle and Secret Reference Management:

```text
Reviewed: 2895aaef0d500606bc984644023ccdc7eb388ac7..e19ce329c087a036f2a9cd458fc493c50063e85d
Decision: PASS
Slice Required Outcomes all satisfied: NO
Next: NEXT TASK
```

Task 26.2 evidence: focused managed-configuration/API/Web regression passed (177 tests); full
regression reported 6 state-dependent failures and 7 skips, with all 6 affected tests passing in a
clean `Task Base` worktree; format/lint, compileall, pip check, canonical config validation,
FFprobe/FFmpeg scan, diff check and isolated wheel smoke passed. Slice RO-1 and RO-3 are advanced,
while RO-4, RO-5, RO-6 and the remaining first-runtime completion are still incomplete.

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

This is the newly planned Task 26.3; the Developer checkpoint is recorded below.

## Developer Completion Report

### Changed Files

- `mediaflow/domain/configuration_management.py`
- `mediaflow/application/configuration_objects.py`
- `mediaflow/infrastructure/runtime_configuration.py`
- `mediaflow/infrastructure/sqlite_configuration_management.py`
- `mediaflow/interfaces/service_api.py`
- `mediaflow/interfaces/operator_ui.py`
- `tests/test_storage_setup_check.py`

### Implemented

- Added bounded, secret-free per-Storage read-only evidence with exact revision/version/digest,
  declared capabilities, attempted and completed root read operations, readiness snapshots,
  side-effect and retry-safety projections, failure categories and recovery actions.
- Added durable per-revision/per-Storage SQLite evidence and currentness projection for Draft edits,
  disabled/missing definitions and changed environment-reference readiness.
- Added one shared Application check path for Local, SMB, OpenList, S3, R2 and S3-compatible
  definitions. It uses the Storage abstraction's root `stat` and `list`, rejects all mutators behind
  a read-only guard, resolves secrets only at the infrastructure adapter boundary, and never loads
  the complete runtime graph or contacts a Provider.
- Added authenticated API action/evidence collection/detail routes and Operator Web action, evidence,
  capability, failure, stale-state and recovery rendering through the same Application service.
- Added focused Local/fake-provider, failure, redaction, persistence, stale/concurrency, Active
  preservation, RBAC, audit and no-runtime-work regression coverage.

### Tests and Results

- PASS — `.venv/bin/python -m unittest tests.test_storage_setup_check tests.test_guided_storage_lifecycle tests.test_configuration_objects tests.test_configuration_snapshot tests.test_configuration_status tests.test_configuration_destination_precheck tests.test_configuration_destination_activation tests.test_api_security tests.test_operator_ui tests.test_management_setup` — 213 tests.
- FAIL / PRE-EXISTING / UNRELATED — `.venv/bin/python -m unittest discover -s tests` — 1144 tests, 6 failures, 7 skipped. The six failures are the previously recorded state-dependent API credential, final-analyze, ResourceLibrary scan, and runtime Storage list/check cases; the prior Task checkpoint records the same failures in the Task Base clean-worktree state. No Task 26.3 test failed.
- PASS — `.venv/bin/ruff format --check .` — 359 files already formatted.
- PASS — `.venv/bin/ruff check .`.
- PASS — `.venv/bin/python -m compileall -q mediaflow tests scripts`.
- PASS — `.venv/bin/python -m pip check` — no broken requirements.
- PASS — `.venv/bin/mediaflow --config config/strategy.example.json config validate`.
- PASS — `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`.
- PASS — `test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)` — no matches.
- PASS — `git diff --check`.
- PASS — isolated `.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w "$release_dir"` followed by `.venv/bin/python scripts/wheel_smoke_test.py "$release_dir"/mediaflow-*.whl`; wheel smoke backup, migration, restore, verify and upgrade-preflight checks completed.
- SKIP / UNAVAILABLE — production SMB, OpenList, AWS S3 and Cloudflare R2 checks; no approved production credentials or endpoints are available, so temporary Local storage and fake adapters were used.

### Decisions

- Kept provider selection and credential resolution in the existing infrastructure boundary, with a
  narrow single-Storage loader/constructor hook so an incomplete setup Draft does not require the
  complete policy graph.
- Used one provider-neutral Application check that performs only root `stat` and `list`; capability
  values are adapter declarations constrained by configured read-only intent, and no mutation probe
  or silent operation fallback is used.
- Stored only environment-reference names and SET/UNSET readiness, never credential values, raw
  provider errors, paths or payloads in evidence or API/Web output.

### Remaining In-Slice Work

- Storage Browser and path selection, ResourceLibrary/MediaLibrary binding, remaining first-runtime
  policy setup, and the applicable later validation/activation journey remain in Slice 26.

### Risks / Deviations

- The full-suite six failures are recorded as `FAIL / PRE-EXISTING / UNRELATED`; no ignored state,
  private configuration or legacy fixture was reset or changed. Seven existing skips remain reported.
- Real external Storage acceptance remains `SKIP / UNAVAILABLE` as required by the Task. All
  implemented evidence and mutation guarantees were tested with temporary Local directories and
  fake adapters/services only.
- `config/alist.json` remains ignored, untracked and unstaged.

### Checkpoint

Status: READY FOR B REVIEW
Head SHA: eba865bb75e5c08b9053dd2770b450fb6bfe6882
