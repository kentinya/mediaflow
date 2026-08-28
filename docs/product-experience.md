# MediaFlow Product Experience

This document defines the canonical operator experience for MediaFlow V1. It describes product
behavior, not visual styling or a frontend framework. The root Chinese product requirements
specification remains the canonical product scope; this document is the canonical journey and UX
interpretation of that scope.

## Guidance hierarchy

`AGENTS.md` supplies permanent safety/workflow rules; the root Chinese specification supplies V1
product scope; this document supplies journey and product-completion semantics;
`docs/requirements.md` and `docs/architecture.md` supply stable engineering requirements and
CURRENT/TARGET design; `docs/roadmap.md` supplies priority; and `TASK.md` narrows the one slice that
may be implemented now. Lower-level guidance may narrow but must not weaken a higher-level safety or
user outcome.

## Product experience contract

An operator-facing capability is complete only when its entire vertical journey works:

```text
Goal → Entry point → Visible state → Action → Outcome → Failure → Recovery
```

Repository, Domain, Application, migration, CLI, API, or Web work may be necessary, but no internal
layer is sufficient by itself. The final V1 management surface is Web. CLI is retained for
administration, debugging, migration, scripted automation, and emergency diagnosis; it is not the
sole acceptance surface for a Web-management requirement.

All journeys share these rules:

- DryRun/Preview is the default before a media mutation.
- No overwrite or source deletion is silent.
- An Active configuration is the exact immutable snapshot used by runtime.
- Every automated recognition/destination decision has bounded, secret-free evidence.
- A batch retains independently visible state and recovery for every item.
- A retry merely repeats work; recovery explains durable state and gives the safe next action.
- Errors name the affected object/item and stage without exposing credentials.
- The user never needs to know Python class names, repository tables, internal IDs that have no
  product meaning, or which module implements an action.

## Configuration lifecycle

Managed configuration has three operator-visible states:

- **Draft**: editable, not consumed by runtime.
- **Validated**: a specific immutable draft version has passed structural/reference validation and
  the applicable safe tests. It is still not active.
- **Active**: an immutable validated snapshot has been explicitly activated and is the exact
  snapshot consumed by the runtime process. The UI displays its version/digest and activation time.

Editing an Active configuration creates a new Draft; it never mutates the Active snapshot in place.
Validation results belong to the exact draft version tested. Any subsequent edit returns it to
Draft. Activation is atomic and fails closed. JSON remains useful for bootstrap, import/export,
migration, and support bundles; after managed activation exists, a JSON file is not a second active
source of truth.

## Phase 22.2 / 22.2R implementation boundary (CURRENT)

The Active Configuration Snapshot implementation provides most of the first end-to-end lifecycle:
the authenticated Configuration view/API can import the bootstrap JSON as a Draft, run the same
normalized loader for validation, show a redacted revision/diff, and explicitly activate one atomic
immutable revision. Before the first activation the authority is visibly `JSON_BOOTSTRAP`; afterward
runtime resolution is `MANAGED` and fails closed if the referenced snapshot is missing or corrupt.
New CLI Tasks and API/Scheduler Jobs carry the snapshot ID/digest; queued work is resolved against
that immutable revision rather than silently switching to a later Active revision.

The 22.2R integrity/recovery implementation also keeps configuration management reachable when a managed
Active row is missing, corrupt, schema-incompatible, or runtime-invalid: the Web/API can show the
last-known identity, accept a whole-document replacement, revalidate the exact digest, and activate
only a runtime-consumable snapshot. Bootstrap-only locators remain immutable, lifecycle state and
redacted audit evidence commit atomically, and resident Scheduler emissions resolve the current
snapshot at each creation boundary. Media-work endpoints still fail closed while this recovery is
in progress.

The Worker entry point uses only that immutable locator until it has claimed a Job. It then loads the
Job's saved snapshot before constructing the media workflow, so a later unhealthy Active does not
silently replace the configuration selected by the queued work.

The F2 implementation publishes API configuration-derived behavior through one immutable binding per
request. Snapshot identity, queue/execute admission, schedules, status, stale-job settings, and
MetadataPolicy references therefore come from one validated revision. A saved Job revision that is
missing, unreadable, digest-corrupt, schema-unsupported, or runtime-invalid fails before workflow
construction and exposes saved identity, durable state, `sideEffects=none`, retry safety, and a
concrete restore-or-create-new-work action in API/Web Job detail.

**Independent review status (2026-08-24): PASS / CLOSED.** Independent review reran the concurrent
lifecycle, activation/request, protected-execute pin, production Web → Worker → Task/Result,
saved-revision failure, and zero-I/O regressions and found no Task-scope P0/P1 defect. Phase 22.2's
bounded whole-document snapshot journey is accepted; object-level setup remains the next journey.

This is not the full first-time setup journey: remote/provider Storage forms, policy editing, provider
switching, and generic per-item stage-aware recovery remain TARGET work.

## Phase 22.3 Local setup slice (CURRENT implementation; PASS / CLOSED)

The Configuration view provides the accepted Local first-setup path over the same managed Draft
authority. Phase 22.3R and its focused corrections closed the independently found lossless-edit,
absolute-root, reference-display, persisted check-recovery, bounded-probe, Web eligibility, and
behavioral snapshot-consumption P1 gaps:

```text
current Active/bootstrap → Draft → guided Local Storage
→ ResourceLibrary + MediaLibrary → reference impact → Validate
→ read-only Local Exists/Stat check → diff → checked Activate
→ existing DryRun Preview Job → pinned Worker/Task/Result
```

The guided forms expose only Local Storage (`id`, `name`, host-absolute `rootPath`, `readOnly`),
ResourceLibrary runtime fields (`storageId`, Storage-relative `storagePath`, optional display root,
extensions, depth, enabled), and MediaLibrary runtime fields (`storageId`, Storage-relative `rootPath`,
enabled). Every write is Draft/version-bound and audited. Direct inbound references are shown and
referenced deletes are refused without cascade. Existing remote Storage objects are preserved but
redacted/read-only. The explicit setup check constructs the existing read-only Storage factory,
never lists or creates a directory, stores exact revision/version/digest evidence, and marks evidence
stale after a later edit. Its submitted Phase 22.3R3 boundary admits one check per resident service,
covers loader/construction/Exists/Stat with one deadline, and wraps selected adapters in a fail-fast
read-only guard. Timeout reports `sideEffects=none` and a safe explicit retry action without claiming
the underlying call was cancelled; capacity remains occupied until that worker exits, while another
request fails immediately without spawning work. Checked activation requires current successful
evidence; the existing raw activation API remains an explicitly labelled compatibility path.
The R3-F1 correction rejects unrepresentable evidence paths before probing, persists a bounded
failure, releases capacity on every ordinary Worker/Future and repository-save path, and allows the
same Validated revision to be edited back to Draft for explicit revalidation/retry. It passed
independent review on 2026-08-25. The submitted R4 implementation now projects that persisted latest
evidence after API/Web reload independently of Draft/Validated state: exact evidence identity,
current/stale state, category, bounded message and operations, duration, side effects, retry safety,
and next action remain visible. Draft directs the operator to correct and Validate without exposing
a runnable check; revalidated stale evidence exposes an explicit rerun but cannot checked-activate;
only exact current passed evidence enables checked activation. Independent R4-F1 review accepted the
remaining action correction: one shared selection now admits only enabled Local-backed source and
destination libraries, controls both button visibility and submitted IDs, and shows correction
guidance without a request when unavailable. R5-F1 and the 2026-08-25 phase-level Final Closure Audit
accepted the combined checked activation → DryRun Preview Job → later Active → Worker → Task/Result
journey: the queued Job consumes the original behavior-distinct immutable revision, preserves exact
ID/digest through Task/Result, grants no execute authority, and leaves source/target media unchanged.
No remote connectivity test or media mutation is part of the closed Phase 22.3 scope; Recognition
configuration and Strategy Test completed independent review as Phase 22.4 on 2026-08-26.
MetadataPolicy managed editing and exact-revision offline resolution preview completed independent
review as Phase 22.5-A on the same date. Live Provider testing and candidate explanation, including
the service-lifetime cache/request-control/evidence-bound correction, completed independent review
as Phase 22.5-B. Candidate confirmation and its F1/F2 durable concurrency corrections completed the
Phase 22.5-C boundary and passed final Integration Acceptance. Phase 22.5-D now implements the
same-Provider managed live correction test for exact current `NotFound`/`NeedConfirm`/`Ambiguous`
evidence: the operator can explicitly submit query/year/Movie-TV or one direct Provider ID, inspect
durable bounded outcomes, and reuse candidate confirmation. Independent High re-review accepted the
correction checkpoint on 2026-08-26. Phase 22.5-E implements only the missing explicit continuation
from one resolved File correction into a new pinned DryRun Preview; it must not replay siblings or inherit
execute authority. Independent High Review returned `FIX REQUIRED` for checkpoint
`08dfd4f921728755209b6d52347d28f221121c47` on 2026-08-27 because the Files detail Web surface was
unreachable; Phase 22.5-E-F1 attached that section to the page and proved it with focused Web
regression coverage, and independent High re-review accepted the correction checkpoint
`dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62` on 2026-08-27. The same-day phase-level Final Closure
Audit accepted Phase 22.5 (slices A, B/F1, C/F1/F2, D, E/F1) as `PASS / CLOSED`. Provider switching
remains later Metadata journey work.

## Phase 22.5-E single-item correction continuation (CURRENT)

Independent High Review of checkpoint `08dfd4f921728755209b6d52347d28f221121c47` returned
`FIX REQUIRED` on 2026-08-27: the Application, API, persistence, and Worker behavior was accepted,
but the Files detail continuation section was built and returned to a caller that discarded it, so
the Web entry point, confirmation, state rendering, links, retry, and stale requeue were
unreachable. Phase 22.5-E-F1 attaches that section to `detailContent` on both branches, so
everything described below is CURRENT for the Application, API, persistence, Worker, and Web.
Independent High re-review accepted the correction checkpoint
`dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62` on 2026-08-27, and the phase-level Final Closure Audit
the same day accepted Phase 22.5 as `PASS / CLOSED`.

The operator goal is to turn exactly one already-resolved File Metadata correction into a fresh,
read-only DryRun Preview without replaying the source Task or any sibling item. Files detail is the
entry point. Before the action is enabled it shows the source Task and TaskItem, resolved correction
identity and version, exact immutable configuration snapshot ID/digest, one-item scope,
`DRY_RUN_ONLY`, and `Storage mutation: NONE`.

The API and Web use the same application admission service. The action accepts only the exact
review ID and expected correction version. Admission atomically creates a durable continuation and
a one-item, non-executable Job, enforces the shared active-job capacity, and rejects duplicate or
stale identity. Viewing or reloading the detail performs no Provider, Storage, queue, or Task work.

The claimed Worker revalidates the File, source Task/TaskItem, resolved correction, correction
version, and exact snapshot pair before constructing anything external. It loads that pinned
snapshot, then runs Parser → Recognition → RecognitionTypePolicy → Metadata → Naming →
Classification → Planner with the correction applied. A new Task is created with `execute=false` and
one item only; a durable DryRun Result is required before the continuation can be completed. Query
corrections perform one Provider search followed by one detail lookup in the focused proof; direct
Provider-ID corrections perform no search and one detail lookup. RecognitionType C remains C even
when its naming/classification policies reference A.

After reload, the operator can distinguish queued, running, completed, failed, stale, and cancelled
continuations. Snapshot-unavailable failure identifies the missing/unreadable/invalid snapshot and
points to repairing the pinned source configuration before resubmission. Provider or downstream
failure preserves the new Task/Item/Result evidence and points to retrying only this correction.
A stale running continuation requires inspection and explicit requeue; cancellation and duplicate
admission are durable and idempotent. Source files, the resolved source review, and sibling items
remain unchanged in every DryRun path.

Provider switching, generic Task resume, automatic continuation retry, execution, and a broader
checkpoint/recovery journey remain deferred TARGET work and are outside the closed Phase 22.5 scope.
Managed Naming / Classification / Organize configuration with exact-revision offline preview is the
next Phase (22.6) and is not claimed here.

## Phase 22.6-A managed NamingPolicy and offline preview (CURRENT; PASS / CLOSED)

The managed Configuration view now exposes each NamingPolicy in an editable Draft, including its
movie and TV templates, media-type mode, enabled state, missing-variable strategy, and exact inbound
RecognitionTypePolicy references. Create, edit, copy, and delete use the existing whole-document
optimistic version and Before/After audit path. A referenced policy remains visible but cannot be
deleted until the operator repoints or removes every listed reference.

The same Web/API application service accepts one bounded synthetic sample or one path string for the
existing local Parser, binds the action to the exact revision ID/version/digest, and invokes the
existing NamingPolicyRegistry, NamingPreviewService, renderer, and sanitizer. Persisted evidence
shows rendered directory segments and filename, applied policy, RecognitionType, sanitization,
missing-variable decisions, warnings, failure category, side effects, retry safety, and one recovery
action. A later Draft edit preserves the prior evidence but labels it stale and requires an explicit
rerun. Movie, single-episode TV, and multi-episode TV are supported without constructing Storage or
Provider services and without creating Tasks, Jobs, queues, plans, or media effects.

Phase 22.6-A is independently accepted at `30af69ac82b30f8a45ad66afbd3c9747597c8fe7` and does not
change checked activation.

## Phase 22.6-B managed ClassificationPolicy and offline preview (CURRENT; PASS / CLOSED)

The same managed Configuration revision view now exposes ClassificationPolicy create/edit/copy/
delete, bounded rule summaries, RecognitionTypePolicy inbound references and reference-blocked
deletion. Rules are normalized through existing ClassificationPolicy/ClassificationRule domain
construction, while the same whole-document revision CAS and Before/After audit remain authoritative.

One bounded synthetic or locally parsed sample runs through the existing
ClassificationPolicyRegistry and ClassificationPreviewService against the exact Draft/Validated
revision. Persisted evidence distinguishes classified/unclassified and current/stale outcomes,
shows matched rule, match evidence, MediaLibrary ID and resolution state, safe relative path,
warnings and recovery. An absent MediaLibrary is an explicit completed-with-warning preview and is
still rejected by existing Draft validation. No Storage, Provider, Task, Job, queue or media work is
created.

Phase 22.6-B is independently accepted at `5e2da5c634f1fa72a40e5f50b035260418fe1a37` and does not
change checked activation.

## Phase 22.6-C managed OrganizePolicy and offline organize authority (CURRENT implementation; awaiting review)

The same managed Configuration revision view now exposes OrganizePolicy create/edit/copy/delete with
a bounded summary of operation, conflict strategy, attachments, duplicate detection and
source-directory cleanup, an explicit destructive-authority warning when overwrite or source cleanup
is enabled, and RecognitionTypePolicy inbound references that block deletion until every referencing
policy is repointed. The editor accepts only Move, Copy, HardLink and SoftLink and refuses `delete`
and `create_directory` as an organize operation. Bounds and the overwrite/conflict-strategy rule are
the production ones, so a managed edit cannot accept or normalize a policy differently from the
configuration runtime consumes.

For an exact Draft or Validated revision the operator names one RecognitionType and gets a persisted,
secret-free explanation of the organize authority that revision would grant: which
RecognitionTypePolicy and OrganizePolicy resolve, the operation and conflict strategy, whether
overwrite and source-directory delete authority are granted, attachment/duplicate/rollback/cleanup
behaviour, which Storage capabilities the operation requires, and the explicit statement that an
unsupported capability is a failure rather than a silent fallback. Required capabilities are declared
from the resolved policy and never probed. An unresolvable RecognitionType — missing or duplicate
type policy, disabled RecognitionType or policy, or an invalid policy reference — is an explained
failure with the action that resolves it, not an unexplained error. A later Draft edit keeps the
prior explanation but labels it stale and names the rerun. No Storage, Provider, Planner, Executor,
Task, Job, queue or media work is created.

Composed final destination preview, destination existence/conflict/capability prechecks, Storage
capability probing and combined activation evidence remain TARGET Phase 22.6 work. Checked activation
and Active runtime-consumption semantics are unchanged, and this Slice is not `PASS / CLOSED` until
independent High Review accepts its exact checkpoint.

## A. First-time setup

### Starting point

The operator opens a new or unconfigured MediaFlow instance and sees setup progress, credential
prerequisites, and that no configuration is Active.

### Information shown

- Storage types and required non-secret fields
- Credential reference status without secret values
- ResourceLibrary scan roots and filters
- MediaLibrary destination roots
- Recognition, Metadata, Naming, Classification, and Organize policy dependencies
- Draft/Validated/Active state and validation errors

### Actions

```text
Storage
→ ResourceLibrary
→ MediaLibrary
→ Policies
→ Test Policy
→ Activate
→ Scan
→ Preview
```

The operator can test connectivity/read capability before saving dependencies, run Strategy Test on
a synthetic or real read-only path, inspect the resulting plan, activate the validated snapshot,
scan, and preview without mutation.

### Safe defaults

- Storage is read-only until explicitly configured otherwise.
- Activation never starts scanning or organizing automatically.
- Scan and Strategy Test are read-only; Preview is DryRun.
- Credentials are referenced from an approved secret source and never echoed.

### Success

The Web UI shows the same Active snapshot version used by runtime, successful Storage/strategy test
evidence, a completed scan summary, and a DryRun preview with explained decisions.

### Errors and recovery

Validation groups errors by object and dependency. Connectivity errors distinguish credentials,
permissions, path, capability, timeout, and unavailable service. Recovery links to the affected
Draft object, preserves valid input, and allows retest without recreating unrelated configuration.

### Must not require internal knowledge

The operator must not edit SQLite, infer policy IDs from Python defaults, restart a process without a
visible instruction, or understand Storage adapter classes or reference tables.

## B. Normal daily organization

### Starting point

The operator opens Dashboard or a configured ResourceLibrary and sees the Active configuration,
last scan, ready/unstable/error counts, and pending review/conflict counts.

### Information shown

Scope, Active snapshot, discovered items, stability state, recognition/metadata/classification
summary, proposed operations, conflicts, and expected mutations.

### Actions

Scan, review changes, Preview, inspect explanations, resolve blockers, and explicitly organize the
selected scope. Real execution requires a separate confirmation/authority step.

### Safe defaults

Preview first, exclude unstable files, never overwrite by default, and never silently downgrade an
unsupported operation.

### Success

Every item has a visible final result and history link. The summary reconciles totals with success,
skipped, waiting, conflict, ignored, partial, and failed items.

### Errors and recovery

The batch continues when safe. Each failed/partial item shows its durable checkpoint, known file
effects, whether retry is safe, and the stage-aware recovery action. Unknown execution outcomes are
not automatically replayed.

### Must not require internal knowledge

The operator must not correlate Task/Result tables manually or inspect logs to discover which files
moved. Logs supplement, rather than replace, item status and recovery guidance.

## C. Unrecognized or ambiguous media correction

### Starting point

The operator opens a review from Dashboard, Files, a Task item, or a batch summary.

### Information shown

Source/library context, parser evidence, matching/non-matching rules, priorities, scores, warnings,
available RecognitionTypes, and the Active rule snapshot version.

### Actions

Choose an allowed RecognitionType, request re-evaluation after editing/testing rules, or explicitly
ignore the current Task item. Ambiguous results show competing explanations rather than a hidden
winner.

### Safe defaults

No default to A, no automatic type change, and no downstream execution until the decision is explicit.

### Success

The chosen/re-evaluated RecognitionType is visible, downstream policy references are shown, and the
item proceeds through an explicit continuation. C remains C even when reusing A policies.

### Errors and recovery

Stale/disabled types and changed rules explain why the decision cannot apply. The user can return to
the current review, refresh against Active configuration, test a Draft rule, or ignore the item.

### Must not require internal knowledge

The operator must not know RecognitionReview table states, manually craft a selection object, or
edit a rule file without validation feedback.

## D. Metadata failure correction, including Provider switching

### Starting point

The operator opens a Metadata NotFound/NeedConfirm/Ambiguous item from Files, review queues, or Task.

### Information shown

RecognitionType, MetadataPolicy, current Provider and locale, query/year/media type, candidate score
breakdowns, matched title source, canonical/regional year evidence, cache state, and failure category.

### Actions

Edit query/year, switch Movie/TV, select a candidate, enter a direct Provider ID, or choose another
Provider allowed by a validated policy. Provider switching is a planned V1 journey and is not
claimed implemented until its Web/API/configuration path exists.

### Safe defaults

No first-result selection, no same-year-only acceptance, no arbitrary identity injection, and no
network request while merely editing a Draft correction.

### Success

The selected MediaIdentity and evidence are visible, RecognitionType is preserved, and an explicit
continuation produces a new Preview before execution.

### Errors and recovery

Differentiate no result, ambiguity, bad Provider ID, policy/provider unavailable, authentication,
rate limit, timeout, and malformed response. Preserve correction input and offer safe retry,
Provider/policy selection, or ignore according to current capability.

### Must not require internal knowledge

The operator must not know TMDB endpoints/DTOs, manually alter persisted candidates, or infer whether
a failure is retryable from an exception string.

## E. Per-item recovery inside a batch

### Starting point

A batch summary contains waiting, conflict, failed, or partial items while other items completed.

### Information shown

Per item: current stage, durable checkpoint, completed operations, known source/target state,
conflict/review links, retry safety, Active snapshot, and last error category.

### Actions

Resolve the specific review/conflict, retry a safe stage, resume from a checkpoint, request a fresh
plan, ignore, or leave untouched for investigation. Actions can be selected per item even when a
bounded batch action is available.

### Safe defaults

Never replay successful items, never replay an uncertain mutation automatically, and never let one
item's decision overwrite another item's state.

### Success

The recovered item obtains a new auditable result; unchanged successful items remain unchanged and
the batch summary reconciles all item states.

### Errors and recovery

If recovery itself fails, retain both original and recovery evidence, report known mutations, and
offer only actions valid from the new checkpoint. “Retry” alone is not a recovery explanation.

### Must not require internal knowledge

The operator must not reconstruct completed steps from JSONL/SQLite or guess which command is safe.

## F. Configuration editing, dependency impact, test, and activation

### Starting point

The operator opens managed configuration and sees the Active snapshot plus zero or more Drafts.

### Information shown

Object values, enabled state, version, references/dependents, change diff, validation/test evidence,
affected libraries/policies, and Active snapshot identity.

### Actions

Create/edit/copy/enable/disable/delete a Draft object, inspect dependency impact, validate, run the
applicable safe test, review the full activation diff, activate, or discard the Draft.

### Safe defaults

Referenced deletes are blocked, edits never mutate Active, secrets are never returned, tests are
read-only unless a narrowly identified connection-test capability requires otherwise, and activation
does not launch media execution.

### Success

Activation atomically creates an immutable Runtime Snapshot. Web, API status, workers, and engines
agree on its version/digest; prior snapshots and Before/After audit remain available according to
retention policy.

### Errors and recovery

Validation identifies exact fields/references. Test errors distinguish validation from connectivity.
Activation failure leaves the previous Active snapshot in use. Recovery returns to the Draft,
supports retest, and may reactivate a known-valid prior snapshot when that capability is implemented.

### Must not require internal knowledge

The operator must not synchronize JSON and SQLite manually, edit foreign keys, infer restart state,
or compare process memory to a file to discover what is Active.

## G. Manual organize

### Starting point

From a file/media detail or selected items, the operator requests an explicit manual organization
workflow.

### Information shown

Current identity, selected policies, source Storage/path, destination MediaLibrary/path, operation,
attachments, conflicts, capability checks, and complete DryRun plan.

### Actions

Choose only permitted Recognition/Metadata/policy options, regenerate Preview, resolve conflicts,
and explicitly authorize execution. Arbitrary unsafe destination paths are not accepted.

### Safe defaults

DryRun, no overwrite/delete, no implicit operation fallback, and no execution while reviews or
conflicts remain unresolved.

### Success

The exact reviewed plan executes once, with per-operation history and source/target verification.

### Errors and recovery

Failure shows completed operations and checkpoint-aware recovery. If state is uncertain, execution
stops for investigation instead of automatic replay.

### Must not require internal knowledge

The operator must not build an OrganizePlan payload, calculate Storage-relative paths, or invoke
adapter methods directly.

## H. File browsing, detail, history, and explanation

### Starting point

The operator opens Files or follows a link from Dashboard, Task, review, notification, or history.

### Information shown

Bounded searchable file catalog, source/library identity, scan/stability state, parser evidence,
RecognitionType/rule explanation, Metadata identity/matcher explanation, naming/classification/plan,
TaskItem checkpoint, operation history, related reviews/conflicts, and current available actions.

### Actions

Search/filter, open detail, follow Task/review/history links, request re-recognition/re-match/re-plan,
start manual Preview, or initiate a valid recovery action.

### Safe defaults

Browsing is read-only; sensitive paths/options are permission-aware; actions require explicit
confirmation and never execute merely by opening a detail page.

### Success

The operator can answer what MediaFlow decided, why it decided it, what happened, and what safe action
is available next without consulting internal logs or database tables.

### Errors and recovery

Missing/stale records are explicit. Broken links lead back to the current file/task state. If data
was never captured, the UI says unavailable rather than fabricating an explanation.

### Must not require internal knowledge

The operator must not join FileIndex, TaskResult, review, or history records manually, decode cursor
formats, or understand internal pipeline object names.

## Journey acceptance rule

Every future TASK must name the journey(s) it advances and state which segment becomes usable. A
slice may intentionally stop before full V1 completion, but its report must say so. “Backend done,”
“repository complete,” or “CLI command exists” is never a substitute for the promised Web journey.
