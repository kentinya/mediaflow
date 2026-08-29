# Task [ID] — [Coherent implementation unit]

This Task follows [the development workflow](../docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](../SLICE.md).

```text
Task ID: [ID]
Parent Slice: [Slice ID / Name]
Status: PLANNED
Task Base: [full SHA]
Difficulty: Low | Medium | High
Test Level: T0 | T1 | T2 | T3 | T4
Planner / Reviewer: B
```

## Goal

State the one coherent behavior this Task completes and name the parent Slice Required Outcome it
advances. This is an implementation unit, not a smaller Slice.

## Why This Task Exists

Describe the actual user/product/architecture gap found in code and tests. Explain why this is the
largest reasonable next unit and why it belongs inside the current Slice.

## Implementation Scope

List the affected behavior and required layers. Prefer a complete vertical or architectural unit,
for example:

```text
Domain → Persistence → Application → API → Web → Tests
```

List any files or areas that are explicitly frozen when that matters.

## Acceptance Criteria

- [ ] The promised behavior works through every required affected surface.
- [ ] Success, failure and recovery semantics match the parent Slice where applicable.
- [ ] Safety and architecture invariants remain intact.
- [ ] Required compatibility, concurrency, stale-state or per-item behavior is covered where
      applicable.
- [ ] The assigned Test Level passes with actual evidence.
- [ ] The checkpoint contains only this Task and is coherent/reviewable.

Replace or extend these with concrete Task-specific criteria; do not retain inapplicable boilerplate.

## Required Tests

List exact focused/related/quality commands required by the assigned Test Level. Full regression is
required only for T4 or when B gives a concrete risk-based reason. Real external services require an
explicit isolated acceptance plan and never use production data.

## Non-goals

- Work outside the parent Slice Contract.
- The next Task or next Slice.
- Optional proof, copy polish, P2 cleanup or refactor not required by these Acceptance Criteria.
- Any Task-specific exclusion.

## Developer Completion Report

### Changed Files

### Implemented

### Tests and Results

### Decisions

### Remaining In-Slice Work

### Risks / Deviations

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: [full SHA]
```

## B Review Result

```text
Reviewed: [Head SHA or Task Base..Head]
Decision: PENDING | PASS | FIX REQUIRED
Slice Required Outcomes all satisfied: PENDING | YES | NO
Next: PENDING | SAME TASK FIX LOOP | NEXT TASK | SLICE READY FOR A REVIEW
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
