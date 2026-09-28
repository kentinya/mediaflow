# MediaFlow V2 Stable Requirements

This document is the stable V2 requirements layer for the active Operator Web migration. It
extends the frozen V1 requirements baseline without renumbering or reinterpreting any `REQ-*` or
`UX-*` entry in [`requirements.md`](requirements.md). Slice-specific architecture and proof details
remain in [`SLICE.md`](../SLICE.md) and the architecture document; this file records only durable
product and authority boundaries.

## Current program boundary

```text
V1: RELEASED / MAINTENANCE — 1.0.0 — v1.0.0 — release/v1
V2: ACTIVE DEVELOPMENT — main — package 2.0.0.dev0
Most recently closed large Slice: Slice 40 — V2 Settings and Empty-Baseline Startup — PASS / CLOSED
Slice 40 Base: d814b7c1c6819e79271245a1126f53aca6aeaf69
Slice 40 Implementation Head: 7805fa09d540fdeb5f0b39a5e3ac39c8c5ff7bb7
Slice 40 A Final Review: PASS / CLOSED — 2026-09-28
Current Contract: Slice 41 — V2 Organizing Rules Workspace — ACTIVE
Slice 41 Base: 8a6a15597bab2fd10673db84d73a5bbc1d455ad8
Slice 41 Implementation Head: not yet set
Next action: checkpoint the A-owned Contract and Roadmap, then B plans the first coherent Task
```

The current V2 package version and implementation status are governance metadata, not stable
product requirements. Slices 30, 31, 32, 33 and 37–40 are closed; Slice 41 is active. Slice 37
replaced the prior V2 shell presentation and completed the Files workspace. The previously planned Slice 34–36 boundaries
are retired from the current Roadmap; their historical references remain historical and do not change
the stable requirements layer. The stable common-file-management target retains its broader future
capability set; the current Slice 37 delivery boundary explicitly excludes direct browser
Upload/Download and does not claim those surfaces as delivered.
Slice 38 has implemented the MediaLibrary workspace, route-separation baseline and focused
page-local editing requirements through its reviewed implementation head. Slice 39 has implemented
the Storage management workspace, provider-root/setup recovery and admitted-transfer Worker
continuity/readiness through its reviewed implementation head. Slice 40 has implemented native V2
Settings, legal empty-business activation, conditional configuration applicability, command-specific
readiness and resident-service adoption without mandatory media mounts or restart. Slice 41 is the
active TARGET for the native V2 organizing-rules workspace. Its five supplied page images describe
business relationship and visual style, not actual production data or pixel-identical fixtures. The
stable requirements below describe delivered boundaries and explicitly identified targets; Slice
contracts own implementation scope and acceptance.

The setup, empty-business configuration and resident-service requirements below are delivered Slice
40 behavior. They replace the former mandatory Storage/library/policy setup wizard and the proposal
for business pages to save first-setup Drafts without Active. The V1 setup handoff remains available
during migration; earlier closed Slice scope is unchanged.
`V2-STO-001` makes existing provider-valid root semantics explicit across Web surfaces.

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
| V2-RULES-001 | V2 provides one discoverable organizing-rules workspace for the complete RecognitionType policy graph. | An administrator can manage Overview, type bindings, Recognition Types, Recognition Rules, Metadata Policies, Naming Policies, Classification Policies and Organize Policies through a native V2 journey. Supplied references govern structure/style only; their example data is never runtime or acceptance authority. |
| V2-RULES-002 | Rule-workspace edits use one exact successor Draft and explicit whole-revision publication. | Read/navigation creates no Draft. Object Save changes only the labelled Draft; Active remains the immutable runtime-consumed snapshot until explicit checked activation succeeds. Stale/failed/unknown publication preserves or verifies durable state without automatic resubmission. |
| V2-RULES-003 | RecognitionType and RecognitionRule editing exposes the production condition and resolution semantics. | Typed nested AND/OR/NOT conditions, compatible field/operator/value controls, priority, score, stop-on-match, ambiguity and bounded evidence match the backend engine. Unsafe regex and invalid values fail; list order does not invent a first-match algorithm. |
| V2-RULES-004 | RecognitionTypePolicy binds one enabled RecognitionType to Metadata, Naming, Classification and Organize policies without changing recognition identity. | Duplicate enabled bindings and missing/disabled references fail. Downstream policy reuse remains legal and explainable; RecognitionType C remains C when it uses another type's naming, classification or organize policies. |
| V2-RULES-005 | Metadata, Naming, Classification and Organize policies have purpose-built typed Web editors over the shared managed configuration authority. | Forms expose current domain fields and compatibility without inventing Provider switching, fallback or execution authority. Movie/TV templates remain distinct; classification selects MediaLibrary plus safe relative path; high-risk organize effects are explicit. |
| V2-RULES-006 | Rule and policy tests/previews are exact-revision, bounded, explainable and zero Storage mutation. | Recognition Strategy Test, Metadata test, Naming Preview, Classification Preview and Organize authority/whole-chain explanation identify the tested Draft, become stale after relevant edits, expose secret-free evidence and create no executable work or execution authority. Provider access occurs only through an explicit applicable test. |
| V2-RULES-007 | Object lifecycle, references and activation remain backend authoritative and consistent across Web/API/runtime consumers. | Create/copy/edit/enable-disable/reference-safe delete, audit, RBAC, optimistic concurrency, validation/applicable evidence and atomic activation reuse shared services. Files Organize, Automation, API and CLI consume the same published semantics; the frontend never resolves or caches policy as authority. |
| V2-RULES-008 | Empty, partial, invalid and failed rule graphs provide actionable recovery. | Empty Active offers dependency guidance without generated defaults. Disabled/missing references, invalid conditions/templates/paths, Provider/secret failures, stale Drafts, denied permission, malformed responses and activation failures state what is durable, whether Active changed and the explicit safe next action. |
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

## Authority and evolution

The V1 canonical specification and stable V1 requirements remain the product baseline. V2 uses
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
