# Task 24.7 — Secret-Free File/Media Result History

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md). It is the focused implementation correction required by A's
2026-09-01 Slice Final Review. B reviewed and passed it on 2026-09-01 and returned `SLICE.md` to
`READY FOR A REVIEW`; no implementation Task is active.

```text
Task ID: 24.7
Parent Slice: 24 — Files / Media Detail and Manual Organize
Status: PASS
Task Base: 83ec59b07f38da4f58e9b5a97a9242fc2885433d
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Close the remaining RO-1/RO-7 and secret-free safety blocker by making complete File/Media Result
history and its adjacent latest-Result view safe across the Result lifecycle:

```text
Result publication
→ restart-safe SQLite persistence
→ File/Media detail projection
→ authenticated API
→ Operator Web-visible result/history/error view
```

Historical unsafe rows must be shape-preservingly redacted on read without being rewritten, and
newly published Slice 24 Result errors and effect text must not persist credential values.

## Why This Task Exists

A's review of
`4ff5479d9f4a81906ee52a9f784931b65cd9ab90..7f35e0634a68a1dc62d4d02f54f1aee6cb7e435b`
proved a real P1 inside the unchanged Slice Contract: a `PersistentResultRecord.error` containing
`Authorization: Bearer slice24-final-review-secret` remained recoverable from SQLite, and an
authenticated `GET /api/v1/files/one` returned the complete value in both `latestResult.error` and
`results[0].error`.

The current code builds these two Result projections separately in `MediaFlowApi` and copies Result
fields, including `error`, `completed_operations` and `uncertain_effects`, verbatim. The generic
SQLite Result insertion paths likewise persist those explanatory fields without applying the shared
recursive redaction rule. This is one coherent security correction across Persistence,
Application/API projection and the existing Web journey; it does not change the Slice boundary,
Result schema or organizer behavior.

## Implementation Scope

Implement one focused vertical correction across:

```text
Shared result-safety boundary
→ SQLite Result publication/reload
→ File/Media latest/history projection
→ authenticated API and Operator Web-visible data
→ T4 security and regression evidence
```

- Reuse the existing shared shape-preserving redaction behavior from
  `mediaflow.domain.manual_safety`; do not add a competing Result-specific credential regex.
- Give the complete File/Media Result document one safe projection boundary and use it consistently
  for both `results[]` history and adjacent `latestResult`. Apply recursive redaction to every
  projected string, including error, title/path-like display values and nested/list operation or
  effect text, while preserving ordinary non-secret facts and the current bounded response shape.
- Protect every generic SQLite Result write route exercised by Slice 24—direct append, atomic
  TaskItem/evidence completion and manual-execution atomic publication—so newly persisted
  human/explanatory Result fields cannot retain fake credential values. At minimum this includes
  `error`, `completed_operations` and `uncertain_effects`; the implementation must not rely on the
  normal producer having already sanitized them.
- Keep exact source/destination identity, FileIndex linkage, plan/fingerprint identity,
  recognition/policy ownership and OrganizerExecutor execution semantics intact. Redaction must not
  authorize, replan, replay or otherwise alter work.
- Return a deliberately seeded historical unsafe Result row safely through FileCatalog, the
  authenticated API and the data consumed by Operator Web, without rewriting that row or producing
  Task, Job, audit, Provider, Storage, authorization or execution side effects.
- Add direct fake-credential regressions for top-level Result errors plus credential-shaped
  `completed_operations` and `uncertain_effects`, covering new-write SQLite bytes/reload and the
  historical latest/history API/Web-visible projection that reproduced A's blocker.
- Use only fake credentials, temporary SQLite databases, temporary Local roots and fake/in-memory
  Providers or Storage. Do not access production services, user media or real credentials.

## Acceptance Criteria

- [ ] An authenticated `GET /api/v1/files/<id>` for a deliberately seeded historical Result whose
      error is `Authorization: Bearer slice24-final-review-secret` returns HTTP 200, preserves a
      useful redaction marker and contains no `slice24-final-review-secret` substring anywhere in
      either `latestResult` or `results[]`.
- [ ] The same complete projection recursively removes complete Bearer/Basic Authorization values
      and the supported API-key/password/secret/token/cookie assignment forms from every
      potentially secret-bearing Result string, including nested/list completed-operation and
      uncertain-effect text; ordinary Result facts and collection shape remain useful and stable.
- [ ] `latestResult` and the matching history entry cannot drift into different safety behavior:
      both pass through the shared Result projection/redaction boundary while retaining their
      existing public field contracts.
- [ ] Direct `append_result`, atomic `complete_item_with_evidence` and manual-execution atomic Result
      publication protect newly written Result error/effect text. After close/reopen, fake
      credential values are absent from SQLite bytes and reconstructed newly written Results, with
      no weakening of atomic rollback or per-item publication semantics.
- [ ] A historical unsafe Result row is safe at FileCatalog/API/Web-visible read projection but is
      not rewritten merely by opening or refreshing detail; the regression distinguishes this
      read-time compatibility behavior from the new-write byte-absence proof.
- [ ] File/Media detail and refresh remain side-effect free: no Task, Job, audit, Provider request,
      Storage probe/mutation, authorization consumption, replanning or OrganizerExecutor call is
      introduced.
- [ ] Result status, source/destination linkage, RecognitionType C, policy IDs, operation,
      attachment count, effect certainty, timestamps, bounded ordering/truncation and safe recovery
      context remain unchanged except for secret replacement.
- [ ] Existing Pipeline Evidence/manual-organize redaction, exact-plan/one-shot authority,
      per-item independence, OrganizerExecutor-only mutation, no-silent-fallback and destructive
      authority regressions remain green.
- [ ] No test is deleted, weakened or hidden behind a new skip; no real credential/private path,
      `config/alist.json`, unrelated file or A-owned `SLICE.md` change is included in the Developer
      checkpoint.
- [ ] All required T4 tests and quality/safety gates pass with every result reported as `PASS`,
      `FAIL`, `SKIP` or `UNAVAILABLE`.

## Required Tests

Use only fake credentials, temporary SQLite databases, temporary Local roots and fake/in-memory
Providers/Storage. Do not use production credentials, remote services or user media.

1. Focused Result persistence, File/Media detail and authenticated projection regressions:

   ```bash
   .venv/bin/python -m unittest \
     tests.test_file_media_detail \
     tests.test_file_catalog_api
   ```

   Add direct cases for A's exact fake Bearer reproduction; Basic and supported assignment forms;
   credential-shaped error/completed-operation/uncertain-effect text; all three new-write routes;
   SQLite-byte absence and restart reload; intentionally unsafe historical rows; identical safe
   latest/history behavior; Operator Web-visible data; and read-only zero-side-effects.

2. Directly affected Result, persistence, FileCatalog, API/Web, checkpoint, security and manual
   execution regression:

   ```bash
   .venv/bin/python -m unittest \
     tests.test_file_media_detail \
     tests.test_file_catalog \
     tests.test_file_catalog_api \
     tests.test_operator_ui \
     tests.test_task_persistence \
     tests.test_processing_checkpoint \
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

5. Build and isolated installed-wheel smoke because this Task changes shared persisted Result
   publication and operator-facing serialization:

   ```bash
   mediaflow_release_dir=$(mktemp -d /tmp/mediaflow-task-24.7-release.XXXXXX)
   .venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w "$mediaflow_release_dir"
   .venv/bin/python scripts/wheel_smoke_test.py "$mediaflow_release_dir"/mediaflow-*.whl
   ```

Before checkpointing, inspect `git status --short`, the complete Task Base..Head diff and exact
manifest. Confirm no deleted/weakened tests, hidden skips, unrelated files, real credentials/private
paths, tracked/staged `config/alist.json`, or A-owned `SLICE.md` change is included in the Developer
checkpoint. Report every gate as `PASS`, `FAIL`, `SKIP` or `UNAVAILABLE`.

## Non-goals

- Changing the Slice User Goal, Required Outcomes, Required Surfaces, Safety Invariants, Explicitly
  Deferred scope or immutable Base.
- Editing `SLICE.md`, its Closure Packet/A Final Review, Roadmap, Progress, product/architecture
  CURRENT documentation or any stable product requirement. After this Task passes, B only returns
  the Slice to `READY FOR A REVIEW` with a reconciled factual packet.
- Reopening or changing the PASS decision for Task 24.6; this is the new correction Task required
  by A's later full-Slice review.
- A Result schema/migration redesign, data-rewriting migration for historical rows, broad secret
  storage/logging redesign, or redacting/rekeying exact stored source/destination identities in a
  way that breaks FileIndex linkage, plan identity or recovery.
- Changing Pipeline Evidence, manual choices/Preview, authorization, conflict, checkpoint,
  OrganizerExecutor, Storage mutation or retry/recovery behavior except where necessary to reuse
  the already-shared redaction primitive and prove their existing invariants remain intact.
- Real remote SMB/OpenList/S3/R2/TMDB acceptance, production data, credentials or destructive
  operations.
- Optional copy polish, cleanup, broad refactor or extra proof unrelated to A's single blocker.

## Developer Completion Report

### Changed Files

- `mediaflow/domain/task_persistence.py`
- `mediaflow/infrastructure/sqlite_runtime.py`
- `mediaflow/application/file_catalog.py`
- `mediaflow/application/processing_checkpoint.py`
- `mediaflow/interfaces/service_api.py`
- `tests/test_file_media_detail.py`

### Implemented

- Added one shared `PersistentResultRecord` redaction helper backed by the existing
  `manual_safety` rules. It protects Result title, error, completed-operation and uncertain-effect
  text at SQLite write/reload boundaries while preserving exact source/destination lookup fields.
- Routed direct Result append, atomic TaskItem/evidence completion and manual-execution atomic
  publication through the same redacted SQLite value builder.
- Applied one recursive, shape-preserving API Result projection to both File detail `results[]`
  and `latestResult`; FileCatalog detail also redacts identity strings for display without
  changing persisted linkage or execution data.
- Reused the shared redaction helper in the read-only Processing Checkpoint Result path so its
  embedded latest Result cannot re-expose unsafe destination/effect text.
- Added fake-credential regressions for new SQLite writes, restart reload, unsafe historical rows,
  unchanged historical bytes, FileCatalog, authenticated API and Operator Web-consumed data.

### Tests and Results

- `.venv/bin/python -m unittest tests.test_file_media_detail tests.test_file_catalog_api` — PASS
  (19 tests, 0 failures).
- `.venv/bin/python -m unittest tests.test_file_media_detail tests.test_file_catalog
  tests.test_file_catalog_api tests.test_operator_ui tests.test_task_persistence
  tests.test_processing_checkpoint tests.test_api_security tests.test_manual_organize_execution
  tests.test_final_integration` — PASS (112 tests, 0 failures).
- `.venv/bin/python -m unittest discover -s tests` — PASS (1005 tests, 0 failures, 7 explicit
  skips).
- `.venv/bin/ruff format --check .` — PASS (338 files already formatted).
- `.venv/bin/ruff check .` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m pip check` — PASS (no broken requirements).
- Both required `mediaflow config validate` commands — PASS.
- FFprobe/FFmpeg dependency scan — PASS (no matches).
- `git diff --check` — PASS.
- `git check-ignore -q config/alist.json` and tracked-file check — PASS; the private config remains
  ignored and untracked.
- Wheel build with `pip wheel --no-deps --no-build-isolation` and isolated
  `scripts/wheel_smoke_test.py` — PASS; runtime schema 27 backup, rehearsal, restore, verify and
  upgrade preflight all passed.

### Decisions

- Kept source and destination identities exact in the repository Result model so FileIndex lookup,
  plan identity and recovery semantics do not change; display projections opt into identity-text
  redaction and recursively sanitize every emitted string.
- Centralized SQLite serialization in `_result_values`, including the manual atomic path through
  `_insert_result_locked`, so protection does not depend on normal producers sanitizing first.
- Historical rows are sanitized on reconstruction/projection only and are never rewritten by a
  detail read or refresh.
- Extended only the existing read-only Processing Checkpoint formatter because File detail embeds
  its latest Result there; no Task, execution, Storage or OrganizerExecutor behavior changed.

### Remaining In-Slice Work

After implementation, B reviews this Task; on PASS, B returns Slice 24 directly to A.

### Risks / Deviations

- Python 3.13 emitted existing unclosed-SQLite `ResourceWarning` messages during the full suite;
  all tests passed and this Task did not introduce a new failure.
- Real SMB/OpenList/S3/R2/TMDB and endurance acceptance were not run; they are unavailable and
  outside this offline Task test setup. No production credentials, remote services or user media
  were used.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: d2e399803078317f2092d895eae627327998de2f
```

## B Review Result

```text
Reviewed: 83ec59b07f38da4f58e9b5a97a9242fc2885433d..d2e399803078317f2092d895eae627327998de2f
Decision: PASS
Slice Required Outcomes all satisfied: YES
Next: SLICE READY FOR A REVIEW
```

### B Verification Evidence

- A's blocker independently reproduced and closed. B seeded a historical `task_results` row with
  raw SQL carrying A's exact `Authorization: Bearer slice24-final-review-secret` in `error`, plus
  `password=`, `Authorization: Basic` and `cookie=` forms in `title`, `completed_operations`,
  `uncertain_effects` and `destination_path`. An authenticated `GET /api/v1/files/one` returned
  HTTP 200, `Authorization: [redacted]` in both `latestResult.error` and `results[0].error`, and no
  `slice24-final-review-secret` substring anywhere in the document. The committed regression proves
  the same behavior with an equivalent fake token value.
- Both File/Media Result projections share one boundary: `FileCatalogService.detail` passes latest
  and history records through `redact_persistent_result`, and `MediaFlowApi._file_result_value`
  returns `redact_manual_value(document)`. Response key sets are unchanged (19 keys for
  `latestResult`, 25 for `results[]`), so the projection is shape-preserving.
- All three `INSERT OR REPLACE INTO task_results` routes (`append_result`,
  `complete_item_with_evidence`, `_insert_result_locked` used by `complete_manual_execution_item`
  and `reconcile_manual_execution`) now share `_result_values`, which redacts before binding. After
  close, no file in the database directory contained the fake credential; reopened records returned
  `Authorization: [redacted]`, `password=[redacted]` and `token=[redacted]` with status, source and
  destination linkage and RecognitionType `C` unchanged.
- The single row-reconstruction path `_result` redacts on read, so every Result reader is covered;
  the one remaining unredacted construction (`SQLiteFileIndexRepository._enriched_record`) is used
  only for derived list filtering and its Result never reaches a response.
- A seeded historical row was byte-identical before and after detail reads; no rewrite, Task, Job,
  audit, Provider, Storage, authorization or OrganizerExecutor call was added.
- Test and gate results reproduced by B at this Head: focused 19 tests PASS; directly affected
  regression 112 tests PASS; `unittest discover -s tests` 1005 tests PASS with 7 environment-gated
  skips; `ruff format --check` 338 files PASS; `ruff check`, compileall, `pip check`, both
  `config validate` commands, FFmpeg/FFprobe scan, `git diff --check` and the `config/alist.json`
  ignored/untracked checks PASS; wheel build plus isolated `scripts/wheel_smoke_test.py` PASS at
  runtime schema 27. Real SMB/OpenList/S3/R2 and endurance acceptance remain SKIP/UNAVAILABLE.
- Diff hygiene: `83ec59b..HEAD` touches only `TASK.md`, five `mediaflow` modules and
  `tests/test_file_media_detail.py`. No test was deleted, no assertion removed, no skip added, no
  `SLICE.md` change and no real credential or private path is present.
- Two P3 observations are recorded in the Slice Closure Packet for A and are not Task blockers.

Task 24.7 requires no further Developer work. B returns Slice 24 to `READY FOR A REVIEW` with a
reconciled Closure Packet. This result does not close the Slice or update Roadmap.
