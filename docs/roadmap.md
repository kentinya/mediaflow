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
| 23 — Stage-aware per-item recovery | Provide checkpoint-aware single and bounded batch recovery without replaying successful siblings or uncertain mutation | ACTIVE | 22.6 closure |
| 24 — Files / Media detail and manual organize | Complete the operator journey from explanation and review to safe manual Preview/Organize and recovery | PLANNED | 23 |
| 25 — Automation and production hardening | Complete operator-configured scheduled scanning and unattended organization using RecognitionType-selected policies under explicit bounded execution authority, plus production-loop hardening | PLANNED | 24 |

## Current boundary

The current work boundary is [Slice 23](../SLICE.md): stage-aware per-item recovery over the existing
Task/TaskItem/Result model. Slice 22.6 remains closed; its legacy A–O/F1 history is evidence inside
that closed Slice, not authorization for another configuration micro-Slice.

Slices 24 and 25 remain large planned boundaries only. B may plan Tasks only inside active Slice 23.

## Roadmap rules

- A alone creates or materially changes large Slice boundaries and ordering.
- B plans Tasks only after a Slice becomes ACTIVE; Roadmap never pre-splits future Slices into Tasks.
- Task PASS, fixes, test counts, probes, rejected SHAs and review narratives never enter this file.
- Safety, product and architecture requirements remain authoritative even when omitted from this
  compact prioritization view.
