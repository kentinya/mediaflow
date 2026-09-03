# Task 26.5 — Provider-neutral Checked Activation for the First Runtime

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 26.5
Parent Slice: 26 — Web-first Fresh Setup and Storage Completion
Status: PLANNED
Task Base: 07a46c5d84b0bb858c159060bb68c9b9d448673d
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete Slice 26 RO-7 and close the Slice's first-runtime journey: from the first Draft, the
operator can finish the Recognition/TMDB Metadata/Naming/Classification/Organize setup, run the
applicable exact-revision tests/previews for every configured Storage kind, inspect dependency
impact and failures, and checked-activate only the exact revision whose required evidence is
current. Every failure preserves the Draft and any prior Active. Activation starts no scan, Job,
Task, Automation occurrence or media mutation, and an existing DryRun Preview resolves the exact
newly Active snapshot.

## Operator Journey

- **User goal:** finish first setup and make the tested, immutable runtime Active without
  hand-editing SQLite or a whole runtime JSON document.
- **Entry:** an authenticated configuration manager opens a Validated Draft and uses the existing
  checked-activation flow through API or Operator Web.
- **Visible state:** per-Storage read-only check status, destination precheck verdict,
  Recognition Strategy Test state, evidence currentness per exact revision, dependency impact,
  blockers with failure categories, and the current Active revision (if any).
- **Action:** run or rerun the read-only per-Storage checks, the strategy test and the destination
  precheck, inspect evidence and blockers, then explicitly checked-activate the exact revision.
- **Success:** the exact revision becomes the sole Active authority. No scan, Job, Task,
  Automation occurrence, Provider request or media mutation is started by activation, and the
  existing DryRun Preview consumes the exact new Active snapshot.
- **Failure:** missing, stale, failed or inapplicable evidence, changed Draft, missing secret
  reference, broken dependency or concurrent edit blocks activation with a bounded conflict
  naming the affected Storage/evidence, durable state, retry safety and an explicit recovery
  action. The Draft and the prior Active revision remain unchanged.
- **Recovery:** reload the revision, correct configuration or credential references, rerun the
  named evidence on the current version/digest, then activate checked again.

## Why This Task Exists

Tasks 26.1–26.4 delivered the minimal management bootstrap, first managed Draft, provider-neutral
Storage lifecycle and read-only checks, the bounded Storage Browser and library path selection.
Checked activation, however, is still gated by a Local-only setup check
(`require_current_local_check`) and a Local-only destination precheck
(`require_current_destination_precheck`). A fresh instance whose ResourceLibrary or MediaLibrary
uses SMB, OpenList, AWS S3, Cloudflare R2 or generic S3-compatible Storage cannot produce evidence
that matches its own configuration; remote destination evidence is silently skipped rather than
tested. The provider-neutral read-only per-Storage check from Task 26.3 already exists but does
not feed activation. This is the largest remaining coherent unit before the Slice's first Active
runtime is usable by the existing scan/Preview/Automation pipeline.

## Implementation Scope

One first-runtime activation vertical:

```text
provider-neutral activation evidence model (per-Storage read-only checks)
→ provider-neutral read-only destination precheck for every Storage kind
→ exact-revision evidence gates and fail-closed activation admission
→ API + Operator Web evidence display, blockers, recovery and activation parity
→ focused, safety, RBAC, integration and full regression
```

Required behavior:

- Checked activation requires current, exact-revision, passed read-only per-Storage checks for
  every enabled Storage referenced by a ResourceLibrary or MediaLibrary. The old Local-only setup
  check may remain as the Local kind's implementation or as a compatibility alias, but it is no
  longer the single authority for remote or mixed configurations. The applicability rule is
  documented and no configuration may activate through an evidence gap.
- Destination precheck becomes provider-neutral: every MediaLibrary destination Storage receives
  a read-only, zero-mutation precheck through the Storage abstraction using only guarded
  exists/stat/list and declared capabilities. No write, create-directory, move, copy, delete,
  link or mutation probe is performed, and no operation silently falls back. Existing Local
  verdicts, failure categories, per-sample isolation and capability_gap blocking keep their
  current semantics; remote kinds map onto the same bounded evidence contract.
- Strategy-test and destination evidence stay exact-revision gated. A missing, stale, failed or
  wrong-revision evidence, changed Draft, missing secret reference, broken dependency or
  concurrent edit cannot checked-activate and preserves the Draft plus any prior Active
  (Slice acceptance 6).
- Activation safety is unchanged and never weakened: atomic pointer change only after validation
  and current required evidence, optimistic version admission, prior Active available when
  replacement fails. Activation performs no scan, Job, Task, Automation occurrence, Provider
  request or media mutation; a separately requested existing DryRun Preview uses the exact new
  Active snapshot (Slice acceptance 7).
- API and Operator Web use the same Application services, RBAC, validation, evidence, redaction
  and audit rules for running evidence and for activation. Only configuration managers may run
  evidence-bearing checks or activate. Web shows per-Storage evidence state, blockers, stale
  markers and recovery guidance after reload.
- Persistence reuses the existing evidence tables and the immutable bootstrap database locator;
  a schema change is made only if the evidence model strictly requires it and then runs the
  migration regression.
- Documentation (architecture, product-experience) records the provider-neutral activation
  evidence model, first-runtime completion semantics and the unchanged zero-work activation rule.

Frozen:

- `SLICE.md` User Goal, Required Outcomes, Required Surfaces, Safety Invariants and Base.
- Storage check/browser contracts from Tasks 26.3/26.4 and the Storage-relative path rules.
- The existing Recognition/TMDB/Naming/Classification/Organize policy setup semantics; this Task
  completes their journey, it does not redesign them.
- Scanner, Parser, Recognition, Metadata core, Naming, Classification, OrganizePlan,
  OrganizerExecutor, Task/TaskItem/Result and execution authority boundaries.
- `config/alist.json`, real credentials, production endpoints and user media.

## Acceptance Criteria

- [ ] A Draft whose libraries reference Local, SMB, OpenList, AWS S3, Cloudflare R2 or generic
      S3-compatible Storage can checked-activate only after current, passed, exact-revision
      read-only per-Storage checks exist for every enabled referenced Storage; missing, stale,
      failed or wrong-revision evidence blocks activation with a bounded conflict naming the
      affected Storage, durable state, retry safety and next action.
- [ ] Destination precheck runs provider-neutrally for every MediaLibrary destination Storage
      kind with zero mutation and no write/capability probe, preserves the existing Local
      verdict/failure/redaction model, and blocks activation on capability_gap or failed
      evidence the same way for every kind.
- [ ] A failed test, stale evidence, changed Draft, missing secret reference, broken dependency
      or concurrent edit cannot checked-activate and preserves the Draft plus any prior Active.
- [ ] Activation starts no scan, Job, Task, Automation occurrence, Provider request or media
      mutation; a separately requested existing DryRun Preview uses the exact new Active
      snapshot.
- [ ] API and Web show the same per-Storage evidence, blockers, redaction and recovery, and
      enforce management RBAC for evidence runs and activation.
- [ ] No secret value appears in managed documents, SQLite evidence, API/Web payloads, logs,
      fixtures, Git diff or test output. RecognitionType C regression, OrganizerExecutor-only
      mutation and all closed-Slice safety gates stay green. Real external-service checks
      unavailable to the validation environment remain `SKIP / UNAVAILABLE`; fakes and local
      services prove software behavior only.
- [ ] The assigned T4 gate passes with actual evidence, and the checkpoint contains only this
      Task.

## Required Tests

Add focused coverage for:

- checked activation across Local, SMB, OpenList, AWS S3, Cloudflare R2 and generic S3-compatible
  documents using temporary Local roots, fake adapters and fake/local services;
- per-Storage evidence applicability, exact revision/version/digest gating, missing/stale/failed
  evidence refusal, prior Active preservation and bounded conflict/recovery;
- provider-neutral destination precheck per Storage kind with zero mutation, no write probe, no
  silent fallback, capability_gap blocking and the same verdict/failure/redaction model as Local;
- activation zero-work (no Job/Task/Automation/Provider construction) and DryRun Preview
  resolving the exact newly Active snapshot;
- API/Web parity, management RBAC, optimistic concurrency, audit behavior and redaction;
- the full first-Draft journey for each Storage kind: configure policies, validate, run checks
  and previews, inspect blockers, checked-activate.

Run and report:

```bash
.venv/bin/python -m unittest tests.test_configuration_destination_activation \
  tests.test_configuration_destination_precheck tests.test_storage_setup_check \
  tests.test_configuration_objects tests.test_configuration_snapshot \
  tests.test_configuration_status tests.test_guided_storage_lifecycle \
  tests.test_management_setup tests.test_api_security tests.test_operator_ui \
  tests.test_storage_browser tests.test_strategy_test
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

Isolated wheel build and smoke test, as in Task 26.4:

```bash
release_dir=$(mktemp -d /tmp/mediaflow-task-26-5.XXXXXX)
.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w "$release_dir"
.venv/bin/python scripts/wheel_smoke_test.py "$release_dir"/mediaflow-*.whl
```

Environment note: the main worktree contains an ignored `.mediaflow/mediaflow.sqlite3` holding an
Active HDD_2 runtime snapshot that overrides `--config` in six CLI tests
(`test_api_credentials`, `test_final_integration`, `test_resource_library_pipeline`,
`test_runtime_storage_configuration`). The same six failures reproduce at the Task Base in a clean
worktree after copying `.mediaflow` there, which proves they are environment-dependent and
unrelated. Either run the full suite from a clean worktree or report the six failures with that
Base reproduction evidence; do not hide or skip them.

Use temporary Local directories, temporary SQLite databases, fake adapters/local services and fake
environment references only. Production SMB, OpenList, S3/R2 credentials and user media are
forbidden.

## Non-goals

- The current Files/File Catalog rename or redesign, processing disposition, Reprocess,
  repository-level Scan/Preview/Organize, processing-Worker readiness or any Slice 27 work.
- Day-2 configuration IA, System Settings, export/notification administration or Slice 28 work.
- Dockerfile/Compose, production WSGI, `/data` packaging or Slice 29 work.
- Widening Overwrite/Delete/cleanup/rollback/operation-fallback or any execution authority.
- Redesigning the policy graph editors or the Recognition/Strategy Test semantics; only wiring
  their existing exact-revision evidence into the first-runtime journey.
- Changing Slice boundaries, Required Outcomes, Required Surfaces, Safety Invariants or the Slice
  Base; unrelated adapter rewrites and P2 cleanup.

## Previous Task Review

Task 26.4 — Storage Browser and Bounded Path Selection:

```text
Reviewed: b662c9073c17d724045488db378d78174ed71abe..07a46c5d84b0bb858c159060bb68c9b9d448673d
Decision: PASS
Slice Required Outcomes all satisfied: NO
Next: NEXT TASK
```

Evidence: the fix checkpoint added strict canonical Base64 cursor validation plus a regression
test rejecting appended/inserted/padding/alphabet-invalid cursors before any adapter read.
Focused regression passed 225 tests. Full suite ran 1156 tests with 6 failures and 7 skips; the
identical six failures were reproduced at the Task Base in a clean worktree with the main
worktree's ignored `.mediaflow` runtime database copied in (1144 tests, same six failures, same
seven skips), proving they are environment-dependent and unrelated to Task 26.4. Ruff
format/lint, compileall, pip check, both canonical configuration validations, forbidden
FFprobe/FFmpeg scan, `git diff --check` and isolated wheel build/smoke passed. The diff contains
only the intended files; no credentials, deleted tests, relaxed assertions or hidden skips.
RO-7 and the first-runtime activation journey remain incomplete.

## Developer Completion Report

### Changed Files

- `mediaflow/application/configuration_objects.py`
- `mediaflow/interfaces/operator_ui.py`
- `tests/test_configuration_destination_activation.py`
- `tests/test_configuration_destination_precheck.py`
- `tests/test_configuration_objects.py`
- `tests/test_configuration_snapshot.py`
- `tests/test_operator_ui.py`
- `docs/architecture.md`
- `docs/product-experience.md`

### Implemented

- Checked activation is provider-neutral: `activate_checked` now requires current, passed,
  exact-revision read-only per-Storage checks for every enabled Storage referenced by a
  ResourceLibrary or MediaLibrary (`require_current_storage_checks`). A referenced-but-missing
  Storage fails closed; a disabled referenced Storage is not required. The Local-only
  `require_current_local_check` gate and method were removed; `local_check` itself remains
  available through API/CLI/Web as a Local diagnostic and is no longer an activation authority.
- `require_current_destination_precheck` now applies whenever the Draft has MediaLibraries, for
  every Storage kind; stale, failed and capability_gap evidence still block checked activation
  with the prior Active preserved.
- `destination_precheck` now supports SMB, OpenList, AWS S3, Cloudflare R2 and generic
  S3-compatible destinations: the Local-only `unsupported_storage_type` rejection was removed and
  replaced with pre-flight `disabled` and `missing_secret` failures that fire before any adapter
  construction. The existing one-destination-Storage-per-run rule, verdicts, per-sample isolation,
  redaction and capability_gap blocking are unchanged; runner wording is provider-neutral.
- Operator Web activation readiness now requires the per-Storage checks (new
  `firstStorageCheckBlocker`/`referencedStorageChecksSatisfied` helpers reusing the Task 26.3
  evidence projection); destination precheck gating, blockers and recovery text are
  provider-neutral. API and Web keep using the same Application rules and RBAC.
- Activation safety is unchanged: atomic pointer change only after validation and current
  evidence, optimistic version admission, prior Active preserved, and zero scan/Job/Task/
  Automation/Provider/media work during activation.
- Docs: architecture.md and product-experience.md record the provider-neutral activation
  evidence model and first-runtime completion semantics.

### Tests and Results

- DEVIATION — the Task's Required Tests command lists `tests.test_strategy_test`, which does not
  exist in the repository. The two real strategy modules were run instead:
  `tests.test_strategy_configuration` and `tests.test_strategy_cli`.
- PASS — focused regression (12 modules incl. the two real strategy modules): 258 tests, OK.
- PASS — full offline suite in a clean detached worktree of checkpoint `6ed11d3`:
  1160 tests, OK, 7 skipped (no `.mediaflow` environment artifact present).
- FAIL / PRE-EXISTING / ENVIRONMENT-DEPENDENT — full suite in the main worktree: 1160 tests,
  6 failures, 7 skipped. The six failures are exactly the CLI tests named in this Task
  (`test_api_credentials` ×2, `test_final_integration`, `test_resource_library_pipeline`,
  `test_runtime_storage_configuration` ×2), caused by the ignored `.mediaflow/mediaflow.sqlite3`
  Active HDD_2 runtime snapshot overriding `--config`; the identical set reproduces at the Task
  Base when that artifact is copied into a clean worktree, so it is unrelated to this Task's diff.
- PASS — `.venv/bin/ruff format --check .` (361 files formatted).
- PASS — `.venv/bin/ruff check .`.
- PASS — `.venv/bin/python -m compileall -q mediaflow tests scripts`.
- PASS — `.venv/bin/python -m pip check`.
- PASS — `.venv/bin/mediaflow --config config/strategy.example.json config validate`.
- PASS — `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`.
- PASS — forbidden FFprobe/FFmpeg scan: no matches in `mediaflow`/`pyproject.toml`.
- PASS — `git diff --check`.
- PASS — isolated wheel build (`pip wheel` into a temp directory) and
  `scripts/wheel_smoke_test.py` on the checkpoint tree: backup, migration, restore, verify and
  upgrade preflight completed.
- SKIP / UNAVAILABLE — production SMB, OpenList, AWS S3, Cloudflare R2 and generic S3-compatible
  services: no approved isolated environment, so fake adapters/local services and temporary
  Local roots were used. No production credentials or user media were touched.

### Decisions

- Replaced the Local-only activation gate with per-Storage evidence rather than stacking both,
  so a Draft's activation gates always match its own configuration; `local_check` survives as a
  Local diagnostic to keep the existing guided-Local UX.
- Implemented remote destination evidence by removing the Local-only applicability restriction
  instead of adding a parallel path: the precheck already operates through the guarded Storage
  abstraction, so remote kinds reuse the same verdicts, failure categories and zero-mutation
  guard, with new pre-flight `disabled`/`missing_secret` failures before adapter construction.
- Kept the one-destination-Storage-per-precheck rule and the strategy-test gate unchanged; this
  Task wires evidence applicability, it does not redesign existing policy semantics.
### Remaining In-Slice Work

- None known inside Task 26.5's scope; re-evaluation of all Slice Required Outcomes belongs to B.

### Risks / Deviations

- The `tests.test_strategy_test` module named by the Task does not exist; the two real strategy
  modules were run instead (see above).
- The six main-worktree full-suite failures are environment-dependent (ignored `.mediaflow`
  runtime database), reproduced at the Task Base with the same artifact; they are not caused by
  this checkpoint, and the same suite is fully green in a clean worktree of this checkpoint.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 6ed11d3320363448568498264018044916951516
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
