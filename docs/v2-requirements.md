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
Most recently closed large Slice: Slice 37 — Files Workspace, Common File Management and V2 Shell — PASS / CLOSED
Slice 37 Base: b507edba167f5af3af8c53bfcf1417ba4fefddf4
Slice 37 Implementation Head: aa54854c442d117c7eb23ae9800045c423db1368
Slice 37 A Final Review: PASS / CLOSED — 2026-09-23
Active large Slice: none — A selects the next large Slice after Slice 37 closure
```

The current V2 package version and implementation status are governance metadata, not stable
product requirements. Slices 30, 31, 32, 33 and 37 are closed. Slice 37 replaced the prior V2
shell presentation and completed the Files workspace. The previously planned Slice 34–36 boundaries
are retired from the current Roadmap; their historical references remain historical and do not change
the stable requirements layer. The stable common-file-management target retains its broader future
capability set; the current Slice 37 delivery boundary explicitly excludes direct browser
Upload/Download and does not claim those surfaces as delivered.

## Stable V2 requirements

| ID | Requirement | Acceptance meaning |
|---|---|---|
| V2-UX-001 | User experience is the primary product-design and acceptance criterion for V2 Operator Web journeys. | Normal operator journeys are Web-completable with task-oriented actions: no CLI fallback for an ordinary Web journey, no raw internal-token copy/paste as the final UX, no unnecessary implementation identifiers, and no repeated interaction without new human intent. |
| V2-UX-002 | Safety, authority and data-integrity controls must be delivered with the lowest practical operator friction. | Scope validation, capability checks, limits, authorization binding, short-lived/scoped execution authority where required and backend permission enforcement are automatically composed by the product wherever technically safe. Extra interaction occurs only at meaningful authority, ambiguity, uncertain-effect or irreversible/destructive boundaries. |
| V2-UX-003 | Implementation mechanisms must not define the operator journey. | Bearer tokens, execution tokens, revision IDs, locks, claims, checkpoints, grants or fencing mechanisms do not by themselves justify mandatory user exposure. They remain backend-authoritative and may be surfaced when useful for diagnosis/support, without weakening `V2-AUTH-*`, `V2-SAFE-*` or other authority requirements. |
| V2-WEB-001 | V2 Operator Web is a first-class product surface for the operator journeys selected by the active V2 program. | Required operator outcomes are delivered through a discoverable Web surface, not only through internal APIs or CLI commands. |
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
| V2-DEPLOY-001 | Production remains operable without a Node runtime server. | Node may build the frontend, while the existing Python/MediaFlow application serves the built static assets and API. |
| V2-MIG-003 | Final V1 UI retirement requires explicit parity and cutover acceptance. | `/ui` is not removed merely because a V2 route or partial migration exists; parity, accessibility and migration evidence are required first. |

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
- Non-Files business features and routes remain outside the current Roadmap focus, but their shared
  shell pixels intentionally change and must remain functionally compatible.
