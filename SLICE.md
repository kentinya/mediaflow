# Slice 22.6 — Naming / Classification / Organize Configuration Journey

This is the A-owned Slice Contract. B and Developer may not expand or weaken it. Detailed lifecycle
rules are defined only in [`docs/development-workflow.md`](docs/development-workflow.md).

```text
Slice ID: 22.6
Owner: A — Slice Owner / Architect / Final Reviewer
Status: READY FOR B READINESS CHECK
Base SHA: 7339a8b21b244e57bdb8067f688df91c7dc03280
Implementation Head: 89f064b22be5c1f04ae75bfc0d6fbe72c9147e7d
A Final Review: PENDING
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
| RO-1 | NamingPolicy, ClassificationPolicy and OrganizePolicy are managed through the same Draft/version/digest, validation, reference protection, audit and immutable activation authority | IMPLEMENTED — B verification pending |
| RO-2 | The exact selected revision provides bounded, secret-free naming, classification, organize-authority and composed-destination preview using production policy/engine semantics | IMPLEMENTED — B verification pending |
| RO-3 | Destination composition preserves RecognitionType identity, attributes policy/library contributions, uses Storage-relative safe paths and exposes actionable unsafe/unresolved outcomes | IMPLEMENTED — B verification pending |
| RO-4 | Local destination precheck is read-only, bounded and supports one sample or 1–8 samples under one RecognitionType, one destination Storage, independent rows/recovery and cross-item collision detection | IMPLEMENTED — B verification pending |
| RO-5 | Run verdict uses capability-gap precedence and otherwise the most severe projected outcome; every sample row retains the accepted uniform evidence contract | IMPLEMENTED — B verification pending |
| RO-6 | API and Web expose the same persisted current/stale/completed/failed evidence, visible failure/recovery, and all applicable Local setup/Strategy/precheck requirements before checked activation | IMPLEMENTED — B verification pending |
| RO-7 | Analysis/precheck/activation paths perform zero media mutation, grant no overwrite/delete/execute authority, never silently fall back, and keep Active equal to the immutable runtime-consumed snapshot | IMPLEMENTED — B verification pending |

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

- [ ] A review of Base..Implementation Head confirms RO-1 through RO-7 across every Required Surface.
- [ ] The operator journey has a discoverable entry, visible exact-revision state/action, successful
      preview/precheck/activation outcome, bounded failures, durable state and explicit recovery.
- [ ] Single- and multi-sample behavior preserve independent rows; one failure does not erase or
      overwrite another sample's diagnosis/recovery.
- [ ] Active configuration identity and runtime consumption cannot diverge.
- [ ] Final focused/integration/full validation passes at the actual Implementation Head, with skips
      and unavailable external gates reported rather than counted as proof.
- [ ] Safety audits confirm zero mutation/authority for preview/precheck and no weakened destructive
      operation boundaries.
- [ ] Requirements, Product Experience and Architecture CURRENT/TARGET claims are truthful and all
      Explicitly Deferred items remain non-claims.
- [ ] No unresolved in-Slice P0/P1 defect remains. P2 improvements and optional extra proof do not
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

## Current Closure Blockers

No unimplemented product Required Outcome or current P0/P1 blocker was identified by the governance
migration audit. Remaining gates are:

1. B independently checks all Required Outcomes and performs the single Slice-final validation.
2. B fills the Closure Packet and decides either `SLICE READY FOR A REVIEW` or identifies a genuine
   blocker; optional test/copy/documentation polish cannot create another micro-Task.
3. A reviews Base..Implementation Head and returns the final Slice decision.

The canonical Chinese specification's opening CURRENT-status narrative still stops before the
completed Phase 22.6 journey, and stable product/architecture documents retain some pre-migration
checkpoint annotations. These are A-owned factual closure reconciliation, not authorization for a
new Implementation Task and not evidence of an unimplemented product outcome.

## Closure Packet

```text
Slice: 22.6 — Naming / Classification / Organize Configuration Journey
Base SHA: 7339a8b21b244e57bdb8067f688df91c7dc03280
Head SHA: 89f064b22be5c1f04ae75bfc0d6fbe72c9147e7d

Required Outcomes: PENDING B READINESS CHECK
Implemented: PENDING B CLOSURE PACKET
Tasks completed: legacy implementation history; compact mapping pending B
Final Tests: PENDING SLICE FINAL
Safety Evidence: PENDING B CLOSURE PACKET
Known Non-blocking Issues: PENDING B CLOSURE PACKET
Explicitly Deferred: see Contract above
Documentation Reconciliation Needed: canonical Chinese CURRENT-status header; decide whether to
  normalize remaining legacy checkpoint annotations in stable CURRENT documents during A closure

Decision: PENDING
```

## A Final Review

```text
Reviewed Range: 7339a8b21b244e57bdb8067f688df91c7dc03280..89f064b22be5c1f04ae75bfc0d6fbe72c9147e7d
Decision: PENDING
P0/P1 Blockers: PENDING
Closure Reconciliation: PENDING
```
