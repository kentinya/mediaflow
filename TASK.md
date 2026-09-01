# Task 24.6 — End-to-End Secret-Free Pipeline Evidence

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md). It is the focused implementation correction required by A's
Slice Final Review. `SLICE.md` remains in its workflow-defined `FIX REQUIRED` state while this
Task is implemented and reviewed.

```text
Task ID: 24.6
Parent Slice: 24 — Files / Media Detail and Manual Organize
Status: READY FOR B REVIEW
Task Base: dcad185778facd022b18ab3d62286cc185fb7df1
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Close A's remaining RO-1/RO-7 and secret-free safety blocker by making shared Pipeline Evidence
secret-free across its complete lifecycle:

```text
Pipeline result / error
→ bounded evidence construction
→ restart-safe SQLite persistence
→ File/Media detail application projection
→ authenticated API and Operator Web response
```

No credential value may remain recoverable from newly persisted evidence or from a File/Media
detail response, including when the original value is nested in operation errors, warnings,
reasons or other evidence collections.

## Why This Task Exists

A's review of
`4ff5479d9f4a81906ee52a9f784931b65cd9ab90..7a0e2e0b44cbe137205161f98d6497fbcd4c50a1`
proved that the shared Pipeline Evidence path still has a complete credential leak:

- the local evidence regex turns
  `Authorization: Bearer closure-review-secret` into
  `Authorization: [redacted] closure-review-secret`, leaving the credential tail visible;
- nested `ExecutionResult.errors` are copied into
  `sections.operation.value.errors` without redaction;
- the resulting document is persisted by TaskItem completion and returned by File/Media detail,
  so the same fake credential is recoverable from SQLite, API and Web-visible data.

Task 24.5 corrected the manual Preview/execution helpers but did not apply that complete shared rule
to Pipeline Evidence. This is one coherent security boundary spanning Domain, Application,
Persistence and operator-facing read surfaces; it is not a standalone regex, field or test change.

A also identified stale facts in the existing Slice Closure Packet. B will reconcile the actual
Head, completed Task list, test results and safety evidence after this Task passes. That factual
packet repair is intentionally not Developer implementation work and does not justify a separate
Task.

## Implementation Scope

Implement one focused vertical correction across:

```text
Shared domain redaction contract
→ Pipeline Evidence construction and serialization
→ SQLite write/read boundaries
→ FileCatalog detail / API / Operator Web projection
→ T4 security and regression evidence
```

- Replace the superseded Pipeline Evidence credential regex with the complete shared redaction
  behavior already introduced for Slice 24. Reuse or appropriately relocate that behavior so
  Pipeline Evidence and manual-organize records do not maintain competing credential patterns.
- Apply the shared rule recursively to every potentially secret-bearing string in a Pipeline
  Evidence document before persistence and before response. This includes, at minimum:
  top-level `error` and `warnings`; every section's `value`, `items`, `warnings` and
  `unavailableReason`; operation errors/warnings; recognition/metadata reasons; and any
  secret-shaped source/path or explanatory text.
- Consume complete credential forms rather than only the first token. Cover fake
  `Authorization: Bearer ...` and `Authorization: Basic ...` values and the existing bounded
  API-key/password/secret/token/cookie assignment forms. Keep the redacted marker useful while
  ensuring no credential tail survives.
- Defend both persistence and presentation boundaries:
  - newly appended or atomically completed Pipeline Evidence must be serialized without the fake
    credential, even if an in-memory evidence object was not produced by the normal builder;
  - reloaded evidence and File/Media detail responses must be redacted before projection, including
    an intentionally seeded historical document containing unsafe nested text;
  - read-only detail/API requests must not rewrite the database or create audit, Task, Job,
    Provider, Storage or execution side effects.
- Preserve the immutable evidence schema, bounded collection limits, deterministic ordering,
  truncation flags and useful non-secret facts. Do not replace whole evidence sections with an
  opaque error when shape-preserving recursive redaction is sufficient.
- Preserve exact source/configuration/plan fingerprints and all OrganizerExecutor admission,
  conflict, capability, one-shot authority, checkpoint and per-item semantics. Redaction must not
  change execution identity or authorize/replay any operation.
- Add direct regressions that reproduce A's top-level plus nested
  `Authorization: Bearer closure-review-secret` example and falsify leakage at document,
  persistence, reload, authenticated File/Media API and Web-visible projection boundaries.
- Use only fake credentials, temporary SQLite databases, temporary Local roots and fake/in-memory
  Providers or Storage. Do not access real user media, credentials or external services.

## Acceptance Criteria

- [ ] `build_pipeline_evidence` with the same fake Authorization credential in its top-level
      error and nested `ExecutionResult.errors` produces a bounded document containing a
      redaction marker but no `closure-review-secret` substring.
- [ ] Complete Bearer and Basic Authorization values and the supported API-key, password, secret,
      token and cookie assignment forms are removed from top-level and recursively nested
      Pipeline Evidence strings. No duplicate or weaker Pipeline Evidence-specific credential
      pattern remains.
- [ ] Direct repository append and atomic TaskItem completion serialize newly supplied evidence
      through the same protection: after close/reopen, the fake credential is absent from the
      persisted SQLite bytes and from the reconstructed `PipelineEvidence`.
- [ ] A deliberately seeded historical Pipeline Evidence document containing the fake credential
      is returned redacted by repository/application/transport projections. A read does not mutate
      that historical row; the test distinguishes response safety from the new-write byte check.
- [ ] An authenticated operator's File/Media detail API response and the data rendered by the
      Operator Web contain the expected bounded evidence and redaction marker but no fake
      credential. Existing READ RBAC, collection bounds, ordering and reload stability remain
      intact.
- [ ] Redaction preserves non-secret evidence shape and facts, including section availability,
      outcome, item/operation structure, deterministic ordering, truncation indicators and safe
      recovery context.
- [ ] Opening or refreshing File/Media detail remains side-effect free: no Task, Job, audit,
      Provider request, Storage probe/mutation, authorization consumption, replanning or
      OrganizerExecutor call occurs.
- [ ] Existing manual-organize redaction, exact-plan identity, RecognitionType C preservation,
      per-item independence, one-shot execution and OrganizerExecutor-only mutation regressions
      remain green.
- [ ] No test is deleted, weakened or hidden behind a new skip; no real credential/private path,
      `config/alist.json`, unrelated file or A-owned `SLICE.md` change is included in the
      Developer checkpoint.
- [ ] All required T4 tests and quality/safety gates pass with actual results reported.

## Required Tests

Use only fake credentials, temporary SQLite databases, temporary Local roots and fake/in-memory
Providers/Storage. Do not use production credentials, remote services or user media.

1. Focused Pipeline Evidence construction, persistence, reload and File/Media projection:

   ```bash
   .venv/bin/python -m unittest tests.test_file_media_detail
   ```

   Add direct regressions for A's exact top-level plus nested Authorization reproduction; recursive
   errors/warnings/reasons; complete Bearer/Basic and assignment-form redaction; direct append and
   atomic completion; SQLite-byte absence for new writes; safe read projection of an intentionally
   seeded historical unsafe document; authenticated File/Media API/Web-visible absence; and
   read-only zero-side-effects.

2. Directly affected evidence, persistence, FileCatalog, API/Web, security and manual execution
   regression:

   ```bash
   .venv/bin/python -m unittest \
     tests.test_file_media_detail \
     tests.test_file_catalog \
     tests.test_file_catalog_api \
     tests.test_operator_ui \
     tests.test_task_persistence \
     tests.test_api_security \
     tests.test_manual_organize_execution \
     tests.test_final_integration
   ```

3. Complete offline regression:

   ```bash
   .venv/bin/python -m unittest discover -s tests
   ```

4. Quality, safety, configuration and private-file gates:

   ```bash
   .venv/bin/ruff format --check .
   .venv/bin/ruff check .
   .venv/bin/python -m compileall -q mediaflow tests scripts
   .venv/bin/python -m pip check
   .venv/bin/mediaflow --config config/strategy.example.json config validate
   .venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate
   test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"
   git diff --check
   git check-ignore -q config/alist.json
   test -z "$(git ls-files --error-unmatch config/alist.json 2>/dev/null || true)"
   ```

5. Build and isolated installed-wheel smoke because this Task hardens persisted evidence
   serialization/read behavior:

   ```bash
   mediaflow_release_dir=$(mktemp -d /tmp/mediaflow-task-24.6-release.XXXXXX)
   .venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w "$mediaflow_release_dir"
   .venv/bin/python scripts/wheel_smoke_test.py "$mediaflow_release_dir"/mediaflow-*.whl
   ```

Before checkpointing, inspect `git status --short`, the complete Task Base..Head diff and exact
manifest. Confirm no deleted/weakened tests, hidden skips, unrelated files, real credentials/private
paths, tracked/staged `config/alist.json`, or A-owned `SLICE.md` change is included in the
Developer checkpoint. Report every gate as `PASS`, `FAIL`, `SKIP` or `UNAVAILABLE`.

## Non-goals

- Changing the Slice User Goal, Required Outcomes, Required Surfaces, Safety Invariants, Explicitly
  Deferred scope or Base.
- Editing `SLICE.md`, repairing its Closure Packet, changing Roadmap/progress/current-state
  documentation, or conducting another Slice Final Review. B owns packet reconciliation after
  Task PASS; A owns the next final review.
- Reopening accepted Tasks 24.1–24.5 or changing their behavior beyond the direct shared redaction
  root cause and its necessary regressions.
- Broad redesign of logging, secret storage, Provider credentials, manual-organize contracts,
  Pipeline Evidence schema, Task/Result/checkpoint ownership or File/Media UX.
- A data-rewriting migration for historical rows. Historical unsafe test data must be safe on
  response without turning a read-only detail request into a write.
- Redacting ordinary non-secret media metadata merely because it is private, removing actionable
  bounded failure/recovery context, or changing plan/fingerprint identity.
- Real remote SMB/OpenList/S3/R2/TMDB acceptance, production data, credentials or destructive
  operations.
- Optional copy polish, cleanup, refactor or extra proof unrelated to A's blocker.

## Developer Completion Report

### Changed Files

- `mediaflow/domain/manual_safety.py`
- `mediaflow/domain/media_evidence.py`
- `mediaflow/application/evidence_capture.py`
- `mediaflow/application/file_catalog.py`
- `mediaflow/infrastructure/sqlite_runtime.py`
- `tests/test_file_media_detail.py`

### Implemented

- Reused one shared domain redaction rule for manual-organize and Pipeline Evidence text, removing
  the weaker Pipeline Evidence-specific pattern and consuming complete Bearer/Basic credentials and
  supported assignment forms.
- Applied shape-preserving recursive redaction to evidence construction and documents, including
  top-level fields, section values/items/warnings/unavailable reasons, nested operation errors and
  secret-shaped source or explanatory text.
- Defended direct append and atomic TaskItem completion writes by serializing a redacted evidence
  copy, and redacted both SQLite reload and FileCatalog application projections without rewriting
  historical rows.
- Added fake-credential regressions across builder output, both persistence paths, SQLite bytes,
  restart reload, deliberately unsafe historical evidence, FileCatalog, authenticated API and the
  existing Operator Web evidence renderer data path.

### Tests and Results

- `.venv/bin/python -m unittest tests.test_file_media_detail` — PASS (17 tests, 0 failures).
- `.venv/bin/python -m unittest tests.test_file_media_detail tests.test_file_catalog tests.test_file_catalog_api tests.test_operator_ui tests.test_task_persistence tests.test_api_security tests.test_manual_organize_execution tests.test_final_integration` — PASS (101 tests, 0 failures).
- `.venv/bin/python -m unittest discover -s tests` — PASS (1004 tests, 0 failures, 7 skipped).
- `.venv/bin/ruff format --check .` — PASS (338 files already formatted).
- `.venv/bin/ruff check .` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m pip check` — PASS (no broken requirements).
- Both required `mediaflow config validate` commands — PASS.
- FFprobe/FFmpeg dependency scan — PASS (no matches).
- `git diff --check` — PASS.
- `git check-ignore -q config/alist.json` and tracked-file check — PASS; the private config remains
  ignored and untracked.
- Wheel build plus `scripts/wheel_smoke_test.py` — PASS (wheel built and installed in isolation;
  schema 27 backup, migration rehearsal, restore, verify and upgrade preflight passed).

### Decisions

- Kept the accepted `manual_safety` import surface as compatibility aliases while exposing generic
  evidence helpers backed by the same regexes, so accepted manual-organize behavior and Pipeline
  Evidence cannot drift into competing credential patterns.
- Applied redaction at builder/document, persistence serialization, repository reconstruction and
  FileCatalog projection boundaries. Historical unsafe rows remain unchanged on read, while their
  reconstructed and operator-facing documents are safe.
- Preserved the evidence schema, section ordering, collection/truncation shape and ordinary
  fingerprints/identities; no migration, execution admission or OrganizerExecutor behavior changed.

### Remaining In-Slice Work

The factual Slice Closure Packet reconciliation remains for B after this Task passes.

### Risks / Deviations

- The full suite emitted existing Python 3.13 `ResourceWarning` messages for unclosed SQLite
  connections but exited successfully.
- The full suite reported 7 existing skipped tests; no test was deleted, weakened or newly skipped.
- Real SMB/OpenList/S3/R2 and production credential acceptance was not run because it is outside
  this Task and no real service or credential was used; all required T4 offline gates passed.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 72d44f12c8d46f36eb42eab29f54a23e50d343c3
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

If `FIX REQUIRED`, B will list only this Task's remaining blockers below and the Developer will
continue in the same Task/Task Base/Goal/Scope correction loop. This result does not close the
Slice or update Roadmap.
