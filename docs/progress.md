# MediaFlow Slice Closure Ledger

This file is the compact large-Slice ledger. Git retains detailed Task and review history. The full
pre-migration Progress log is preserved as
[legacy read-only history](history/progress-legacy-2026-08-29.md); it is evidence, not current
workflow authority. Closure rules live only in
[the development workflow](development-workflow.md).

## Current development pointer

V2 remains active on `main`. Slice 38 — **MediaLibrary Files Workspace and Route Separation** —
is `PASS / CLOSED` under [`SLICE.md`](../SLICE.md) after A's 2026-09-25 review from Base
`9e801ae4485bc95d714a8902bf45bf37896fbc2a` through Implementation Head
`7d4503e45dc3aa79628ed0d98e887167e1e7c529`. The reviewed delivery includes focused
ResourceLibrary/MediaLibrary page-local editing with checked atomic activation. There is no active
implementation Task; A selects the next large Slice in a later planning turn. Slice 37
remains `PASS / CLOSED` after A's 2026-09-23 review through
`aa54854c442d117c7eb23ae9800045c423db1368`; its complete Contract/final review is retained at
`9e801ae4485bc95d714a8902bf45bf37896fbc2a:SLICE.md` in Git. This pointer records current
post-closure state and is not a Task history log.

Slice 37 closure record (2026-09-23): delivered the shared V2 shell, live ResourceLibrary Files
workspace, bounded common file management, safe Organize continuation, formal `library/path`
parity, truthful refresh and exact Storage path identity, plus RecognitionType-driven Web policy
binding. Direct browser Upload/Download, arbitrary media editing, unbounded operations, new
providers/identity systems, universal rollback and automatic uncertain replay remain deferred.

A post-closure backend-governance maintenance change retires the obsolete direct file
re-recognition, metadata re-match, file re-plan and recognition-review retry surfaces across the
CLI, Web UI and `/api/v1`, while retaining review resolution, metadata continuation and explicit
Task retry/recovery paths. This maintenance does not reopen Slice 33 or create an active Task.
At that historical checkpoint the next legal action was A selecting the next large Slice.

A follow-up current-source execution alignment imports the `/opt/mediaflow` manual Organize
correction while preserving the retired retry-surface cleanup on `main`: exact Previews persist the
reviewed Storage ID, source path and Storage-derived source fingerprint, and the Worker executes by
opening that Storage and calling `stat(source_path)` directly. If the source is missing or the live
fingerprint differs from the Preview fingerprint, execution fails closed before mutation; routine
FileIndex rescans no longer cause execution to re-resolve `file_id -> FileIndex -> path`. Conflicting
legacy tests that asserted FileIndex-driven staleness were removed or converted to scanner-backed
current-source fixtures. This maintenance does not reopen Slice 33 or create an active Task. The next
legal action at that historical checkpoint was A selecting the next large Slice.

## Most Recently Closed Slice

V1 release baseline: `1.0.0`. V2 program package: `2.0.0.dev0`.

### Slice 38 — MediaLibrary Files Workspace and Route Separation

```text
Status: PASS / CLOSED
Base: 9e801ae4485bc95d714a8902bf45bf37896fbc2a
Implementation Head: 7d4503e45dc3aa79628ed0d98e887167e1e7c529
A Final Review: PASS / CLOSED — 2026-09-25
```

Delivered separate MediaLibrary and ResourceLibrary Files routes, live MediaLibrary browsing,
bounded common file maintenance and transfer recovery, reference-aligned presentation and
symmetric exact-Active page-local library editing with checked atomic activation. Deferred scope
remains card statistics/capacity/placeholders, thumbnails, MediaLibrary Scan/Preview/Organize,
browser Upload/Download, cross-kind direct transfers, transfer Replace mode, ID migration, broad
configuration redesign, V1 cutover, universal rollback and automatic uncertain replay.

### Slice 37 — Files Workspace, Common File Management and V2 Shell

```text
Status: PASS / CLOSED
Base: b507edba167f5af3af8c53bfcf1417ba4fefddf4
Implementation Head: aa54854c442d117c7eb23ae9800045c423db1368
A Final Review: PASS / CLOSED — 2026-09-23
```

Delivered the reference-aligned shared V2 light shell and Files workspace: live
ResourceLibrary-scoped browsing, atomic ResourceLibrary activation, bounded Create
Folder/Text/Rename/Copy/Move/Delete/text Edit, multi-item Organize continuation, formal
`library/path` destination parity, truthful refresh/presentation, exact Storage path identity and
exact FileIndex reconciliation without a second authority or mutation path. The manual Organize Web
editor derives downstream policies from the selected RecognitionType under the pinned snapshot and
fails closed when that mapping is unavailable. The Files page does not
render recognition-result or organize-status feedback; exact boundary whitespace remains visibly
unambiguous and navigable. The direct browser Upload/Download vertical is outside the current
surface, while generic Storage/provider transfer primitives remain available. Deferred scope
remains arbitrary binary/media editing, unbounded operations, V1 cutover, general non-Files
redesign, new providers/identity systems, universal rollback and automatic uncertain replay.

### Slice 33 — Operations Workspace

```text
Status: PASS / CLOSED
Base: 827c36b410687e41b1da53ba6475d8c03a47dbfd
Implementation Head: e4a5f7696d1742f7b6ef2a784c3b5d234b707d08
A Final Review: PASS / CLOSED — 2026-09-13
```

Delivered the V2 daily-operations command center across actionable Dashboard entry, durable
Task/Job state and controls, bounded Scan/Preview, Web-native exact manual Organize, Automation
definition/schedule/grant/occurrence operation and Webhook definition/test/activation/delivery
recovery. The post-closure Worker correction restores exact pinned source-authority reconstruction
and fail-closed pre-mutation revalidation. Shared Python `/api/v1/*` authority, memory-only
Bearer/RBAC, exact immutable snapshot and one-shot execution binding, zero-mutation analysis,
OrganizerExecutor-only mutation, per-item evidence and V1 `/ui` coexistence remain intact. Deferred
scope remains Slice 34 Review/Recovery, Slice 35 general Configuration, Slice 36
parity/accessibility/cutover and every other Slice 33 Contract deferral.

### Slice 32 — Library & Files Experience

```text
Status: PASS / CLOSED
Base: 76de3f60e223131a8b7db97a566d0ceaadd9b2a0
Implementation Head: ad8ba3b272e683ab2bb1627b4df8f60aa49d6e99
A Final Review: PASS / CLOSED — 2026-09-10
```

Delivered the authenticated read-only V2 Library journey across distinct Active Storage browsing,
FileIndex catalog/search/filter/stable paging, bounded detail/history/evidence and safe uniquely
confirmed physical/indexed context. Existing Python `/api/v1/*` authority, memory-only Bearer/RBAC,
V1 `/ui` coexistence, Storage confinement and OrganizerExecutor-only mutation remain intact.
Deferred scope remains Slices 33–36 Operations, Review/Recovery, Configuration and parity/cutover,
plus every other Slice 32 Contract deferral.

### Slice 31 — Operator Shell & Information Architecture

```text
Status: PASS / CLOSED
Base: 2e7aceb50750fb54689ab26bfd1214b8e36c25f8
Implementation Head: 45cb1d4cdda6cf46a6d6699600bc4a4563efc06b
A Final Review: PASS / CLOSED — 2026-09-09
```

Delivered the centralized typed V2 product-area model, persistent responsive shell, semantic and
keyboard-usable navigation, memory-only deep-link authentication continuation, actionable
401/403/unavailable/not-found recovery and truthful V1 migration handoffs. Dashboard remains the
only implemented V2 business area; V1 `/ui`, `/api/v1/*`, RBAC, Python authority and
OrganizerExecutor-only mutation remain unchanged. Deferred scope remains the Slice 32–36 Library,
Operations, Review/Recovery, Configuration and parity/cutover journeys, new identity/API systems and
all other Slice 31 Contract deferrals.

### Slice 30 — V2 Frontend Platform & Architecture

```text
Status: PASS / CLOSED
Base: 7c7c602c6531c60ddf2d6678857e2ef76c3860b6
Implementation Head: 6953b87afa09e61ff62ffea5eb2a9a7d96c55492
A Final Review: PASS / CLOSED — 2026-09-09
```

Delivered the first-class React/TypeScript/Vite frontend and test boundary, central typed
memory-only Bearer client, complete read-only Dashboard proving journey, Python `/ui-v2/` static
serving and a locked multi-stage Docker artifact with no Node production runtime, while retaining
V1 `/ui`, `/api/v1/*`, RBAC and OrganizerExecutor-only mutation authority. Deferred scope remains
the Slice 31–36 shell, Files, Operations, Review/Recovery, Configuration and parity/cutover journeys,
new identity/session systems, API redesign and all other Contract deferrals.

### Slice 29 — Docker Production Self-hosted Release

```text
Status: PASS / CLOSED
Base: b57db5a28ee944bc121b69608bb6475d8ae555a7
Implementation Head: 657f1a3697eec8e1537bee1335d45a06bec35c6f
A Final Review: PASS / CLOSED — 2026-09-08
```

Delivered the one-image Docker Compose self-hosted journey across production WSGI serving, four
independent non-root services, durable `/data` and explicit media mounts, distinct health/readiness,
restart-safe task ownership and notification state, fail-closed backup/upgrade/migration recovery,
release-security validation and the pre-release Jobs/Preview/Organize execution-boundary correction.
Deferred scope remains built-in identity/OIDC, TLS/proxy termination, full Secret Store/Docker Secrets,
Provider switching, remote/distributed persistence and workers, uncertain-mutation replay, rollback
and specialized notification channels.

### Slice 28 — Web-first Configuration and Operations Administration

```text
Status: PASS / CLOSED
Base: 957a4ebcb0fde03e64be9c406fbcdfed9a12501d
Implementation Head: 8546ff8fe15386dfbbb5fefb29a66b936ed4613f
A Final Review: PASS / CLOSED — 2026-09-07
```

Delivered the authenticated day-2 administration journey across Configuration, Settings,
configuration/result packages and Notifications: successor Draft from exact Active, forms-first
managed object lifecycle, exact validation/test/activation authority, consumed System Settings,
versioned secret-free package exchange, managed Webhook definitions/tests and isolated
per-delivery recovery. Existing Active snapshot, RBAC, redaction, Task/Result history, Storage and
OrganizerExecutor-only mutation boundaries remain intact.

Deferred scope remains Slice 29 Docker production release, Provider switching, built-in identity,
full Secret Store/Docker Secrets ingestion, specialized notification channels, distributed workers,
mutation-based Storage probes and automatic uncertain media-mutation replay.

### Slice 27 — Manual Operations and File Lifecycle

```text
Status: PASS / CLOSED
Base: 306b77d0aad44ab0a2e233866f8972247b437a7d
Implementation Head: 34365121342557b0f40eacc7ad9bbb74499cc4cb
A Final Review: PASS / CLOSED — 2026-09-05
```

Delivered the authenticated daily-operations journey across real Storage-backed Files, distinct
FileIndex state, current-source occurrence/disposition, bounded manual Scan/Preview/Organize,
per-item conflict/review/recovery continuation, and durable Processing Worker readiness and fenced
ownership evidence across Application, Persistence, API and Operator Web. Existing Storage,
OrganizerExecutor-only mutation, Active snapshot, authority, redaction and sibling-isolation rules
remain intact.

Slice 28 day-2 configuration and operations administration, Slice 29 Docker production release,
Provider switching, built-in identity, full Secret Store integration, distributed workers and
uncertain-mutation replay remain deferred as documented.

### Slice 26 — Web-first Fresh Setup and Storage Completion

```text
Status: PASS / CLOSED
Base: 3c660d5a1512b5b221b0284bcff9ae6dd00bbf23
Implementation Head: 928b727552a2fbb298e694cb0312e082e4662dda
A Final Review: PASS / CLOSED — 2026-09-03
```

Delivered the authenticated management-only fresh-instance journey through first managed Draft,
guided Local/SMB/OpenList/S3/R2 Storage configuration, deployment-owned secret references,
read-only Storage checks, bounded Storage Browser/path selection, provider-neutral destination
precheck and exact-revision checked activation. The immutable Active snapshot remains the runtime
authority, and failures preserve the Draft and prior Active without media work.

Slice 28 day-2 configuration and operations administration, Slice 29 Docker production release,
Provider switching, built-in identity, full Secret Store integration and mutation-based Storage
probes remain deferred as documented.

### Slice 25 — Scheduled Automation and Unattended Organization

```text
Status: PASS / CLOSED
Base: 2cee7cc756b90618f14d5d7b112f974fb445a580
Implementation Head: d4da92879b99f1c44ddd717fba1a26e4b0a73493
A Final Review: PASS / CLOSED — 2026-09-02
```

Delivered the bounded operator-managed Automation Task Definition journey: exact validation and
zero-mutation Preview, idempotent snapshot-pinned scheduled occurrences, persistent revocable
unattended authority, existing-pipeline execution, per-item Result/checkpoint recovery and
intra-item live-authority enforcement across API and Operator Web. RecognitionType C, independent
policy ownership, fail-closed mutation, redaction and no automatic uncertain-effect replay remain
intact.

Provider switching, remote guided setup/prechecks, scheduled cache/log cleanup, uncertain-effect
replay, universal compensation, historical rollback and the other explicit Slice deferrals remain
outside this closed Slice.

### Slice 24 — Files / Media Detail and Manual Organize

```text
Status: PASS / CLOSED
Base: 4ff5479d9f4a81906ee52a9f784931b65cd9ab90
Implementation Head: d2e399803078317f2092d895eae627327998de2f
A Final Review: PASS / CLOSED — 2026-09-01
```

Delivered the bounded authenticated Files/Media detail and history journey, durable manual intent
and choices, exact zero-mutation Preview, explicit one-shot reviewed execution, per-item results and
checkpoint-aware recovery across API and Operator Web. Result and evidence projections are bounded
and secret-free, and all real mutation remains behind OrganizerExecutor with explicit authority.

Provider switching, scheduled unattended real organization, automatic uncertain/crash replay,
universal compensation or historical rollback, remote setup/probing and other deferred capabilities
remain outside this Slice.

### Slice 23 — Stage-Aware Per-Item Recovery

```text
Status: PASS / CLOSED
Base: b3083c417849e744b1b9c4629ce9ef312dd194ff
Implementation Head: 26c0450054e4b3d65d6fbf3641d61e022e9561fd
A Final Audit: PASS — 2026-08-30
```

Delivered evidence covers durable per-item Processing Checkpoints, exact-version stage-aware
recovery admission, pinned analysis-only continuation through the existing Worker pipeline, and
independent single-item/bounded-batch recovery with linked Task/Result evidence across Application,
Persistence, API and Web.

The B Closure Packet and A Base..Implementation Head review found every Required Outcome complete,
all Required Surfaces present, final validation credible and no unresolved P0/P1 blocker. Optional
proof, P2 cleanup and wording changes did not extend the Slice.

Deferred scope is recorded in [`SLICE.md`](../SLICE.md), including remote destination prechecks,
uncertain-mutation replay and cross-run compensation, distributed crash replay, Provider switching,
the broader Files/Media manual-organize journey and scheduled unattended real organization.

## Closure Ledger

Pre-migration Slices did not consistently record an immutable Slice Base. Those Base SHAs are not
backfilled or guessed; consult Git and the legacy archive for their detailed lineage.

| Slice | Status | Base | Implementation Head | Final Audit | Delivered | Deferred |
|---|---|---|---|---|---|---|
| 38 — MediaLibrary Files Workspace and Route Separation | PASS / CLOSED | `9e801ae4485bc95d714a8902bf45bf37896fbc2a` | `7d4503e45dc3aa79628ed0d98e887167e1e7c529` | A Final Review PASS / CLOSED — 2026-09-25 | Separate MediaLibrary and ResourceLibrary Files routes, live MediaLibrary browsing, bounded common maintenance and transfer recovery, reference-aligned presentation, and symmetric exact-Active page-local library editing with checked atomic activation | Card statistics/capacity/placeholders, thumbnails, MediaLibrary Scan/Preview/Organize, browser Upload/Download, cross-kind direct transfers, transfer Replace mode, ID migration, broad configuration redesign, V1 cutover, universal rollback and automatic uncertain replay |
| 37 — Files Workspace, Common File Management and V2 Shell | PASS / CLOSED | `b507edba167f5af3af8c53bfcf1417ba4fefddf4` | `aa54854c442d117c7eb23ae9800045c423db1368` | A Final Review PASS / CLOSED — 2026-09-23 | Reference-aligned shared V2 shell, live ResourceLibrary Files workspace, atomic activation, bounded common file management without the direct browser Upload/Download vertical, formal `library/path` destination parity, truthful refresh/presentation, exact Storage path identity, multi-item Organize continuation and RecognitionType-driven Web policy binding | Arbitrary binary/media editing, unbounded operations, V1 cutover, broad non-Files redesign, new providers/identity systems, universal rollback and automatic uncertain replay |
| 33 — Operations Workspace | PASS / CLOSED | `827c36b410687e41b1da53ba6475d8c03a47dbfd` | `e4a5f7696d1742f7b6ef2a784c3b5d234b707d08` | A Final Review PASS / CLOSED — 2026-09-13 | Actionable Dashboard, durable Tasks/Jobs and controls, bounded Scan/Preview, Web-native exact manual Organize, Automation operation and Webhook delivery operation, typed Preview safety projection, and resident Worker pinned-source revalidation | Slices 34–36 Review/Recovery, Configuration, parity/accessibility/cutover and other Contract deferrals |
| 32 — Library & Files Experience | PASS / CLOSED | `76de3f60e223131a8b7db97a566d0ceaadd9b2a0` | `ad8ba3b272e683ab2bb1627b4df8f60aa49d6e99` | A Final Review PASS / CLOSED — 2026-09-10 | Distinct bounded Active Storage and FileIndex journeys, stable catalog paging, strict detail/evidence and safe physical/indexed context | Slices 33–36 Operations/Review/Configuration/parity/cutover and other Contract deferrals |
| 31 — Operator Shell & Information Architecture | PASS / CLOSED | `2e7aceb50750fb54689ab26bfd1214b8e36c25f8` | `45cb1d4cdda6cf46a6d6699600bc4a4563efc06b` | A Final Review PASS / CLOSED — 2026-09-09 | Typed product-area IA, responsive/accessible shell, safe deep-link auth continuation, actionable route/permission recovery and truthful V1 handoff | Slices 32–36 business migrations/parity/cutover, new identity/API systems and other Contract deferrals |
| 30 — V2 frontend platform and architecture | PASS / CLOSED | `7c7c602c6531c60ddf2d6678857e2ef76c3860b6` | `6953b87afa09e61ff62ffea5eb2a9a7d96c55492` | A Final Review PASS / CLOSED — 2026-09-09 | React/TypeScript/Vite platform, typed memory-only API boundary, read-only Dashboard proof, Python V2 static serving and Python-only Docker runtime artifact | Slices 31–36 migrations/cutover, new identity/session systems, API redesign and other Contract deferrals |
| 29 — Docker production self-hosted release | PASS / CLOSED | `b57db5a28ee944bc121b69608bb6475d8ae555a7` | `657f1a3697eec8e1537bee1335d45a06bec35c6f` | A Final Review PASS / CLOSED — 2026-09-08 | One-image four-service Docker Compose production release, durable `/data`, explicit media mounts, health/readiness, restart/fencing, upgrade/recovery, release security and execution-boundary completeness | Built-in identity/OIDC, TLS/proxy, full Secret Store/Docker Secrets, Provider switching, remote/distributed persistence, uncertain-mutation replay, rollback and specialized notifications |
| 28 — Web-first configuration and operations administration | PASS / CLOSED | `957a4ebcb0fde03e64be9c406fbcdfed9a12501d` | `8546ff8fe15386dfbbb5fefb29a66b936ed4613f` | A Final Review PASS / CLOSED — 2026-09-07 | Day-2 Web/API configuration administration, consumed System Settings, secret-free package exchange and Webhook test/delivery recovery | Slice 29 Docker release, Provider switching, built-in identity, full Secret Store, specialized notifications, distributed workers and uncertain-mutation replay |
| 22.3 — Local Storage + Library configuration | PASS / CLOSED | LEGACY — not recorded as a Slice Base | `e28a24aff99c073c67b52351a82cb4a29e163de0` | Legacy combined audit PASS — 2026-08-25 | Guided Local managed configuration, checks, activation and immutable pin | Remote setup/capability checks |
| 22.4 — Recognition configuration | PASS / CLOSED | LEGACY — not recorded as a Slice Base | `d95ea2b64a6fce559341d7eb5824977e07794dff` | Legacy combined audit PASS — 2026-08-26 | Managed recognition, Strategy Test, explanation and activation | Later policy journeys |
| 22.5 — Metadata configuration and correction | PASS / CLOSED | LEGACY — not recorded as a Slice Base | `dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62` | Legacy final audit PASS — 2026-08-27 | Managed MetadataPolicy through bounded one-item DryRun continuation | Provider switching, generic Task resume, wider per-item recovery |
| 22.6 — Naming / Classification / Organize configuration | PASS / CLOSED | `7339a8b21b244e57bdb8067f688df91c7dc03280` | `89f064b22be5c1f04ae75bfc0d6fbe72c9147e7d` | A Final Review PASS — 2026-08-29 | Managed policy editing, exact-revision preview, Local read-only destination precheck and checked activation | See `SLICE.md` Explicitly Deferred |
| 23 — Stage-aware per-item recovery | PASS / CLOSED | `b3083c417849e744b1b9c4629ce9ef312dd194ff` | `26c0450054e4b3d65d6fbf3641d61e022e9561fd` | A Final Review PASS — 2026-08-30 | Durable checkpoints, exact-version admission and independent DryRun single/batch continuation | Manual organization, Provider switching, uncertain/crash replay and unattended execution |
| 24 — Files / Media detail and manual organize | PASS / CLOSED | `4ff5479d9f4a81906ee52a9f784931b65cd9ab90` | `d2e399803078317f2092d895eae627327998de2f` | A Final Review PASS — 2026-09-01 | Bounded detail/history, exact manual Preview and execution, per-item results and recovery across API/Web | Provider switching, unattended real organization, automatic uncertain/crash replay, universal rollback and remote setup/probing |
| 25 — Scheduled automation and unattended organization | PASS / CLOSED | `2cee7cc756b90618f14d5d7b112f974fb445a580` | `d4da92879b99f1c44ddd717fba1a26e4b0a73493` | A Final Review PASS / CLOSED — 2026-09-02 | Managed Automation Task Definition, exact Preview, scheduled occurrences, persistent unattended authority, existing-pipeline execution and per-item recovery | Provider switching, remote guided setup/prechecks, scheduled cache/log cleanup, uncertain-effect replay, universal compensation and historical rollback |
| 27 — Manual operations and file lifecycle | PASS / CLOSED | `306b77d0aad44ab0a2e233866f8972247b437a7d` | `34365121342557b0f40eacc7ad9bbb74499cc4cb` | A Final Review PASS / CLOSED — 2026-09-05 | Real Storage/Files and FileIndex distinction, current source lifecycle, bounded manual Scan/Preview/Organize, conflict/review/recovery continuation and Worker readiness/fencing | Slice 28 day-2 administration, Slice 29 Docker release, Provider switching, built-in identity, full Secret Store, distributed workers and uncertain-mutation replay |
| 26 — Web-first fresh setup and Storage completion | PASS / CLOSED | `3c660d5a1512b5b221b0284bcff9ae6dd00bbf23` | `928b727552a2fbb298e694cb0312e082e4662dda` | A Final Review PASS / CLOSED — 2026-09-03 | Management-only fresh bootstrap, first managed Draft, all V1 Storage forms/tests, bounded Storage Browser/path selection and immutable checked activation | Slice 28 day-2 administration, Slice 29 Docker release, Provider switching, built-in identity, full Secret Store and mutation-based probes |

Earlier completed delivery and every historical Task/Fix/test/review record remain available in Git
and the legacy archive. They are intentionally not duplicated here or translated into new Slices.

## 2026-09-13 — UI-V2 Files ResourceLibrary Contract

- Reworked UI-V2 Files authority from Storage/FileIndex membership to ResourceLibrary -> live Storage.
- Removed ordinary UI-V2 FileIndex catalog/detail routes and navigation entries.
- Added ResourceLibrary-scoped Files API and frontend model without FileIndex membership fields.
- Added Storage-source Preview admission that builds SourceIdentity from live Storage.stat without requiring a FileIndex row.
- Preserved Worker execution revalidation against Preview SourceIdentity and live Storage.

## 2026-09-14 — Files display and organize authority confirmation

- Confirmed from the current code that `RuntimeFilesBrowserService.browse_resource_library` reads
  the enabled ResourceLibrary's live Storage root and intentionally does not consult its optional
  FileIndex composition argument.
- Confirmed that `StorageFilesPage` sends `resourceLibraryId`, relative path and cursor for Files
  reads; the typed Files model excludes FileIndex membership, `fileId`, scan status, occurrence and
  fingerprint fields.
- Confirmed that Files-originated organize Preview sends `scopeKind=file`,
  `resourceLibraryId` and `relativePath`. `create_current_from_storage` resolves the bound
  Storage, calls `Storage.stat()`, creates SourceIdentity and enters `create_from_sources` before
  the existing zero-mutation Preview planner.
- Confirmed by focused tests that a Storage-source Preview succeeds without a FileIndex row and
  that Files and FileIndex remain separate API surfaces.
- FileIndex-backed compatibility and legacy operation paths remain in the codebase but are not
  valid dependencies for the ResourceLibrary Files display or organize path.

## 2026-09-14 — Slice 37 Files Page Visual Fidelity Activation

- Retired the previously planned Slice 34–36 roadmap boundary from current planning; historical
  references remain immutable history.
- Activated the Files-page-only Slice 37 contract with Base
  `b507edba167f5af3af8c53bfcf1417ba4fefddf4`.
- Added the canonical visual specification for `docs/pics/文件页.png` at `1536 x 1024`, including
  exact copy, reference data, layout, drawer state, journey, frozen pages and pixel-level acceptance.
- This activation changed documentation only. No code, tests, image asset or other-page behavior
  changed.

## 2026-09-22 — Slice 37 Post-reactivation Closure

- A reviewed the original Slice Base `b507edba167f5af3af8c53bfcf1417ba4fefddf4` through final
  Implementation Head `3feab84a0fbbf7cebfe1f5507e548636da5ab283` and decided `PASS / CLOSED`.
- Delivered the final exact Storage path-identity correction: Files preserves boundary whitespace
  through normalization, visibly distinguishes it, and navigates with the exact encoded path while
  retaining truthful refresh, bounded not-found recovery and no FileIndex authority.
- Deferred scope remains unchanged: direct browser Upload/Download, arbitrary binary/media editing,
  unbounded operations, new providers/identity systems, universal rollback and automatic uncertain
  replay remain deferred or outside this Slice.

## 2026-09-21 — Slice 37 Post-reactivation Closure

- A reviewed the original Slice Base `b507edba167f5af3af8c53bfcf1417ba4fefddf4` through corrected
  Implementation Head `2115d1839eb0611f097913eae8a43492d00346a2` and decided `PASS / CLOSED`.
- Delivered formal `library/path` destination parity, source-linked offline Preview completion and
  final safety/quality-gate reconciliation; the current Files surface excludes direct browser
  Upload/Download while retaining the remaining bounded file-management and Organize journeys.
- Deferred scope remains unchanged: arbitrary binary/media editing and stream inspection, unbounded
  operations, new providers/identity systems, universal rollback and automatic uncertain replay.
