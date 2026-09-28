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
| 41 — V2 Organizing Rules Workspace | Deliver the native V2 recognition-to-policy management journey: reference-aligned rule workspace, typed Recognition/Metadata/Naming/Classification/Organize editors, reference-safe object lifecycle, exact-revision zero-mutation tests/previews and one-click Save that automatically validates and atomically activates while preserving RecognitionType identity | ACTIVE | 40 closure and existing managed-configuration/rule-engine/policy-preview foundations |

## Current boundary

The released V1 line is version `1.0.0`, maintained on `release/v1` at tag `v1.0.0`. `main` is now
the active V2 development trunk with package version `2.0.0.dev0`.

Slices 26, 27, 28 and 29 are PASS / CLOSED. Slice 28 closed at Base
`957a4ebcb0fde03e64be9c406fbcdfed9a12501d` and Implementation Head
`8546ff8fe15386dfbbb5fefb29a66b936ed4613f`, delivering day-2 Web/API configuration
administration, consumed System Settings, versioned secret-free configuration/result exchange, and
managed Webhook definition/test/delivery recovery. Slice 29 then delivered the Docker production
self-hosted release: one immutable image, four independent services, production WSGI serving,
durable `/data`, explicit media mounts, health/readiness, restart/fencing, upgrade/recovery and
release-security validation. Together with the closed Slice 26/27 foundations, the current V1
product covers fresh setup, real Storage/FileIndex operations, manual organization, scheduled
unattended organization, exact Active runtime authority, day-2 administration and self-hosted
deployment without redesigning the processing engine.

V1 retains
environment-owned API-principal bearer authentication, deployment-owned secret injection and the TMDB
production Provider. Built-in user/session identity, OIDC, Metadata Provider switching, full Secret
Store integration, mutation-based Storage capability probes, distributed workers and uncertain media-
mutation replay remain explicit V1.x/V2 or deployment-specialized work, not hidden Docker Tasks.

## V2 program boundary

V2 remains active development for Operator Web Architecture & UX Modernization. Slices 30–33 and
37–40 are closed historical capabilities. Slice 41 is ACTIVE for the native V2 organizing-rules
workspace selected by A on 2026-09-28 from the six user-supplied business/style references. Those
images define relationship, composition and visual language rather than actual production data or
pixel-identical fixtures. Slice 39 delivered the V2 Storage management
workspace, reusing the existing managed-configuration and Storage foundations, together with
resident transfer continuity and health/waiting recovery authorized on 2026-09-26. Slice 38 remains
closed; no separate Worker project was created. The previously
planned Slice 34, Slice 35 and Slice 36 boundaries
were retired from the current Roadmap on 2026-09-14; their historical references remain in Git and
are not current work commitments. Slice 37's post-reactivation closure, finalized by A on 2026-09-23,
delivered the replacement
shared V2 shell presentation and the current Files workspace defined by
[`file-page-visual-spec.md`](file-page-visual-spec.md), including truthful refresh/presentation and
exact Storage path identity. The final 2026-09-23 correction review also confirms that the manual
Organize Web editor derives and locks NamingPolicy, ClassificationPolicy and OrganizePolicy from
the selected RecognitionType under the pinned snapshot. Both post-closure correction loops remained
within the original Slice boundary and preserved the existing live Storage authority and non-Files
business boundaries. Slice 38 is PASS / CLOSED for MediaLibrary file management and the necessary
route separation. Its canonical image is `docs/pics/媒体库页.png`, with card statistics and file
thumbnails explicitly excluded. It moved Files to `/ui-v2/resourcelib/files`, added MediaLibrary at
`/ui-v2/medialib/files` and retires both old Library routes while retaining Files/Organize behavior.
The reviewed Slice Head includes selected-card editing for both ResourceLibrary and MediaLibrary:
immutable ID, focused field editing, exact-Active optimistic concurrency, checked activation and
zero Storage-content migration. A's Final Review is PASS / CLOSED on 2026-09-25.
User experience remains the primary product-design and acceptance criterion, while correctness,
RBAC, audit, data integrity, ResourceLibrary confinement and OrganizerExecutor-only mutation remain
mandatory. Slice 30 is `PASS / CLOSED` at Base
`7c7c602c6531c60ddf2d6678857e2ef76c3860b6` and Implementation Head
`6953b87afa09e61ff62ffea5eb2a9a7d96c55492`, having delivered the typed V2 Dashboard proving path,
frontend/test boundary and Python-only production artifact while retaining V1 `/ui`. Slice 31 is
`PASS / CLOSED` at Base `2e7aceb50750fb54689ab26bfd1214b8e36c25f8` and Implementation Head
`45cb1d4cdda6cf46a6d6699600bc4a4563efc06b`, having delivered the shared responsive Operator Shell,
centralized information architecture, memory-only deep-link continuation and actionable route/auth
recovery. Slice 32 is `PASS / CLOSED` at Base
`76de3f60e223131a8b7db97a566d0ceaadd9b2a0` and Implementation Head
`ad8ba3b272e683ab2bb1627b4df8f60aa49d6e99`, having delivered the V2 read-oriented Library journey
across bounded Active Storage browsing, FileIndex discovery/detail and truthful physical/indexed
context without pulling operational mutation or recovery work forward. Slice 33 — Operations
Workspace is PASS / CLOSED on 2026-09-13 at Base `827c36b410687e41b1da53ba6475d8c03a47dbfd` and final
Implementation Head `e4a5f7696d1742f7b6ef2a784c3b5d234b707d08`, delivering the coherent V2
daily-operations journey across actionable Dashboard state, Tasks/Jobs, bounded Scan/Preview,
Web-native exact manual Organize, scheduled Automation and Notification delivery. The accepted Head
includes both post-closure P1 corrections: the first restores the typed Manual Organize Preview safety
projection and separate destructive confirmations; the second restores Worker reconstruction of the
exact pinned source authority and fail-closed pre-mutation revalidation. Slice 40 is the most
recently closed large Slice at Base `d814b7c1c6819e79271245a1126f53aca6aeaf69` and Implementation
Head `7805fa09d540fdeb5f0b39a5e3ac39c8c5ff7bb7`. It delivered native V2 Settings, a legal empty
business Active, conditional publication checks, command-specific readiness and resident service
adoption without mandatory media mounts or process restart. Mandatory media-business onboarding,
wholesale policy-page migration and V1 retirement remained deferred at closure. Slice 41 now owns
the organizing-rule portion of that migration: `/ui-v2/rules`, the complete RecognitionType policy
graph, typed policy forms, exact-revision tests/previews and one-click Save with automatic checked
activation using existing Python authority. Metadata Provider switching, Review/Recovery migration, actual media execution
from the rules page, V1 retirement and unrelated configuration redesign remain outside Slice 41.
This Roadmap does not retain the retired Slice 34–36 program rows.

## Roadmap rules

- A alone creates or materially changes large Slice boundaries and ordering.
- B plans Tasks only after a Slice becomes ACTIVE; Roadmap never pre-splits future Slices into Tasks.
- Closed Slice 37 delivered the shared V2 shell's visual replacement, the Files page, drawer and common
  bounded file-management commands. Its authorized post-closure correction also delivered
  formal `library/path` destination parity with the local CLI. Its historical non-Files boundary
  remains part of that closure. Closed Slice 38 delivered the MediaLibrary journey and required
  route/navigation integration. Closed Slice 39 delivered Storage management and its necessary
  shared shell integration. Closed Slice 40 delivered Settings/empty-baseline startup and resident
  service configuration adoption; existing Files, MediaLibrary and other journeys remain protected.
- Active Slice 41 owns the V2 organizing-rules workspace and may not absorb actual media execution,
  Provider switching, Review/Recovery migration, V1 cutover or unrelated page redesign.
- Task PASS, fixes, test counts, probes, rejected SHAs and review narratives never enter this file.
- Safety, product and architecture requirements remain authoritative even when omitted from this
  compact prioritization view.
