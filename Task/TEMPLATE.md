# Task [ID] — [Coherent implementation unit]

This Task follows [the development workflow](../docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](../SLICE.md).

Planning/review reads [B's experience](../docs/agent-experience/task-planner-reviewer.md);
implementation reads [Developer's experience](../docs/agent-experience/developer-implementation-role.md).

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

Follow [test levels, stages and evidence rules](../docs/development-workflow.md#6-test-levels).
The Slice's explicit validation requirements take precedence. Fill in Task-specific commands and
risks; do not copy the general workflow here.

### Development and correction feedback

Commands for changed tests, known failures, affected regressions and necessary integration/browser feedback.

### Final checkpoint gates

Assigned acceptance commands and covered risks. Explain any T0–T3 full suite; T4 retains complete
assigned gates. Identify focused coverage included in a full run and any separate required gates.

### B independent verification

Critical behavior B reproduces independently and matching evidence B inspects; declare any reuse.

### Evidence and rerun rules

Stable ignored/CI artifact reference, candidate/input identities and Task-specific rerun conditions.
Record actual results and missing/failed/unavailable gates under the linked workflow rules.

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

If new reusable lessons emerge, supply brief candidates for the Slice Closure Packet. A merges
them at Slice closure; a separate per-Task summary is not required and is not a PASS gate.

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
