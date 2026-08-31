# Task 24.1 — Bounded File/Media Detail, Evidence, and Cross-Links

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 24.1
Parent Slice: 24 — Files / Media Detail and Manual Organize
Status: READY FOR B REVIEW
Task Base: 74029a10ea9945d515bf4060ad27e1e826113451
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the read-only File/Media detail journey in Slice Required Outcome RO-1, including the
read-side portion of RO-7: an authenticated operator can open one bounded, reload-stable detail
from every existing related operational surface and understand the indexed source, captured
pipeline decisions and explanations, durable work/history/effects, unavailable legacy evidence,
and only the next actions currently valid for that file.

This Task advances Product Experience journeys H (File browsing, detail, history, and explanation)
and E (per-item recovery inside a batch). The usable segment ends at explanation, navigation, and
existing safe actions; creating manual-organize intent, choosing overrides, generating a new manual
Preview, or granting execution authority belongs to later Tasks in this Slice.

## Why This Task Exists

The current `FileCatalogDetail` joins a FileIndex record to only one latest Result and a small set
of review links. The API and Web therefore cannot show the captured Parser/Recognition/Metadata
explanations, immutable configuration identity, complete policy/plan ownership, prior Results,
conflicts, operation effects, Processing Checkpoint, or a coherent recovery decision. Important
pipeline data exists transiently in `StrategyTestResult`, while other durable facts are split among
TaskItem, Result, review/conflict, recovery, and operation records. Legacy gaps also cannot be
distinguished consistently from a genuine negative result.

This is the largest reasonable first unit because it establishes one normalized, bounded evidence
and navigation authority across Domain → Persistence → Application → API → Web before later
manual selection and Preview Tasks bind decisions to it. It must reuse the existing pipeline,
Processing Checkpoint, review/conflict, Result, RBAC, and redaction authorities rather than create a
parallel media catalog or infer history from logs.

## Implementation Scope

Implement one coherent vertical read journey:

```text
Pipeline evidence capture
→ restart-safe SQLite persistence/migration
→ bounded File/Media detail projection
→ shared Application service
→ authenticated versioned API
→ Operator Web detail and inbound cross-links
→ automated migration/integration/safety tests
```

- Define provider-neutral immutable evidence/read contracts sufficient to explain captured parse,
  recognition, normalized metadata identity/matcher outcome, selected policy identities, naming,
  classification, destination/operation, attachment/conflict/capability/warning decisions and the
  configuration snapshot that owned them. Evidence must be bounded and structurally exclude raw
  Provider DTOs, credentials, headers, cookies, private configuration and unbounded exception text.
- Persist that evidence at the existing tracked TaskItem/pipeline boundaries for newly processed
  waiting, DryRun, skipped, failed, partial and successful items. Link it to the exact Task,
  TaskItem, Result/plan where available, source Storage-relative identity and immutable
  configuration snapshot. Persistence failure must roll back the applicable evidence/state write
  rather than publish a misleading partial detail.
- Add a forward SQLite migration that preserves existing rows. Records created before evidence was
  captured must remain readable and display field/section-level `unavailable` or `unknown`; do not
  reconstruct Parser, matcher, plan, capability or effect facts from a status string, filename,
  current Active configuration or a later run.
- Extend the File/Media detail projection to join the authoritative FileIndex record with bounded,
  deterministic captured evidence; pinned configuration identity; related TaskItems and their
  Processing Checkpoints; all relevant review types and conflict confirmations; prior Results;
  completed/verified/uncertain operation effects; errors/audits; and links to the current durable
  objects. Use explicit per-collection limits and stable ordering, and expose truncation/availability
  state rather than silently omitting excess or legacy evidence.
- Derive currently valid next actions from the same existing application/checkpoint/review state
  used by their write endpoints. Detail may link or offer only already implemented safe actions
  such as blocker resolution, exact checkpoint recovery/investigation, re-recognition, re-match,
  re-plan and the existing correction DryRun continuation. Merely reading or refreshing detail must
  never create work, probe Storage, call a Provider, grant authority or mutate media.
- Keep `GET /api/v1/files/{file_id}` as the shared versioned File/Media detail surface (compatible
  additive response changes are preferred). Render purposeful sections and unavailable/unknown
  states in Operator Web rather than a generic object dump. A viewer with read permission can see
  permitted evidence; write controls remain governed by their existing narrower permissions and
  confirmation rules.
- Add inbound File/Media navigation from existing TaskItem/Processing Checkpoint, recognition and
  metadata/classification review, conflict confirmation, and Result/history Web surfaces when a
  current indexed file can be resolved. A missing, stale or ambiguous source link must show an
  explicit unavailable/current-state explanation and must not guess a File ID.
- Preserve RecognitionType independently from all downstream policy identities. In particular,
  captured and projected C evidence must remain C while Naming/Classification/Organize policy A is
  shown as downstream ownership.
- Update architecture or operator documentation only where needed to record the new CURRENT
  read/evidence boundary. Do not change the Slice Contract, Roadmap boundary, canonical product
  requirements, or claim manual organize/Preview/execution completion.

## Acceptance Criteria

- [ ] From Files and from an existing TaskItem/checkpoint, recognition review, metadata review or
      correction, classification review, conflict confirmation and Result/history entry, an
      authenticated operator can reach the same current File/Media detail when the indexed source
      identity resolves uniquely; stale/missing/ambiguous links produce an explicit safe explanation.
- [ ] The detail shows bounded source Storage/ResourceLibrary and FileIndex scan/change/stability
      state plus captured Parser fields, warnings and evidence availability without reading media or
      inferring unavailable legacy parse facts.
- [ ] Captured Recognition status/type, matched and rejected rule/reason evidence, normalized
      Metadata identity and matcher outcome, selected policy identities, naming/classification
      results, destination/operation, attachments, capability/conflict verdicts and warnings are
      attributable to the exact TaskItem/configuration snapshot and remain stable after reload.
- [ ] RecognitionType C remains C in persisted evidence, API output, Web detail and linked
      Result/checkpoint while downstream Naming/Classification/Organize policy A remains visibly A.
- [ ] The detail presents a deterministic bounded history of related TaskItems/checkpoints,
      reviews/conflicts, Results, completed/verified/uncertain operation effects, errors and audits;
      limits/truncation and section-level `unavailable`/`unknown` states are explicit.
- [ ] Waiting recognition, metadata, metadata-correction, classification and conflict cases each
      link to their existing shared resolution surface and block only the affected item. Failed,
      partial and uncertain cases show the existing checkpoint-aware recovery or investigation
      action; terminal or ineligible items do not expose replay controls.
- [ ] The API and Web use the same File/Media detail application projection, RBAC decision and
      current-action semantics. A principal without READ is rejected, and a read-only principal
      cannot invoke mutation/decision controls it lacks permission to use.
- [ ] Opening, refreshing and traversing File/Media detail creates no Task, Job, review, conflict,
      recovery request, authorization, audit mutation or Provider request and performs no Storage
      list/stat/exists/read/mutation call. Response and rendered error/evidence content are bounded
      and secret-free.
- [ ] The SQLite migration upgrades an older runtime database without losing FileIndex, Task,
      TaskItem, Result, review/conflict, checkpoint/recovery or audit rows; restart/reopen returns the
      same captured detail, and a failed transactional evidence/state write leaves no half-published
      record.
- [ ] Existing Files list/filter/stats and current file actions remain compatible, and no alternate
      pipeline, free-form path/plan input, Active-configuration mutation or execution authority is
      introduced.
- [ ] All T4 Required Tests pass, `config/alist.json` remains ignored/untracked/unstaged, and the
      checkpoint contains only this Task's coherent implementation and completion report.

## Required Tests

Run and report every command below. Use temporary SQLite databases, temporary Local roots and
fake/in-memory ports only; no production Storage, Provider credential or user media is permitted.

1. Focused File/Media evidence, projection, cross-link, RBAC and zero-I/O coverage (create the
   focused module if it does not exist):

   ```bash
   python -m unittest tests.test_file_media_detail
   ```

   Cover captured and legacy-unavailable evidence; waiting/DryRun/success/failure/partial/uncertain
   states; deterministic bounds/truncation; stale/missing links; Type C with A downstream policies;
   read-only reload; permission denial; redaction; and spies that fail on Provider construction,
   Storage reads/mutations, queue/work creation or authorization creation during detail reads.

2. Directly affected persistence, API/Web, checkpoint and pipeline regressions:

   ```bash
   python -m unittest \
     tests.test_file_catalog \
     tests.test_file_catalog_api \
     tests.test_operator_ui \
     tests.test_processing_checkpoint \
     tests.test_task_persistence \
     tests.test_migration_rehearsal \
     tests.test_upgrade_preflight \
     tests.test_final_integration
   ```

3. Complete offline regression:

   ```bash
   python -m unittest discover -s tests
   ```

4. Quality, safety, configuration and dependency gates:

   ```bash
   ruff format --check .
   ruff check .
   python -m compileall -q mediaflow tests scripts
   python -m pip check
   mediaflow --config config/strategy.example.json config validate
   mediaflow --config config/mediaflow.phase13.2.example.json config validate
   test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"
   git diff --check
   ```

5. Build and isolated installed-wheel smoke test because this Task changes the runtime schema and
   packaged application surface:

   ```bash
   mediaflow_release_dir=$(mktemp -d /tmp/mediaflow-task-24.1-release.XXXXXX)
   python -m pip wheel . --no-deps --no-build-isolation -w "$mediaflow_release_dir"
   python scripts/wheel_smoke_test.py "$mediaflow_release_dir"/mediaflow-*.whl
   ```

Before checkpointing, also inspect `git status --short`, the complete Task Base..Head diff and exact
manifest; confirm no deleted/weakened tests, hidden skips, unrelated files, secrets/private paths,
or tracked/staged `config/alist.json`.

## Non-goals

- Creating durable manual-organize intent or bounded selection, editing per-item choices, or
  enumerating configurable override options (RO-2).
- Running or persisting a new manual Preview, Preview invalidation, or plan-bound authorization
  (RO-3/RO-4).
- Real execution admission, one-shot exact-plan authority, destructive authority, Storage mutation,
  file-index source/target reconciliation, or new recovery execution semantics (RO-5/RO-6).
- Provider switching, arbitrary Provider payloads, free-form source/destination/plan/operation
  editors, playback/media-server catalog work, or anything Explicitly Deferred by `SLICE.md`.
- Replacing FileIndex, Task/TaskItem/Result, Processing Checkpoint, review/conflict,
  OrganizerExecutor, security audit or managed configuration authorities with a parallel model.
- Work outside the parent Slice Contract, the next Task or next Slice, optional proof/copy polish,
  P2 cleanup, or unrelated refactoring.

## Developer Completion Report

### Changed Files

- `mediaflow/domain/media_evidence.py` (new): bounded immutable evidence contract.
- `mediaflow/application/evidence_capture.py` (new): normalized evidence builder.
- `mediaflow/application/media_organizer.py`: evidence attachment/capture at pipeline boundaries.
- `mediaflow/application/task_runtime.py`: evidence persistence and atomic completion path.
- `mediaflow/infrastructure/sqlite_runtime.py`: Runtime schema `27`, `pipeline_evidence`
  table/indexes, evidence/source history queries, atomic item/result/evidence write.
- `mediaflow/application/file_catalog.py`: enriched File/Media detail projection, source-link
  resolution, checkpoint-derived current actions.
- `mediaflow/interfaces/service_api.py`: expanded `GET /api/v1/files/{file_id}` detail, additive
  `GET /api/v1/files/by-source`, zero-audit read behavior for File/Media detail reads.
- `mediaflow/interfaces/operator_ui.py`: File/Media evidence/history/action rendering and inbound
  cross-links from TaskItems, reviews, conflicts, Results and recovery surfaces.
- `docs/architecture.md`: records the new CURRENT detail/evidence boundary and schema marker.
- `tests/test_file_media_detail.py` (new): focused evidence, projection, cross-link, RBAC,
  migration, rollback and zero-I/O coverage.
- Updated schema-marker assertions in affected persistence tests.

### Implemented

- Captures bounded provider-neutral evidence at existing tracked TaskItem boundaries for waiting,
  DryRun, skipped, failed, partial and successful items, including Parse, Recognition, Metadata,
  policy ownership, Naming, Classification, plan, operation/effect and declared Storage
  capability sections.
- Persists evidence in a forward-migrated SQLite table (`runtime` marker `27`) with stable
  ordering, bounded collections and explicit truncation; legacy records remain readable as
  section-level `unavailable` and are never reconstructed.
- Writes completed item outcome, Result and evidence in one repository transaction; waiting
  evidence is recorded before the existing review/conflict wait transition.
- Extends `FileCatalogDetail` with bounded evidence, related TaskItems/checkpoints, Results/effects,
  related reviews/conflicts and current checkpoint-derived actions; API and Web use the same
  projection.
- Adds `GET /api/v1/files/by-source` for safe inbound navigation from TaskItem/checkpoint, review,
  conflict and Result surfaces; missing or ambiguous links return an explicit unavailable reason.
- Renders purposeful evidence/history/action sections and unavailable/truncation states in the
  Operator Web instead of a raw object dump, and adds File/Media navigation buttons to existing
  surfaces.
- Preserves RecognitionType C independently from downstream Naming/Classification/Organize policy A
  in captured evidence, persisted rows, API output and Web rendering.
- Keeps File/Media detail reads free of Provider construction, Storage I/O, queue/work/authorization
  creation, and security-audit mutations for authorized detail reads.

### Tests and Results

All commands below passed in the repository's `.venv`.

```text
.venv/bin/python -m unittest tests.test_file_media_detail
  PASS (8 tests)

.venv/bin/python -m unittest \
  tests.test_file_catalog tests.test_file_catalog_api tests.test_operator_ui \
  tests.test_processing_checkpoint tests.test_task_persistence \
  tests.test_migration_rehearsal tests.test_upgrade_preflight tests.test_final_integration
  PASS (70 tests)

.venv/bin/python -m unittest discover -s tests
  PASS (954 tests, 7 skipped)

.venv/bin/ruff format --check .
  PASS
.venv/bin/ruff check .
  PASS
.venv/bin/python -m compileall -q mediaflow tests scripts
  PASS
.venv/bin/python -m pip check
  PASS
.venv/bin/mediaflow --config config/strategy.example.json config validate
  PASS
.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate
  PASS
test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"
  PASS
git diff --check
  PASS

python -m pip wheel . --no-deps --no-build-isolation -w <temp release dir>
python scripts/wheel_smoke_test.py <temp release dir>/mediaflow-*.whl
  PASS (schema 27 backup/rehearsal/restore/preflight)
```

### Decisions

- Evidence is stored as one immutable JSON document per TaskItem attempt with bounded section
  documents, keeping the contract stable and avoiding a parallel domain model.
- `PersistentTaskCoordinator.complete_item` uses `complete_item_with_evidence` when the repository
  supports it so Result, item state and evidence publish or roll back together.
- `GET /api/v1/files/by-source` is an additive read-only source-resolution endpoint rather than
  guessing File IDs in the Web layer.
- Current actions are taken from the latest actionable TaskItem checkpoint, so an older blocked
  item remains actionable even when a later terminal attempt exists.
- Authorized File/Media detail reads skip the generic security-audit write to satisfy the
  zero-audit-mutation requirement while denial/error paths and other API reads remain audited.

### Remaining In-Slice Work

- Durable manual-organize intent, bounded selection and per-item override choices (RO-2).
- Persistent manual Preview/plan and stale-evidence invalidation (RO-3/RO-4).
- Exact-plan execution admission, one-shot authority and OrganizerExecutor-only real mutation
  (RO-5/RO-6).
- Any later Slice 24 Tasks B plans after this read journey is reviewed.

### Risks / Deviations

- No external Provider/Storage services were used; the full regression's 7 skipped tests are the
  pre-existing external/acceptance skips.
- The CLI `files show` renderer remains the prior basic projection; the Task's operator-facing
  surface (API/Web) carries the new detail journey.
- The existing WSGI security-audit boundary is intentionally suppressed only for authorized GET
  File/Media detail and by-source reads; all other API requests retain their audit behavior.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 3fdcc1bea562469d1d0dc39fb6128a4efa3c4a7c
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```
