# MediaFlow Product Experience

This document defines the canonical operator journeys for MediaFlow V1. It describes user-visible
behavior and completion semantics, not implementation history or frontend styling. Large-Slice order
and status are maintained in [`roadmap.md`](roadmap.md); the active implementation boundary is in
[`SLICE.md`](../SLICE.md).

## Product completion contract

Every operator-facing capability is evaluated as:

```text
Goal → Entry → Visible state → Action → Success → Failure → Recovery
```

An Application service, repository, migration, CLI command or API route is not by itself a complete
Web journey. API and Web use the same application behavior, permissions, validation, state and
safety rules. CLI remains important for administration, debugging, migration and automation, but it
does not replace a required Web management surface.

All journeys share these rules:

- DryRun/Preview is the default before media mutation.
- Overwrite and source deletion are never silent.
- Active means the exact immutable configuration snapshot consumed by runtime.
- Automated decisions expose bounded, secret-free explanations.
- Batch items retain independent state, result and recovery.
- Retry repeats work; recovery explains durable state, known effects, safe repeatability and the
  explicit next action.
- Errors identify the affected object or item and processing stage without exposing secrets.

## Configuration lifecycle

### Current

The authenticated Configuration view and API expose whole-document Draft import/edit, validation,
revision detail and explicit activation. The current managed object journey also exposes guided
Local Storage, ResourceLibrary, MediaLibrary and policy-graph editing, exact-revision previews and
reference protection. The compatibility JSON bootstrap remains the current first-instance entry
path.

The visible states are:

- **Draft**: editable and not consumed by runtime;
- **Validated**: one exact version passed structural/reference validation and is still inactive;
- **Active**: explicitly activated immutable snapshot consumed by runtime;
- **Superseded**: former Active revision retained for history and pinned work.

Editing invalidates prior evidence. Activation is atomic and fail-closed. A failed or unavailable
Active revision leaves recovery/status routes available and does not start media work.

### Journey

- **Goal:** safely change the runtime behavior.
- **Entry:** open Configuration with an API-principal bearer token, or use the configuration CLI.
- **Visible state:** authority (`JSON_BOOTSTRAP` or `MANAGED`), revision status, version, digest,
  validation errors, evidence currentness and Active identity.
- **Action:** import or edit a Draft, validate it, run applicable exact-revision tests, then choose
  checked activation or the explicitly labelled compatibility activation.
- **Success:** the selected revision becomes the sole Active runtime authority; no scan, Job or
  mutation is started by activation itself.
- **Failure:** stale version/digest, invalid reference, missing or stale evidence, corrupt Active,
  concurrent edit or runtime incompatibility is shown with the durable state and next action.
- **Recovery:** refresh the revision, correct the Draft, rerun validation/checks, or stage an explicit
  replacement Draft. A prior Active remains intact when replacement fails.

## First-time setup

### Current boundary

A fresh instance currently starts from a compatibility JSON document containing the complete runtime
catalog and database/API bootstrap values. Managed configuration can then be used through the
authenticated Web/API, including guided Local setup. The current Web does not provide a minimal
bootstrap-to-first-runtime flow for remote Storage or a Storage Browser/path picker.

### Slice 26 target

- **Goal:** turn a minimal fresh instance into a tested, immutable first runtime without hand-editing
  SQLite or a complete runtime JSON document.
- **Entry:** authenticate against management-only bootstrap state with no Active workflow revision.
- **Visible state:** setup required, Draft contents, validation errors, Storage/library selections,
  read-only test evidence and checked-activation readiness.
- **Action:** create the first complete Draft, configure Local/SMB/OpenList/S3/R2 Storage and
  libraries, select bounded paths, validate, test and checked-activate.
- **Success:** the first immutable Active snapshot is bound to runtime and can be used by an explicit
  Preview or work request.
- **Failure:** missing secret reference, invalid path, permission/authentication/timeout/not-found,
  stale evidence, broken dependency or concurrent edit blocks activation without discarding the
  Draft or any prior Active.
- **Recovery:** correct only the stated blocker, rerun the bounded read-only action and activate the
  same or a new Draft after exact evidence becomes current.

## Recognition and metadata

- **Goal:** identify the RecognitionType and actual movie/show without changing files.
- **Entry:** submit a scan, Preview, File detail action or Strategy Test.
- **Visible state:** parser evidence, matched rule, RecognitionType, selected RecognitionTypePolicy,
  MetadataPolicy/provider identity, candidate list, score explanation and status.
- **Action:** run offline Strategy Test by default; explicitly run the live TMDB test when needed;
  choose an exact persisted candidate or provide a bounded Metadata correction when the current
  review allows it.
- **Success:** a bounded identity is selected or a clear automatic match proceeds to Naming and
  Classification. RecognitionType remains independent of downstream policy reuse; C remains C even
  when it uses A's Naming/Classification/Organize policies.
- **Failure:** unrecognized, ambiguous, below-threshold, provider, credential, timeout or malformed
  response failures remain visible and do not fabricate a type or identity.
- **Recovery:** edit the relevant Draft/rule, rerun the exact Strategy Test, resolve the review, or
  continue one resolved File correction as a new pinned DryRun. Provider switching is not a V1
  capability; the production provider is TMDB through the Provider abstraction.

## Naming, classification and organize policy

- **Goal:** understand and approve what name, destination and operation the current policies produce.
- **Entry:** Configuration policy editor, exact-revision preview, Strategy Test, File detail or
  Automation Preview.
- **Visible state:** selected policy IDs, rendered directory/filename, RecognitionType ownership,
  MediaLibrary and relative path, operation, conflict strategy, required capabilities, warnings and
  composed destination.
- **Action:** edit the Draft, run Naming/Classification/Organize authority and destination previews,
  and run the Local read-only destination precheck where applicable.
- **Success:** the operator can inspect a complete explainable plan; a Preview remains zero-mutation.
- **Failure:** unsafe template/path, missing library, unsupported capability, conflict, stale
  revision/evidence or unavailable Local destination blocks the affected action.
- **Recovery:** correct the named policy or reference and rerun the exact-revision preview/check.
  Unsupported operations never silently fall back to another operation.

## Files and Media

- **Goal:** determine what MediaFlow knows about a file and what safe action is available next.
- **Entry:** Files view, Dashboard, Task/Job, review, notification or history link.
- **Visible state:** bounded FileIndex fields, source/library identity, scan and stability state,
  parser/recognition/metadata evidence, policies, target, latest Results, related reviews/conflicts,
  checkpoint and available actions.
- **Action:** search/filter, open detail, request re-recognition/re-match/re-plan, resolve a review,
  start manual Preview or enter a recovery action.
- **Success:** the operator can see why the file was classified, what happened and what can be done
  without reading SQLite or internal logs.
- **Failure:** missing, stale or unavailable evidence is shown as unavailable; the page does not
  invent a decision or silently rebuild a plan.
- **Recovery:** follow the stated review, replan, Preview or checkpoint action. Reads never mutate
  Storage or invoke a Provider unless the explicit live action requires it.

## Manual organize

- **Goal:** review and execute a bounded, explicit one-shot organization for selected indexed files.
- **Entry:** select current Files and choose manual organize.
- **Visible state:** durable intent, choices, exact Preview, pinned configuration identity, source and
  destination, attachments, conflicts, capabilities, destructive implications and per-item state.
- **Action:** choose allowed metadata/classification decisions, create a zero-mutation Preview,
  select the exact Preview items and provide the separate confirmation/execute authorization.
- **Success:** the existing OrganizerExecutor performs only the reviewed selected operations; each
  TaskItem and Result records source, target, completed effects and certainty.
- **Failure:** stale/changed source, conflict, unsupported capability, insufficient authority,
  pre-mutation failure, partial effect or uncertain effect is attributed to the item.
- **Recovery:** inspect the checkpoint/effects and use the explicitly offered safe recovery or
  reconciliation action. Known successful siblings remain terminal; uncertain mutation is never
  automatically replayed.

## Per-item failure and recovery

- **Goal:** continue a failed or waiting item without hiding successful siblings or replaying unknown
  effects.
- **Entry:** Task detail, File detail, recovery batch or linked review.
- **Visible state:** Task/TaskItem stage, pinned configuration identity, source/target, completed
  operations, effect certainty, error category, durable checkpoint and available actions.
- **Action:** resolve Recognition/Metadata/Classification review, retry a failed read-only stage,
  continue a resolved correction as DryRun, resume a safe checkpoint or create a bounded recovery
  batch; ignore a waiting item only through the explicit terminal ignore action.
- **Success:** the item gets an independent new continuation/Result where appropriate; successful,
  skipped, ignored and DryRun siblings remain unchanged and visible.
- **Failure:** snapshot unavailable, stale request, duplicate admission, cancellation, permission or
  uncertain mutation remains durable and actionable.
- **Recovery:** repair the stated dependency, revalidate exact snapshot identity and choose the
  permitted action. A retry is not presented as recovery when effect certainty is unknown.

## Scheduled unattended organization

### Current

The authenticated Automation view manages a ResourceLibrary-scoped Automation Task Definition,
interval/Cron schedule, exact Preview, persistent revocable unattended authority, occurrences,
linked Tasks/TaskItems/Results and recovery. Each due run pins the Active snapshot at Job creation
and rechecks scope, authority, capabilities, conflicts and current authority at every mutation
boundary.

### Journey

- **Goal:** run a reviewed, bounded organization schedule without a click for every due run.
- **Entry:** open Automation and create or edit a definition for an existing ResourceLibrary.
- **Visible state:** enabled state, scope, schedule/timezone, next run, Active identity, Preview,
  grant/revocation state, occurrence history and per-item outcomes.
- **Action:** validate, Preview, explicitly grant scoped unattended authority, then inspect or revoke
  the definition and its runs.
- **Success:** each due occurrence creates one pinned AutomationJob and uses the existing pipeline;
  item outcomes and recovery remain independently visible.
- **Failure:** invalid snapshot/reference/provider, unstable input, conflict, unsupported capability,
  revoked authority or another safety gate stops only the affected item/run and records next action.
- **Recovery:** repair the definition or configuration, rerun Preview, regrant when scope changed,
  and use the item checkpoint/recovery path. No uncertain mutation is automatically replayed.

## Operations administration

### Slice 27 target

- **Goal:** administer the running installation after first setup.
- **Entry:** Settings, configuration/result import-export or Notifications.
- **Visible state:** consumed settings and Active identity, versioned secret-free exports, Webhook
  definitions/events/readiness, delivery state, leases, dead letters and recovery actions.
- **Action:** edit and activate settings, export/import a Draft, create/edit/enable/disable a
  Webhook, run its explicit read-only test, inspect delivery and retry/requeue safely.
- **Success:** day-2 operational behavior is managed through Web/API with durable audit and no
  secret leakage.
- **Failure:** invalid setting, secret reference, delivery or stale import is isolated and does not
  change completed media work.
- **Recovery:** correct the Draft or endpoint, validate again, and use the delivery-specific retry
  or dead-letter action.

## Docker self-hosted operation

### Slice 28 target

- **Goal:** deploy and operate MediaFlow as a durable production self-hosted service.
- **Entry:** prepare deployment-owned secrets and explicit media mounts, then run Docker Compose.
- **Visible state:** independent API/Worker/Scheduler/Notification Worker health, business/runtime
  readiness, `/data` persistence and actionable mount/permission/migration status.
- **Action:** start, inspect health, restart, back up, preflight and upgrade the image.
- **Success:** production WSGI serving works behind an explicit LAN/reverse-proxy boundary; restart
  preserves state without duplicate schedules or mutation replay.
- **Failure:** missing mount, non-root permission issue, missing secret, unsupported exposure, schema
  incompatibility or migration failure is explicit and fail-closed.
- **Recovery:** fix deployment inputs, retain backup/previous artifact, rerun preflight or restore
  through the documented migration/recovery path. TLS and public exposure remain deployment duties.

## V1 and post-V1 boundary

Current V1 work is ordered as Slice 26, Slice 27, then Slice 28. Provider switching and additional
production Providers, built-in username/password or OIDC identity, a general Secret Store, automatic
uncertain-mutation replay, historical rollback and specialized email/chat/media-server notifications
remain V1.x/V2 or deployment-specific work.
