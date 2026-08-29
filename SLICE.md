# Slice 22.6 — Naming / Classification / Organize Configuration Journey

This is the A-owned Slice Contract. B and Developer may not expand or weaken it. Detailed lifecycle
rules are defined only in [`docs/development-workflow.md`](docs/development-workflow.md).

```text
Slice ID: 22.6
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PASS / CLOSED
Base SHA: 7339a8b21b244e57bdb8067f688df91c7dc03280
Implementation Head: 89f064b22be5c1f04ae75bfc0d6fbe72c9147e7d
A Final Review: PASS
```

The Base is the checkpoint immediately before Phase 22.6-A implementation began. The Implementation
Head is the pushed checkpoint containing the completed implementation and CURRENT-documentation
reconciliation. This governance-migration checkpoint does not change product implementation and
must not silently move the audited Implementation Head.

The former Phase 22.6-A through O and F1 names are LEGACY IMPLEMENTATION HISTORY inside this one
Slice. They are evidence in Git and the archived logs, not current Slice/Task lifecycle objects and
not authorization for a Phase 22.6-P/Q/R continuation.

## User Goal

An operator can configure Naming, Classification and Organize policy behavior inside one managed
Draft, understand dependency impact, preview the exact revision's names/classification/destination
and organize authority, safely precheck a Local destination, correct actionable failures, and use
checked activation without granting execution authority or mutating media.

## Required Outcomes

| ID | Required Outcome | Migrated evidence state |
|---|---|---|
| RO-1 | NamingPolicy, ClassificationPolicy and OrganizePolicy are managed through the same Draft/version/digest, validation, reference protection, audit and immutable activation authority | COMPLETE |
| RO-2 | The exact selected revision provides bounded, secret-free naming, classification, organize-authority and composed-destination preview using production policy/engine semantics | COMPLETE |
| RO-3 | Destination composition preserves RecognitionType identity, attributes policy/library contributions, uses Storage-relative safe paths and exposes actionable unsafe/unresolved outcomes | COMPLETE |
| RO-4 | Local destination precheck is read-only, bounded and supports one sample or 1–8 samples under one RecognitionType, one destination Storage, independent rows/recovery and cross-item collision detection | COMPLETE |
| RO-5 | Run verdict uses capability-gap precedence and otherwise the most severe projected outcome; every sample row retains the accepted uniform evidence contract | COMPLETE |
| RO-6 | API and Web expose the same persisted current/stale/completed/failed evidence, visible failure/recovery, and all applicable Local setup/Strategy/precheck requirements before checked activation | COMPLETE |
| RO-7 | Analysis/precheck/activation paths perform zero media mutation, grant no overwrite/delete/execute authority, never silently fall back, and keep Active equal to the immutable runtime-consumed snapshot | COMPLETE |

## Required Surfaces

- Domain policy/configuration models and destination composition/path-safety helpers.
- SQLite managed-configuration persistence and revision-keyed evidence.
- Application services for managed objects, previews, destination precheck and checked activation.
- Authenticated API routes and Operator Web configuration journey using the same behavior,
  permissions, validation and recovery semantics.
- Automated acceptance/regression evidence for policy CRUD, previews, Local precheck, multi-sample
  rows/collisions/verdict, stale/current evidence, checked activation, RecognitionType C and zero
  mutation/authority.

## Safety Invariants

- Scanner, Parser, Recognition, Metadata, Naming, Classification, Planner, preview and DryRun do not
  mutate Storage; only OrganizerExecutor may do so.
- Destination precheck is Local-only and read-only. Its guard mutation counters remain zero and it
  grants no overwrite, delete or execute authority.
- Delete/overwrite require explicit policy and authority; unsupported operations never silently
  degrade to Copy or Move.
- RecognitionType C remains C while reusing Naming/Classification policies from A.
- Checked activation consumes evidence for the exact revision and publishes one immutable runtime
  snapshot atomically; stale/failed/missing/capability-gap evidence fails closed where applicable.
- API/Web remain permission- and behavior-consistent; evidence/logs remain bounded and secret-free.
- Batch samples retain independent state, outcome and explicit recovery.

## Explicitly Deferred

The following are outside this Slice and are not closure blockers:

- remote SMB/OpenList/S3 destination precheck;
- mutation-based Storage capability probing;
- multiple RecognitionTypes or multiple destination Storages in one precheck request;
- known-media duplicate detection (`ConflictType.DUPLICATE_MEDIA`);
- attachment destination precheck;
- absolute mounted-path display;
- Provider switching;
- generic Task resume and per-item Processing Checkpoint recovery;
- the broader manual-organize journey;
- unattended or scheduled `organize --execute`.

## Slice Acceptance Criteria

- [x] A review of Base..Implementation Head confirms RO-1 through RO-7 across every Required Surface.
- [x] The operator journey has a discoverable entry, visible exact-revision state/action, successful
      preview/precheck/activation outcome, bounded failures, durable state and explicit recovery.
- [x] Single- and multi-sample behavior preserve independent rows; one failure does not erase or
      overwrite another sample's diagnosis/recovery.
- [x] Active configuration identity and runtime consumption cannot diverge.
- [x] Final focused/integration/full validation passes at the actual Implementation Head, with skips
      and unavailable external gates reported rather than counted as proof.
- [x] Safety audits confirm zero mutation/authority for preview/precheck and no weakened destructive
      operation boundaries.
- [x] Requirements, Product Experience and Architecture CURRENT/TARGET claims are truthful and all
      Explicitly Deferred items remain non-claims.
- [x] No unresolved in-Slice P0/P1 defect remains. P2 improvements and optional extra proof do not
      block closure.

## Final Validation Expectations

B performs one `SLICE FINAL` validation before readiness:

- the complete offline regression suite (last known evidence: 874 tests, 7 explicit external-service
  skips; report actual current totals);
- focused Naming/Classification/Organize/destination/activation/API/Web suites;
- Ruff lint/format, compileall, dependency check, both example configuration validations, wheel
  build and isolated smoke;
- schema-marker, Markdown-link, private-config/secret, FFmpeg/FFprobe, business-filesystem mutation
  and `git diff --check` audits;
- Base..Implementation Head manifest and safety-boundary inspection.

No real production Storage, Provider, credential or media data is required. Previously accepted
falsification probes need not be mechanically replayed unless B finds a concrete regression signal.

## Closure Status

No closure blocker remains. A independently reviewed Base..Implementation Head, accepted RO-1
through RO-7 and every Required Surface, found no unresolved in-Slice P0/P1 defect, and completed
the authoritative factual reconciliation. Explicitly Deferred work remains outside this closed
Slice and is not a delivered claim.

## Closure Packet

```text
Slice: 22.6 — Naming / Classification / Organize Configuration Journey
Base SHA: 7339a8b21b244e57bdb8067f688df91c7dc03280
Head SHA: 89f064b22be5c1f04ae75bfc0d6fbe72c9147e7d

Required Outcomes:
- RO-1: COMPLETE
- RO-2: COMPLETE
- RO-3: COMPLETE
- RO-4: COMPLETE
- RO-5: COMPLETE
- RO-6: COMPLETE
- RO-7: COMPLETE

Required Surfaces:
- Domain policy/configuration models and destination path-safety helpers: COMPLETE
- SQLite revision-keyed managed-configuration evidence: COMPLETE
- Application preview, precheck and checked-activation services: COMPLETE
- Authenticated API and Operator Web journey: COMPLETE
- Acceptance, regression and safety evidence: COMPLETE

Implemented:
- Managed NamingPolicy, ClassificationPolicy and OrganizePolicy lifecycle and previews
- Exact-revision destination composition and attributed organize authority
- Local read-only destination precheck, checked activation and Web/API recovery journey
- Multi-sample independent rows, collision detection, uniform evidence and run verdict

Tasks completed:
- Legacy 22.6-A through O/F1 implementation history; no current micro-Slice lifecycle objects

Final Tests:
- Focused Naming/Classification/Organize/destination/activation/API/Web: 198 passed
- Complete offline regression: 874 passed, 7 explicit external-service skips
- Ruff check/format (311 files), compileall, pip check and both example validations: passed
- Wheel build and isolated install/configuration/database smoke: passed
- Markdown links: 123 tracked files, 36 local links, 0 broken; git diff --check: passed

Safety Evidence:
- Configuration schema marker 10 and Runtime schema marker 22 remain valid
- FFmpeg/FFprobe production audit and direct business-filesystem mutation audit: 0 findings
- Storage mutation calls remain confined to OrganizerExecutor
- Private config is ignored/untracked/unstaged; high-confidence secret/private-path scan: 0 findings
- Exact-revision, zero-mutation/authority, RecognitionType C and immutable activation regressions pass

Known Non-blocking Issues:
- Python 3.13 emitted existing unclosed-SQLite ResourceWarning messages without test failures
- Stable documents retain some legacy Phase/SHA lifecycle annotations for A reconciliation
Explicitly Deferred: see Contract above
Documentation Reconciliation Needed:
- A decides whether to update the canonical Chinese CURRENT-status header and normalize remaining
  legacy checkpoint annotations in stable CURRENT documents during closure
- A records the final Slice decision and reconciles authoritative closure documents once

Decision: SLICE READY FOR A REVIEW
```

## A Final Review

```text
Reviewed Range: 7339a8b21b244e57bdb8067f688df91c7dc03280..89f064b22be5c1f04ae75bfc0d6fbe72c9147e7d
Decision: PASS
P0/P1 Blockers: NONE
Closure Reconciliation: SLICE.md, TASK.md, Roadmap, Progress, canonical CURRENT status,
  Product Experience CURRENT and Architecture CURRENT were reconciled in the Slice closure
  checkpoint. Stable requirements did not require modification.
```
