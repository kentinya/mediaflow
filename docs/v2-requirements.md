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
Most recently closed large Slice: Slice 33 — Operations Workspace — PASS / CLOSED
Slice 33 Base: 827c36b410687e41b1da53ba6475d8c03a47dbfd
Slice 33 Implementation Head: e4a5f7696d1742f7b6ef2a784c3b5d234b707d08
Active large Slice: Slice 37 — Files Page Visual Fidelity
Slice 37 Base: b507edba167f5af3af8c53bfcf1417ba4fefddf4
```

The current V2 package version and implementation status are governance metadata, not stable
product requirements. Slices 30, 31, 32 and 33 are closed. Slice 37 is the current focused Files
page effort. The previously planned Slice 34–36 boundaries are retired from the current Roadmap;
their historical references remain historical and do not change the stable requirements layer.

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

## UI-V2 Files Contract — 2026-09-13

- UI-V2 Files exposes ResourceLibrary as the first-level business object.
- Files browsing is ResourceLibrary-scoped and backed by live Storage reads.
- UI-V2 Files requests use `resourceLibraryId` plus ResourceLibrary-relative `path`; browser-supplied `storageId` and arbitrary Storage paths are not authority.
- FileIndex catalog/detail journeys are not ordinary UI-V2 user routes.
- Files entries must not expose FileIndex membership, fileId, scan status, occurrence IDs, fingerprints, claim tokens, or plan hashes.
- Manual organize Preview admission from UI-V2 Files uses `resourceLibraryId` and `relativePath`; the server creates SourceIdentity and OrganizePlan.
- The UI-V2 Files path is FileIndex-independent for both display and organize Preview. The server
  resolves the Active ResourceLibrary/Storage binding and derives source identity from live
  Storage; it does not re-resolve the selected path through FileIndex.
- FileIndex-backed compatibility and legacy operation paths may remain elsewhere in the product,
  but they are not valid dependencies of the ResourceLibrary Files page.

## UI-V2 Files Visual Contract — 2026-09-14

- The sole visual reference is [`docs/pics/文件页.png`](pics/文件页.png) at `1536 x 1024`.
- The exact page composition, copy, data fixture, drawer state and screenshot acceptance are
  defined in [`file-page-visual-spec.md`](file-page-visual-spec.md).
- This visual contract narrows the current implementation focus only; it does not add a new API,
  persistence model, FileIndex authority or mutation path.
- Non-Files pages and their existing routes remain outside the current Roadmap focus and unchanged.
