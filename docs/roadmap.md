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
| 26 — Web-first fresh setup and Storage completion | Let an authenticated operator start from a minimal fresh-instance bootstrap, create the first complete managed Draft, configure/test all V1 Storage types and libraries, browse bounded Storage directories, and checked-activate the first immutable runtime without hand-authoring a full JSON runtime | ACTIVE | 25 |
| 27 — Manual operations and file lifecycle | Let an operator browse real configured Storage, distinguish it from FileIndex, run file- or ResourceLibrary-scoped Scan/Preview/Organize with the correct authority, understand current processing disposition, and complete conflict/review/recovery through an explicit safe continuation | PLANNED | 26 and closed 23–25 foundations |
| 28 — Web-first configuration and operations administration | Complete the day-2 Web configuration lifecycle and object-management experience, consumed System Settings, versioned secret-free configuration/result import-export, and managed Webhook delivery configuration/test/recovery | PLANNED | 26 |
| 29 — Docker production self-hosted release | Deliver and verify the one-image, multi-service Docker Compose product journey with production HTTP serving, local durable `/data`, explicit media mounts, non-root operation, lifecycle health, restart persistence and fail-closed upgrade/migration | PLANNED | 27 and 28 |

## Current boundary

Slice 26 is ACTIVE at Base `3c660d5a1512b5b221b0284bcff9ae6dd00bbf23`. It owns the complete
fresh-instance Web setup journey and V1 Storage-management completion. It does not own Webhook/System
administration, Docker packaging/runtime release, Metadata Provider switching, a built-in user
database, OIDC, a full Secret Store, mutation-based Storage capability probes or any redesign of the
closed media-processing engine. Its provider-neutral Storage Browser and path-selection contracts
may be reused later, but Slice 26 does not rename the current Files/File Catalog surface, add
processing disposition or change Preview/Organize/Recovery semantics.

The remaining V1 order is intentional. Configuration and Storage semantics must be product-complete
before the browser can become the real Files entry point. The core day-to-day media journey must then
converge Storage browsing, FileIndex state, manual work, Preview findings, execution blockers and
safe recovery before packaging claims a usable product. Day-2 configuration/notification
administration can proceed from the Slice 26 authority without redefining that processing journey,
but both Slice 27 and Slice 28 must be stable before the final Docker integration/release Slice.
V1 retains environment-owned API-principal bearer authentication and the TMDB production Provider.
Built-in user/session identity and Metadata Provider switching are explicit post-V1 work, not hidden
Docker Tasks.

## Roadmap rules

- A alone creates or materially changes large Slice boundaries and ordering.
- B plans Tasks only after a Slice becomes ACTIVE; Roadmap never pre-splits future Slices into Tasks.
- Task PASS, fixes, test counts, probes, rejected SHAs and review narratives never enter this file.
- Safety, product and architecture requirements remain authoritative even when omitted from this
  compact prioritization view.
