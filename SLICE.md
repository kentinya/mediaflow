# Slice 27 — Manual Operations and File Lifecycle

This is the A-owned Slice Contract. B and Developer may not expand or weaken it. Detailed lifecycle
rules are defined only in [`docs/development-workflow.md`](docs/development-workflow.md).

```text
Slice ID: 27
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PASS / CLOSED
Base SHA: 306b77d0aad44ab0a2e233866f8972247b437a7d
Implementation Head: 34365121342557b0f40eacc7ad9bbb74499cc4cb
```

The Base is the Slice 26 closure checkpoint and the real repository commit immediately before the
current Slice 27 implementation line began. This document corrects the active Slice Contract to match
that already-started Slice 27 line; B must still review actual Task checkpoints and may not treat any
forward commit as accepted merely because it predates this document correction. B records the real
product Implementation Head only when preparing the Slice Closure Packet.

## User Goal

On an authenticated self-hosted MediaFlow instance with an Active runtime, an operator can browse the
real configured Storage, distinguish it from MediaFlow's indexed FileIndex, select a bounded file or
ResourceLibrary scope, run manual Scan or analysis-only Preview, and explicitly organize approved
items through the existing safe execution authority. The operator can see current source identity,
processing disposition, Worker readiness, plans, conflicts and failures, then recover an affected
item through explicit continuation without replaying successful siblings or uncertain mutation.

This Slice ends when that daily manual operations journey is usable through Operator Web and the
versioned API using the existing processing pipeline, result/checkpoint model and safety boundaries.
It does not package or deploy Docker and does not redesign the closed processing engine.

## Vertical Journey

```text
Active runtime
→ Files real-Storage browse
→ FileIndex/current-source state
→ bounded file or ResourceLibrary selection
→ manual Scan
→ exact Active-snapshot Preview
→ inspect findings, target, conflict and authority requirements
→ explicit one-shot Organize authority
→ Worker/Task processing and per-item Result
→ disposition, Attention/Conflict/Review/Recovery state
→ explicit decision, re-analysis or safe continuation
```

Every operator-facing path must expose the entry point, visible state, available action, success
outcome, failure outcome and recovery path. Viewing, refreshing, retrying a read-only stage or saving
a decision must not accidentally start work or mutate Storage unless that explicit action is defined
as the safe continuation.

## Current Foundation

- Slice 26 is `PASS / CLOSED` and provides the immutable Active runtime authority,
  provider-neutral bounded Storage Browser/path selection, Storage-relative path semantics and the
  authenticated API/Web management boundary.
- Closed Slices 23, 24 and 25 provide durable checkpoints/recovery, bounded manual organize
  foundations, scheduled/unattended execution authority, Task/TaskItem/Result persistence,
  conflict/review decisions, audit, RBAC, redaction and OrganizerExecutor-only mutation.
- The existing pipeline already preserves the core module boundaries: ResourceLibrary → Scan → Parse
  → RecognitionRule → RecognitionType → RecognitionTypePolicy → Metadata → Naming → Classification
  → OrganizePlan → OrganizerExecutor → Result.
- The repository contains current Slice 27 implementation checkpoints and an active Task 27.7 review
  candidate. Those checkpoints are implementation facts only; B/A review must still inspect actual
  diff and test evidence before PASS or Slice closure.

## Current Gap

The product still needs one accepted daily-operations Slice boundary that ties together real Storage
Files, FileIndex processing state, current source occurrence, manual Scan/Preview/Organize,
conflict/review recovery continuation and processing Worker readiness. A user must not confuse a
Storage browser with an index, a scan/stability state with an organize disposition, a stale path with
a current source occurrence, a Preview blocker with execution authority, or a queued Job with a live
Worker guarantee.

## Required Outcomes

| ID | Required Outcome | Initial State |
|---|---|---|
| RO-1 | **Real Files and FileIndex distinction.** Authenticated Web/API users can browse configured Active-runtime Storage through bounded Storage-relative Files views, while FileIndex separately presents indexed discovery records. Membership, root/breadcrumb, pagination, hostile-name, symlink and provider-error behavior are bounded and read-only. | Slice 26 browser exists as setup surface; current Slice 27 commits require review under this Contract. |
| RO-2 | **Current source lifecycle and disposition.** FileIndex distinguishes discovery/stability state from processing disposition, correlates current Storage/library/path occurrence with bounded fingerprint evidence, marks prior Results current/historical/unverified, and exposes exact-occurrence Reprocess admission without silently creating work or mutating Storage. | Current implementation evidence exists but requires Task/Slice acceptance and migration proof. |
| RO-3 | **Bounded manual Scan.** From Files, FileIndex or ResourceLibrary, an authenticated operator can submit a file- or ResourceLibrary-scoped manual Scan with durable Task state, bounded cancellation and scope isolation. Scan discovers and reconciles candidates only; it does not organize or silently advance to mutation. | Must be proven through Web/API, persistence and zero-mutation safety. |
| RO-4 | **Exact analysis-only Preview.** A selected current source or bounded ResourceLibrary scope can run the complete applicable Parse → Recognition → Metadata → Naming → Classification → OrganizePlan path against one immutable Active snapshot. Durable Preview findings explain identity, policies, target, operation, conflict, capability and blockers per item; Preview performs zero Storage mutation and creates no execution authority or mandatory review backlog. | Must be proven at current-source and bounded-scope entry points. |
| RO-5 | **Explicit manual Organize.** An operator can select exact Preview items, provide separate one-shot manual authority/confirmation and execute only that reviewed plan. OrganizerExecutor remains the sole mutation boundary; attachments, capabilities, conflicts, operation and per-item Result/effect certainty are persisted, with no silent overwrite/delete or unsupported-operation fallback. | Manual execution foundations exist but require current-source journey and safety proof. |
| RO-6 | **Conflict, review and recovery continuation.** An affected item can enter visible Attention, Conflict, Review or Recovery state with durable stage, known effects, effect certainty, retry safety and next action. The operator can save a decision, re-analyze the exact current occurrence, obtain explicit continuation authority and continue safely while successful/skipped/ignored/DryRun siblings remain independent and uncertain mutation is never automatically replayed. | Must be accepted as continuation of the original Organize journey, not a disconnected retry. |
| RO-7 | **Processing Worker readiness and fenced ownership.** A resident processing Worker registers itself, heartbeats and stops durably, binds to an immutable runtime snapshot, and exposes bounded readiness/liveness/ownership evidence separately from API process health. No-worker and stale-worker queue conditions have concrete next actions; a stale owner cannot commit over a newer owner. API/Web/CLI do not implicitly spawn, supervise or register a Worker. | Current Task 27.7 is awaiting B review against this outcome. |
| RO-8 | **Shared application, API/Web parity and operational evidence.** All Slice journeys use the same Application behavior, validation, permissions, state transitions, optimistic/concurrent checks, audit and redaction across versioned API and Operator Web. Collections and diagnostics are bounded and secret-free; missing, stale, unavailable and unauthorized state is shown as such with recovery, never as false success. | Existing foundations must be proven across every new surface and failure path. |

## Required Surfaces

- **Operator Web:** real Storage-backed Files browsing; distinct FileIndex list/detail; bounded
  Scan/Preview/Organize entry points; Task/Result/disposition; conflict/review/recovery continuation;
  and read-only Worker readiness/registered-worker evidence.
- **Versioned API:** the same read and write journeys, validation, RBAC, bounded pagination,
  optimistic checks, error/recovery vocabulary, audit and redaction as Web. API reads cannot
  substitute for a missing required Web journey.
- **Application:** shared use cases for Storage browsing, FileIndex lifecycle, scoped Scan, exact
  Preview, manual authority/execution, recovery continuation and Worker readiness. API and Web must
  not implement a parallel pipeline.
- **Runtime Worker and task execution:** existing `worker run` / `worker run-next` entry points,
  durable registration/readiness/ownership and claim fencing, while preserving the existing Task,
  TaskItem, Result and OrganizerExecutor authorities.
- **Persistence and migrations:** durable current-source, disposition, Preview, Task/Result,
  checkpoint, recovery, Worker and audit evidence with additive fresh/current database coverage.
- **Storage infrastructure and verification:** configured Local, SMB, OpenList, AWS S3, Cloudflare
  R2 and generic S3-compatible adapters through the Storage abstraction, using fakes/local services
  for unavailable production environments and no production media or credentials.
- **Documentation/tests:** factual CURRENT documentation, focused/integration tests, safety gates and
  final validation that distinguish production compatibility from fake/local software proof.

## Safety Invariants

- Scanner, Parser, Recognition, Metadata lookup, Naming, Classification and Planner remain
  zero-mutation.
- DryRun and Preview execute the complete applicable analysis path but perform zero Storage mutation,
  create no execution authority and do not create a mandatory review merely because analysis found a
  blocker.
- Only OrganizerExecutor may invoke mutating Storage operations. Overwrite, Delete, source removal
  and directory cleanup require explicit policy and authority; no operation silently falls back to
  Copy or Move.
- Every Preview, authority, Task, TaskItem, Result and recovery continuation is bound to the exact
  immutable Active snapshot and current source occurrence/fingerprint required by its stage. Draft,
  stale evidence, changed source or stale authority fails closed.
- Batch work preserves independent item state, known effects, certainty and recovery. Unknown or
  uncertain mutation is investigation-only unless a separately proven safe action is offered; it is
  never automatically replayed.
- Storage access uses the Storage abstraction and confined Storage-relative paths. Files browsing,
  FileIndex reads, status pages and read-only checks do not scan, invoke a Provider, create work or
  mutate Storage unless an explicit action says so. Arbitrary host-path escape is not allowed.
- Worker lifecycle is self-owned by the Worker runtime. API/Web cannot spawn, supervise or register
  Workers, and durable claim/owner fencing prevents stale owners from overwriting newer results.
- RecognitionType identity is never changed by downstream policy reuse; RecognitionType C remains C
  when it uses A Naming, Classification or Organize policies.
- No FFmpeg or FFprobe dependency or media-stream inspection is introduced.
- API/Web and persistence evidence is least-privilege, bounded, auditable and secret-free. Passwords,
  tokens, API keys, authorization headers, cookies, private endpoints and secret values must not enter
  managed documents, databases, responses, logs, fixtures or Git. `config/alist.json` remains ignored,
  untracked and unstaged.

## Explicitly Deferred

- Slice 28 day-2 configuration and operations administration: Active-to-Draft object-management IA,
  System Settings, configuration/result import-export and Webhook definition management/delivery
  recovery.
- Slice 29 Docker/Compose production packaging, production WSGI topology, container healthchecks,
  `/data` deployment, restart/upgrade release acceptance and deployment-owned mount lifecycle.
- Metadata Provider switching, additional production Providers and arbitrary Provider plugins; the
  V1 production Provider remains TMDB through the existing abstraction.
- Built-in users, sessions, username/password login, OIDC, reverse-proxy identity integration,
  general Secret Store and Docker Secrets integration.
- Automatic uncertain-mutation replay, universal compensation, complete historical/crash Rollback,
  mutation-based Storage probes, distributed locks, work stealing, queue routing, priorities and a
  scheduler redesign.
- Notification Worker registration/delivery redesign and specialized email, chat or media-server
  notifications; the existing signed Webhook engine remains a Slice 28 management journey.
- Media streaming, poster/fanart/trailer generation or download, NFO generation, multi-version
  upgrade policy and other post-V1 media features.
- Refactoring Scanner, Parser, Recognition, Metadata, Naming, Classification, OrganizePlan,
  OrganizerExecutor, Task/TaskItem/Result or existing execution authorities except for the minimum
  compatible integration required by these outcomes.

## Dependencies

- Slice 26 is `PASS / CLOSED` at Base `3c660d5a1512b5b221b0284bcff9ae6dd00bbf23` and reviewed
  Implementation Head `928b727552a2fbb298e694cb0312e082e4662dda`.
- Closed Slices 23, 24 and 25 provide the current checkpoint/recovery, manual organize and
  scheduled/unattended execution foundations that this Slice must reuse.
- An immutable Active runtime and configured Storage/ResourceLibrary/MediaLibrary are prerequisites
  for the daily operations journey; first-instance setup remains Slice 26 behavior.
- Slice 28 depends on stable FileIndex, Task/Result and operational evidence contracts here; Slice 29
  depends on the completed Slice 27 and Slice 28 journeys and does not redefine them.

## Acceptance Criteria

1. With a valid Active runtime, an authenticated operator can enter real Storage-backed Files, browse
   bounded Storage-relative directories and entries, and separately inspect FileIndex records without
   confusing discovery state with Storage contents.
2. The Files/FileIndex journey preserves exact Storage/library/path and current occurrence identity,
   distinguishes discovery/stability from processing disposition, and gives a bounded explicit
   Reprocess action only when the current occurrence is eligible.
3. A file- or ResourceLibrary-scoped manual Scan is durable, bounded, cancellable and isolated;
   incomplete or failed discovery cannot fabricate Missing and Scan never performs organization.
4. A current-source or bounded-scope Preview follows the production analysis chain against one exact
   Active snapshot, persists inspectable per-item findings and blockers, and proves zero mutation,
   no implicit Provider/work/authority side effect and no mandatory review creation.
5. Manual Organize requires the exact Preview, explicit one-shot authority and confirmation, then
   executes only through OrganizerExecutor with per-item source/target/operation/effect evidence,
   attachment handling, conflict policy and capability checks.
6. Failed, waiting and partial items preserve independent durable state and expose an explicit
   recovery path. Resolved decisions can continue the original journey only after exact source,
   snapshot, capability, conflict and authority checks; uncertain effects do not auto-replay.
7. Worker registration, heartbeat, stop, readiness, owner projection and claim fencing are durable
   and visible through the required read surfaces. API health is distinct from Worker readiness, and
   stale ownership cannot overwrite a newer owner's terminal result.
8. API and Web use shared application behavior and identical permission, validation, concurrency,
   evidence, redaction and recovery semantics. Viewer/read-only users cannot mutate or execute.
9. Fresh and current database migration/restart paths preserve FileIndex, Tasks, Results,
   checkpoints, authority, automation and audit state. No Slice behavior introduces secrets,
   FFprobe/FFmpeg or `config/alist.json` into the tracked tree.
10. All required focused, integration, full-regression, safety and quality gates in Final Validation
    Expectations pass, with unavailable production services reported truthfully as
    `SKIP / UNAVAILABLE`.

## Final Validation Expectations

- Focused vertical regression from the repository root using the project environment:

```bash
.venv/bin/python -m unittest \
  tests.test_runtime_files_browser \
  tests.test_storage_browser \
  tests.test_file_index_lifecycle \
  tests.test_manual_scan \
  tests.test_manual_preview \
  tests.test_manual_organize_intent \
  tests.test_manual_organize_preview \
  tests.test_manual_organize_execution \
  tests.test_processing_recovery_admission \
  tests.test_recovery_continuation \
  tests.test_recovery_batch \
  tests.test_conflict_resolution \
  tests.test_processing_worker_readiness \
  tests.test_automation_job_fencing \
  tests.test_stale_job_visibility \
  tests.test_automation_api \
  tests.test_dashboard \
  tests.test_migration_rehearsal \
  tests.test_api_security \
  tests.test_operator_ui
```

- Related regression must remain green, including `tests.test_operator_job_submission`,
  `tests.test_operator_job_cancellation`, `tests.test_task_persistence`,
  `tests.test_file_media_detail`, `tests.test_attachments`,
  `tests.test_organizer_mutation_authority`, `tests.test_source_directory_cleanup`,
  `tests.test_recognition_review`, `tests.test_metadata_review` and
  `tests.test_classification_review`.
- Full offline validation:

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff format --check mediaflow tests
.venv/bin/ruff check mediaflow tests
.venv/bin/python -m compileall -q mediaflow tests
.venv/bin/pip check
.venv/bin/python -m mediaflow.final_cli --config config/strategy.example.json config validate
.venv/bin/python -m mediaflow.final_cli --config config/mediaflow.phase13.2.example.json config validate
git diff --check
grep -rIn "ffprobe\|ffmpeg" mediaflow tests pyproject.toml
git check-ignore -v config/alist.json
git ls-files config/alist.json
```

- Run migration/persistence checks for fresh and current databases, isolated temporary Local roots,
  fake/local SMB, OpenList and S3-compatible services, RBAC/redaction, no-mutation probes and
  installed-wheel smoke where the repository release gate requires them.
- Production SMB, OpenList, AWS S3, Cloudflare R2 and destructive Storage acceptance remain
  `SKIP / UNAVAILABLE` unless an explicitly isolated environment exists. Fakes and local services
  prove software behavior only and must not be reported as production compatibility.
- Final validation must report actual commands, totals, failures, skips and unavailable gates. No
  in-process or fake evidence may be presented as multi-process production compatibility.

## Independent Business Capability

This Slice is independently acceptable because it completes the authenticated operator's daily manual
media-operation journey from real Storage browsing and current FileIndex state through bounded Scan,
exact Preview, explicitly authorized Organize, per-item result/disposition and safe recovery, with
Worker readiness and ownership visible. It reuses the established processing and authority
foundations and leaves day-2 administration and Docker release to later Slices.

## Closure Packet

```text
Slice: 27 — Manual Operations and File Lifecycle
Base SHA: 306b77d0aad44ab0a2e233866f8972247b437a7d
Head SHA: 34365121342557b0f40eacc7ad9bbb74499cc4cb

Required Outcomes:
- RO-1 COMPLETE — real Storage-backed Files and distinct FileIndex lifecycle/disposition.
- RO-2 COMPLETE — current source occurrence, fingerprint evidence and exact Reprocess admission.
- RO-3 COMPLETE — bounded file/ResourceLibrary manual Scan with durable isolated Task state.
- RO-4 COMPLETE — exact Active-snapshot analysis-only Preview with durable per-item evidence and zero mutation.
- RO-5 COMPLETE — explicit Preview-bound manual Organize through OrganizerExecutor with authority, conflicts and effects.
- RO-6 COMPLETE — visible conflict/review/recovery continuation with independent sibling state and fail-closed uncertainty.
- RO-7 COMPLETE — durable Worker registration, readiness, ownership fencing and bounded recovery evidence.
- RO-8 COMPLETE — shared Application behavior, API/Web parity, RBAC, concurrency, audit, redaction and bounded diagnostics.

Required Surfaces:
- Operator Web COMPLETE — Files/FileIndex, Scan, Preview, Organize, Task/Result, recovery and read-only Worker evidence.
- Versioned API COMPLETE — matching bounded journeys, permissions, validation, evidence, audit and redaction.
- Application COMPLETE — shared Storage, FileIndex, Scan, Preview, Organize, recovery and Worker readiness behavior.
- Runtime Worker and task execution COMPLETE — registration, heartbeat, stop, claim and completion fencing.
- Persistence and migration COMPLETE — current/fresh state-preserving runtime schema and evidence.
- Documentation/tests COMPLETE for Slice behavior and unavailable external services.

Implemented:
- Real Storage browser and separate FileIndex/current-source lifecycle with bounded identity and disposition.
- Scoped manual Scan, exact Active-snapshot Preview and explicit one-shot manual Organize.
- Per-item conflict, review, result and recovery continuation with source/effect/authority safeguards.
- Durable processing Worker registration, readiness, heartbeat/stop lifecycle, owner projection and claim fencing.
- Shared authenticated API/Web behavior with RBAC, audit, redaction, bounded collections and recovery evidence.

Tasks completed:
- Task 27.1 — runtime Files / FileIndex split.
- Task 27.2 — current file source lifecycle.
- Task 27.3 — scoped manual Scan Tasks.
- Task 27.4 — current-source analysis Preview.
- Task 27.5 — exact manual organization.
- Task 27.6 — blocker and recovery continuation.
- Task 27.7 — Processing Worker registration, readiness and fenced ownership.

Final Tests:
- PASS — Slice vertical regression: `.venv/bin/python -m unittest tests.test_runtime_files_browser tests.test_storage_browser tests.test_file_index_lifecycle tests.test_manual_scan tests.test_manual_preview tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_processing_recovery_admission tests.test_recovery_continuation tests.test_recovery_batch tests.test_conflict_resolution tests.test_processing_worker_readiness tests.test_automation_job_fencing tests.test_stale_job_visibility tests.test_automation_api tests.test_dashboard tests.test_migration_rehearsal tests.test_api_security tests.test_operator_ui` — 322 tests, OK.
- PASS — related regression: `.venv/bin/python -m unittest tests.test_operator_job_submission tests.test_operator_job_cancellation tests.test_task_persistence tests.test_file_media_detail tests.test_attachments tests.test_organizer_mutation_authority tests.test_source_directory_cleanup tests.test_recognition_review tests.test_metadata_review tests.test_classification_review` — 80 tests, OK.
- FAIL / PRE-EXISTING / UNRELATED — `.venv/bin/python -m unittest discover -s tests` — 1273 tests, 6 failures, 7 skips. The six failures are the documented ambient `.mediaflow` configuration failures: API credentials x2, final integration x1, resource library x1 and runtime storage x2; they reproduce at the Task Base and do not touch Slice 27 Worker/manual-operations behavior.
- PASS — `.venv/bin/ruff format --check mediaflow tests`; `.venv/bin/ruff check mediaflow tests`; `.venv/bin/python -m compileall -q mediaflow tests`; `.venv/bin/pip check`; `git diff --check`.
- PASS — both canonical `final_cli ... config validate` commands.
- PASS — wheel build and isolated installed-wheel smoke via `.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w /tmp/mediaflow-slice27-wheel-20260905` and `scripts/wheel_smoke_test.py`.
- PASS — Markdown local-link check, forbidden FFprobe/FFmpeg scan, private config check and migration/backup/restore evidence.
- SKIP / UNAVAILABLE — production SMB, OpenList, AWS S3, Cloudflare R2, live TMDB and real multi-process Worker acceptance; fakes/local services and temporary Local roots were used.

Safety Evidence:
- Scanner, Parser, Recognition, Metadata, Naming, Classification and Planner remain zero-mutation; DryRun/Preview remains zero-mutation.
- OrganizerExecutor remains the sole mutating Storage authority; overwrite/delete/fallback safeguards remain explicit.
- Worker lifecycle is runtime-owned; API/Web expose read-only projections and never start, stop or supervise Workers.
- Claim completion requires Worker identity and claim token; stale/requeued owners cannot overwrite newer state.
- Active snapshot, source occurrence, authority, result and recovery evidence remain exact and bounded.
- API/Web evidence is RBAC-protected, audited, redacted and secret-free; `config/alist.json` remains ignored and untracked.

Known Non-blocking Issues:
- Six full-suite failures are pre-existing/unrelated ambient configuration failures documented above.
- Existing SQLite teardown emits non-fatal `ResourceWarning` messages.

Explicitly Deferred:
- Slice 28 day-2 administration, Slice 29 Docker/Compose production packaging, Provider switching, built-in identity, full Secret Store integration, mutation probes, distributed workers, automatic uncertain-mutation replay and other deferrals already recorded in this Contract.

Documentation Reconciliation Needed:
- A should reconcile CURRENT product, architecture, requirements, roadmap and progress statements with this factual Slice 27 closure without changing scope or safety contracts.

Decision: SLICE READY FOR A REVIEW
```

## A Final Review

```text
Reviewed Range: 306b77d0aad44ab0a2e233866f8972247b437a7d..34365121342557b0f40eacc7ad9bbb74499cc4cb
Decision: PASS
P0/P1 Blockers: NONE
Closure Reconciliation:
- Slice 27 is factually recorded as PASS / CLOSED at the reviewed Implementation Head.
- Roadmap and Progress now record Slice 27 as PASS / CLOSED and retain Slice 28 then Slice 29 as the remaining V1 order.
- Product Experience, Architecture, requirements and the Chinese product specification now record real Storage Files/FileIndex, current-source lifecycle, manual operations, recovery continuation and Worker readiness as delivered current behavior.
- Existing Storage, Active snapshot, RBAC, redaction, audit, OrganizerExecutor-only mutation and explicit deferred scope remain unchanged.
- TASK.md is NO ACTIVE IMPLEMENTATION TASK and hands selection of the next large Slice back to A.
```

## Review State

```text
Slice Status: PASS / CLOSED
Implementation Head: 34365121342557b0f40eacc7ad9bbb74499cc4cb
P0/P1 Defects: NONE FOUND
Decision: PASS / CLOSED
```
