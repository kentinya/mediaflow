# Slice 23 — Stage-Aware Per-Item Recovery

This is the A-owned Slice Contract. B and Developer may not expand or weaken it. Detailed lifecycle
rules are defined only in [`docs/development-workflow.md`](docs/development-workflow.md).

```text
Slice ID: 23
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PASS / CLOSED
Base SHA: b3083c417849e744b1b9c4629ce9ef312dd194ff
Implementation Head: 26c0450054e4b3d65d6fbf3641d61e022e9561fd
A Final Review: PASS
```

The Base is the repository HEAD immediately before this Contract was activated. `NOT SET` is the
canonical empty Implementation Head while the Slice is in development; B records the real product
Implementation Head only when preparing the Closure Packet.

## User Goal

When a batch contains waiting, failed or partial media items, an operator can open the Task, see each
item's durable processing checkpoint and known effects, understand why it stopped and which actions
are safe, then recover one item or a bounded selection without replaying successful siblings,
guessing from logs, changing pinned configuration, or gaining media-execution authority.

## Current Foundation and Gap

MediaFlow already persists Task, TaskItem, stage/status, Result, completed-operation evidence,
configuration pins, reviews, conflicts, retry requests, pause/resume state and file links. Those
facts and actions are fragmented across CLI commands and separate Web/API views. The current model
does not provide one durable Processing Checkpoint, one stage-aware allowed-action decision, or an
end-to-end Web/API recovery continuation. A generic retry request can mark an item pending, but that
alone is not complete or safe recovery evidence.

This Slice completes the bounded recovery journey over the existing Task/TaskItem/Result model. It
does not introduce a parallel task system or move Recognition, Metadata, Naming, Classification,
planning, conflict resolution or execution decisions into Task orchestration.

## Required Outcomes

| ID | Required Outcome | Initial state |
|---|---|---|
| RO-1 | Every persisted media TaskItem has a durable, restart-safe Processing Checkpoint projection that identifies its current/last durable stage, source and immutable configuration identity, plan/result linkage, completed and verified effects, explicitly uncertain effects, blocking review/conflict, error category, retry safety and currently permitted actions; unavailable legacy evidence is labelled unknown rather than inferred | NOT STARTED |
| RO-2 | Checkpoint facts remain transactionally consistent with TaskItem, Result, operation, review and conflict transitions, preserve prior evidence across recovery attempts, reject stale/concurrent decisions and provide bounded secret-free audit of who requested which recovery action | NOT STARTED |
| RO-3 | One shared stage-aware recovery decision derives only actions valid for the exact checkpoint, including applicable review/conflict resolution, re-evaluation, re-plan, safe continuation/retry, ignore, investigate or explicit refusal; a generic Retry label is never presented when safety cannot be established | NOT STARTED |
| RO-4 | An accepted recovery action creates a durable, auditable request or continuation bound to the exact TaskItem/checkpoint version, original source scope and pinned configuration; it never silently follows a newer Active configuration, treats historical destructive authority as sufficient or upgrades execute, overwrite, delete or cleanup authority | NOT STARTED |
| RO-5 | Single-item and bounded batch recovery operate independently: successful/skipped/DryRun siblings are never replayed, one item's decision cannot overwrite another, each selected item retains its own outcome/recovery, and parent/continuation summaries reconcile waiting, ignored, recovered, partial, failed and unchanged items | NOT STARTED |
| RO-6 | Authenticated API and Operator Web Task detail/batch recovery use the same application behavior, RBAC, validation and concurrency rules and expose entry, visible checkpoint/effects, allowed action, explicit confirmation, success/failure state, linked new Task/Result and a concrete next recovery action after reload | NOT STARTED |
| RO-7 | Safe continuations re-enter the existing production pipeline only at a checkpoint-supported boundary and produce a new linked Result while retaining original evidence; uncertain mutation is never automatically replayed, all analysis/selection paths are zero-mutation, and any permitted real mutation still occurs only through OrganizerExecutor after current safety and authority validation | NOT STARTED |

## Required Surfaces

- Domain Processing Checkpoint, effect-certainty and stage-aware recovery-action contracts built on
  the existing Task/TaskItem/Result identities.
- SQLite persistence, migration, optimistic concurrency, audit and queries for checkpoint/recovery
  evidence without rewriting or fabricating legacy history.
- Application services that capture stage transitions, project linked result/review/conflict facts,
  decide allowed actions, admit exact-version recovery and orchestrate bounded continuations.
- Existing review, conflict, configuration snapshot, operation-history, file-lock/fencing and
  OrganizerExecutor boundaries where recovery must validate or continue normal behavior.
- Authenticated API and Operator Web Task detail/batch summary and recovery actions using the same
  bounded application contract and explicit confirmations.
- Automated domain, persistence, migration, application, API, Web, concurrency, batch-independence,
  pinned-configuration, authority and zero-mutation regression evidence.

## Safety Invariants

- Scanner, Parser, Recognition, Metadata, Naming, Classification, Planner, checkpoint projection and
  recovery selection perform zero Storage mutation. Only OrganizerExecutor may mutate Storage.
- Successful, skipped and DryRun items are never replayed by recovery. One item cannot hide,
  overwrite or block another item's durable diagnosis or safe recovery.
- Unknown or uncertain execution effects fail closed to investigation/refusal. They are never
  labelled retry-safe, automatically replayed, or treated as proof that source/target is unchanged.
- Recovery preserves the original immutable configuration snapshot identity. A later Active
  revision cannot silently change Provider, policy, destination, operation or conflict semantics.
- A recovery request does not grant, renew or elevate execute, overwrite, delete, source-cleanup or
  rollback authority. Any real continuation must independently satisfy the execution-authority,
  Storage-capability, conflict and destructive-operation gates applicable at that moment.
- Optimistic concurrency, Task/Job fencing and Storage-relative source locks prevent stale or
  duplicate recovery from committing over newer ownership or results.
- RecognitionType C remains C when a recovered item reuses NamingPolicy or ClassificationPolicy A.
- Recovery never permits arbitrary policy IDs, MediaLibrary paths or destinations outside the
  pinned configuration and normal production policy pipeline.
- API/Web evidence, errors and audit are bounded, permission-aware and secret-free; viewing a Task
  or checkpoint creates no Task, Job, Provider request, Storage probe or mutation.
- No silent overwrite/delete or unsupported-operation fallback is introduced.

## Explicitly Deferred

The following remain V1 or later work outside this Slice and are not closure blockers:

- the broader Files/Media detail and manual-organize journey, including arbitrary multi-file manual
  policy selection and execution (planned large Slice 24);
- Metadata Provider switching;
- Automation Task Definitions and scheduled unattended real organization (planned large Slice 25);
- new cross-run compensation or historical rollback beyond the existing bounded per-invocation
  Organizer rollback contract;
- automatic replay of uncertain media mutations or recovery that silently grants execution
  authority;
- distributed Task leases, forced interruption of in-flight external calls and automatic crash
  replay;
- remote destination precheck, mutation-based capability probing and other closed-Slice 22.6
  deferrals;
- redesign of Recognition, Metadata, Naming, Classification, OrganizePlan or OrganizerExecutor
  policy ownership.

## Slice Acceptance Criteria

- [x] From an authenticated Task detail/batch summary, the operator can distinguish waiting, failed,
      partial, ignored, recovered and unchanged items and open each item's durable checkpoint without
      consulting raw SQLite, JSONL or logs.
- [x] Checkpoint evidence truthfully identifies stage, pinned configuration, linked plan/result,
      known completed/verified/uncertain effects, blocker/error, retry safety and only actions valid
      for the current version; missing legacy evidence is visibly unavailable.
- [x] A linked Recognition/Metadata/Classification review or conflict directs the operator to its
      existing resolution journey and returns with a current stage-aware continuation action rather
      than bypassing that decision.
- [x] A safe pre-mutation failure can be recovered as one item or a bounded selection and produces
      new auditable Task/TaskItem/Result linkage while successful and unselected siblings retain
      their existing TaskItem/Result records and are not processed again.
- [x] A partial or uncertain mutation shows completed/known effects and refuses unsafe replay;
      investigation remains a valid explicit outcome when no safe automatic continuation exists.
- [x] Stale checkpoint versions, duplicate/concurrent requests, changed ownership, missing pinned
      snapshots, invalid references and insufficient authority fail closed without losing the
      original item/result/recovery evidence.
- [x] API and Web expose the same checkpoint, allowed actions, confirmations, outcomes and recovery
      semantics under the same permissions; reload preserves every durable decision and link.
- [x] DryRun recovery cannot become execute, and real recovery cannot inherit historical authority;
      any permitted mutation uses the normal plan/conflict/capability checks and OrganizerExecutor.
- [x] Batch summaries reconcile item states after partial recovery, and one recovery failure never
      erases another item's success, diagnosis or next action.
- [x] RecognitionType C remains C through re-evaluation/re-plan/continuation while reusing A policies.
- [x] Explicitly Deferred capabilities remain non-claims and no unresolved in-Slice P0/P1 defect
      remains.

## Final Validation Expectations

B performs one `SLICE FINAL` validation before readiness:

- focused checkpoint/action-domain tests for every supported TaskItem stage, known/uncertain effect
  combination, allowed/refused action and legacy-evidence projection;
- SQLite migration, restart/reload, atomic checkpoint/result/review/conflict transitions,
  optimistic-concurrency, duplicate-request, rollback-on-failure and bounded-query tests;
- Application/API/Web integration for Task detail, single and bounded batch recovery, explicit
  confirmation, new Task/Result links, failure/recovery and permission parity;
- production-pipeline regressions covering pre-mutation failure, waiting review/conflict, DryRun,
  failed/partial execution, pinned configuration, missing snapshot and current authority checks;
- falsification evidence that successful/unselected siblings are not processed, uncertain effects
  are not replayed, stale workers/requests cannot commit, and viewing/request selection performs zero
  Storage/Provider/media work;
- RecognitionType C, no-silent-fallback, overwrite/delete, lock/fencing, secret/redaction and
  OrganizerExecutor-only mutation safety regressions;
- the complete offline regression suite plus Ruff lint/format, compileall, dependency check,
  configuration validation, schema-marker/migration checks, wheel build/isolated smoke, Markdown
  links, private-config/secret scan and `git diff --check`;
- explicit reporting of PASS/FAIL/SKIP/UNAVAILABLE for any external-service or destructive acceptance
  gate. No production Storage, Provider credentials or user media are required.

## Closure Packet

```text
Slice: 23 — Stage-Aware Per-Item Recovery
Base SHA: b3083c417849e744b1b9c4629ce9ef312dd194ff
Head SHA: 26c0450054e4b3d65d6fbf3641d61e022e9561fd

Required Outcomes:
- RO-1: COMPLETE
- RO-2: COMPLETE
- RO-3: COMPLETE
- RO-4: COMPLETE
- RO-5: COMPLETE
- RO-6: COMPLETE
- RO-7: COMPLETE

Required Surfaces:
- Domain checkpoint, effect-certainty and recovery-action contracts: COMPLETE
- SQLite persistence, migration, concurrency, audit and recovery queries: COMPLETE
- Application checkpoint projection, exact-version admission and bounded continuation: COMPLETE
- Existing review/conflict/configuration/operation/fencing/OrganizerExecutor boundaries: COMPLETE
- Authenticated API and Operator Web single-item/batch recovery journey: COMPLETE
- Automated acceptance, integration, concurrency and safety evidence: COMPLETE

Implemented:
- Durable stage-aware Processing Checkpoint projection with bounded effects, blockers, retry safety
  and allowed actions
- Exact-version recovery admission bound to source scope and immutable configuration, with audit and
  fail-closed concurrency/authority checks
- Analysis-only single-item continuation through the existing production pipeline with linked new
  Task/TaskItem/Result evidence
- Bounded independent batch continuation with per-child outcomes, resumable stranded admission,
  and distinct ignored/recovered/failed/partial/unchanged reconciliation
- Authenticated API and Operator Web entry, confirmation, checkpoint, outcome, linkage and recovery
  actions using shared application behavior

Tasks completed:
- 23.1 — Durable Processing Checkpoint and stage-aware recovery actions
- 23.2 — Exact-version recovery admission and audit
- 23.3 — Single-item safe recovery continuation
- 23.4 — Bounded batch recovery continuation

Final Tests:
- Focused batch recovery: 35 passed
- Related checkpoint/recovery/API/Web/migration/persistence/security suites: 131 passed
- Complete offline regression: 946 passed, 7 explicit external SMB/OpenList/S3/endurance skips
- Ruff format/check (323 files), compileall, pip check and both example configuration validations:
  passed
- Wheel build and isolated install/configuration/backup/rehearsal/restore/preflight smoke: passed;
  Runtime schema 26 and configuration schema 10 verified
- Markdown links: 123 tracked files, 36 local links, 0 broken; git diff --check: passed
- Real-service/endurance acceptance: 7 SKIP/UNAVAILABLE because dedicated isolated profiles were
  absent; destructive safety regressions passed with temporary/fake Storage and no production data

Safety Evidence:
- Recovery selection and all continuations remain DryRun-only and grant no execute, overwrite,
  delete, cleanup or historical mutation authority
- Successful/skipped/DryRun/unselected siblings are not replayed; ignored siblings reconcile
  independently; uncertain effects fail closed to investigation/refusal
- Exact checkpoint version, source-relative scope, pinned configuration, request/Job fencing and
  optimistic concurrency regressions pass
- RecognitionType C remains C while NamingPolicy A and ClassificationPolicy A are reused
- Storage mutation-call audit remains confined to OrganizerExecutor; recovery zero-mutation and
  no-silent-fallback regressions pass
- FFmpeg/FFprobe audit: 0 findings; private config remains ignored/untracked; production-code
  high-confidence secret/private-path scan: 0 findings

Known Non-blocking Issues:
- Python 3.13 emits existing unclosed-SQLite ResourceWarning messages without test failures

Explicitly Deferred:
- Broader Files/Media detail and arbitrary multi-file manual organization (Slice 24)
- Metadata Provider switching
- Automation Task Definitions and scheduled unattended real organization (Slice 25)
- Cross-run compensation or historical rollback beyond existing bounded Organizer rollback
- Automatic replay of uncertain mutation or recovery-granted execution authority
- Distributed Task leases, forced interruption and automatic crash replay
- Remote destination precheck and mutation-based capability probing
- Redesign of Recognition, Metadata, Naming, Classification, OrganizePlan or OrganizerExecutor

Documentation Reconciliation Needed:
- None; A reconciled the canonical CURRENT baseline, Product Experience, Architecture, Roadmap and
  closure ledger in the single Slice-closure checkpoint; stable requirements required no change

Decision: SLICE READY FOR A REVIEW
```

## A Final Review

```text
Reviewed Range: b3083c417849e744b1b9c4629ce9ef312dd194ff..26c0450054e4b3d65d6fbf3641d61e022e9561fd
Decision: PASS
P0/P1 Blockers: NONE
Closure Reconciliation: SLICE.md, TASK.md, Roadmap, Progress, canonical CURRENT baseline,
  Product Experience CURRENT and Architecture CURRENT reconciled once; stable requirements unchanged
```
