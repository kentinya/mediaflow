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

- [ ] The promised behavior completes the required user journey through every affected surface,
      including success, failure and recovery semantics from the parent Slice.
- [ ] A normal Web journey needs no avoidable CLI fallback, raw internal-token transfer or
      implementation-detail ceremony; added friction represents meaningful human intent.
- [ ] Stable UX-first requirements and all correctness, security, data-integrity and architecture
      invariants remain intact.
- [ ] Required compatibility, concurrency, stale-state or per-item behavior is covered where
      applicable.
- [ ] The assigned Test Level passes with actual evidence.
- [ ] The checkpoint contains only this Task and is coherent/reviewable.

Replace or extend these with concrete Task-specific criteria; do not retain inapplicable boilerplate.

## Required Tests

Follow the staged test/evidence rules in `docs/development-workflow.md`. List exact commands and
the behavior/risk each covers. T0–T3 full suites need a concrete reason; T4 keeps complete assigned
checkpoint gates. The parent Slice's explicit validation requirements take precedence.

### Development and correction feedback

List the changed/new tests, directly affected regressions and necessary integration/browser checks
to run while coding or correcting a blocker. These runs do not replace final checkpoint gates.

### Final checkpoint gates

List the required focused/integration/regression/quality commands for the submitted candidate.
State the risk-based reason for any T0–T3 full suite. If a final full suite covers the focused cases
under the required configuration, identify that coverage instead of duplicating the run. Keep
separate real-Python/Docker/visual/compatibility gates where required. Real external services need
an explicit isolated acceptance plan and never use production data.

### B independent verification

Name the critical user journey or safety behavior B must independently reproduce and the actual
artifacts B must inspect. Other checkpoint gates may use verified matching evidence under the
workflow's reuse rules; missing or incompatible evidence requires a fresh run.

### Evidence and rerun rules

Specify a stable ignored artifact location or CI artifact reference; retain it through A's final
decision. Record source/checkpoint identity, commands/environment/dependency/configuration/selection
and built-artifact identity, results/counts/durations and readable raw logs/visuals. Keep first
failures and repeats. Declare reuse and uncovered gates; `/tmp` alone or a completion report is
insufficient. Source/input changes require fresh affected evidence; T4 final candidates retain
complete gates. Report-only successors require verified unchanged runtime inputs and rerun any
checks that consume the changed documents.

## Non-goals

- Work outside the parent Slice Contract.
- The next Task or next Slice.
- Optional proof, copy polish, P2 cleanup or refactor not required by these Acceptance Criteria.
- Any Task-specific exclusion.

## Developer Completion Report

### Changed Files

### Implemented

### Tests and Results

Include the evidence index and actual commands/counts/durations. Identify the validated candidate,
first failures/repeats, reused matching runs and any missing/failed/unavailable gate. Do not claim
development-only feedback or an unverifiable prior run as final checkpoint acceptance.

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
