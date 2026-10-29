# Task [ID] — [Coherent implementation unit]

Authority: committed [SLICE.md](../SLICE.md) for a Slice Task, or the explicit user-authorized
independent bug scope; [Development Workflow](../docs/development-workflow.md) governs both paths.
Read the [B](../docs/agent-experience/task-planner-reviewer.md) or
[Developer](../docs/agent-experience/developer-implementation-role.md) experience for your role.

```text
Task ID: [ID]
Task Type: SLICE | STANDALONE MINOR BUG
Parent Slice: [numeric Slice ID for SLICE; NONE for STANDALONE MINOR BUG]
Status: PLANNED
Task Base: [full SHA]
Difficulty: Low | Medium | High
Test Level: T0 | T1 | T2 | T3 | T4
Planner / Reviewer: B
```

Choose one concrete Task Type and its matching Parent Slice. Standalone minor bugs are owned and
finished by B, without reopening an accepted Slice or changing its Roadmap/closure ledger.
Existing Slice Tasks may omit Task Type for compatibility; new plans should state it explicitly.
If the user requested planning only, keep a clearly marked draft under a no-active-implementation
notice; the plan does not itself authorize implementation or other agents.

## Goal

One coherent behavior tied to a named Slice Required Outcome or the authorized independent bug,
with the actual code/product gap and bounded correction scope.
For user-facing work: goal, entry, visible state, action, success, failure and recovery.

## Implementation Scope

Affected behavior/layers and explicit frozen boundaries. Reuse existing services; no fragmented
field/module-only Tasks. Give simple ordered steps with concrete inputs/outputs and failure handling:

1. ...
2. ...
3. ...

## Acceptance Criteria

Concrete observable Task outcomes, including applicable safety, stale/concurrent/per-item behavior.
Do not repeat generic policy or retain inapplicable boilerplate.

- [ ] ...
- [ ] ...

## Required Tests

Follow [test levels and ownership](../docs/development-workflow.md#6-test-levels).

### Developer — affected tests

Exact commands for this round's new/modified tests, known failing cases, directly affected
regressions/integration and changed-file checks; state the covered risks. No full-suite assignment.

### B — acceptance and full regression

Critical behavior to reproduce and risk-specific integration/native/packaging commands. Reference
[shared full gates](../docs/development-workflow.md#shared-full-regression-commands) for applicable
T4 coverage; explain any T0–T3 full-suite need. B runs/records acceptance before PASS, including full
regression for T4. Developer hands off after its affected tests, without running B's full gates.

## Non-goals

Task-specific exclusions within the parent Contract or independent bug scope; no next Task/Slice,
scope expansion or optional proof/cleanup promoted to a blocker.

## Developer Completion Report

- Checkpoint: full SHA; Status READY FOR B REVIEW.
- Changed behavior/files and key decisions.
- Affected tests: actual commands/results, known failures and risks.
- Remaining Task work; full acceptance is pending B.

Keep the report compact; no full-suite evidence dossier or per-round diary.

## B Review Result

```text
Reviewed: [SHA or Task Base..Head]
Decision: PASS | FIX REQUIRED
Acceptance runs: [commands/results or log reference; full gates when applicable]
Task blockers: [none or actionable fixes]
Slice Required Outcomes / Surfaces all satisfied (Slice Tasks only): YES | NO
Authorized bug acceptance complete (standalone Tasks only): YES | NO
Next: SAME TASK FIX LOOP | NEXT TASK | SLICE READY FOR A REVIEW | NO ACTIVE IMPLEMENTATION TASK
```

For FIX REQUIRED give simple fix steps here; explain cause/introduction/user trigger in the review
response. For a new plan explain usage scenario and complexity/new states/races in the response,
not this file. No Slice closure or Roadmap update by B. For a standalone bug, B records PASS with
the exact reviewed Base..Head and results, then restores the compact no-active-implementation
notice; no A Final Review/Closure Packet is needed.
