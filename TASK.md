# Task 26.1 — Management-only Bootstrap and First Draft Entry

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 26.1
Parent Slice: 26 — Web-first Fresh Setup and Storage Completion
Status: READY FOR B REVIEW
Task Base: de352057d6c06b288a3e6e839157923e749fa345
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the first independently usable part of Slice 26 RO-1, RO-2 and RO-8: from a fresh local
database and a minimal management bootstrap containing only the immutable database locator and
environment-owned API-principal references, an authenticated operator can open Web, see an explicit
Setup Required / runtime-not-configured state, and atomically create or resume the first versioned,
secret-free managed starter Draft without supplying a complete runtime JSON document.

The Task ends with a durable Draft and a clear next step into guided setup. It does not configure or
test a Storage yet.

## Why This Task Exists

`ManagementBootstrapConfiguration` and locator-only recovery already exist, but `api serve` currently
uses the complete runtime loader when no managed Active revision has ever existed. A genuinely
minimal bootstrap therefore fails before the management API/Web can start. The current Web can create
a Draft only by pasting/importing a complete document or by copying the currently authoritative JSON,
which is not usable when the bootstrap intentionally contains no workflow graph.

This is the largest reasonable first unit because the bootstrap mode, fresh persistence, readiness
projection, work-admission gate, starter-Draft application behavior, API and Web entry must agree to
form one user-visible outcome. Splitting the loader, endpoint and UI into separate Tasks would leave
each checkpoint unusable. Remote Storage forms, connection tests and Storage Browser depend on this
entry but are separate later implementation units.

## Implementation Scope

Implement one coherent vertical path:

```text
Bootstrap/runtime boundary
→ fresh configuration persistence
→ managed first-Draft application service
→ authenticated API readiness and Draft action
→ Operator Web setup-required entry/resume
→ focused, integration, concurrency and full safety regression
```

Required behavior:

- Admit `api serve` from a minimal bootstrap that contains only:
  - the local SQLite `persistence.databasePath`; and
  - the existing environment-reference API principal configuration.
- Keep `/health` as bounded process liveness while exposing an authenticated management/configuration
  projection that unambiguously reports:
  - management is ready;
  - no business runtime is configured;
  - setup is required;
  - no Active revision exists; and
  - workflow work is unavailable until explicit activation.
- Add one server-owned, explicitly versioned setup starter document and one shared Application action
  for creating the first managed Draft. The API and Web must use that same action.
- The starter must:
  - preserve the bootstrap database locator and API-principal environment references;
  - contain the canonical managed-document structure needed for later guided Storage, library and
    policy editing;
  - use safe, non-destructive and disabled defaults where a default is necessary;
  - contain no literal secret, real endpoint, user-private path, enabled schedule/Webhook, execution
    grant or media-operation authority;
  - make every unfinished operator choice explicit as a Draft/setup blocker rather than fabricating a
    working runtime; and
  - remain inactive until the existing explicit validation/test/activation lifecycle succeeds.
- Persist the first Draft with normal version, digest and bounded configuration audit evidence.
- Make repeated or concurrent first-Draft creation deterministic: it must not create multiple
  ambiguous starter Drafts. The operator either resumes the existing setup Draft or receives a
  bounded conflict containing its current revision identity and next action.
- Show the setup state in Operator Web without making whole-document JSON paste the primary fresh
  entry. An authorized operator can create the starter Draft and then open/resume it; a read-only
  principal can inspect the state but cannot create or edit a Draft.
- Fail all Job/Task/Automation/manual-execution or other workflow-producing actions closed while in
  management-only setup state, before creating durable work or constructing Storage/Provider
  objects. Return a stable, actionable runtime-not-configured error.
- Preserve these existing modes:
  - a complete compatibility JSON bootstrap remains usable before first managed activation;
  - a valid managed Active remains the exact runtime authority;
  - a missing/corrupt Active after prior managed activation remains fail-closed recovery, never
    first-time setup and never JSON fallback;
  - existing Draft import/edit/validate/activate and `source=current` compatibility behavior remain
    available;
  - bootstrap database locator immutability and API-principal RBAC remain unchanged.
- Reads, setup-state refresh and starter-Draft creation must create no Job, Task, occurrence, grant,
  Storage adapter, Provider request or media mutation.

Affected layers may include Domain/Application readiness values, configuration persistence/admission,
runtime/bootstrap loading, CLI API assembly, API transport, Operator Web and tests. A schema migration
is allowed only if atomic first-Draft admission cannot be implemented safely with the current schema;
if used, it must be additive, backward-compatible and covered by fresh/current/newer-schema tests.

Frozen:

- `SLICE.md` User Goal, Required Outcomes, Required Surfaces, Safety Invariants and Base.
- Storage adapter behavior and provider-specific configuration forms.
- Scanner, Parser, Recognition, Metadata, Naming, Classification, Organizer, Task execution,
  manual/unattended execution authority and mutation boundaries.

## Acceptance Criteria

- [ ] A minimal bootstrap with a fresh writable local database and configured environment-owned admin
      principal starts `mediaflow api serve` without Storage, library, policy, Provider, schedule or
      notification workflow content.
- [ ] `/health`, authenticated management readiness and configuration status clearly distinguish
      process alive, management ready, setup required and runtime not configured. The response is
      bounded and secret-free and does not claim an Active identity.
- [ ] The embedded Web loads in this state and presents a primary `Create first Draft` action plus a
      clear explanation that activation and media work have not occurred.
- [ ] The API and Web call the same first-Draft Application behavior; manage-configuration permission
      is required, while read-only principals can inspect but cannot create.
- [ ] The created starter Draft is explicitly versioned, has a valid managed revision version/digest,
      preserves only the permitted bootstrap locator/principal references, contains no literal
      secrets/private paths/real endpoints and grants no execution authority.
- [ ] The starter supplies the canonical editable structure needed by later Slice 26 Tasks and
      exposes incomplete setup as actionable validation/setup blockers rather than appearing
      runtime-ready.
- [ ] Creating the starter Draft starts no validation, Storage test, Provider request, scan, Job,
      Task, Automation occurrence, grant, Preview, activation or media mutation.
- [ ] Repeated and concurrent create attempts cannot produce multiple ambiguous first setup Drafts;
      the durable winner is discoverable and the losing/repeated caller receives the existing Draft
      identity and an explicit resume/reload action.
- [ ] When a setup Draft already exists and there is no Active revision, reload/restart preserves it
      and Web offers resume rather than silently creating or replacing another Draft.
- [ ] Every workflow-producing API action tested in management-only state fails before persistence
      with a stable runtime-not-configured response, `sideEffects=none`, safe retry/recovery guidance
      and no Storage/Provider construction.
- [ ] Invalid/missing principal environment references, unwritable/invalid database location,
      unsupported newer schema and starter persistence failure fail clearly without partial Draft or
      workflow state.
- [ ] A prior managed activation whose Active is missing, corrupt or runtime-invalid is still
      reported as recovery/unavailable, not Setup Required; no bootstrap JSON fallback occurs.
- [ ] Complete compatibility JSON bootstrap, valid managed Active, Draft lifecycle, activation
      atomicity, exact runtime binding and existing RBAC behavior remain green.
- [ ] No secret value appears in managed documents, audits, API/Web output, logs, fixtures, diff or
      test output.
- [ ] The checkpoint changes only this coherent Task and all assigned T4 validation passes.

## Required Tests

Add focused automated coverage for at least:

- minimal-bootstrap parsing and rejection of workflow/secret ambiguity;
- fresh API startup and authenticated setup/readiness projections;
- Web setup-required/create/resume behavior and RBAC;
- starter document version, canonical sections, safe defaults, redaction and immutable bootstrap
  fields;
- repeated/concurrent first-Draft admission and transaction rollback;
- restart/reload with an existing setup Draft;
- fail-closed Job/Task/Automation/manual work admission with zero repository work rows and
  Storage/Provider constructors patched to fail if reached;
- full JSON-bootstrap compatibility, valid Active behavior and broken/missing Active recovery;
- fresh/current/newer configuration and runtime database schema behavior when persistence changes.

Run and report:

```bash
python3 -m unittest tests.test_configuration_snapshot tests.test_configuration_status \
  tests.test_configuration_objects tests.test_api_security tests.test_operator_ui \
  tests.test_operator_job_submission
python3 -m unittest discover -s tests
ruff format --check .
ruff check .
python3 -m compileall -q mediaflow tests scripts
python3 -m pip check
mediaflow --config config/strategy.example.json config validate
mediaflow --config config/mediaflow.phase13.2.example.json config validate
test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"
git diff --check
```

Because this Task changes the installed API bootstrap/entry behavior, also run:

```bash
release_dir=$(mktemp -d /tmp/mediaflow-task-26-1.XXXXXX)
python3 -m pip wheel . --no-deps --no-build-isolation -w "$release_dir"
python3 scripts/wheel_smoke_test.py "$release_dir"/mediaflow-*.whl
```

Use only temporary local SQLite databases, fake services and fake environment references. Production
Storage, TMDB, SMB, OpenList, S3/R2 credentials and user media are forbidden.

## Non-goals

- Guided SMB/OpenList/S3/R2 forms, credential readiness and Storage connection/root tests.
- Storage Browser, path picker, ResourceLibrary/MediaLibrary path selection or Local mount guidance.
- Completing the entire policy editor, Strategy Test, destination precheck or checked-activation
  journey beyond preserving their existing behavior and providing the starter structure they later
  consume.
- Day-2 Active-to-Draft IA or full forms-first redesign deferred to Slice 28.
- Files/FileIndex redesign, manual operations lifecycle, Worker readiness or any Slice 27 work.
- Docker/Compose, production WSGI serving or any Slice 29 work.
- Metadata Provider switching, built-in users/sessions/OIDC, a general Secret Store, literal secret
  persistence or arbitrary host-path access.
- Any Storage mutation probe, media scan, Preview, organize execution, execution-authority expansion
  or refactor of closed processing foundations.

## Developer Completion Report

### Changed Files

- `mediaflow/application/configuration_snapshot.py`
- `mediaflow/domain/configuration_management.py`
- `mediaflow/final_cli.py`
- `mediaflow/infrastructure/configuration_snapshot.py`
- `mediaflow/infrastructure/runtime_configuration.py`
- `mediaflow/infrastructure/sqlite_configuration_management.py`
- `mediaflow/interfaces/operator_ui.py`
- `mediaflow/interfaces/service_api.py`
- `tests/test_management_setup.py`
- `TASK.md` (Developer status and completion report)

### Implemented

- Added strict minimal management-bootstrap admission and API CLI assembly. A fresh local SQLite
  database plus environment-owned principal references can start management API/Web without
  constructing Storage, FileIndex or Metadata Provider objects.
- Added bounded liveness, authenticated management readiness, configuration status and management
  system projections that distinguish process health, management readiness, setup required, runtime
  configuration and workflow availability.
- Added one shared Application action that builds a server-owned, versioned, secret-free starter
  Draft with canonical empty configuration sections, safe disabled defaults, explicit setup blockers,
  normal digest/version metadata and bounded audit evidence.
- Added SQLite `BEGIN IMMEDIATE` first-Draft admission with duplicate/authority checks, atomic
  revision-plus-audit persistence, deterministic concurrent conflict identity and resume guidance.
- Added authenticated API/Web create/resume behavior with configuration RBAC and authentication-time
  readiness routing, and fail-closed runtime-not-configured responses before workflow admission.
- Preserved complete JSON compatibility, managed Active authority, broken-Active recovery, existing
  Draft lifecycle and bootstrap principal/database-locator behavior.
- Added focused fresh-start, CLI assembly, Web, RBAC, safety, concurrency, rollback and restart
  regression coverage.

### Tests and Results

- PASS — `.venv/bin/python -m unittest tests.test_management_setup tests.test_configuration_snapshot tests.test_configuration_status tests.test_configuration_objects tests.test_api_security tests.test_operator_ui tests.test_operator_job_submission` — 174 tests.
- FAIL / PRE-EXISTING / UNRELATED — `python3 -m unittest discover -s tests` — 1131 tests, 6 failures, 1 error, 7 skipped. The system interpreter has no `httpx` for the optional OpenList path; the six failures are the existing ignored default-database/legacy-CLI state-dependent failures.
- FAIL / PRE-EXISTING / UNRELATED — `.venv/bin/python -m unittest discover -s tests` — 1133 tests, 6 failures, 7 skipped. Five state-dependent cases observe the pre-existing ignored `.mediaflow` managed Active/data instead of isolated fixture state (API credential status, ResourceLibrary scan and Storage list/check); one is the untouched legacy final-analyze CLI case.
- PASS — `.venv/bin/ruff format --check .` (`357 files already formatted`).
- PASS — `.venv/bin/ruff check .`.
- PASS — `.venv/bin/python -m compileall -q mediaflow tests scripts`.
- PASS — `.venv/bin/python -m pip check` (`No broken requirements found`).
- UNAVAILABLE — `ruff format --check .` / `ruff check .`; the system `ruff` executable is not installed. The venv equivalents passed.
- UNAVAILABLE — `python3 -m pip check`; the system interpreter has no `pip`. The venv equivalent passed.
- PASS — `.venv/bin/mediaflow --config config/strategy.example.json config validate`.
- PASS — `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`.
- PASS — `rg` FFprobe/FFmpeg constraint scan returned no references in `mediaflow` or `pyproject.toml`.
- PASS — `git diff --check`.
- PASS — `.venv/bin/python -m pip wheel . --no-deps --no-build-isolation` and `scripts/wheel_smoke_test.py` using a temporary wheel directory; backup, migration rehearsal, restore and verify checks completed successfully.

### Decisions

- Kept the existing permissive locator-only loader for prior managed recovery and added a separate
  strict fresh-bootstrap admission boundary, preventing stale workflow JSON from becoming authority.
- Used the existing configuration schema and an SQLite `BEGIN IMMEDIATE` transaction; no migration is
  needed for atomic first-Draft admission. The `first_draft_create` audit marker makes the setup root
  durable and discoverable.
- Copied only the immutable database locator and API principal environment references into the
  server-owned starter. All workflow/media authority is empty or explicitly disabled until guided
  editing, validation and activation.
- Kept API and Web on the same Application action and added the management-only gate before runtime
  binding refresh, work-row creation or Storage/Provider construction.

### Remaining In-Slice Work

- Guided Storage and library setup, read-only Storage checks/browser behavior, completion of the
  policy journey, exact-revision evidence and checked activation remain for later Slice 26 work.

### Risks / Deviations

- The full-regression failures are recorded as `FAIL / PRE-EXISTING / UNRELATED`; the ignored
  `.mediaflow` database existed before this Task with managed Active/workflow data and was not reset,
  staged or included in the implementation checkpoint. Full regression also used the system
  interpreter once, where optional `httpx` is unavailable.
- Bare system `ruff` and `pip check` were unavailable; equivalent venv tooling and CLI commands
  passed. Task-specific tests used only temporary local SQLite databases and fakes; no production
  Storage, Provider or credentials were used and no media mutation was authorized.
- `config/alist.json` remains ignored, untracked and unstaged. No schema migration was added.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: b935e205559f997ecca1e64d69d3bd95191a78f5
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: NO
Next: PENDING
```
