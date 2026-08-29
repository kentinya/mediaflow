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
| 22.6 — Naming / Classification / Organize configuration | Complete managed policy editing, exact-revision preview, Local destination precheck and checked activation | READY FOR B READINESS CHECK | 22.5 |
| 23 — Batch per-item recovery | Provide stage-aware per-item recovery without replaying successful siblings | PLANNED | 22.6 closure |
| 24 — Files / Media detail and manual organize | Complete the operator journey from explanation and review to safe manual Preview/Organize and recovery | PLANNED | 23 |
| 25 — Automation and production hardening | Complete scheduled-operation safety, operational readiness and release hardening | PLANNED | 24 |

## Current boundary

The only current work boundary is [Slice 22.6](../SLICE.md). Its legacy A–O/F1 history is evidence
inside that one Slice, not a set of current lifecycle objects. No Phase 22.6-P/Q/R or other micro-
Slice is authorized.

Slice 23 is a large planned boundary only. It has not started, and no Slice 23 Implementation Task
may be defined until A closes Slice 22.6 and selects the next Slice.

## Roadmap rules

- A alone creates or materially changes large Slice boundaries and ordering.
- B plans Tasks only after a Slice becomes ACTIVE; Roadmap never pre-splits future Slices into Tasks.
- Task PASS, fixes, test counts, probes, rejected SHAs and review narratives never enter this file.
- Safety, product and architecture requirements remain authoritative even when omitted from this
  compact prioritization view.
