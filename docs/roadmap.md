# MediaFlow Slice Roadmap

This file records only large business-capability Slices, their order, dependencies and current
status. Detailed Task, Fix, SHA, test and review history belongs to Git; the pre-migration Roadmap is
preserved as [legacy read-only history](history/roadmap-legacy-2026-08-29.md). Lifecycle rules live
only in [the development workflow](development-workflow.md).

| Slice | Goal | Status | Depends On |
|---|---|---|---|
| 22.3 — Local Storage + Library configuration | Complete the guided Local Storage, ResourceLibrary and MediaLibrary managed-configuration journey | PASS / CLOSED | Managed configuration authority |
| 22.4 — Recognition configuration | Complete managed recognition editing, Strategy Test, explanation and activation | PASS / CLOSED | 22.3 |
| 22.5 — Metadata configuration and correction | Complete managed MetadataPolicy testing, candidate decision, correction and bounded DryRun continuation | PASS / CLOSED | 22.4 |
| 22.6 — Naming / Classification / Organize configuration | Complete managed policy editing, exact-revision preview, Local destination precheck and checked activation | PASS / CLOSED | 22.5 |
| 23 — Stage-aware per-item recovery | Provide checkpoint-aware single and bounded batch recovery without replaying successful siblings or uncertain mutation | PASS / CLOSED | 22.6 closure |
| 24 — Files / Media detail and manual organize | Complete the operator journey from explanation and review to safe manual Preview/Organize and recovery | PASS / CLOSED | 23 |
| 25 — Scheduled automation and unattended organization | Complete operator-configured scheduled scanning and unattended organization using RecognitionType-selected policies under explicit bounded execution authority, plus the production-loop hardening required by that journey | PASS / CLOSED | 24 |
| 26 — Web-first fresh setup and Storage completion | Let an authenticated operator start from a minimal fresh-instance bootstrap, create the first complete managed Draft, configure/test all V1 Storage types and libraries, browse bounded Storage directories, and checked-activate the first immutable runtime without hand-authoring a full JSON runtime | PASS / CLOSED | 25 |
| 27 — Manual operations and file lifecycle | Let an operator browse real configured Storage, distinguish it from FileIndex, run file- or ResourceLibrary-scoped Scan/Preview/Organize with the correct authority, understand current processing disposition, and complete conflict/review/recovery through an explicit safe continuation | PASS / CLOSED | 26 and closed 23–25 foundations |
| 28 — Web-first configuration and operations administration | Complete the day-2 Web configuration lifecycle and object-management experience, consumed System Settings, versioned secret-free configuration/result import-export, and managed Webhook delivery configuration/test/recovery | PASS / CLOSED | 27 |
| 29 — Docker production self-hosted release | Deliver and verify the one-image, multi-service Docker Compose product journey with production HTTP serving, local durable `/data`, explicit media mounts, non-root operation, lifecycle health, restart persistence and fail-closed upgrade/migration | PASS / CLOSED | 27 and 28 |
| 30 — V2 Frontend Platform & Architecture | Establish the V2 frontend build/runtime boundary and prove it through one typed Dashboard journey without moving production authority out of Python | PASS / CLOSED | V1.0.0 release baseline |
| 31 — Operator Shell & Information Architecture | Deliver the authenticated V2 application shell, navigation, route ownership and shared operator information architecture | PASS / CLOSED | 30 |
| 32 — Library & Files Experience | Migrate bounded Storage Files and FileIndex discovery/detail journeys with their existing read-only and authority boundaries | PASS / CLOSED | 31 |
| 33 — Operations Workspace | Migrate Dashboard, Tasks, Jobs, schedules and notifications into a coherent V2 workspace, including a complete Web-native interactive organize journey that may redesign operator-facing authorization and whose routine execution avoids CLI token issuance/copy-paste while preserving backend authority, audit, limits and mutation invariants | PASS / CLOSED | 30, 31 |
| 37 — Files Workspace, Common File Management and V2 Shell | Replace the former V2 shell with the shared light shell and exact Files composition in `docs/pics/文件页.png`; complete ResourceLibrary activation, Create Folder/Text File, Rename/Copy/Move/Delete/text Edit, organize continuation and post-mutation reconciliation without introducing a second authority; remove the direct browser Upload/Download vertical; correct formal classification `library/path` destination parity with CLI; repair stale ResourceLibrary directory-tree state after Files refresh; make the manual Organize editor derive downstream policies from RecognitionType | PASS / CLOSED | 33 and existing Files foundation |
| 38 — MediaLibrary Files Workspace and Route Separation | Replace the Library landing with reference-aligned MediaLibrary live browsing, atomic library create/edit/remove and bounded common file management without Organize, card statistics or thumbnails; separate MediaLibrary and ResourceLibrary routes while preserving and extending the Files journey with checked ResourceLibrary/MediaLibrary editing | PASS / CLOSED | 37 and existing MediaLibrary/managed-configuration/Storage foundations |
| 39 — Storage Management Workspace | Deliver the V2 Storage management journey from the supplied reference: bounded provider inventory and references, typed Local/SMB/OpenList/S3/R2 configuration, page-local checked Active Add/Edit/copy/enable/disable/remove, and zero-mutation Connection/Read diagnostics; complete the existing admitted-transfer Worker handoff across first activation/configuration changes, with truthful health and waiting-state recovery | PASS / CLOSED | 38 and existing managed-configuration/Storage foundations |
| 40 — V2 Settings and Empty-Baseline Startup | Start from management-only deployment, explicitly create/view/export/activate an empty business baseline in V2 Settings, edit supported configuration absent from other pages, then publish exact business-page successors with applicable checks and truthful command readiness; keep Worker, Scheduler and Notification Worker resident across setup and activation without mandatory media mounts | PASS / CLOSED | 39 closure and existing managed-configuration/operations foundations |
| 41 — V2 Organizing Rules Workspace | Deliver the native V2 recognition-to-policy management journey: reference-aligned rule workspace, typed Recognition/Metadata/Naming/Classification/Organize editors, reference-safe object lifecycle, exact-revision zero-mutation tests/previews and one-click Save that automatically validates and atomically activates while preserving RecognitionType identity | PASS / CLOSED | 40 closure and existing managed-configuration/rule-engine/policy-preview foundations |
| 42 — V2 Operations and Tasks Workspace | Deliver a reference-aligned unified run inventory, authoritative search/counts/progress, task detail/operation records/export, contextual live-file organize entry, cooperative controls, safe Web continuation and task-scoped native decision/failed-item recovery without replaying successful or uncertain effects | PASS / CLOSED | 41 closure and existing Operations/Files/Task/Worker/recovery foundations |
| 43 — V2 Automation Workspace and Engine Settings | Complete reference-aligned definition management with checked Save, exact Preview and scoped scheduled authority, deliberate Run once, truthful statistics and linked history/recovery, and global engine settings verified against actual resident consumers | ACTIVE | 42 closure, accepted 44 improvements and existing Automation/managed-configuration/Operations/resident-service foundations |
| 44 — Existing V2 Pages Functional Improvements | Improve existing V2 pages: consistent ResourceLibrary/MediaLibrary ordinary file operations with optional fingerprints; reference-aligned Rules presentation; classification destinations using MediaLibrary plus path with explicit legacy conversion and preserved historical authority; object-scoped Rules tests and separate complete-flow checks; usable long-name paths/toolbars on both library pages; bounded ResourceLibrary folder/mixed-selection organization through exact Preview and confirmed execution | PASS / CLOSED | Accepted existing V2 pages through 42; explicit user priority change before 43 closure |

## Current boundary

Slice 43 is ACTIVE under [SLICE.md](../SLICE.md), resumed at the user's explicit request after
accepted Slice 44. Branch `slice/43-resumed-after-44` combines that accepted baseline with the
preserved unfinished work. The original Slice Base and business boundary remain intact; resumption
is not acceptance. Current development uses the Slice 44-era governance documents and Slice/Task
rules. [TASK.md](../TASK.md) owns the current Task plan and review; Git retains prior review rounds.

Slice 44 remains PASS / CLOSED, with its accepted six-outcome boundary and exceptional-discovery
recovery deferrals retained. Its complete Contract/reviews remain reachable at its closure checkpoint.
The preservation branch `frozen/slice-43-2026-10-07` remains unchanged. Retired Slice 34–36 boundaries
remain historical only.

[Release](release.md) owns release-line facts, [Progress](progress.md) owns closure Base/Head,
dates, delivered outcomes and deferrals, and [Architecture](architecture.md) and
[Product Experience](product-experience.md) own CURRENT behavior. This file does not repeat them.

## Roadmap rules

A owns large-Slice boundaries and priority; Tasks follow the [development workflow](development-workflow.md).
Task/fix/test/review history belongs to Git. Omission from this compact view never weakens product,
architecture, safety or the active Contract.
