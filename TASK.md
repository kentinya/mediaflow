# Task 27.2 - Current Source Occurrence and Processing Disposition

This Task follows [the development workflow](../docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](../SLICE.md).

```text
Task ID: 27.2
Parent Slice: 27 - Manual Operations and File Lifecycle
Status: PLANNED
Task Base: ebe31799a38d07e1dc02aa4a9a343739461e6123
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the current-source lifecycle portion of Slice 27 RO-2, with the matching FileIndex
projection needed by RO-8: an authenticated operator can distinguish discovery/stability state from
the processing disposition of the current source occurrence, see when a prior result is still
relevant, and explicitly request bounded Reprocess for the exact current occurrence when duplicate
work protection applies. Reprocess is an auditable admission request only; it does not start a scan,
Provider request, Task, Preview, organization or Storage mutation.

## Why This Task Exists

Task 27.1 established separate real-Storage `Files` and indexed `FileIndex` surfaces. The current
FileIndex still primarily identifies a record by Storage/path and exposes scan state, while prior
Task/Result history can be joined by the same path. A file replaced at that path can therefore be
mistaken for the earlier occurrence, and the operator has no durable orthogonal processing
disposition or safe duplicate-work decision. Task 27.1 was reviewed PASS at checkpoint
`6a577b9ac0192954a03ca2f706552517a14bd1e0`; the report-only follow-up commit is the Task Base for
this unit.

This is the largest reasonable next unit because current occurrence identity and disposition are the
state contract required by the later scoped Scan, Preview, Organize and recovery Tasks. It can be
accepted independently through durable FileIndex reload, replacement reconciliation and the
read-only FileIndex journey without introducing those later execution workflows.

## Implementation Scope

```text
Domain -> Persistence/migration -> discovery/result integration -> Application -> versioned API
-> Operator Web -> tests
```

- **Domain:** add bounded, immutable source-occurrence identity/fingerprint evidence and a distinct
  processing-disposition model. Keep `(Storage ID, ResourceLibrary ID, Storage-relative path)` as
  the FileIndex location identity, but do not use it as the occurrence identity. Evidence must be
  deterministic, secret-free, provider-neutral and based only on the Storage abstraction; do not
  use FFprobe/FFmpeg or media-stream inspection. Define an explicit legacy/unverified state rather
  than inferring success from old rows.
- **Persistence:** add the minimum durable current-occurrence pointer/history, fingerprint
  evidence, disposition, prior-result relevance and Reprocess audit/request state. Migrate fresh
  and existing runtime databases without dropping FileIndex, Task, TaskItem, Result, checkpoint,
  authority or automation state. Updates that reconcile an occurrence or admit Reprocess must be
  atomic and bounded; concurrent/stale requests must fail closed.
- **Discovery integration:** update the existing FileIndex discovery/upsert path so an unchanged
  source retains its occurrence, a changed or replaced source at the same Storage/path receives a
  new occurrence, and an incomplete/cancelled/failed scan cannot fabricate `Missing`. Preserve the
  existing full-scan reconciliation boundary and zero-mutation Scanner semantics. Do not add the
  file-/ResourceLibrary-scoped Scan submission journey in this Task.
- **Task/Result integration:** correlate existing TaskItem/Result evidence to the occurrence that
  was actually observed by the work. Project at least successful/organized, skipped, attention/conflict,
  review, partial, failed and unknown/unverified outcomes without deriving disposition from
  `scanStatus`. COPY and Skip must leave the source occurrence present with its independent
  disposition; a MOVE result must not claim the source is missing until discovery observes that fact.
  Results for an old occurrence remain historical and cannot suppress or satisfy a replacement
  occurrence.
- **Application:** provide one read projection service for FileIndex list/detail and one bounded,
  auditable Reprocess admission operation. Reprocess must be bound to the exact `fileId`, current
  occurrence identity/fingerprint and current state, use existing least-privilege authorization,
  and expose one explicit next action for the later Scan/Preview workflow. It must not execute work,
  clear history, grant authority or silently reset an unrelated occurrence.
- **API:** extend the explicit `/api/v1/file-index` list/detail contract, retaining compatible
  aliases where required, with orthogonal scan/discovery state, current occurrence evidence,
  processing disposition, prior-result relevance, effect/retry facts where available and bounded
  actions. Add the corresponding explicit Reprocess write route(s) through the same application
  service, with stable validation/concurrency errors, actor audit, redaction and no arbitrary path,
  operation or Provider payload accepted in the request body.
- **Operator Web:** FileIndex list/detail visibly separates scan status from processing disposition,
  identifies the current occurrence and marks historical or unverified results as such. Show
  Reprocess only when the current occurrence is eligible, require explicit confirmation, and render
  the durable result and next action after admission or failure. Keep the 27.1 `Files` browser
  read-only and free of processing-disposition claims.
- **Tests:** cover domain transitions, persistence migration/reload, same-path replacement,
  unchanged/copy/skip/move/missing cases, incomplete-scan protection, result relevance,
  duplicate/stale Reprocess requests, API/Web parity, RBAC, redaction and zero Storage/Provider/
  Task/authority side effects using temporary roots, fakes or isolated local services.

Frozen unless a listed Acceptance Criterion cannot be met without a minimal compatible change:

- `SLICE.md`, its Base SHA, Required Outcomes, Required Surfaces, Safety Invariants and Explicitly
  Deferred entries;
- the Task 27.1 real-Storage Files browser contract, cursor/confinement semantics and membership
  projection;
- new file-/ResourceLibrary-scoped Scan submission and durable Scan Task orchestration (next Task);
- Preview findings, manual Organize admission/execution, conflict/review/recovery continuation and
  Worker registration/readiness (later Tasks);
- Recognition, Metadata, Naming, Classification, OrganizePlan, OrganizerExecutor, Storage mutation
  semantics, scheduled automation and manual execution authority, except for the minimum compatible
  result-linkage hook required to preserve occurrence correctness;
- `config/alist.json`, real credentials, private endpoints and user media.

## Acceptance Criteria

- [ ] FileIndex exposes `scanStatus`/discovery state and `processingDisposition` as separate
      durable fields. A scan-state change cannot silently rewrite a processing outcome, and a
      processing outcome cannot be inferred merely from `READY`, `MISSING` or another scan status.
- [ ] Repeated observation of an unchanged current file retains the same occurrence identity and
      preserves its disposition. A changed or replaced file at the same Storage/path gets a new
      current occurrence with sufficient bounded fingerprint evidence; prior results remain linked
      to the old occurrence or explicitly `not current` and cannot suppress the new one.
- [ ] Fingerprint/identity uncertainty, legacy rows, unreadable source evidence and conflicting
      reconciliation fail closed into an explicit unverified/attention state with durable state,
      known effects, retry safety and one concrete next action. No success or currentness is
      fabricated from a path-only match.
- [ ] Discovery reconciliation preserves the existing safety boundary: a cancelled, failed or
      partial/incomplete scan does not fabricate `Missing`; a completed full-scan observation may
      mark a source missing. COPY and Skip keep the source occurrence present with independent
      dispositions, while MOVE can become source-missing only after discovery confirms absence.
- [ ] Existing TaskItem/Result outcomes are correlated to the occurrence observed by the work. At
      minimum, organized/successful, skipped, attention/conflict/review, partial, failed and
      unknown/unverified outcomes are projected with bounded effect/retry information, while
      successful or failed history for an older occurrence remains visible but does not become the
      current occurrence's outcome.
- [ ] An explicit Reprocess request is admitted only for an eligible exact current `fileId` and
      occurrence, records a bounded actor/audit and durable state, rejects duplicate, stale,
      missing, ambiguous and wrong-state requests atomically, and exposes the exact next action
      for later explicit analysis. It creates no Storage mutation, Provider request, Task/Job,
      Preview, review obligation or execution authority.
- [ ] Authenticated API and Operator Web expose the same occurrence/disposition/relevance state,
      validation, RBAC, pagination, redaction, audit and Reprocess safety semantics. Viewer/read
      access cannot admit Reprocess or mutate durable lifecycle state, and no request body can
      supply an arbitrary path, operation or provider payload.
- [ ] The 27.1 `Files` response remains a real configured-Storage read surface and does not claim
      current occurrence, processing disposition or organization outcome from membership alone.
- [ ] Fresh and pre-Task-27.2 runtime databases migrate and reload without loss of existing
      FileIndex, Task, TaskItem, Result, checkpoint, configuration-authority or automation state;
      legacy lifecycle values are explicit and bounded.
- [ ] Required T4 tests, safety scans and quality gates pass. The checkpoint contains only this
      Task's coherent changes and introduces no real credentials, private endpoints, user media or
      `config/alist.json`.

## Required Tests

Run from the repository root with the project environment. Add the Task-specific lifecycle module
to the focused command once created:

```bash
.venv/bin/python -m unittest \
  tests.test_file_index_lifecycle \
  tests.test_scanner \
  tests.test_file_catalog \
  tests.test_file_catalog_api \
  tests.test_task_persistence \
  tests.test_migration_rehearsal \
  tests.test_api_security \
  tests.test_operator_ui
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff format --check mediaflow tests
.venv/bin/ruff check mediaflow tests
.venv/bin/python -m compileall -q mediaflow tests
.venv/bin/pip check
git diff --check
```

The focused tests must prove same-path unchanged/replaced behavior, source-fingerprint or
occurrence uncertainty, COPY/Skip/MOVE/Missing and incomplete-scan semantics, reload/migration,
result relevance, duplicate/stale Reprocess requests, API/Web parity, RBAC, redaction and that
read/admission paths do not construct Providers, call mutating Storage methods, create Tasks/Jobs,
create reviews or grant execution authority. Use temporary Local roots, fakes or isolated local
services only. Record full-suite skips, baseline/environment failures and unavailable production
SMB/OpenList/AWS S3/Cloudflare R2 gates truthfully; fake behavior is not production compatibility.

Also run the applicable repository configuration validation, forbidden FFprobe/FFmpeg scan,
private-config/secret scan and migration/persistence checks. Do not contact production Storage,
Provider services or use user media.

## Non-goals

- File-/ResourceLibrary-scoped Scan commands, durable Scan Job/Task orchestration, cancellation or
  per-scope worker execution (Slice 27 RO-3).
- Complete analysis-only Preview findings and production-equivalent parse/recognition/metadata/
  naming/classification planning (Slice 27 RO-4).
- Manual Organize admission/execution, one-shot authority, attachment handling or mutation behavior
  (Slice 27 RO-5).
- Conflict/Review/Recovery continuation, automatic replay rules, batch sibling recovery or Worker
  readiness/fencing (Slice 27 RO-6 and RO-7).
- New Storage providers, mutation-based capability probes, recursive/unbounded browsing, arbitrary
  host filesystem access, Metadata Provider switching, built-in identity, Secret Store integration,
  Docker release work or Slice 28 administration.
- Redesign of the closed processing pipeline, Scanner semantics beyond the minimum lifecycle hook,
  OrganizerExecutor, Storage mutation/fallback policy, scheduled automation or execution authority.
- Optional proof, broad UI redesign, test-only cleanup, P2/P3 polish or work outside Slice 27.

## Developer Completion Report

### Changed Files

- Lifecycle domain, FileIndex contracts, scanner projection, and task/result persistence: `mediaflow/domain/file_lifecycle.py`, `mediaflow/domain/file_index.py`, `mediaflow/domain/scanner.py`, `mediaflow/domain/storage.py`, `mediaflow/domain/task_persistence.py`.
- Application and infrastructure lifecycle behavior: `mediaflow/application/file_index_lifecycle.py`, `mediaflow/application/file_catalog.py`, `mediaflow/application/scanner.py`, `mediaflow/application/task_runtime.py`, `mediaflow/infrastructure/file_index_schema.py`, `mediaflow/infrastructure/memory_file_index.py`, `mediaflow/infrastructure/sqlite_file_index.py`, `mediaflow/infrastructure/sqlite_runtime.py`, `mediaflow/infrastructure/local_storage.py`, `mediaflow/infrastructure/s3_storage.py`.
- Operator surfaces: `mediaflow/interfaces/service_api.py`, `mediaflow/interfaces/operator_ui.py`.
- Tests: `tests/test_file_index_lifecycle.py`, scanner/migration coverage, and runtime schema-version fixtures in the configuration tests.
- Documentation: `docs/architecture.md`, `docs/product-experience.md`, `docs/release.md`.

### Implemented

- Added deterministic, Storage-only source fingerprints and explicit source occurrences, including verified, unverified, and migrated-legacy states, occurrence history, and independent processing dispositions.
- Added additive runtime schema 32 migration and exact occurrence/fingerprint linkage for FileIndex, TaskItems, and ResultRecords. Source replacement, incomplete scans, unreadable sources, stale reconciliation, and operation effect certainty now preserve bounded durable state without allowing old results to represent a new occurrence.
- Added a shared FileIndex lifecycle projection for API and Web. The Files browser remains read-only and separate from FileIndex; operator-facing data distinguishes discovery state, processing disposition, current occurrence, prior-result relevance, and recovery guidance.
- Added exact, RBAC-protected Reprocess admission with required current occurrence and fingerprint, duplicate/unsafe-state rejection, audit information, and no Task creation, provider request, or storage mutation.

### Tests and Results

- PASS — `.venv/bin/python -m unittest tests.test_file_index_lifecycle tests.test_scanner tests.test_file_catalog tests.test_file_catalog_api tests.test_task_persistence tests.test_migration_rehearsal tests.test_api_security tests.test_operator_ui` — 101 tests.
- FAIL / PRE-EXISTING / UNRELATED — `.venv/bin/python -m unittest discover -s tests` — 1178 tests, 9 failures, 7 skips, 0 errors. The three queue-full failures also reproduce at exact Task Base `ebe31799a38d07e1dc02aa4a9a343739461e6123` (Base: 1167 tests, 3 failures, 7 skips). The other six failures are credential/configuration/CLI/storage cases reading the existing ignored private `config/alist.json` and local runtime state; the clean Base worktree does not reproduce them.
- PASS — `.venv/bin/ruff format --check mediaflow tests` (242 files), `.venv/bin/ruff check mediaflow tests`, `.venv/bin/python -m compileall -q mediaflow tests`, `.venv/bin/pip check`, and `git diff --cached --check`.
- PASS — `.venv/bin/mediaflow --config config/strategy.example.json config validate` and `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`.
- PASS — repository scan found no `FFprobe`/`FFmpeg` matches in `mediaflow` or `pyproject.toml`; `config/alist.json` remains ignored, untracked, and absent from the diff.
- SKIP / UNAVAILABLE — production SMB/OpenList/S3/R2/TMDB services were not contacted because no external credentials or services were in scope; coverage uses fakes, local test servers, and temporary local storage.

### Decisions

- A source occurrence is tied to the stable storage/library/path identity plus a deterministic fingerprint; the scanner does not read file content or inspect streams.
- Only a completed full scan may reconcile missing entries. Partial, failed, cancelled, or unreadable discovery does not turn a source into Missing; stale late reconciliation is represented as bounded Attention state.
- Reprocess is an admission record for the exact current occurrence. It deliberately creates no workflow and performs no provider, task, or storage operation.
- Legacy rows are migrated explicitly as `LEGACY` rather than being presented as verified current evidence; result relevance is exact-occurrence and fingerprint-aware.

### Remaining In-Slice Work

- Other Slice 27 journeys, including preview/confirmation, manual organize execution, conflict or review recovery, and worker readiness, remain outside this Task.

### Risks / Deviations

- The full-suite failures listed above remain for B to classify; no unrelated queue/configuration behavior was changed to manufacture a green result.
- Production storage and metadata-provider compatibility is not live-verified in this environment. Existing SQLite ResourceWarnings from unclosed test connections remain non-blocking and pre-existing.
- Existing unrelated `SLICE.md`, `docs/roadmap.md`, `nohup.out`, and `worker.log` worktree changes were preserved and are not part of the checkpoint.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 75c64eb3f6d65a09211acdeaa232a1e6cbddf0ea
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
