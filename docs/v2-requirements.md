# MediaFlow V2 Stable Requirements

This document is the stable V2 requirements layer for the active Operator Web migration. It
extends the frozen V1 requirements baseline without renumbering its `REQ-*` or `UX-*` entries.
Explicit user-approved V2 product amendments identify the baseline behavior they supersede for V2;
they preserve historical V1 meaning and all safety invariants. See `V2-AUTO-009` and the amendment
in [`requirements.md`](requirements.md). Slice-specific architecture and proof details
remain in [`SLICE.md`](../SLICE.md) and the architecture document; this file records only durable
product and authority boundaries.

## Current program boundary

[Release](release.md) owns V1/V2 release-line facts; [Roadmap](roadmap.md) owns Slice priority and
status; [Progress](progress.md) records accepted closures. Current scope and work state live in
[SLICE.md](../SLICE.md) and [TASK.md](../TASK.md). CURRENT journeys and implementation boundaries
are described by [Product Experience](product-experience.md) and [Architecture](architecture.md).

Slice 44 delivers `V2-RULES-009` and the selected improvements to existing Files, MediaLibrary and
Rules journeys. Local tests do not replace whole-graph publication or execution checks. Stable
requirement IDs and acceptance meanings are unchanged; CURRENT details and exceptional discovery
recovery deferrals are recorded in Product Experience/Architecture. Suspended work is not accepted
delivery or an implicit dependency. Reference images define business/style, never runtime authority.

## Stable V2 requirements

| ID | Requirement | Acceptance meaning |
|---|---|---|
| V2-UX-001 | User experience is the primary product-design and acceptance criterion for V2 Operator Web journeys. | Normal operator journeys are Web-completable with task-oriented actions: no CLI fallback for an ordinary Web journey, no raw internal-token copy/paste as the final UX, no unnecessary implementation identifiers, and no repeated interaction without new human intent. |
| V2-UX-002 | Safety, authority and data-integrity controls must be delivered with the lowest practical operator friction. | Scope validation, capability checks, limits, authorization binding, short-lived/scoped execution authority where required and backend permission enforcement are automatically composed by the product wherever technically safe. Extra interaction occurs only at meaningful authority, ambiguity, uncertain-effect or irreversible/destructive boundaries. |
| V2-UX-003 | Implementation mechanisms must not define the operator journey. | Bearer tokens, execution tokens, revision IDs, locks, claims, checkpoints, grants or fencing mechanisms do not by themselves justify mandatory user exposure. They remain backend-authoritative and may be surfaced when useful for diagnosis/support, without weakening `V2-AUTH-*`, `V2-SAFE-*` or other authority requirements. |
| V2-WEB-001 | V2 Operator Web is a first-class product surface for the operator journeys selected by the active V2 program. | Required operator outcomes are delivered through a discoverable Web surface, not only through internal APIs or CLI commands. |
| V2-SETUP-001 | Native V2 Settings owns explicit first-Draft creation/resume and activation, reachable after authentication and from setup-required business pages. | Entry, refresh and reconnect restore existing state without creating another Draft; concurrent creation cannot duplicate setup roots. Viewer receives administrator guidance. Return refetches actual authority; broken prior Active is recovery, not first setup. |
| V2-SETUP-002 | First activation accepts a valid empty business baseline without mandatory media-business forms or generated policies. | An admin explicitly activates through normal validation and atomic runtime binding. Show `配置已激活，媒体业务尚未配置` and capability readiness; activation starts no media work or notification. Thereafter business pages retain exact Active-successor publication, applicable tests and their explicit authority boundaries. |
| V2-CONFIG-001 | Empty business families are valid configuration while populated objects retain structural and declared-dependency validation. | No Storage, libraries, Recognition types/rules/bindings, Metadata/Naming/Classification/Organize policies, Automation or Webhooks is required merely to activate. Malformed/dangling populated objects still fail; no development/default business objects fill gaps. Storage/strategy/destination evidence applies only to actual configured capabilities and enabled applicable bindings. |
| V2-CONFIG-002 | Settings shows labelled Active/Draft JSON and exports complete portable supported managed configuration without secret values or deployment authority. | Default to the exact runtime-consumed Active; no Active shows Draft/no-Draft, while corrupt Active remains explicit. Retain safe environment references, redact unsafe URL credentials, exclude database/principal/token startup authority, and bind validated imports to the receiving deployment. |
| V2-CONFIG-003 | Advanced Settings edits only backend-supported configuration absent from other management pages through the normal managed lifecycle. | Backend allowlists/schema reject arbitrary JSON fields, unknown/unconsumed settings and deployment database/identity changes. RBAC, audit, exact successor, validation and activation apply; deployment/restart-only values cannot be mislabelled as currently consumed. |
| V2-CONFIG-004 | Business readiness is command/scope-specific and separate from configuration validity or Active existence. | Incremental objects can publish while unrelated families remain empty. Missing/disabled/unavailable/unauthorized prerequisites have bounded reasons and recovery; missing media policies do not disable valid direct file operations. Admission/execution revalidate and preserve prior Active/input on failed publication. |
| V2-RULES-001 | V2 provides one discoverable organizing-rules workspace for the complete RecognitionType policy graph. | An administrator can manage Overview, type bindings, Recognition Types, Recognition Rules, Metadata Policies, Naming Policies, Classification Policies and Organize Policies through a native V2 journey. Each family opens as a complete full-width inventory with no editor/drawer selected; only an explicit `添加xx` action opens its create drawer, while existing Edit is an explicit full-page state. Supplied references govern structure/style only; their example data is never runtime or acceptance authority. |
| V2-RULES-002 | Rule-workspace `保存` is one page-level command that automatically validates and activates the exact successor candidate. | Read/navigation creates no Draft. Explicit Save composes the focused candidate from the exact Active snapshot, runs whole-document validation and applicable checks, then atomically publishes Active. There is no ordinary separate Save-Draft/Validate/Activate step; stale/failed/unknown Save preserves or verifies durable state without automatic resubmission. |
| V2-RULES-003 | RecognitionType and RecognitionRule editing exposes the production condition and resolution semantics. | Typed nested AND/OR/NOT conditions, compatible field/operator/value controls, priority, score, stop-on-match, ambiguity and bounded evidence match the backend engine. Unsafe regex and invalid values fail; list order does not invent a first-match algorithm. |
| V2-RULES-004 | RecognitionTypePolicy binds one enabled RecognitionType to Metadata, Naming, Classification and Organize policies without changing recognition identity. | Duplicate enabled bindings and missing/disabled references fail. Downstream policy reuse remains legal and explainable; RecognitionType C remains C when it uses another type's naming, classification or organize policies. |
| V2-RULES-005 | Metadata, Naming, Classification and Organize policies have purpose-built typed Web editors over the shared managed configuration authority. | Forms expose current domain fields and compatibility without inventing Provider switching, fallback or execution authority. Movie/TV templates remain distinct; classification selects MediaLibrary plus safe relative path; high-risk organize effects are explicit. |
| V2-RULES-006 | Rule and policy tests/previews are exact-revision, bounded, explainable and zero Storage mutation. | Recognition Strategy Test, Metadata test, Naming Preview, Classification Preview and Organize authority/whole-chain explanation identify the tested non-Active candidate, become stale after relevant edits, expose secret-free evidence and create no executable work or execution authority. Provider access occurs only through an explicit applicable test. |
| V2-RULES-007 | Object lifecycle, references and automatic Save/activation remain backend authoritative and consistent across Web/API/runtime consumers. | Create/copy/edit/enable-disable/reference-safe delete and page-level Save use audit, RBAC, optimistic concurrency, validation/applicable evidence and atomic activation shared services. Files Organize, Automation, API and CLI consume the same published semantics; the frontend never resolves or caches policy as authority. |
| V2-RULES-008 | Empty, partial, invalid and failed rule graphs provide actionable recovery. | Empty Active offers dependency guidance without generated defaults. Disabled/missing references, invalid conditions/templates/paths, Provider/secret failures, stale Save candidates, denied permission, malformed responses and automatic-activation failures state what is durable, whether Active changed and the explicit safe next action. |
| V2-RULES-009 | Each Rules editor's default offline test analyzes its current object and necessary inputs; complete-flow checks have a separate explicit entry. | RecognitionType definition is independent of rule conditions and downstream bindings; absent associated rules is inapplicable. A RecognitionRule test evaluates actual conditions and output type without resolving downstream policies, explains match/non-match with bounded condition evidence and never forces recognition. Binding/Metadata/Naming/Classification/Organize checks use only relevant dependencies. Local results, downstream readiness and full-flow outcomes remain distinct; synthetic identities are labelled and offline local tests call no Provider or Storage. Candidate/sample/context evidence stays exact and stale-aware; local passes cannot replace whole-graph publication, complete planning or execution authority. Existing complete Test Policy/DryRun remains available through native Web and shared backend behavior. Delivered within the accepted Slice 44 boundary. |
| V2-RUNTIME-001 | MediaFlow Worker starts and registers without Active and consumes later eligible work without restart. | Keep FileTransfer consumption resident; no valid authorized published context means no processing/mutation. Preserve supported command readiness, exact admitted pins, claims/leases/fences and per-item uncertainty recovery. Current Active governs new admission and does not replace older valid pins. |
| V2-RUNTIME-002 | Scheduler and Notification Worker remain resident through absent/empty/unavailable configuration and adopt current valid configuration without restart. | No eligible schedule means no Job; unavailable Active never uses cached schedules. No usable Webhook means no send or targetless claim; preserve target identity and delivery recovery without silent retargeting. Configuration read failures explain waiting while preserving process and durable state. |
| V2-STO-001 | Every provider-valid Storage root round-trips through typed Save, inventory, detail and Edit. | OpenList's empty root and `/` both represent its service root; render a clear provider-root label without dropping the row or rejecting the whole inventory. Existing saved empty-root entries remain readable. Other provider and Local confinement rules stay intact; failed list rendering never implies Save rollback or triggers automatic resubmission. |
| V2-AUTH-001 | During the current V2 program, the existing API-principal Bearer-token model and RBAC remain the identity/authentication and role/permission authorization boundary. | A scoped execution grant, execution unlock, step-up authorization or equivalent mutation-admission authority may be layered on top when required by an approved V2 journey, but it does not replace principal identity, authentication or RBAC. V2 does not silently introduce a new username/password identity system, OIDC integration, session or cookie authority. |
| V2-AUTH-002 | The API principal token remains memory-only in the browser during the current identity architecture. | The token is not persisted in `localStorage`, `sessionStorage`, IndexedDB, URLs/query strings or frontend-managed authentication cookies. |
| V2-AUTH-003 | Python remains the authoritative backend for domain behavior, execution authority and storage mutation. | Frontend code does not duplicate or move domain decisions, execution permission or Storage mutation out of the Python application; `OrganizerExecutor` remains the sole Storage mutator. |
| V2-MIG-001 | Existing `/api/v1/*` and shared application behavior remain authoritative during migration. | V2 UI and V1 UI use the same API semantics, validation, permissions, state transitions and safety gates. |
| V2-MIG-002 | V1 `/ui` and the V2 migration surface may coexist until parity and cutover acceptance. | The V1 UI remains available during migration, and a separate V2 entry is used until the approved cutover. |
| V2-SAFE-001 | Read-only V2 UI actions remain zero-side-effect. | A read, refresh or status view does not create Jobs/Tasks, invoke a Provider or mutate Storage unless a later explicitly approved journey says otherwise. |
| V2-SHELL-001 | V2 uses one shared reference-aligned operator shell across all V2 routes. | The light left rail/top bar in `docs/pics/文件页.png` replaces the earlier dark horizontal shell; Files does not create a parallel navigation model, existing route/auth/deep-link semantics remain shared, and non-Files business journeys remain functional inside the new chrome. |
| V2-FILES-001 | Files is a live-Storage ResourceLibrary browser and a complete common file-management surface. | An authorized operator can Create Folder/Text File, Rename, Copy, Move, Delete, Edit an allowlisted bounded text file, Upload and Download eligible files/directories, with bounded multi-selection where meaningful, without entering the media-organize policy pipeline. |
| V2-FILES-002 | Direct file management is low friction but backend authoritative. | A direct command needs no Organize Preview, recognition/metadata/naming/classification stages or raw execution token; it still enforces RBAC, explicit destructive/overwrite intent, Active ResourceLibrary confinement, Storage capability, stale/conflict checks, audit and `OrganizerExecutor`-only mutation. |
| V2-FILES-003 | Direct file operations preserve truthful state and bounded recovery. | Known success refreshes from live Storage; invalid path/name/content, unsupported capability, conflict, stale source, root/unbounded directory scope, transfer/verification failure, denied permission or uncertain effect remains item-specific and is never silently overwritten/deleted or automatically replayed. Copy/Move source media byte totals are informational rather than admission limits; boundedness is enforced through selection, entry/depth/path and bounded control-plane evidence. |
| V2-FILES-004 | ResourceLibrary configuration can be edited from its selected Files card without exposing managed-lifecycle mechanics. | ID stays immutable; name, enabled state, Storage and source root are prefilled and saved through exact-Active optimistic concurrency, field-preserving merge, complete validation and checked atomic activation. Storage contents are never migrated by the edit, and failures retain the prior Active and correctable input. |
| V2-DEPLOY-001 | Production remains operable without a Node runtime server. | Node may build the frontend, while the existing Python/MediaFlow application serves the built static assets and API. |
| V2-DEPLOY-002 | Fresh Compose requires only management bootstrap, durable data and deployment-owned administrator credentials, with distinct process, infrastructure and work readiness. | No mandatory media mount; configured Local Storage still requires explicit mounts/permissions. Waiting for first configuration is normal resident state, not false Scheduler/notification readiness. DB/schema/heartbeat and Active/pin/secret failures are distinct, fail closed and retain safe recovery; health checks have no media/provider/delivery side effects. |
| V2-MIG-003 | Final V1 UI retirement requires explicit parity and cutover acceptance. | `/ui` is not removed merely because a V2 route or partial migration exists; parity, accessibility and migration evidence are required first. |

## MediaLibrary requirements — delivered baseline and editing

| ID | Requirement | Acceptance meaning |
|---|---|---|
| V2-MEDIALIB-001 | MediaLibrary file management browses the real contents of an Active destination library through its configured Storage and root. | Physical membership is live Storage truth, independent of FileIndex, metadata or prior organization. Exact relative paths, bounded navigation/search/paging and truthful refresh/recovery are required; page entry starts no processing. |
| V2-MEDIALIB-002 | MediaLibrary offers bounded common file maintenance without the media Organize journey. | Create Folder/Text, single Rename, Copy, Move, Delete and allowlisted text Edit share backend RBAC, kind-specific library confinement, capability/stale/conflict checks, explicit destructive intent, OrganizerExecutor mutation and durable per-item recovery. Equal IDs or reused evidence cannot exchange MediaLibrary and ResourceLibrary authority. |
| V2-MEDIALIB-003 | Adding/editing/removing MediaLibrary configuration is a complete Web/API journey using actual managed runtime authority. | Page-local create/edit Save validates and atomically activates a successor; edit keeps ID immutable, preserves unexposed fields and rejects stale writers. Failures preserve Active and correctable input. Disabled libraries have a Web re-enable path; Storage/root edits and reference-protected removal never move or delete physical files. |
| V2-MEDIALIB-004 | Files and MediaLibrary have distinct navigation identities while sharing suitable presentation and file-operation mechanisms. | Route changes preserve Files capabilities, Organize return context, authentication and other journeys. MediaLibrary follows its reference with type icons and without card statistics/placeholders, thumbnails or Organize actions; row sizes and bounded selection/operation summaries remain available. |

## Operations and Tasks requirements — delivered baseline (Slice 42 PASS / CLOSED)

These requirements extend the existing Operations foundation and are delivered within Slice 42's
accepted boundary. CURRENT behavior and explicit deferrals are documented in Architecture and
Product Experience. Task-linked recovery is delivered; cross-Task recovery lists were deferred by
that baseline and are selected separately by the Slice45 TARGET amendment below.
This factual status update does not change the stable requirement IDs or acceptance meaning below.

| ID | Requirement | Acceptance meaning |
|---|---|---|
| V2-OPS-001 | One native V2 task center presents a reference-aligned inventory, summary, filters and selected-run detail/records. | Default entry has no open detail; selection/deep link opens it. Shared shell, narrow/keyboard use, bounded return context and existing Task/Job links work without hard-coded reference data. |
| V2-OPS-002 | Unified runs preserve the distinct Job/Task/item/Result model while showing one explicitly linked admission/processing run once. | Pending/pre-Task failure and standalone Tasks are visible. Queue completion cannot overwrite the Task outcome. Automation occurrences and recovery attempts retain independent linked history; all existing command families remain discoverable. |
| V2-OPS-003 | Search, status/kind/time filters, counts and paging are bounded and authoritative on the server. | Cards and filtered totals use one authorized population and consistent read basis; cursors bind to query/authorization context. Attention is a labelled overlapping facet. No frontend page-only totals, fabricated pages or unavailable-as-zero. |
| V2-OPS-004 | Names/scopes and progress reflect durable historical evidence rather than current configuration or approximate UI inference. | Preserve admission/pinned context or label missing legacy evidence. Known item counts reconcile; unknown totals stay indeterminate; scan errors/attachment steps are separate; Preview, waiting, ignored and uncertain outcomes are not organize success. |
| V2-OPS-005 | Task detail connects per-item explanations, durable operation/results, relevant audit/logs and secret-free JSON export. | Source/target, recognition/policies, completed steps, failure/effect certainty and next action remain independently inspectable. Logs supplement results; records and exports are task-scoped and clearly bounded. |
| V2-OPS-006 | New manual organization completes through live ResourceLibrary file selection, exact Preview, explicit execution and the selected durable run. | Reuse Files authority and return context for single/bounded multiple files. MediaLibrary is not a new organize source; FileIndex cannot authorize physical selection. Stale/unknown admission never silently resubmits. |
| V2-OPS-007 | Task controls and continuation are backend-authoritative, cooperative and Web-completable for supported paused asynchronous work. | Pause/cancel requests do not undo effects or interrupt in-flight calls. Continue queues the exact remaining safe scope with pins/fences and current authority; no CLI fallback, consumed-token reissue, revoked-grant bypass or successful/uncertain replay. |
| V2-OPS-008 | Task-linked decisions and single/bounded failed-analysis recovery complete in native V2 with per-item safety. | Recognition, Metadata, Classification and conflict decisions use existing gates; saving decisions does not execute. Exact analysis/Preview and separate execution intent link back to the original item. Mixed selections preserve accepted/refused outcomes; uncertain mutation stays investigation-only and retired retry APIs stay retired. |

## Operations and Tasks redesign — TARGET (Slice 45)

The user-approved 2026-10-15 amendment extends the accepted baseline without claiming implementation.
The final journey and nine reference images are in [task-center-page-spec.md](task-center-page-spec.md).
It supersedes the mandatory separate Preview-page realization of `V2-OPS-006/008` and the former
standalone Scan-entry obligation; exact zero-mutation plans, explicit execution authority and all
`V2-AUTH-*` / `V2-SAFE-*` requirements remain unchanged. The user-approved 2026-10-18 prelaunch
amendment removes only old standalone-Scan settlement/migration and dedicated historical compatibility
obligations: there are no production users or old production Scan jobs. Supported-work history and
frozen accepted facts remain intact. The subsequent user-approved FileIndex amendment below adds
complete retirement and CLI/Web live-list parity to the same Slice45.

| ID | Requirement | Acceptance meaning |
|---|---|---|
| V2-OPS-009 | Task Center provides nine sibling list pages, including cross-Task recovery by problem type. | All/running/attention/ended and Recognition/Metadata/Classification/conflict/failure lists share one horizontal navigation row. Recovery lists group one Task per type with affected-file counts across the complete authorized population; tasks may belong to several views. Queries/counts/paging are server-authoritative, pending membership uses current problems rather than page-only filtering or blanket Pending status, and read/refresh/navigation has no work/Provider/Storage side effects. |
| V2-OPS-010 | Organization creation first shows an exact plan summary in the current interface and then explicitly confirms its eligible selected scope. | Live ResourceLibrary file/folder selection uses bounded discovery, stability, production policy/planning and attachment behavior. Show source, completeness, ready/unready items, operations, destination, per-item effects/conflicts and destructive impacts. Preparation is zero-mutation and grants no execution authority; confirmation binds exact plans/sources/pins/subset and separately permitted effects atomically. Unselected/unready state remains independent; incomplete material bounds cannot execute a first-N prefix. Stale/unknown submission reconciles without automatic replay. No separate Preview page/action is required or offered inside the organizing journey. |
| V2-OPS-011 | Standalone Scan is completely retired as a product while shared internal discovery and stability remain. | Remove its Web/API/CLI admission, standalone executable/retry/continuation paths and exclusive code; no hidden diagnostic alias or compatible executor. Under the user-approved prelaunch amendment, do not build old standalone-Scan settlement, takeover, upgrade migration or dedicated history/detail/cancel/export compatibility. Retired requests receive a bounded refusal directing to new organization; they never discover, execute or convert into organizing authority. This does not authorize media/runtime-data deletion or weaken other supported Task/Result/pin/audit/non-replay safety. Organization/Automation dependencies complete observations internally; shared Scanner/filtering/stability and general DryRun/Rules tests remain. Complete FileIndex retirement is selected separately in the same Slice by V2-FILES-005/006; definition-bound Automation mode retirement remains owned by its frozen Contract. |
| V2-OPS-012 | Recovery lists lead to native task/type-scoped file processing with integrated analysis, plan summary and explicit continuation. | Recognition, Metadata candidate/correction, Classification, conflict and failure use current legal backend choices/checkpoints and appropriate correctable forms. Save/analysis does not mutate media or confer execution authority; fresh mutation is confirmed against the in-context exact summary without a separate Preview route or operator-managed DryRun task. Pending lists/counts follow durable per-item resolution while retaining history, return context and successful siblings. Uncertain effects stay investigation-only; existing bounded within-Task analysis recovery preserves independent outcomes, with no new cross-Task bulk mutation. |

For V2-OPS-012, the failure journey must expose the failed stage, source/target, completed steps,
effect certainty and permitted action per file/attachment. Repair dependencies or save a legal
decision, explicitly re-analyze the allowed scope, handle any new blocker, then review the in-context
summary and confirm the eligible selected subset. Admission/running is not resolution; membership
follows current durable problems, recovery attempts retain independent history, and a repeated
failure explains its new cause and next step. Dependency repair never silently repins old work to
new Active; unavailable pinned context refuses continuation with guidance. Unknown confirmation
responses reconcile the exact durable request; uncertain effects have evidence/investigation only,
and preparation-only unready items are not fabricated execution failures.

## FileIndex retirement and shared live lists — TARGET (Slice45)

The user-approved 2026-10-18 amendment adds complete FileIndex retirement to current Slice45.
It supersedes V1 global indexing, FileIndex catalog/detail/statistics, automatic result sync and
optional indexed Files feedback; it preserves supported Task/Result/pin/audit/permission/source
safety and actual internal stability. [The retirement design](file-index-retirement-spec.md)
defines the CLI and end-to-end journey. No implementation is claimed.

| ID | Requirement | Acceptance meaning |
|---|---|---|
| V2-FILES-005 | CLI `mediaflow files list`, ResourceLibrary Files and MediaLibrary browsing share library-scoped live Storage listing without recording a file catalog. | Resolve the same Active library kind/ID/root and bounded relative directory/cursor through shared application behavior. Preserve exact names, supported entry types, path confinement, kind-separated cursors, bounded/unknown totals and actionable errors. List/refresh/paging creates no file/observation records, Tasks/Jobs/Results, execution authority, Provider/Hash calls or media mutations; it never falls back to an index. Explicit subsequent work retains its required durable records. |
| V2-FILES-006 | FileIndex fully exits the product and all runtime consumers under the prelaunch boundary. | Remove indexed CLI/API/UI/reprocess/statistics, global file-directory/occurrence/disposition persistence, repositories/stand-ins, dedicated schema, initialization, sync/repair paths and dead code. Fresh supported deployments and every supported CLI/API/Worker/discovery/organize/recovery/Automation foundation work without FileIndex; do not hide or rename it or substitute a no-op/global cache. Exact work-scoped source/plan/pin/stability/results, locks and completed/uncertain non-replay stay authoritative. No old FileIndex production migration, dual write, historical FileID/API or takeover compatibility is required; do not clear existing runtime data/media. Necessary shared dependency removal does not implement frozen Automation business features. |

## Automation workspace requirements — TARGET (Slice 43)

Slice43 is frozen by user request (2026-10-15). Its unchanged business Contract is preserved at
`ed974e0df8b263f631bfe48b524da461013d8780:SLICE.md` on `frozen/slice-43-2026-10-15`.
These retained Automation targets are not inherited by Slice45 or a delivery claim. Slice45's
ACTIVE Contract separately owns the task-center redesign, standalone Scan retirement and integrated
manual plan-summary journey; Slice43 remains frozen.

The existing Automation/Settings foundations remain CURRENT. The following complete workspace
journey is TARGET, selected from `docs/pics/自动化.png` and `docs/pics/自动化-全局设置.png` for business
logic and visual style only. Activation is not a delivery claim; the preserved Slice43 Contract owns its bounded scope.

| ID | Requirement | Acceptance meaning |
|---|---|---|
| V2-AUTO-001 | One native Automation workspace provides definition inventory, execution records and global settings in the shared shell. | Real data, bounded server search/filter/sort/paging, responsive/keyboard/deep-link use and actionable empty/denied/error states replace reference fixtures; every authorized definition is reachable. |
| V2-AUTO-002 | Definition lifecycle uses typed forms and one focused checked Save to publish the intended automatic-organization successor. | There is no mode selector or conversion action. Create/copy/edit/enable/disable/reference-safe remove retain whole-document validation, applicable evidence, RBAC, audit and optimistic concurrency without publishing sibling Draft edits. Published, enabled, authorized and running states remain distinct; copy starts disabled without authority and removal preserves history. |
| V2-AUTO-003 | Exact zero-media-mutation Preview and explicit scoped revocable unattended authority complete in native V2. | Preview never grants permission; broadened scope cannot inherit insufficient authority. Valid due runs need no further per-run click but retain pinned configuration, normal per-item planning and current authority/capability/conflict checks. |
| V2-AUTO-004 | Run once performs automatic organization from a published definition's bounded source/limit without changing its schedule. | Automatically discover eligible live sources and freeze the complete bounded manifest; no file picking in the normal journey. Exact Preview and separate explicit one-shot execution remain required. The effective bound is the smaller of the definition ceiling and the existing 100-primary manual/discovery limit. Overflow/incomplete discovery refuses execution with scope-narrowing, publication and fresh discovery/Preview recovery; never silently truncate to first N. Empty scope reports no work; changed scope/sources require fresh evidence and intent. Disabled schedules can run manually with current permissions. Scheduled grants are not manual permission. Durable origin links, principal-scoped reconciliation and atomic admission prevent duplicate work or authority consumption. Legacy scan/plan definitions cannot admit new runs. |
| V2-AUTO-005 | Cross-definition history and metrics use durable run links and truthful current or historical outcomes. | Job/Task/execution count once; pre-Task failures remain visible, standalone diagnostic/grant-preflight Previews, discovery alone and rejected admissions are not runs. Previously admitted scan/plan runs retain their historical mode and count once against that mode's outcome; they are never relabelled as organization. Partial/waiting/uncertain states are not successful organization. Server-calculated windows/timezone/denominators, labelled no-work outcomes and missing-data states are truthful; historical context survives definition edits/removal. |
| V2-AUTO-006 | Automation history reaches existing native Operations result, control and per-item recovery behavior with return context. | Bound reached does not imply source exhaustion; original/continuation/sibling outcomes remain traceable. Successful/uncertain effects are not replayed, and no second task/recovery engine is introduced. |
| V2-AUTO-007 | Global Automation settings use the shared managed authority and truthful operational meanings. | Activity capacity bounds pending plus running Jobs in the shared pool, not execution parallelism. Stale age detects lack of durable updates, not total runtime or permission to requeue. Four-field checked Save preserves unrelated settings/Drafts and uses backend validation, not reference example ranges. |
| V2-AUTO-008 | Settings consumption is proved by the actual eligible runtime consumers. | Resident Worker/Scheduler adopt configured polling changes at safe boundaries without routine restart, including idle/long-wait transitions. Fresh consumer values/version distinguish published/adopted/pending/override/unavailable; API binding alone is insufficient. CLI overrides, heartbeats/fences and admitted pipeline pins remain authoritative. |
| V2-AUTO-009 | Automation supports automatic organization only; the other two modes are entirely removed. | Remove scan-only/scan-and-plan mode values/aliases, selectors and definition-bound publication, scheduling/admission/execution branches across Web/API/CLI. No legacy-mode inventory, conversion feature, grandfathering or compatible old-mode executor is required or permitted. Unsupported old configuration/work fails closed with existing correction/removal/cancel/history guidance. Preserve recorded intent, pins, results and audits as read-only historical data; never reinterpret it as organizing authority or replay completed/uncertain effects. That amendment itself retains internal analysis and diagnostic Preview/DryRun; the subsequent V2-OPS-010–012 target separately retires standalone Scan and integrates organization's Preview UI. User-approved Automation amendment and clarification dated 2026-10-13; previous V1 acceptance and safety invariants remain historical facts. |

## Authority and evolution

The complete canonical V1 definition and stable IDs in [requirements.md](requirements.md) remain
the product baseline. V2 uses
operator goals and the UX requirements above to shape interaction while preserving every existing
correctness, security, authority and data-integrity invariant. Each active Slice contract may refine
its V2 surface and architecture within these boundaries, and a
future Slice may add stable requirements through an explicit A-owned documentation change. Task files
must not silently expand this V2 layer.

React, TypeScript, Vite, TanStack Router, TanStack Query, testing tools and the feature-first source
tree are adopted Slice 30 architecture decisions. They are intentionally not encoded as permanent
product requirements here; the Python runtime, authority, authentication, coexistence and cutover
boundaries are.

## UI-V2 Files Contract — 2026-09-14

The bullets below retain the accepted historical baseline. Slice45's later `V2-FILES-005/006`
TARGET explicitly supersedes their FileIndex display/synchronization/compatibility allowances;
they do not authorize retaining an index after that outcome is implemented and accepted.

- UI-V2 Files exposes ResourceLibrary as the first-level business object.
- Files browsing is ResourceLibrary-scoped and backed by live Storage reads.
- UI-V2 Files requests use `resourceLibraryId` plus ResourceLibrary-relative `path`; browser-supplied `storageId` and arbitrary Storage paths are not authority.
- FileIndex catalog/detail journeys are not ordinary UI-V2 user routes.
- Files entries must not expose FileIndex membership, `fileId`, occurrence IDs, fingerprints, claim
  tokens or plan hashes as ordinary page authority. A bounded recognition/business-status projection
  may be shown as display feedback when available; missing feedback must not hide or rewrite the live
  Storage entry.
- Manual organize Preview admission from UI-V2 Files uses `resourceLibraryId` and `relativePath`; the server creates SourceIdentity and OrganizePlan.
- The UI-V2 Files path is FileIndex-independent for physical listing and organize Preview. The
  server resolves the Active ResourceLibrary/Storage binding and derives source identity from live
  Storage; it does not re-resolve the selected path through FileIndex. FileIndex may be consulted
  only for the bounded display feedback projection.
- The `+ 添加资源库` action creates a ResourceLibrary. Its final `保存` action submits one complete
  candidate; the backend bases it on the current Active configuration, runs the existing validation
  and checked-activation flow internally, and publishes a new immutable Active runtime only on
  success. Any error rejects the save and preserves the previous Active runtime.
- Every terminal Organize item automatically synchronizes its known outcome to FileIndex after the
  OrganizerExecutor result is recorded. A synchronization failure is an independent durable
  recovery state and never authorizes replay of an uncertain Storage mutation.
- Browsing, selection, ResourceLibrary configuration and Preview admission must not otherwise
  introduce a FileIndex dependency.
- The current Slice 37 Files surface exposes Create Folder/Text File, Rename, Copy, Move, Delete and
  allowlisted bounded text Edit. Direct browser Upload/Download controls, routes, services and
  projections are outside the current delivery boundary; generic Storage/provider transfer
  primitives remain available for supported backend workflows. The page does not render
  recognition-result or organize-status feedback; its live entry names, breadcrumb paths and
  current directory path preserve exact Storage identity, including boundary whitespace, and
  visibly disambiguate that whitespace.
- Direct file commands do not run the media Organize pipeline or require its Preview/execution-token
  ceremony. Conflicts default to no overwrite, Delete requires one explicit permanent-effect
  confirmation, and Replace/Edit Save are explicit overwrite intents bound to current Storage state.
- Bounded selection and bounded directory recursion preserve per-item outcomes. Same-Storage
  operations require advertised native capability; cross-Storage Copy is explicit, and cross-Storage
  Move is an explicit Copy/verify/Delete-source compound operation that never deletes the source
  after failed verification and never masquerades as a fallback.
- Unbounded recursion and arbitrary binary/media editing remain outside this requirement. Any future
  browser transfer surface must preserve the same bounded, backend-authoritative and
  OrganizerExecutor-only safety boundary.
- A known direct-operation result may reconcile bounded FileIndex display state after Storage
  outcome is recorded. FileIndex does not authorize the operation, and reconciliation failure does
  not replay it.
- FileIndex-backed compatibility and legacy operation paths may remain elsewhere in the product,
  but they are not valid physical-listing, source-identity or execution dependencies of the
  ResourceLibrary Files page. The bounded display-feedback exception and terminal-result
  synchronization above are the only permitted Files-page uses.

## UI-V2 Files Visual Contract — 2026-09-14

- The sole visual reference is [`docs/pics/文件页.png`](pics/文件页.png) at `1536 x 1024`.
- The exact page composition, copy, data fixture, drawer state and screenshot acceptance are
  defined in [`file-page-visual-spec.md`](file-page-visual-spec.md).
- The reference left navigation rail and top bar replace the previous dark horizontal V2 shell
  through the single shared shell used by every V2 route. This is not a Files-only alternate shell.
- This visual contract does not move authority into the frontend or make FileIndex a source or
  execution authority. Focused backend behavior for direct file commands, ResourceLibrary
  save/activation and post-mutation reconciliation is part of the confirmed Files journey.
- Under the closed Slice 37 visual boundary, non-Files business features and routes were preserved
  while their shared shell changed. Slice 38's explicit MediaLibrary requirements above now
  authorize that page and its route integration while preserving the Files body.
