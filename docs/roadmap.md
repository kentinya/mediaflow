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
| 30 — V2 Frontend Platform & Architecture | Establish the V2 frontend build/runtime boundary and prove it through one typed Dashboard journey without moving production authority out of Python | ACTIVE | V1.0.0 release baseline |
| 31 — Operator Shell & Information Architecture | Deliver the authenticated V2 application shell, navigation, route ownership and shared operator information architecture | PLANNED | 30 |
| 32 — Library & Files Experience | Migrate bounded Storage Files and FileIndex discovery/detail journeys with their existing read-only and authority boundaries | PLANNED | 31 |
| 33 — Operations Workspace | Migrate Dashboard, Tasks, Jobs, schedules and notification operations into a coherent V2 workspace | PLANNED | 30, 31 |
| 34 — Review & Recovery Workspace | Migrate per-item review, conflict, checkpoint and safe recovery journeys with independent batch state | PLANNED | 32, 33 |
| 35 — Configuration Administration | Migrate managed Configuration, Settings, revision evidence and activation administration through shared API/Web behavior | PLANNED | 31, 33 |
| 36 — V2 Parity, Accessibility & Legacy UI Retirement | Complete parity and accessibility evidence, cut over the supported `/ui` surface, and retire the V1 UI only after migration acceptance | PLANNED | 32, 33, 34, 35 |

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

V2 is active development for Operator Web Architecture & UX Modernization. The rows for Slices 30–36
are the complete current program boundary; they are not a single Slice and must be activated and
reviewed independently. Slice 30 is `ACTIVE` under the committed A-owned Contract in
[`SLICE.md`](../SLICE.md). No implementation Task is active yet; the next legal action is for B to
plan Task 30.1. This Roadmap does not pre-plan Task details.

## Roadmap rules

- A alone creates or materially changes large Slice boundaries and ordering.
- B plans Tasks only after a Slice becomes ACTIVE; Roadmap never pre-splits future Slices into Tasks.
- Task PASS, fixes, test counts, probes, rejected SHAs and review narratives never enter this file.
- Safety, product and architecture requirements remain authoritative even when omitted from this
  compact prioritization view.
