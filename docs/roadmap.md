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
| 29 — Docker production self-hosted release | Deliver and verify the one-image, multi-service Docker Compose product journey with production HTTP serving, local durable `/data`, explicit media mounts, non-root operation, lifecycle health, restart persistence and fail-closed upgrade/migration | PLANNED | 27 and 28 |

## Current boundary

Slices 26, 27 and 28 are PASS / CLOSED. Slice 28 closed at Base
`957a4ebcb0fde03e64be9c406fbcdfed9a12501d` and Implementation Head
`8546ff8fe15386dfbbb5fefb29a66b936ed4613f`, delivering day-2 Web/API configuration
administration, consumed System Settings, versioned secret-free configuration/result exchange, and
managed Webhook definition/test/delivery recovery. Together with the closed Slice 26/27 foundations,
the current V1 product covers fresh setup, real Storage/FileIndex operations, manual organization,
scheduled unattended organization, exact Active runtime authority and day-2 administration without
redesigning the processing engine.

The remaining V1 Slice is Slice 29 Docker production self-hosted release. V1 retains
environment-owned API-principal bearer authentication, deployment-owned secret injection and the TMDB
production Provider. Built-in user/session identity, OIDC, Metadata Provider switching, full Secret
Store integration, mutation-based Storage capability probes, distributed workers and uncertain media-
mutation replay remain explicit V1.x/V2 or deployment-specialized work, not hidden Docker Tasks.

## Roadmap rules

- A alone creates or materially changes large Slice boundaries and ordering.
- B plans Tasks only after a Slice becomes ACTIVE; Roadmap never pre-splits future Slices into Tasks.
- Task PASS, fixes, test counts, probes, rejected SHAs and review narratives never enter this file.
- Safety, product and architecture requirements remain authoritative even when omitted from this
  compact prioritization view.
