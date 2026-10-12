# MediaFlow Slice Closure Ledger

This file is the compact large-Slice ledger. Git retains detailed Task and review history. The full
pre-migration Progress log is preserved as
[legacy read-only history](history/progress-legacy-2026-08-29.md); it is evidence, not current
workflow authority. Closure rules live only in
[the development workflow](development-workflow.md).

## Current development pointer

Slice 43 — **V2 Automation Workspace and Engine Settings** — is **ACTIVE** on
`slice/43-resumed-after-44`, integrating accepted Slice 44 with preserved unfinished work under
the current Slice 44-era governance. [SLICE.md](../SLICE.md) retains the original Base and business
boundary; [TASK.md](../TASK.md) retains Task 43.1 **FIX REQUIRED** and the unresolved P1, with the
same Task correction loop next. Detailed implementation and review history remains in Git.

Slice 44 remains **PASS / CLOSED** with all six Required Outcomes and nine Required Surfaces accepted.
Its closure-ledger entry and all earlier accepted entries below are unchanged. The frozen Slice 43
branch and exact review snapshots remain reachable as historical evidence.

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

Expanded closure narratives remain available in Git at `ed967d4:docs/progress.md`. The table below
is the single compact summary of each accepted closure; its recorded facts are unchanged.

## Closure Ledger

Pre-migration Slices did not consistently record an immutable Slice Base. Those Base SHAs are not
backfilled or guessed; consult Git and the legacy archive for their detailed lineage.

| Slice | Status | Base | Implementation Head | Final Audit | Delivered | Deferred |
|---|---|---|---|---|---|---|
| 44 — Existing V2 Pages Functional Improvements | PASS / CLOSED | `853973dbbf8289fa2ad40657033e94e870a690e4` | `8be263ea778df08aa374e9433f138a218c1d4af9` | A Final Review PASS / CLOSED — 2026-10-12 | Shared ordinary maintenance with optional fingerprints and durable Delete on both library kinds; reference-aligned Rules forms and object-local tests/separate complete flow; MediaLibrary-plus-path classification with explicit legacy conversion; long-name list/grid navigation/toolbars; bounded ResourceLibrary folder/mixed discovery through frozen primary/attachment Preview and confirmed execution | Seamless exceptional discovery crash/control/activation/legacy continuity, frozen Slice 43, unselected pages/providers, Upload/Download, MediaLibrary Organize, larger/split manifests, implicit destructive authority and automatic uncertain replay; other Contract deferrals unchanged |
| 42 — V2 Operations and Tasks Workspace | PASS / CLOSED | `ffee77348cebcb05e356c8111c5861ed64ca0388` | `ce3fc2a3e70d40279fa725b5d7dc838d11123980` | A Final Review PASS / CLOSED — 2026-10-06 | Native unified task center, authoritative queries/counts and historical progress/evidence, live-file exact organize return, cooperative controls, durable safe Web continuation and task-linked single/bounded decision and analysis recovery | Global Review/cross-task bulk, history retention/deletion, unbounded or MediaLibrary organize, arbitrary historical Reprocess, Automation/Notifications redesign, new authority/providers, uncertain replay, universal rollback and V1 retirement; other Contract deferrals unchanged |
| 41 — V2 Organizing Rules Workspace | PASS / CLOSED | `8a6a15597bab2fd10673db84d73a5bbc1d455ad8` | `8433319168272ecf7ccde017afc36525e8c62ea0` | A Final Review PASS / CLOSED — 2026-09-30 | Native V2 Rules graph workspace, typed editors, reference-safe lifecycle, exact-candidate zero-mutation analysis, one-Save checked publication and Settings readiness/recovery with preserved RecognitionType identity | Provider switching/new providers, Review/Recovery redesign, media execution from Rules, new rule/naming/classification domains, bulk/diff/rollback, V1 retirement/auth redesign and other unchanged Contract deferrals |
| 40 — V2 Settings and Empty-Baseline Startup | PASS / CLOSED | `d814b7c1c6819e79271245a1126f53aca6aeaf69` | `7805fa09d540fdeb5f0b39a5e3ac39c8c5ff7bb7` | A Final Review PASS / CLOSED — 2026-09-28 | Native V2 Settings and first-Draft lifecycle, legal empty-business Active, conditional publication, incremental successors, command readiness, media-free startup and resident service adoption without restart | Wholesale policy/Recognition/Review/Recovery migration, V1 cutover, generated onboarding defaults, new identity/Secret Store/deployment mutation, scheduler/queue redesign, new providers/commands and automatic uncertain replay |
| 39 — Storage Management Workspace | PASS / CLOSED | `d02539e49d5c99c3e3c0c70de5e994e42824a18e` | `f458646d3dac280b118a511c60ec53a5d3075d67` | A Final Review PASS / CLOSED — 2026-09-27 | V2 Storage management workspace, typed checked lifecycle, zero-mutation diagnostics, provider-root/setup recovery, resident ResourceLibrary/MediaLibrary transfer continuity and truthful Worker readiness/waiting recovery | Mutation-based Storage probes, general Configuration/native V2 setup migration, new providers/Secret Store integration, new file commands, scheduler redesign, automatic uncertain replay and new identity/session systems |
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
