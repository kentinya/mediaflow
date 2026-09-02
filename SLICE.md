# Slice 25 — Scheduled Automation and Unattended Organization

This is the A-owned Slice Contract. B and Developer may not expand or weaken it. Detailed lifecycle
rules are defined only in [`docs/development-workflow.md`](docs/development-workflow.md).

```text
Slice ID: 25
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PASS / CLOSED
Base SHA: 2cee7cc756b90618f14d5d7b112f974fb445a580
Implementation Head: d4da92879b99f1c44ddd717fba1a26e4b0a73493
A Final Review: PASS / CLOSED — 2026-09-02
```

The Base is the repository HEAD immediately before this Contract was activated. `NOT SET` is the
canonical empty Implementation Head while the Slice is in development; B records the real product
Implementation Head only when preparing the Closure Packet.

## User Goal

From one Automation Web journey, an authenticated operator can create and safely enable a durable
Automation Task Definition for one configured ResourceLibrary and bounded source scope, validate and
Preview exactly what it may do, separately grant or revoke narrowly scoped unattended execution,
and then inspect every scheduled occurrence, Task, media item, Result and recovery action. A valid
due run may organize without another per-run click, but it must use the normal RecognitionType-
selected policy chain and must fail closed before any unauthorized or unsafe mutation.

## Current Foundation and Gap

MediaFlow already has immutable managed runtime snapshots, interval/Cron and timezone evaluation,
atomic idempotent scan/preview schedule emission, AutomationJob capacity and audit, Worker claim
fencing/cancellation/heartbeat, the existing Task/TaskItem/Result pipeline, stage-aware per-item
recovery, one-shot manual/remote execution authorities, exact manual Preview/execution and
OrganizerExecutor-only mutation.

Current schedule definitions are configuration-authored, read-only in the Operator Web and limited
to `scan` or `preview`. They are not the long-lived operator-managed Automation Task Definition
promised by V1: they have no bounded ResourceLibrary/source-scope contract, no exact-definition
validation and Preview journey, no independently revocable persistent unattended grant, and no
safe route from a due occurrence to real organization. The existing remote `organize` Job consumes
a one-time token and is not scheduled authority.

This Slice completes that missing vertical journey by extending the existing Scheduler, Job,
Worker, Task, policy, planning, execution and recovery authorities. It must not create a parallel
media pipeline, a second Task/Result lifecycle, a Scheduler-owned policy decision or a free-form
path/plan editor.

## Required Outcomes

| ID | Required Outcome | Initial state |
|---|---|---|
| RO-1 | An authenticated operator can use managed Web/API surfaces to create, copy, edit, enable, disable and inspect a versioned Automation Task Definition with stable identity, name, one enabled ResourceLibrary, optional safe Storage-relative sub-scope, scan-only/scan-and-plan/automatic-organization mode, interval or Cron/timezone schedule and bounded per-run limits; validation, references, optimistic concurrency and secret-free Before/After audit use the existing managed configuration authority, and no edit silently changes the immutable Active snapshot | NOT STARTED |
| RO-2 | Before unattended mutation can be enabled, the operator can validate/test and run an exact-definition, exact-snapshot Preview/DryRun that exposes bounded source scope, current configuration identity, referenced RecognitionTypePolicy ownership, discovered/permitted items, decisions, destinations, operations, attachments, capabilities, conflicts, warnings and per-item blockers; evidence is reloadable, zero-mutation and becomes visibly stale after any plan-, definition-, scope- or snapshot-affecting change | NOT STARTED |
| RO-3 | At each due occurrence, Scheduler resolves one exact enabled definition from the same current immutable Active configuration authority, atomically emits at most one bounded AutomationJob for that definition and occurrence, pins the exact definition/configuration identity, respects capacity and restart/concurrency semantics, and advances due state only with durable Job/audit publication; Scheduler performs no scan, Provider, policy, plan, Storage or mutation work | NOT STARTED |
| RO-4 | A claimed occurrence reuses the existing Worker and Task/TaskItem/Result chain for only its configured ResourceLibrary/sub-scope and mode; every selected item follows Scan → Parse → Recognition → RecognitionType → RecognitionTypePolicy → Metadata → Naming → Classification → OrganizePlan/Preview and, only when authorized, OrganizerExecutor → Result/Log, so different RecognitionTypes may select different configured Providers, MediaLibraries, destinations and operations without copying those decisions into the Automation definition | NOT STARTED |
| RO-5 | Automatic organization requires a separate explicit, persistent, revocable unattended execution grant bound to one exact Automation Task Definition identity/version, ResourceLibrary/sub-scope, allowed run mode and bounded workload; grant/revoke/widening decisions are permission-checked and audited, widening or material change cannot inherit an older grant, manual/remote one-shot authority remains separate, and current grant plus scope is revalidated before every not-yet-performed mutation | NOT STARTED |
| RO-6 | Missing or changed definition/configuration/reference, invalid scope, unstable source, Provider or Storage failure, unresolved recognition/metadata/classification/conflict, unsupported capability, revoked/mismatched authority, destructive-operation denial, duplicate/concurrent occurrence or cancellation fails closed at the affected boundary and leaves durable per-item state, known/uncertain effects, retry safety and one explicit safe next action; successful, skipped, ignored, blocked, failed, partial, unchanged and unselected siblings remain independently visible and are never replayed or concealed | NOT STARTED |
| RO-7 | The authenticated Automation Web view and versioned API use the same application services, RBAC, validation, state transitions, audit, snapshot/definition pinning, authority and safety rules; after reload the operator can see definition and grant state, next run, last/current occurrences, exact configuration used, linked Job/Task/TaskItems/Results, per-item outcomes and recovery, and can independently disable future scheduling or revoke not-yet-used mutation authority without rewriting completed history | NOT STARTED |

## Required Surfaces

- Managed Automation Task Definition configuration contracts covering stable identity, enabled
  state, configured ResourceLibrary and safe relative sub-scope, run mode, interval/Cron/timezone,
  bounds, references, validation, optimistic version and audit without embedding per-file policy,
  Provider, destination or operation choices.
- Durable exact-definition validation/Preview evidence and a persistent unattended-grant lifecycle
  with scope/version binding, grant/revoke audit, stale/invalidation semantics and restart-safe
  SQLite persistence/migrations.
- Shared application services for Automation definition management, exact Preview, grant/revoke,
  due-occurrence admission, live scope/authority validation, execution handoff and bounded linked
  history/recovery projection.
- The existing immutable configuration resolver, interval/Cron Scheduler, AutomationJob admission,
  Worker claim/fencing/cancellation, Task/TaskItem/Result/Log, Processing Checkpoint and batch-
  independence boundaries.
- The existing Scanner, Parser, Recognition, Metadata, Naming, Classification, attachment,
  duplicate/conflict, Storage capability, source/path lock, OrganizePlan and OrganizerExecutor
  authorities, with no Scheduler-specific policy or mutation path.
- Authenticated versioned API and Operator Web Automation list/detail/edit/validate/Preview/grant/
  revoke/run-history/result/recovery surfaces with explicit confirmations and cross-links.
- Automated domain, persistence/migration, application, Scheduler/Worker, API, Web, RBAC,
  concurrency, batch-independence, zero-mutation and real-execution safety evidence.

## Safety Invariants

- Scanner, Parser, Recognition, Metadata, Naming, Classification and Planner remain zero-mutation.
  Automation definition reads/edits, validation/test, Preview, Scheduler evaluation/emission and
  history/detail projection also perform zero Storage mutation. Only OrganizerExecutor may mutate
  Storage.
- Opening or refreshing Automation/detail/history creates no Job, Task, Provider request, Storage
  probe, grant or mutation. Every write action is explicit, permission-checked, version-bound and
  audited.
- Active configuration is the exact immutable snapshot consumed at a Job's creation boundary. Each
  emitted Job pins both configuration and Automation-definition identity; a later Draft edit or
  activation affects only later occurrences and never rewrites queued/running semantics.
- Scheduler decides only which enabled definition is due and emits one durable occurrence. It never
  selects a Provider, policy, MediaLibrary, path or operation, never invokes the pipeline, and never
  calls Storage.
- Automation source scope comes only from one enabled configured ResourceLibrary plus a normalized
  bounded Storage-relative sub-scope. API/Web input cannot inject an arbitrary Storage root, host
  path, destination, OrganizePlan, transfer command or adapter call.
- Automation definitions never own per-file Metadata, Naming, Classification, destination or
  Organize decisions. RecognitionTypePolicy retains that ownership, and RecognitionType C remains C
  when downstream A policies are reused.
- Preview is equivalent analysis evidence and never grants execution authority. Definitions default
  disabled or without unattended mutation authority; enabling scheduling and granting unattended
  execution are distinct explicit decisions.
- A persistent unattended grant is live, independently revocable and no broader than its exact
  definition/version/source/run bounds. A scope-widening or material definition change invalidates
  it. The live grant, current permission and exact plan scope are rechecked before each
  not-yet-performed mutation.
- An unattended grant does not imply Overwrite, Delete, MOVE source removal, source-directory
  cleanup, rollback, operation fallback or access outside scope. Each remains denied by default and
  requires its independent configured and system authority.
- Manual/Overwrite conflicts and recognition/metadata/classification reviews block only affected
  items until resolved. Resolution or any plan-affecting change requires fresh valid evidence; the
  runtime never silently replans around the pinned/reviewed facts to obtain execution authority.
- Unsupported Move/Copy/HardLink/SoftLink operations fail explicitly. No adapter, Scheduler, Worker
  or recovery path silently substitutes another operation.
- Due-occurrence idempotency, queue capacity, claim fencing, source/path locks, optimistic versions
  and bounded run limits prevent duplicate or concurrent execution. Disable prevents future
  occurrences; cancellation/revocation stops future safe boundaries but never claims to interrupt an
  in-flight external call or erase a completed effect.
- Per-item results and checkpoints remain independent. Known completed effects survive failure;
  uncertain mutation stops for investigation and is never automatically replayed. Successful,
  skipped, ignored and unselected siblings are not replayed by retry/recovery.
- API/Web state, explanations, errors, audit and persistence are bounded, deterministic,
  permission-aware and secret-free. Credentials, tokens, authorization headers, private endpoints
  and private configuration values never enter definition, grant, Preview, Job, Result or Log
  evidence; `config/alist.json` remains ignored, untracked and unstaged.

## Explicitly Deferred

The following remain V1 or later work outside this Slice and are not closure blockers:

- managed Metadata Provider switching and Provider credential/configuration lifecycle; scheduled
  work uses the Provider selected by each MetadataPolicy in its pinned snapshot, and unavailable
  Providers fail closed rather than silently switching;
- scheduled cache cleanup, scheduled log cleanup and the broader managed System Settings object
  journey; this Slice covers ResourceLibrary media scan/plan/organization definitions only;
- guided remote-Storage setup, mutation-based capability probes and remote destination prechecks;
  already configured adapters must still honor their declared capabilities and the normal pipeline;
- automatic replay of uncertain mutation, universal cross-run compensation, historical/crash
  rollback, distributed Task leases, forced interruption of in-flight external calls and automatic
  crash replay;
- redesign or replacement of manual/remote one-shot execution authority, Task/TaskItem/Result,
  Processing Checkpoint, policy ownership, OrganizePlan or OrganizerExecutor;
- unbounded whole-library work without configured per-run bounds, arbitrary path/plan/operation/
  Provider editors, cross-definition policy overrides and implicit scope expansion;
- product notification Provider management, delivery guarantees beyond the existing bounded
  notification infrastructure, and media-server refresh;
- a Secret Store or identity-administration product, advanced audit administration, multi-version/
  upgrade management, generated/downloaded artwork or NFO, and complete user/media-server features.

## Slice Acceptance Criteria

- [ ] From Automation, an authenticated authorized operator can create or edit one definition for a
      configured ResourceLibrary, understand its scope/mode/schedule/timezone/limits/references,
      validate it, Preview it, activate/enable it and later disable it without editing JSON or SQLite.
- [ ] Automation definition changes are optimistic, audited and governed by the managed immutable
      configuration lifecycle; Web-visible Active identity is the exact snapshot used to create new
      occurrences, while older Jobs retain their pinned identities.
- [ ] Exact-definition Preview persists and reloads complete bounded per-item zero-mutation evidence;
      edits or plan-affecting changes make it stale and cannot silently authorize a later run.
- [ ] Concurrent/restarted Scheduler instances emit at most one Job per definition occurrence,
      respect configured capacity and commit due-state advancement, Job and audit atomically without
      constructing the media pipeline or accessing Storage/Provider services.
- [ ] Scan-only and scan-and-plan occurrences remain zero-mutation; an automatic-organization
      occurrence uses only the existing full policy/planning/execution chain and links Definition →
      Job → Task/TaskItem → Result/Log after reload.
- [ ] The operator grants unattended execution only through a distinct explicit confirmation that
      shows the exact scope and implications. The grant is durable, version/scope-bound, visible,
      independently revocable and never substitutes for destructive-operation authority.
- [ ] Revoked, stale, widened, out-of-scope, over-limit, permission-invalid, conflict-blocked or
      capability-invalid work fails before unauthorized mutation; authority is checked again before
      every not-yet-performed effect and no plan or operation is silently substituted.
- [ ] A bounded mixed run preserves independent Previewed/blocked/skipped/ignored/success/failed/
      partial/unchanged/unselected item outcomes, known effects, retry safety and checkpoint-aware
      recovery; successful siblings and uncertain mutation are never automatically replayed.
- [ ] Disabling a definition prevents future occurrence emission. Revoking authority prevents future
      eligible mutation without rewriting completed Job/Task/Result history, and cooperative
      cancellation reports honestly when an external call cannot be force-interrupted.
- [ ] API and Web expose the same entry, state, actions, confirmations, success, failure and recovery
      under the same RBAC/concurrency/audit rules, with bounded secret-free Definition, Preview,
      authority, occurrence and history projections.
- [ ] RecognitionType C remains C across scheduled Preview, plan, execution and Result while its
      configured downstream A policy ownership remains visible.
- [ ] Explicitly Deferred capabilities remain non-claims and no unresolved in-Slice P0/P1 defect
      remains.

## Final Validation Expectations

B performs one `SLICE FINAL` validation before readiness:

- domain and managed-configuration tests for definition identity, ResourceLibrary/sub-scope, run
  modes, interval/Cron/timezone, limits, references, optimistic edits, Draft/Validated/Active truth,
  stale evidence and audit;
- SQLite migration, restart/reload, exact-version update, grant/revoke/invalidation, occurrence
  lineage, transaction rollback, bounded-query and legacy schedule compatibility tests;
- Scheduler concurrency, duplicate-occurrence, missed/coalesced occurrence, DST, disabled
  definition, capacity, snapshot pin and atomic due-state/Job/audit falsification without Storage,
  Provider or pipeline construction;
- Worker and application integration for scan-only, scan-and-plan and automatic-organization modes,
  exact ResourceLibrary/sub-scope/limit enforcement, mixed RecognitionTypes and complete Definition
  → Job → Task/TaskItem → Result/Log linkage;
- authenticated API and Operator Web integration for create/edit/copy/enable/disable, validate/test,
  Preview, grant, revoke, list/detail/history, explicit confirmations, RBAC, optimistic concurrency,
  reload and recovery;
- isolated real-execution tests using temporary Local roots plus fake/in-memory SMB, OpenList and
  S3/R2 adapters as needed, covering Move/Copy/HardLink/SoftLink, attachments, collisions,
  Skip/Rename/Manual/authorized Overwrite, source cleanup and injected partial/uncertain failure;
- falsification evidence that view/edit/validate/test/Preview/Scheduler paths perform zero mutation,
  Scheduler owns no policy decision, out-of-scope input cannot execute, changed snapshot/definition/
  plan/scope/permission or revoked grant fails closed, and revocation wins before every
  not-yet-performed mutation without replaying siblings;
- RecognitionType C, OrganizerExecutor-only mutation, no-silent-fallback, overwrite/delete/cleanup,
  source/path locking, Job fencing/idempotency, redaction/private-config and per-item recovery safety
  regressions;
- the complete offline regression suite plus Ruff lint/format, compileall, dependency check,
  configuration validation, schema-marker/migration checks, wheel build/isolated smoke, Markdown
  links, private-config/secret scan and `git diff --check`;
- explicit reporting of PASS/FAIL/SKIP/UNAVAILABLE for real Scheduler endurance, process-stop,
  SMB/OpenList/S3/R2 and destructive acceptance gates. No production Storage, Provider credentials
  or user media are required.

## Closure Packet

```text
Slice: 25 — Scheduled Automation and Unattended Organization
Base SHA: 2cee7cc756b90618f14d5d7b112f974fb445a580
Head SHA: d4da92879b99f1c44ddd717fba1a26e4b0a73493

Required Outcomes:
- RO-1: COMPLETE
- RO-2: COMPLETE
- RO-3: COMPLETE
- RO-4: COMPLETE
- RO-5: COMPLETE
- RO-6: COMPLETE
- RO-7: COMPLETE

Required Surfaces:
- Managed Automation Task Definition configuration contracts: COMPLETE
- Durable exact-definition validation/Preview evidence and unattended-grant lifecycle: COMPLETE
- Shared definition, Preview, grant/revoke, occurrence, execution and history/recovery
  application services: COMPLETE
- Immutable configuration, Scheduler, AutomationJob, Worker, Task/TaskItem/Result/Log and
  Processing Checkpoint boundaries: COMPLETE
- Existing pipeline, policy, conflict/capability, source-lock, OrganizePlan and OrganizerExecutor
  authorities without a Scheduler-specific policy or mutation path: COMPLETE
- Authenticated versioned API and Operator Web Automation management, Preview, authority,
  occurrence, Result and recovery journey: COMPLETE
- Domain, persistence/migration, application, Scheduler/Worker, API, Web, RBAC, concurrency,
  zero-mutation and real-execution safety evidence: COMPLETE

Implemented:
- Versioned managed Automation Task Definitions with stable identity, bounded ResourceLibrary scope,
  run mode, schedule/timezone/limits, validation, optimistic edits, audit and immutable Active truth
- Reloadable exact-definition and exact-snapshot Preview/DryRun evidence with policy ownership,
  item decisions, destinations, operations, attachments, capability/conflict facts, blockers and
  stale invalidation under a zero-mutation boundary
- Atomic idempotent due-occurrence emission with exact definition/configuration pins, capacity,
  restart/concurrency semantics and Scheduler isolation from Storage, Provider and policy decisions
- Definition-scoped Worker handoff through the existing Task/TaskItem/Result pipeline for scan-only,
  scan-and-plan and authorized automatic-organization modes
- Separate persistent scope/version-bound unattended execution grants with explicit confirmation,
  grant/revoke audit, invalidation and live revalidation before each not-yet-performed mutation
- Fail-closed authorized execution across operation capabilities, conflicts, unstable input,
  Provider/Storage failure, partial or uncertain effects and checkpoint-aware recovery without
  silent fallback or automatic replay
- Shared bounded Automation API/Web occurrence summaries with per-item status counts, configured
  bound visibility, capped attention rows and links to existing TaskItem recovery after reload
- RecognitionType C preserved through scheduled Preview, planning, execution and Result while
  downstream A policy ownership remains visible

Tasks completed:
- 25.1 — Managed Automation Task Definition lifecycle
- 25.2 — Exact Automation Task Definition validation and Preview evidence
- 25.3 — Due-occurrence resolution and atomic Automation Job emission
- 25.4 — Definition-scoped Worker and Task execution handoff
- 25.5 — Persistent revocable unattended execution grant
- 25.6 — Fail-closed authorized scheduled organization and per-item outcome/recovery
- 25.7 — Preview-gated unattended authority and live permission revalidation
- 25.8 — Per-mutation unattended authority enforcement

Final Tests:
- Focused authority/execution suite: PASS, 171 tests
- Related Automation/API/Web/manual execution suite: PASS, 140 tests
- Full primary-worktree regression: PASS, 1124 tests, 7 skips
- Full clean-archive regression from the Slice implementation Head: PASS, 1124 tests, 7 skips
- Ruff lint/format, compileall, pip check, both example configuration validations, forbidden
  FFprobe/FFmpeg runtime scan, Markdown relative links, private-config scan and Git diff checks: PASS
- Schema/migration regression: PASS; runtime schema 31; migration required NO
- Wheel build plus isolated installed-wheel smoke: PASS; supported/runtime schema 31
- `python -m build`: UNAVAILABLE because this virtualenv has no executable `build.__main__`; the
  Task-approved `pip wheel --no-deps --no-build-isolation` substitute passed
- Real Scheduler endurance/process-stop, production SMB/OpenList/S3/R2, Provider credentials and
  destructive acceptance: SKIP / UNAVAILABLE in this offline environment; no production data,
  credentials or user media were used

Safety Evidence:
- Definition reads/edits, validation, Preview, Scheduler emission and Automation history/detail
  projections remain zero-Storage-mutation; read/refresh paths create no Job, Task, grant, Provider
  request or Storage probe
- Scheduler emits only bounded pinned Jobs and owns no Provider, policy, destination, plan or
  operation decision; only OrganizerExecutor performs Storage mutation
- Persistent unattended authority remains distinct from scheduling and one-shot authority, is
  exact definition/version/scope bound, independently revocable and rechecked before each pending
  Storage mutation, including intra-item attachment, primary, cleanup and rollback boundaries
- Overwrite, Delete, cleanup, rollback, out-of-scope work and unsupported operation fallback remain
  denied without their independent authority; Manual/Overwrite conflicts block only affected items
- Per-item Results/checkpoints preserve successful siblings and known effects; uncertain mutation is
  investigation-only and retry admission rechecks blockers, interrupted admission, effect certainty
  and pinned snapshot availability
- Byte-level temporary-Local operation/conflict tests cover Move/Copy/HardLink/SoftLink,
  attachments, Skip/Rename/Manual/Overwrite and injected failures with no silent substitution
- Definition, Preview, grant, Job, Result, checkpoint, audit and API/Web evidence is bounded and
  secret-free; `config/alist.json` and `config/strategy.json` remain ignored, untracked and unstaged

Known Non-blocking Issues:
- P3: existing unclosed SQLite connections emit ResourceWarning messages without changing test
  results

Explicitly Deferred:
- Unchanged; the Explicitly Deferred capabilities in this Slice Contract remain non-claims

Documentation Reconciliation Needed:
- A should reconcile the canonical Chinese specification's CURRENT implementation baseline,
  `docs/product-experience.md`, `docs/architecture.md`, `docs/roadmap.md` and `docs/progress.md` to
  record the reviewed Slice facts; no Contract or stable requirement scope change is requested

Decision: PASS / CLOSED
```

## A Final Review

```text
Reviewed Range: 2cee7cc756b90618f14d5d7b112f974fb445a580..d4da92879b99f1c44ddd717fba1a26e4b0a73493
Decision: PASS / CLOSED
P0/P1 Blockers:
- None.
Closure Reconciliation:
- Slice 25 is closed at Base `2cee7cc756b90618f14d5d7b112f974fb445a580` and reviewed
  Implementation Head `d4da92879b99f1c44ddd717fba1a26e4b0a73493`.
- `docs/roadmap.md` and `docs/progress.md` now record Slice 25 as PASS / CLOSED with its delivered
  managed Automation Task Definition, exact Preview, scheduled occurrence, persistent unattended
  authority, existing-pipeline execution and per-item recovery behavior.
- The Chinese product specification, Product Experience, Architecture and README now describe the
  bounded Slice 25 capability as CURRENT. They retain the explicit deferrals for Provider switching,
  remote guided setup/prechecks, uncertain-effect replay, universal compensation, historical rollback,
  and other deferred V1 capabilities.
- Final validation remains truthful: offline full regression and safety/packaging gates pass; real
  external-service and destructive acceptance gates remain SKIP / UNAVAILABLE and are not promoted
  into production-service claims.
```
