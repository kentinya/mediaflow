# Slice 24 — Files / Media Detail and Manual Organize

This is the A-owned Slice Contract. B and Developer may not expand or weaken it. Detailed lifecycle
rules are defined only in [`docs/development-workflow.md`](docs/development-workflow.md).

```text
Slice ID: 24
Owner: A — Slice Owner / Architect / Final Reviewer
Status: ACTIVE
Base SHA: 4ff5479d9f4a81906ee52a9f784931b65cd9ab90
Implementation Head: NOT SET
A Final Review: NOT STARTED
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

- [ ] From Files or a link on a TaskItem, review, conflict or Result, an authenticated operator can
      open the current File/Media detail and answer what the file is, why each material decision was
      made, what happened, what evidence is unavailable and which safe action is valid next without
      joining database records or reading raw logs.
- [ ] File browsing and detail remain side-effect free, bounded and permission-aware; missing/stale
      links return to current durable state or an explicit unavailable explanation.
- [ ] The operator can start manual work for one indexed file or a bounded selected set, sees the
      pinned immutable configuration identity, and may select only compatible configured
      RecognitionType, Metadata identity and policy options without editing Active configuration or
      supplying an arbitrary Storage path/operation.
- [ ] A manual Preview persists and reloads the complete per-item zero-mutation plan and explanations,
      including destination, operation, attachments, capability verdicts, conflicts and warnings;
      one item's failure or blocker does not erase another item's Preview or recovery.
- [ ] Outstanding reviews/conflicts are navigable and block only affected execution; a decision or
      any other plan-affecting change makes prior Preview/authorization visibly stale and cannot be
      bypassed.
- [ ] Explicit execution consumes separate one-shot authority for only the exact current reviewed
      plan set; stale versions, altered source/destination, duplicate admission, missing capability,
      unresolved conflict or insufficient destructive authority fail before unsafe mutation.
- [ ] Every permitted real mutation passes through OrganizerExecutor, executes the reviewed plan at
      most once, verifies source/target effects and records operation history and a durable Result.
- [ ] A bounded mixed batch reports Previewed/blocked/skipped/ignored/success/failed/partial/
      unchanged/unselected outcomes independently; successful or unselected siblings are not
      replayed, and summaries do not merge ignored into unchanged or conceal item recovery.
- [ ] Pre-mutation failure provides a correctable input or fresh-Preview action. Partial/uncertain
      execution shows known effects and links to the current Processing Checkpoint and only its
      permitted investigation/recovery actions.
- [ ] API and Web expose the same state, choices, confirmations, results, errors and recovery under
      the same permissions/concurrency rules, and reload preserves every durable decision and link.
- [ ] RecognitionType C remains C throughout manual selection, Preview, conflict resolution,
      execution and Result persistence while reusing A downstream policies.
- [ ] Explicitly Deferred capabilities remain non-claims and no unresolved in-Slice P0/P1 defect
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
PENDING — B writes the Slice Closure Packet only after every Required Outcome is complete and the
Slice-level final validation has run.
```

## A Final Review

```text
NOT STARTED — A reviews Base..Implementation Head only after B submits the Closure Packet and marks
the Slice READY FOR A REVIEW.
```
