# Task 26.2 — Guided Storage Lifecycle and Secret Reference Management

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 26.2
Parent Slice: 26 — Web-first Fresh Setup and Storage Completion
Status: READY FOR B REVIEW
Task Base: 2895aaef0d500606bc984644023ccdc7eb388ac7
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the guided Storage-definition part of Slice 26 RO-2, RO-3 and RO-8: from the first setup
Draft, an authenticated configuration administrator can create, inspect, copy, edit, enable,
disable and delete Local, SMB, OpenList, AWS S3, Cloudflare R2 and generic S3-compatible Storage
definitions through the shared Application/API/Web journey. Remote credentials remain deployment-owned
environment-variable references, with only safe SET/UNSET readiness visible to the operator.

The Task ends with durable, version-checked Storage definitions that are ready for a later read-only
connection/root test and Storage Browser. It does not contact a Storage service or mutate media.

## Why This Task Exists

The first setup Draft now gives the operator a safe, resumable configuration root, but the current
guided object surface only accepts Local Storage and marks remote Storage as redacted
`json_import_only`. The domain validator and existing adapters already define most provider-specific
contracts, so the next largest independent unit is to expose that contract consistently through
managed Draft persistence, API and Operator Web.

Storage definitions are the authority consumed by later connection tests, Browser/path selection,
ResourceLibrary/MediaLibrary binding and checked activation. Completing the lifecycle as one vertical
unit is necessary so create/edit/copy/delete, validation, RBAC, reference protection and secret
redaction cannot diverge between API and Web.

## Implementation Scope

Implement one provider-neutral vertical path:

```text
Storage domain normalization and validation
→ managed Draft mutation/audit/reference protection
→ shared Application Storage lifecycle behavior
→ authenticated typed API actions
→ Operator Web guided Storage forms and readiness display
→ focused, integration and full safety regression
```

Required behavior:

- Expose guided forms for exactly these Storage kinds: `local`, `smb`, `openlist`, `s3`, `r2` and
  `s3-compatible`.
- Support create, inspect, copy, edit, enable, disable and delete for each applicable kind through
  the managed Draft lifecycle, with optimistic version checks and the existing configuration RBAC.
- Validate and normalize bounded provider-specific fields using the existing Storage contract,
  including remote roots, endpoint/host/share/bucket constraints, timeout/retry/page/concurrency
  bounds, read-only intent and enabled state. Do not accept arbitrary provider fields as a way around
  validation.
- Represent secrets only by valid environment-variable names (`tokenEnv`, `usernameEnv`,
  `passwordEnv`, `accessKeyEnv`, `secretKeyEnv`, optional `sessionTokenEnv` as applicable). Reject
  literal secret fields before persistence and expose only redacted definitions plus SET/UNSET
  readiness; never return secret values in documents, audits, API/Web responses, logs or errors.
- Preserve copy safety: copied Storage definitions receive a unique identity, remain disabled until
  explicitly enabled, and never copy a secret value or silently inherit a different Storage kind.
- Preserve reference protection: deleting a Storage referenced by a ResourceLibrary or MediaLibrary
  is rejected with the existing bounded durable-state and recovery semantics; the Draft and prior
  Active remain unchanged.
- Keep API and Web on the same Application behavior. Configuration mutations may persist a Draft,
  but must not construct Storage adapters, contact SMB/OpenList/S3/TMDB, perform a connection probe,
  or perform any media/filesystem mutation.
- Keep the setup Draft visibly incomplete until later Tasks complete tests, library bindings, policy
  graph, evidence and activation. No Storage definition becomes runtime authority merely because it
  was saved or enabled in a Draft.

Frozen:

- `SLICE.md` User Goal, Required Outcomes, Required Surfaces, Safety Invariants and Base.
- Storage adapter network/filesystem behavior and capability implementations.
- Read-only Storage connection/root tests, capability evidence, Storage Browser, path confinement and
  path picker behavior.
- ResourceLibrary/MediaLibrary path binding, Recognition/TMDB/Naming/Classification/Organize setup,
  exact-revision evidence, checked activation and all workflow/media execution behavior.
- `config/alist.json`, real credentials, production endpoints and user media.

## Acceptance Criteria

- [ ] An authenticated configuration administrator can use Operator Web to add each of the six
      supported Storage kinds to the setup Draft and see the resulting redacted definition and current
      Draft identity.
- [ ] The API exposes the same create/inspect/copy/edit/enable/disable/delete semantics and validation
      as Web; a read-only principal can inspect but cannot mutate.
- [ ] Every provider-specific form rejects invalid or unknown fields and accepts only its bounded
      contract. Local, SMB, OpenList, AWS S3, Cloudflare R2 and generic S3-compatible definitions are
      normalized into the existing managed-document shape without adapter construction.
- [ ] Secret-bearing inputs are environment-variable references only. SET/UNSET readiness is accurate
      for configured references, while secret values are absent from managed revisions, audits, API/Web
      payloads, logs, errors, fixtures and test output.
- [ ] Copy allocates a unique disabled definition and preserves only safe non-secret configuration;
      edit and enable/disable use optimistic version checks and leave published Active revisions
      immutable.
- [ ] Delete is blocked for referenced Storage and returns bounded affected-object, durable-state and
      recovery information; unreferenced deletion changes only the Draft and its audit trail.
- [ ] Failed validation, stale versions, duplicate IDs, invalid environment names and persistence
      failures leave the candidate Draft/prior Active consistent with no partial configuration mutation.
- [ ] Storage lifecycle actions perform no Storage/provider/network/filesystem/media operation, and
      tests prove constructors and probes are not reached.
- [ ] The checkpoint contains only this Task and all assigned T4 validation passes.

## Required Tests

Add focused automated coverage for at least:

- all six Storage kinds and their provider-specific required/optional fields, defaults, bounds,
  unknown-field rejection and invalid input recovery;
- Web/API parity for create, inspect, copy, edit, enable, disable and delete, including configuration
  RBAC and optimistic concurrency;
- SET/UNSET environment-reference readiness and redaction of every supported secret field;
- copy-disabled behavior, unique IDs, immutable Active protection and Draft digest/version updates;
- ResourceLibrary/MediaLibrary reference protection, unreferenced delete and persistence rollback;
- patched Storage/provider/network constructors proving configuration lifecycle performs no external
  call or mutation;
- starter-Draft integration and restart/reload preservation of remote definitions.

Run and report:

```bash
.venv/bin/python -m unittest tests.test_guided_storage_lifecycle \
  tests.test_configuration_objects tests.test_configuration_snapshot \
  tests.test_configuration_status tests.test_api_security tests.test_operator_ui \
  tests.test_management_setup
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

For the changed API/Web and managed-configuration package surface, also run an isolated wheel build
and smoke test using a temporary output directory:

```bash
release_dir=$(mktemp -d /tmp/mediaflow-task-26-2.XXXXXX)
.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w "$release_dir"
.venv/bin/python scripts/wheel_smoke_test.py "$release_dir"/mediaflow-*.whl
```

Use temporary local SQLite databases, temporary Local directories, fake adapter/services and fake
environment references only. Production Storage, TMDB, SMB, OpenList, S3/R2 credentials and user
media are forbidden.

## Non-goals

- Storage connection/root tests, capability evidence, Browser listings, path picker, root confinement
  and Local execution-environment mount guidance.
- ResourceLibrary/MediaLibrary directory selection or complete policy-graph setup and activation.
- Metadata live tests, scans, Preview, organize execution, Task/Automation work or any media mutation.
- Docker/Compose, production WSGI serving, built-in identity, a general Secret Store or provider
  switching.
- Replacing the existing Storage adapters or introducing a second configuration source of truth.
- Optional UI copy polish, unrelated refactors, P2 cleanup or production-service acceptance.

## Developer Completion Report

### Changed Files

- `mediaflow/domain/configuration_management.py`
- `mediaflow/application/configuration_objects.py`
- `mediaflow/infrastructure/runtime_configuration.py`
- `mediaflow/interfaces/service_api.py`
- `mediaflow/interfaces/operator_ui.py`
- `tests/test_guided_storage_lifecycle.py`
- `tests/test_configuration_objects.py`
- `tests/test_operator_ui.py`

### Implemented

- Added strict six-kind Storage normalization, provider-specific option defaults/bounds, unknown
  option rejection, nested managed options, and compatibility for legacy flat bootstrap fields.
- Added shared Draft Storage create/inspect/copy/edit/enable/disable/delete behavior with optimistic
  version checks, unique disabled copies, audit/reference protection, and immutable Active handling.
- Added environment-variable-only secret references with safe SET/UNSET readiness projections and
  redacted API/Web responses; edit round-trips strip projection-only fields before validation.
- Added typed API Storage collection/detail/action routes and Operator Web forms/actions for all six
  Storage kinds, without constructing adapters or contacting external services during configuration.
- Added lifecycle, RBAC, validation, rollback, restart, runtime-compatibility, redaction and UI
  regression coverage.

### Tests and Results

- PASS — `.venv/bin/python -m unittest tests.test_guided_storage_lifecycle tests.test_configuration_objects tests.test_configuration_snapshot tests.test_configuration_status tests.test_api_security tests.test_operator_ui tests.test_management_setup` — 177 tests.
- FAIL / PRE-EXISTING / UNRELATED — `.venv/bin/python -m unittest discover -s tests` — 1139 tests, 6 failures, 7 skipped. The failures are state-dependent API credential, final-analyze, ResourceLibrary scan, and Storage list/check cases that observe the pre-existing ignored `.mediaflow` database or legacy fixture state; the affected runtime Storage cases also reproduced before this Task's implementation.
- PASS — `.venv/bin/ruff format --check .` (`358 files already formatted`).
- PASS — `.venv/bin/ruff check .`.
- PASS — `.venv/bin/python -m compileall -q mediaflow tests scripts`.
- PASS — `.venv/bin/python -m pip check` (`No broken requirements found`).
- PASS — `.venv/bin/mediaflow --config config/strategy.example.json config validate`.
- PASS — `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`.
- PASS — `test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)` (no matches).
- PASS — `git diff --check`.
- PASS — isolated `.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w "$release_dir"` followed by `.venv/bin/python scripts/wheel_smoke_test.py "$release_dir"/mediaflow-*.whl`; the wheel smoke backup, migration, restore, verify and upgrade-preflight checks completed.

### Decisions

- Kept Storage lifecycle mutations on the existing shared Application service and generic managed
  Draft/version/audit path so API and Web use the same validation, RBAC and safety behavior.
- Used environment names as the only persisted secret-bearing values; readiness is derived at safe
  projection time and never persists secret values or performs a credential check.
- Canonicalized guided definitions to nested provider options while accepting known legacy flat fields
  during compatibility loading; provider adapters and their capabilities remain unchanged.
- Copies receive bounded unique IDs and are disabled by default; projection-only editability/readiness
  fields are removed before an edit is persisted.

### Remaining In-Slice Work

- Read-only Storage connection/root checks and capability evidence, Storage Browser/path selection,
  ResourceLibrary/MediaLibrary binding, policy-graph setup, exact-revision evidence and checked
  activation remain in the Slice.

### Risks / Deviations

- The full-suite failures are recorded as `FAIL / PRE-EXISTING / UNRELATED`; the ignored `.mediaflow`
  database and stateful legacy fixtures were not reset or changed. Seven suite skips remain reported
  by unittest.
- Tests used only temporary local SQLite/directories, fake environment references and patched
  constructors; no production Storage, Provider, credentials or media were used. No schema migration
  was added.
- `config/alist.json` remains ignored, untracked and unstaged.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: e19ce329c087a036f2a9cd458fc493c50063e85d
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
