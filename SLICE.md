# Slice 24 — Files / Media Detail and Manual Organize

This is the A-owned Slice Contract. B and Developer may not expand or weaken it. Detailed lifecycle
rules are defined only in [`docs/development-workflow.md`](docs/development-workflow.md).

```text
Slice ID: 24
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PASS / CLOSED
Base SHA: 4ff5479d9f4a81906ee52a9f784931b65cd9ab90
Implementation Head: d2e399803078317f2092d895eae627327998de2f
A Final Review: PASS / CLOSED — 2026-09-01
```

The Base is the repository HEAD immediately before this Contract was activated. `NOT SET` is the
canonical empty Implementation Head while the Slice is in development; B records the real product
Implementation Head only when preparing the Closure Packet.

## User Goal

From Files, a Task, a review or prior history, an operator can open one coherent File/Media detail,
understand what MediaFlow knows and why, select one file or a bounded set for manual organization,
review an exact zero-mutation Preview, resolve item-specific blockers, explicitly authorize only
that reviewed work, and see durable per-item success, failure and checkpoint-aware recovery without
constructing plans, paths or Storage calls by hand.

## Current Foundation and Gap

MediaFlow already has a bounded FileIndex catalog, latest-Result and review links, manual recognition
and metadata/classification decisions, managed immutable configuration snapshots, the complete
analysis/planning pipeline, conflict decisions, attachment planning, one-time execution authority,
OrganizerExecutor, operation evidence and Slice 23 Processing Checkpoints. It also has broad CLI
batch Preview/organize entry points.

Those pieces do not yet form the promised Files/Media journey. File detail currently projects mainly
FileIndex fields, one latest Result and review links; the operator cannot see one bounded explanation
of parse, recognition, media identity, policies, plan, history, effects and current actions. Existing
real organize admission is not scoped to the exact file selection and exact Preview the operator just
reviewed. This Slice joins and completes those existing authorities rather than creating a second
pipeline, a second Task system or a free-form plan editor.

Within this Slice, “Media detail” means the resolved media identity and decision/history evidence
linked to an indexed file and its durable work. It does not introduce a playback catalog or a new
media-server entity whose existence is required by the processing pipeline.

## Required Outcomes

| ID | Required Outcome | Initial state |
|---|---|---|
| RO-1 | An authenticated operator can reach one bounded, reload-stable File/Media detail from Files, TaskItems, reviews, conflicts and Results and see source/library and scan/stability state, parser evidence, RecognitionType/rule explanation, normalized Metadata identity/matcher evidence, selected policy identities, destination/operation/attachments/conflicts, Processing Checkpoint, prior Results/operation effects/errors and only currently valid next actions; unavailable legacy evidence is labelled unavailable or unknown rather than inferred | NOT STARTED |
| RO-2 | From File detail or a bounded Files selection, the operator can create durable manual-organize work bound to the exact indexed source identities and one immutable runtime configuration snapshot, then keep the configured defaults or choose only enabled, compatible RecognitionType, Metadata identity and Naming/Classification/Organize policy options available under that snapshot; choices are validated, versioned and audited and never edit Active configuration or accept arbitrary paths, operations or provider payloads | NOT STARTED |
| RO-3 | Single-item and bounded batch manual Preview run the existing Scan/Parse/Recognition/Metadata/Naming/Classification/OrganizePlan behavior as applicable and persist a reloadable exact plan for every selected item, including source, identity and explanations, policy ownership, destination, operation, attachments, Storage capability verdicts, conflicts, warnings and zero-mutation execution state; each item has its own preview status and failure/recovery action | NOT STARTED |
| RO-4 | Pending recognition/metadata/classification reviews and conflicts are linked to their existing shared resolution behavior and block execution only for the affected item; resolving or changing an identity, policy, source fact, configuration authority, conflict decision or plan-affecting input invalidates stale Preview/authorization evidence and requires a fresh exact Preview instead of silently carrying an old decision forward | NOT STARTED |
| RO-5 | The operator can explicitly authorize real execution only for the exact current reviewed single-item or bounded batch plans; admission is one-shot, permission-checked, scope- and plan-bound, rejects stale/changed/duplicate/concurrent work, revalidates current Storage capability, conflict and destructive-operation authority, and performs any permitted mutation only through OrganizerExecutor with no silent overwrite/delete or operation fallback | NOT STARTED |
| RO-6 | Manual work persists independently reconcilable per-item state, Result, plan and completed/verified/uncertain operation evidence and updates or links the File view to the durable source/target outcome; success, skipped, ignored, blocked, failed, partial, unchanged and unselected items are not merged or allowed to hide or replay one another, and post-failure recovery reuses the Slice 23 checkpoint/action model without automatically replaying uncertain mutation | NOT STARTED |
| RO-7 | Versioned API and Operator Web use the same application services, RBAC, validation, optimistic concurrency, audit, plan/authority binding and safety decisions for detail, selection, Preview, blocker resolution, execution, result and recovery; entry, visible state, confirmation, success, failure and next action remain available after reload and all collection/evidence responses are bounded, deterministic, permission-aware and secret-free | NOT STARTED |

## Required Surfaces

- A bounded File/Media detail and history/explanation read model over FileIndex, configuration
  identity, TaskItem/Processing Checkpoint, Result, review/conflict and operation evidence.
- Durable manual-organize intent, selected-item, choice, Preview/plan, invalidation, authorization,
  execution and audit contracts with optimistic concurrency and restart-safe SQLite persistence.
- Shared application services for exact source/configuration admission, permitted manual choices,
  single/bounded-batch Preview, stale evidence invalidation and exact-plan execution admission.
- Existing Parser, Recognition, Metadata, Naming, Classification, attachment, duplicate/conflict,
  Storage capability, source lock/fencing, execution-authority and OrganizerExecutor boundaries.
- Authenticated versioned API and Operator Web Files/detail/manual-organize/result/recovery surfaces,
  including cross-links from Tasks, reviews, conflicts and history and explicit confirmations.
- Automated domain, persistence/migration, application, API, Web, RBAC, concurrency, batch-
  independence, zero-mutation and real-execution safety evidence.

## Safety Invariants

- Scanner, Parser, Recognition, Metadata, Naming, Classification, Planner, detail projection, manual
  selection and Preview perform zero Storage mutation. Only OrganizerExecutor may mutate Storage.
- Opening or refreshing Files/detail/history creates no Task, Job, manual work, Provider request,
  Storage probe, authorization or mutation. Preview may perform only the bounded reads required by
  the normal analysis/conflict/capability pipeline and remains DryRun.
- The source scope comes from current indexed/configured Storage-relative identities. API/Web input
  cannot inject an arbitrary source, destination root, target path, transfer command or adapter call.
- Manual policy and identity choices must reference enabled compatible objects in the pinned
  immutable snapshot and remain explicit per-item overrides; they never mutate Active configuration
  or silently switch Provider/policy semantics.
- RecognitionType C remains C even when the operator or its RecognitionTypePolicy selects Naming,
  Classification or Organize policy A.
- Preview never grants execution authority. Real execution requires a separate current explicit
  permission and one-shot authority bound to the exact selected item set, configuration identity and
  reviewed plan content.
- Any change or missing evidence in source identity/facts, snapshot, selected identity/policies,
  plan, attachments, conflict decisions, destination state or authority fails closed or requires a
  fresh Preview; execution never silently replans around the reviewed result.
- Manual and Overwrite conflicts remain blocked until a valid explicit decision. Overwrite, delete,
  source cleanup and rollback require their independent configured and user authority and are never
  implied by manual organize or a prior authorization.
- Unsupported Move/Copy/HardLink/SoftLink operations fail explicitly. No operation is silently
  downgraded or substituted.
- Source locks, optimistic versions, Job/Task fencing and one-shot admission prevent duplicate or
  concurrent execution. Successful/skipped/unselected items are not replayed by another item or a
  batch recovery.
- Known completed effects survive every failure. Unknown or uncertain mutation stops for
  investigation and is never described as retry-safe or automatically replayed.
- API/Web paths, explanations, errors and audits are bounded, permission-aware and secret-free;
  credentials, tokens, authorization headers and private configuration are never persisted in plan
  evidence or returned to the operator.

## Explicitly Deferred

The following remain V1 or later work outside this Slice and are not closure blockers:

- Metadata Provider switching and managed Provider credential/configuration lifecycle; manual
  identity choices in this Slice remain within Providers permitted by the pinned snapshot;
- Automation Task Definitions, schedules and persistent unattended real-execution grants (planned
  large Slice 25);
- automatic replay of uncertain mutation, universal cross-run compensation or historical/crash
  rollback beyond the existing bounded OrganizerExecutor rollback and Slice 23 investigation path;
- distributed Task leases, forced interruption of in-flight external calls and automatic crash
  replay;
- guided remote-Storage setup, mutation-based capability probes and remote destination prechecks
  previously deferred by Slice 22.6; normal configured adapters must still honor declared
  capabilities during Preview and execution;
- unbounded whole-library selection and free-form plan/path/operation/Provider payload editors;
- a standalone playback/media-server catalog, media streaming, multi-version/upgrade management,
  media-server refresh, and generation or download of posters, artwork or NFO files;
- redesign of Recognition, Metadata, Naming, Classification, OrganizePlan, Task/Result or
  OrganizerExecutor policy ownership.

## Slice Acceptance Criteria

- [x] From Files or a link on a TaskItem, review, conflict or Result, an authenticated operator can
      open the current File/Media detail and answer what the file is, why each material decision was
      made, what happened, what evidence is unavailable and which safe action is valid next without
      joining database records or reading raw logs.
- [x] File browsing and detail remain side-effect free, bounded and permission-aware; missing/stale
      links return to current durable state or an explicit unavailable explanation.
- [x] The operator can start manual work for one indexed file or a bounded selected set, sees the
      pinned immutable configuration identity, and may select only compatible configured
      RecognitionType, Metadata identity and policy options without editing Active configuration or
      supplying an arbitrary Storage path/operation.
- [x] A manual Preview persists and reloads the complete per-item zero-mutation plan and explanations,
      including destination, operation, attachments, capability verdicts, conflicts and warnings;
      one item's failure or blocker does not erase another item's Preview or recovery.
- [x] Outstanding reviews/conflicts are navigable and block only affected execution; a decision or
      any other plan-affecting change makes prior Preview/authorization visibly stale and cannot be
      bypassed.
- [x] Explicit execution consumes separate one-shot authority for only the exact current reviewed
      plan set; stale versions, altered source/destination, duplicate admission, missing capability,
      unresolved conflict or insufficient destructive authority fail before unsafe mutation.
- [x] Every permitted real mutation passes through OrganizerExecutor, executes the reviewed plan at
      most once, verifies source/target effects and records operation history and a durable Result.
- [x] A bounded mixed batch reports Previewed/blocked/skipped/ignored/success/failed/partial/
      unchanged/unselected outcomes independently; successful or unselected siblings are not
      replayed, and summaries do not merge ignored into unchanged or conceal item recovery.
- [x] Pre-mutation failure provides a correctable input or fresh-Preview action. Partial/uncertain
      execution shows known effects and links to the current Processing Checkpoint and only its
      permitted investigation/recovery actions.
- [x] API and Web expose the same state, choices, confirmations, results, errors and recovery under
      the same permissions/concurrency rules, and reload preserves every durable decision and link.
- [x] RecognitionType C remains C throughout manual selection, Preview, conflict resolution,
      execution and Result persistence while reusing A downstream policies.
- [x] Explicitly Deferred capabilities remain non-claims and no unresolved in-Slice P0/P1 defect
      remains.

## Final Validation Expectations

B performs one `SLICE FINAL` validation before readiness:

- focused File/Media explanation tests for captured and legacy-unavailable parse, recognition,
  metadata, policy, plan, review/conflict, checkpoint, Result, operation and history evidence;
- SQLite migration, restart/reload, exact-version update, stale Preview invalidation, one-shot
  authority consumption, duplicate/concurrent admission, transaction rollback and bounded-query
  tests;
- Application/API/Web integration for single and bounded Files selection, permitted manual choices,
  exact-snapshot Preview, blocker navigation/resolution, explicit execution, durable result/history
  and checkpoint-aware recovery;
- isolated real-execution tests using temporary Local roots plus fake/in-memory SMB, OpenList and
  S3/R2 adapters as needed, covering Move/Copy/HardLink/SoftLink capability handling, attachments,
  collisions, Skip/Rename/Manual/authorized Overwrite, source cleanup and injected partial failure;
- falsification evidence that browse/detail/selection are side-effect free, Preview performs zero
  mutation, changed source/snapshot/plan/conflict/authority cannot execute, plans are not silently
  rebuilt, and one batch item never replays or hides another;
- RecognitionType C, OrganizerExecutor-only mutation, no-silent-fallback, overwrite/delete/cleanup,
  lock/fencing, redaction/private-config and exact-plan/one-shot-authority safety regressions;
- the complete offline regression suite plus Ruff lint/format, compileall, dependency check,
  configuration validation, schema-marker/migration checks, wheel build/isolated smoke, Markdown
  links, private-config/secret scan and `git diff --check`;
- explicit reporting of PASS/FAIL/SKIP/UNAVAILABLE for external SMB/OpenList/S3/R2 or destructive
  acceptance gates. No production Storage, Provider credentials or user media are required.

## Closure Packet

```text
Slice: 24 — Files / Media detail and Manual Organize
Base SHA: 4ff5479d9f4a81906ee52a9f784931b65cd9ab90
Head SHA: d2e399803078317f2092d895eae627327998de2f

Required Outcomes:
- RO-1: COMPLETE
- RO-2: COMPLETE
- RO-3: COMPLETE
- RO-4: COMPLETE
- RO-5: COMPLETE
- RO-6: COMPLETE
- RO-7: COMPLETE

Required Surfaces:
- Bounded File/Media detail and history/explanation read model: COMPLETE
- Durable manual-organize intent, selection, choice, Preview, invalidation,
  authorization, execution and audit contracts with restart-safe SQLite persistence: COMPLETE
- Shared exact-source/configuration admission, permitted-choice, Preview and exact-plan execution
  application services: COMPLETE
- Existing Parser, Recognition, Metadata, Naming, Classification, attachment, conflict,
  capability, source-lock/fencing and OrganizerExecutor boundaries: COMPLETE
- Authenticated versioned API and Operator Web Files/detail/manual-organize/result/recovery
  journey with explicit confirmations and cross-links: COMPLETE
- Automated domain, persistence, application, API, Web, RBAC, concurrency, batch-independence,
  zero-mutation and safety evidence: COMPLETE

Implemented:
- Bounded reload-stable File/Media detail with captured pipeline explanations, unavailable legacy
  evidence labels, related reviews/conflicts, TaskItem checkpoints, Results, effects and actions
- Durable manual intent with immutable Managed Runtime snapshot, exact source identity, normalized
  compatible choices, optimistic versions and audit
- Single and bounded batch exact Preview with independent outcomes, complete persisted plans,
  capability/conflict evidence, stale invalidation and zero Storage mutation
- One-shot exact-plan authorization and atomic admission bound to Preview, source, choices,
  snapshot, plan, capability, conflict, destructive authority and selected item scope
- OrganizerExecutor-only real Move/Copy/HardLink/SoftLink execution with attachments, collision
  handling, explicit overwrite/source-cleanup authority, source fencing and verified effects
- Durable per-item Task/TaskItem/Result/effect/checkpoint outcomes for success, skipped, failed,
  partial and uncertain work, including explicit investigation-only interrupted execution
  reconciliation without automatic replay
- Shared authenticated API and Operator Web confirmation, execution, reload and recovery views
- One shared secret-free Result boundary: every task_results write route and the single row
  reconstruction path apply the shared redaction rule, and File/Media `latestResult` and `results[]`
  pass through one shape-preserving recursive projection
- RecognitionType C preserved through Preview, admission, execution and Result while downstream A
  policy ownership remains visible

Tasks completed:
- 24.1 — Bounded File/Media detail, evidence and cross-links
- 24.2 — Durable manual organize intent and compatible choices
- 24.3 — Exact manual Preview and stale-evidence invalidation
- 24.4 — Exact reviewed manual execution, durable Results and recovery
- 24.5 — Reload-discoverable exact execution and complete secret-free outcomes
- 24.6 — End-to-end secret-free Pipeline Evidence correction
- 24.7 — Secret-free File/Media Result history (A 2026-09-01 FIX REQUIRED correction)

Final Tests (re-run by B at this Head):
- `.venv/bin/python -m unittest tests.test_file_media_detail tests.test_file_catalog_api`:
  PASS, 19 tests
- Directly affected detail/catalog/API/Web/persistence/checkpoint/security/manual-execution
  regression: PASS, 112 tests
- `.venv/bin/python -m unittest discover -s tests`: PASS, 1005 tests, 7 explicit skips
- `.venv/bin/ruff format --check .`: PASS, 338 files already formatted
- `.venv/bin/ruff check .`, `compileall`, `pip check`, both configuration validation commands,
  FFmpeg/FFprobe scan, `git diff --check` and `config/alist.json` ignored/untracked checks: PASS
- Wheel build with `pip wheel --no-deps --no-build-isolation` and isolated
  `scripts/wheel_smoke_test.py`: PASS; runtime schema 27, backup/rehearsal/restore/verify/preflight
  all passed
- Real SMB/OpenList/S3/R2 and endurance acceptance: SKIP/UNAVAILABLE. All 7 skips are the
  environment-gated external gates (`BLOCKED: dedicated real OpenList/SMB/S3 environment ...` and
  the four absent isolated endurance profiles). No production Storage, Provider credentials or user
  media were used.
- Markdown/local-link check: no dedicated repository checker is present; changed Markdown passed
  `git diff --check` and link targets were reviewed in the Task/doc diffs.

Safety Evidence:
- Files browsing, detail, selection and Preview are side-effect free; Preview never calls
  OrganizerExecutor and performs zero Storage mutation
- Every real mutation is routed through OrganizerExecutor; unsupported operations never silently
  fall back, and overwrite/delete/source cleanup require explicit reviewed authority
- SQLite `BEGIN IMMEDIATE` admission atomically consumes one-shot authority, creates the exact
  Task scope and acquires source/target/attachment fences; stale, duplicate and concurrent work
  fails closed before mutation
- Per-item batch state, Result, effects and checkpoint evidence remain independent; successful,
  skipped, ignored and unselected siblings are not replayed or concealed
- Partial/uncertain and interrupted publication states are durable, investigation-only and never
  automatically replayed; reconciliation releases fences without invoking mutation
- Configuration identity/digest, source identity, choice, plan, conflict and capability changes
  invalidate or reject stale execution evidence
- RecognitionType C remains C with downstream Naming/Classification/Organize policy A visible;
  shared Pipeline Evidence and manual-organize records recursively redact complete credential
  values at construction, persistence and read-projection boundaries; newly written SQLite bytes
  contain no fake credential and historical unsafe rows are redacted without rewrite;
  `config/alist.json` remains ignored/untracked/unstaged
- The A 2026-09-01 P1 is closed and independently reproduced by B: a historical `task_results` row
  seeded by raw SQL with A's exact `Authorization: Bearer slice24-final-review-secret` (plus
  `password=`, `Authorization: Basic` and `cookie=` forms in title, completed operations, uncertain
  effects and destination path) returns HTTP 200 from an authenticated `GET /api/v1/files/<id>` with
  `Authorization: [redacted]` in both `latestResult.error` and `results[0].error` and no secret
  substring anywhere in the document; the row is byte-identical before and after the read, all three
  Result write routes redact before binding so no fake credential reaches new SQLite bytes, and
  Result status, source/destination linkage, policy identities and RecognitionType C are unchanged

Known Non-blocking Issues:
- P3: the shared credential rule matches keyword-plus-separator text, so a legitimate title such as
  `The Secret: Dare to Dream` renders as `The Secret: [redacted] to Dream` in Result title/history
  display. This is inherent to the shared rule already accepted for Pipeline Evidence in 24.5/24.6,
  and tuning it would be a broad secret-rule change rather than a Slice 24 outcome.
- P3: Task-surface path identity stays exact by design, so `GET /api/v1/tasks/<id>` item/result
  `source_path`/`destination_path` and File detail `items[].sourcePath` echo a credential-shaped
  substring embedded in a media path verbatim (Result error/title/effect text is redacted
  everywhere). Keeping stored source/destination identity exact is required by the Contract and was
  an explicit Task 24.7 non-goal; the indexed file path is itself the identity of the detail
  document. Flagged for A's judgement rather than changed by B.
- Python 3.13 emits existing unclosed-SQLite `ResourceWarning` messages without test failures
- External real-service and endurance acceptance is unavailable in this offline environment

Explicitly Deferred:
- Keep the Explicitly Deferred list in this Contract unchanged: Provider switching, scheduled
  unattended real organization, automatic replay/crash replay, distributed leases, remote setup
  and probing, universal compensation/historical rollback and other deferred capabilities

Documentation Reconciliation Needed:
- A should reconcile authoritative CURRENT product/architecture/roadmap documentation and the
  final closure ledger after review; no Slice Contract or stable requirement change is requested

Decision: SLICE READY FOR A REVIEW
```

## A Final Review

```text
Reviewed Range: 4ff5479d9f4a81906ee52a9f784931b65cd9ab90..d2e399803078317f2092d895eae627327998de2f
Decision: PASS / CLOSED
P0/P1 Blockers:
- None. All Slice 24 Required Outcomes and Required Surfaces are complete; the P1 identified in
  the 2026-09-01 review was closed by Task 24.7 and independently reproduced at the reviewed Head.

Closure Reconciliation:
- Slice 24 is closed at Implementation Head
  `d2e399803078317f2092d895eae627327998de2f`; Task 24.7 is B-PASS and no implementation Task is
  active.
- `docs/roadmap.md`, `docs/progress.md`, `docs/product-experience.md`, `docs/architecture.md` and
  the canonical requirements document now describe the bounded Files/Media detail and exact manual
  Preview-to-execution journey as CURRENT, while retaining Provider switching, scheduled unattended
  real organization, automatic uncertain/crash replay, universal rollback and other deferred work.
- Result errors, titles, path-like display values and effect text are secret-free at the persisted
  Result write/reload and authenticated File/Media projection boundaries; exact stored source and
  destination identities remain unchanged for FileIndex, plan and recovery linkage.
- Bounded browsing/detail/Preview remain read-only, real mutation remains OrganizerExecutor-only,
  destructive operations and fallback require explicit authority, RecognitionType C remains C, and
  `config/alist.json` remains ignored and untracked.
- The two Closure Packet P3 observations remain non-blocking: shared keyword redaction can
  over-redact natural titles, and exact Task/path identities can contain credential-shaped filename
  text by contract. Neither is a P0/P1 defect in the closed Slice journey.
```
