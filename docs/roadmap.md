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
| 25 — Automation and production hardening | Complete operator-configured scheduled scanning and unattended organization using RecognitionType-selected policies under explicit bounded execution authority, plus production-loop hardening | PLANNED | 24 |

## Current boundary

No Slice is currently active. [Slice 24](../SLICE.md) closed after A reviewed its immutable
Base..Implementation Head and accepted the bounded Files/Media explanation and manual
Preview-to-exact-plan-execution journey, reusing the existing configuration, recovery and
OrganizerExecutor safety authorities.

Slice 25 remains planned. Selecting and activating the next large Slice is a separate A action.

## Roadmap rules

- A alone creates or materially changes large Slice boundaries and ordering.
- B plans Tasks only after a Slice becomes ACTIVE; Roadmap never pre-splits future Slices into Tasks.
- Task PASS, fixes, test counts, probes, rejected SHAs and review narratives never enter this file.
- Safety, product and architecture requirements remain authoritative even when omitted from this
  compact prioritization view.
