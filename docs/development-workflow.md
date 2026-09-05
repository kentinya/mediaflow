# MediaFlow Development Workflow

This document is the sole authority for development management. `AGENTS.md` owns permanent product,
architecture and safety invariants; this file owns Slice and Task lifecycle, A/B/Developer work,
testing levels, Git checkpoints, review, closure and legacy migration.

## 1. Formal management objects

MediaFlow has exactly two current development-management objects:

1. **Slice** — one complete business-capability range owned by A and defined in root `SLICE.md`.
2. **Task** — one coherent implementation unit inside that Slice, planned and reviewed by B and
   defined in root `TASK.md`.

Phase names, historical A/B/C suffixes, rejected checkpoints and correction names may remain in Git
or legacy archives, but they are not additional lifecycle objects. A fix is normally another pass
through the original Task; it does not automatically create an F1/F2 Task or a new Slice.

## 2. Roles

Role names are decision authorities, not model-size labels. The Developer must not issue B PASS for
its own Task checkpoint, and B must not issue A Final Review for the same Slice. A review inspects
actual repository state and tests rather than accepting a completion report. Any emergency exception
requires explicit user authorization and must be disclosed in the review result.

### A — Slice Owner / Architect / Final Reviewer

A:

- audits requirements, journeys, architecture, code, tests and current repository state;
- defines one large Slice, its Base SHA, user goal, Required Outcomes, required surfaces, boundaries,
  safety invariants, Explicitly Deferred work, acceptance criteria and final validation;
- owns and materially changes `SLICE.md` and large-Slice Roadmap boundaries;
- reviews the entire Slice Base..Implementation Head after B submits a Closure Packet;
- decides `PASS`, `FIX REQUIRED`, or `PARTIAL / RESCOPE`;
- after PASS, reconciles authoritative CURRENT documents once and declares the Slice `PASS / CLOSED`;
- selects the next large Slice only after closure.

A does not plan file-level implementation steps, perform routine Task review, or create another
Slice merely to add a test, assertion, evidence key, UI label or non-blocking wording improvement.

### B — Task Planner / Task Reviewer

B starts every planning or review turn by reading `SLICE.md` and inspecting actual code and tests.
B:

- selects the largest reasonable next coherent implementation unit inside the Slice;
- creates `TASK.md` with Goal, Difficulty, Test Level, scope, acceptance criteria, tests and
  non-goals;
- reviews the Developer's actual Task checkpoint or explicit Task Base..Head range;
- returns `PASS` or `FIX REQUIRED` for the Task;
- keeps fixes in the same Task unless the proposed work is a genuinely independent business goal;
- after every Task PASS, answers: **Are all current Slice Required Outcomes satisfied?**

If the answer is YES, B must not create another Task for test-only completeness, an additional
falsification probe, a field already known to work, non-blocking copy, P2 cleanup, or an improvement
unrelated to Required Outcomes. B runs the Slice-final gate, emits a Closure Packet with decision
`SLICE READY FOR A REVIEW`, and stops.

If the answer is NO, B may plan the next coherent Task. If a genuine P0/P1 correction is needed
after Slice-final preparation, B creates one focused correction Task inside the same Slice.

### Developer — Implementation Role

Developer:

- reads `SLICE.md`, the active `TASK.md`, required product/architecture guidance and actual code;
- implements only the active Task without expanding the Slice;
- runs the Task's assigned Test Level and records actual commands/results;
- creates a coherent implementation checkpoint and reports its full SHA, changed files, behavior,
  tests, decisions, remaining in-Slice work and risks;
- continues in the same Task after `FIX REQUIRED` unless B explicitly authorizes a new Task.

Developer does not define the next Task, materially edit `SLICE.md`, change the Roadmap, declare
Task PASS, or declare a Slice closed.

## 3. State machines

### Task lifecycle

```text
PLANNED
→ IN PROGRESS
→ READY FOR B REVIEW
→ PASS
```

Correction loop:

```text
READY FOR B REVIEW
→ FIX REQUIRED
→ IN PROGRESS
→ READY FOR B REVIEW
```

Task has no `CLOSED` state. After Task PASS there are only two legal outcomes:

```text
NEXT TASK
```

or:

```text
SLICE READY FOR A REVIEW
```

### Slice lifecycle

```text
PLANNED
→ ACTIVE
→ READY FOR A REVIEW
→ PASS / CLOSED
```

Slice correction loop:

```text
READY FOR A REVIEW
→ FIX REQUIRED
→ B creates one focused correction Task
→ Developer implementation
→ B Review
→ READY FOR A REVIEW
```

`READY FOR B READINESS CHECK` is a one-time legacy-migration state only. On its first assessment B
must resolve it to `ACTIVE` with a genuine Required-Outcome blocker and Task, or to
`READY FOR A REVIEW` with a Closure Packet. It must not become a permanent third workflow.

Only A can set `PASS / CLOSED`.

## 4. Slice Contract

Root `SLICE.md` is A-owned and contains at least:

- Slice ID / Name, Owner, Status, Base SHA and Implementation Head;
- User Goal;
- Required Outcomes and Required Surfaces;
- Safety Invariants;
- Explicitly Deferred;
- Slice Acceptance Criteria;
- Final Validation Expectations;
- Closure Packet and A Final Review sections.

B and Developer may update factual progress fields explicitly delegated by the Contract, but must
not add outcomes, weaken criteria, move deferrals into scope, change Base, or redefine boundaries.
Material Contract change returns to A.

Slice Base is the immutable checkpoint immediately before Slice implementation starts. Slice Final
Review always covers Base..Implementation Head, not only the last Task or documentation commit.

## 4.1 Repository governance preflight

Before B plans the first Task for a Slice, the Slice Contract must already be checkpointed in
reachable Git history. B verifies `HEAD:SLICE.md`, not only the working-tree file, and requires the
committed Slice ID to match the planned Task's Parent Slice and the committed Slice status to be
`ACTIVE`. A working-tree Contract that is newer than HEAD is a draft, not an activated Slice; Task
planning stops until the Contract is committed. The corresponding committed Roadmap row must also be
`ACTIVE`.

Before any Developer Task execution, the Developer records `git status --short`, classifies every
pre-existing change, and preserves changes outside the Task ownership. In particular, pre-existing
`SLICE.md`, `docs/roadmap.md`, A-owned requirement/architecture files, B-owned Task state and user
files must not be reset, restored from HEAD, checked out over, cleaned, dropped from a stash, or
silently included in the Task checkpoint. "The Developer does not modify this file" includes
indirectly making its contents disappear through worktree cleanup.

The read-only `scripts/check_governance.py` guard is the executable check for these rules. It uses
committed `HEAD:SLICE.md` and the committed Roadmap as authority, fails fast on an uncheckpointed
working-tree Contract, validates active Task parent/status/Roadmap alignment, and validates Base
SHA commit existence and ancestry. It never edits, stages, resets, restores, checks out, cleans or
stashes repository content. The existing quality workflow runs it before formatting, lint and tests.

Base SHA validation is an ancestry check, not an equality check. A valid sequence is:

```text
Slice Base
  ↓
A Slice Contract / Activation commit
  ↓
B Task planning
  ↓
Developer implementation
```

The Base remains the immutable checkpoint immediately before the Slice implementation line. Contract
and planning commits are allowed after Base and must not cause the Base to move.

## 5. Task planning and sizing

Task planning optimizes for coherent implementation units, not minimum diff size. A Task should
normally deliver a complete reviewable behavior across every affected layer, for example Domain →
Persistence → Application → API → Web → tests, rather than one field, assertion, test, UI label,
evidence key or document sentence.

A normal Slice should usually fit roughly 3–7 major Implementation Tasks. This is a planning
heuristic, not a quota. If B expects more than 8, B must stop and reassess whether Tasks are too
small, the Slice boundary is wrong, or non-blocking work is being promoted. B returns to A for
rescoping when necessary; letter ladders such as A/B/C/.../N/O and automatic F1/F2 chains are not a
substitute for a coherent Slice.

Every Task declares:

- **Difficulty**: `Low`, `Medium`, or `High`;
- **Test Level**: `T0`, `T1`, `T2`, `T3`, or `T4`;
- one Goal tied to a named Slice Required Outcome;
- implementation scope and acceptance criteria;
- required tests appropriate to risk;
- explicit non-goals.

## 6. Test levels

| Level | Use | Default validation |
|---|---|---|
| T0 — DOC | Pure factual documentation sync that does not change product requirements, architecture contracts, safety rules or Slice scope | Markdown/link and relevant textual checks; `git diff --check`; no Python full regression |
| T1 — TEST ONLY | Adds automation for unchanged production behavior | New/changed test plus affected and necessary related test modules; full regression normally omitted |
| T2 — LOCAL | Low-risk implementation within one module/boundary | Focused tests, directly affected module tests and relevant lint/static checks |
| T3 — INTEGRATION | Behavior spanning Application/API/Web/Persistence or comparable layers | Focused, related integration, affected regression and normal quality gates |
| T4 — FULL / HIGH RISK | OrganizerExecutor, Storage mutation, destructive behavior, permissions, Active configuration, migrations/schema, concurrency, core pipeline or safety boundaries | Focused, integration, full regression and complete quality/safety gates |

Canonical requirement changes, architecture-contract changes, safety-rule changes and Slice-scope
changes are not ordinary T0 work. B assigns the level from actual risk, not desired speed.

### SLICE FINAL

Before declaring `SLICE READY FOR A REVIEW`, B normally runs one Slice-level full regression plus
the safety, packaging, migration or real-service gates material to that Slice. This concentrates
expensive final evidence at Slice level instead of repeating it for every small Task. B records
actual totals, skips, unavailable external gates and known non-blocking issues.

## 7. Task execution and review

1. B confirms `SLICE.md` is `ACTIVE`, inspects actual state and writes one Task.
2. Developer implements the Task, runs its Test Level, inspects scope/diff/private files, creates a
   coherent checkpoint, updates the Developer Completion Report and returns `READY FOR B REVIEW`.
3. B reviews the explicit checkpoint or Task Base..Head against Task criteria and the parent Slice.
4. On `FIX REQUIRED`, B lists only Task blockers. Developer corrects the same Task and creates a new
   checkpoint without amending accepted history.
5. On `PASS`, B reevaluates every Slice Required Outcome and chooses only NEXT TASK or
   SLICE READY FOR A REVIEW.

A Task PASS does not update Roadmap or Progress, does not create a `docs(review)` checkpoint, and
does not close any Slice. Detailed Task history lives in Git and the compact final Closure Packet.
`TASK.md` may be replaced when the next Task begins and may travel with that Task's implementation
checkpoint. There is no mandatory review-record → next-task-doc → implementation commit cycle.
The B Review Result may exist in the review output without a standalone commit; if `TASK.md` is
later replaced, the reviewed SHA plus the Slice Closure Packet are the durable compact index back
to Git history.

## 8. Git and checkpoint strategy

- One Implementation Task should normally produce one coherent implementation checkpoint; a
  correction adds a new checkpoint in the same Task loop and never amends reviewed history.
- B Review identifies an explicit SHA or Base..Head. It does not require a standalone review commit.
- A Final Review identifies Slice Base and Implementation Head and audits the complete range.
- Git history is the detailed Task/review history; `docs/progress.md` is not a duplicate log.
- Never rewrite accepted or rejected history, fabricate a SHA, force push, use destructive reset, or
  include unrelated/private files.
- Ordinary local checkpoints follow repository authorization. `git push`, destructive Git and
  history-changing operations require explicit user authorization.

There is no universal per-Task push gate. A Slice Contract may require remote reachability before
downstream integration; otherwise repository-local closure is truthful only as local closure and
must not be reported as pushed. A does not broaden push authorization by declaring PASS.

Before a checkpoint, inspect status, complete diff, name/status/stat, `git diff --check`, the exact
manifest, secrets/private files and all frozen scopes named by the Task.

## 9. B stop rule and Closure Packet

After Required Outcomes are satisfied, B outputs exactly one compact packet and stops Task planning:

```text
Slice:
Base SHA:
Head SHA:

Required Outcomes:
- complete / incomplete

Implemented:
- ...

Tasks completed:
- compact list only

Final Tests:
- ...

Safety Evidence:
- ...

Known Non-blocking Issues:
- ...

Explicitly Deferred:
- ...

Documentation Reconciliation Needed:
- ...

Decision:
SLICE READY FOR A REVIEW
```

Non-blocking test enhancement, copy polish, extra proof, P2 cleanup or an idea unrelated to the
Contract is recorded in the packet or deferred; it is not a reason to generate another Task.

For stop-rule decisions, P0 means a credible data-loss, destructive-operation, security, secret,
authority or whole-journey availability defect. P1 means an unmet Required Outcome, broken required
surface/recovery path, architecture/safety invariant regression or material user-journey break. P2
means a non-blocking quality, wording, maintainability or optional-proof improvement. The Slice may
specialize severity in its Contract but may not downgrade safety or Required Outcomes.

## 10. A Final Review and closure

A reviews Slice Base..Implementation Head and focuses on Required Outcomes, the user journey,
integration completeness, failure/recovery, architecture, safety, final regression, P0/P1 defects
and documentation truthfulness. A does not block closure for optional proof strength, non-blocking
wording, P2 cleanup or future deferred capability.

A returns one of:

- `PASS`
- `FIX REQUIRED` — only current-Slice P0/P1 or unmet Required Outcomes; B creates one focused Task.
- `PARTIAL / RESCOPE` — the Contract or business boundary must return to A before more work.

After PASS, A performs one factual closure reconciliation as needed across `SLICE.md`, Roadmap,
Progress, requirements, Product Experience, Architecture, README/configuration guidance, and then
records `PASS / CLOSED`. Those closure changes should form one coherent Slice-closure checkpoint,
not separate review-record, next-task and status commits. A chooses the next large Slice only after
that closure; B does not pre-plan its Implementation Tasks. The closure checkpoint records the
already-reviewed Implementation Head and does not silently extend the Base..Head product range.
If reconciliation would change product scope, architecture contracts or safety rather than record
facts, A must not hide that change in closure; the decision returns to `PARTIAL / RESCOPE`.

## 11. Document responsibilities

| Document | Responsibility |
|---|---|
| `AGENTS.md` | Permanent architecture, safety, domain invariants, role principles and guidance hierarchy |
| `docs/development-workflow.md` | All detailed Slice/Task lifecycle, planning, testing, review, Git and migration workflow |
| `SLICE.md` | Current A-owned large-Slice Contract and final review packet |
| `TASK.md` | Current B-owned Implementation Task only, or an explicit no-active-Task notice |
| `Task/TEMPLATE.md` | B-owned Task template |
| `docs/roadmap.md` | Large Slice goal, order, dependency and status only |
| `docs/progress.md` | Large Slice closure ledger only |
| `docs/requirements.md` | Stable requirements, not Task status or review logging |
| `docs/product-experience.md` | User journeys, not workflow audit history |
| `docs/architecture.md` | CURRENT/TARGET architecture, not Task workflow |
| `CLAUDE.md` | Thin execution/autonomy and destructive-operation guidance by reference |

## 12. Workspace and private configuration

At the start of a workspace/session, record repository root, branch, HEAD, status, worktree
writability and Git/index writability. Do not bypass a read-only Git boundary. Inspect existing
changes and preserve unrelated user work.

`config/alist.json` must remain ignored, untracked and unstaged. Never expose or commit real tokens,
private endpoints, credentials, cookies, authorization headers or user-private paths. Use only
approved example configuration and fake/local services in tests unless an explicit isolated
acceptance plan authorizes otherwise.

## 13. Legacy migration

- Do not rewrite Git history, accepted/rejected commits or historical `Task/` records.
- Detailed pre-migration Roadmap/Progress logs move intact to dated files under `docs/history/`,
  marked `LEGACY / READ ONLY / NOT CURRENT WORKFLOW AUTHORITY`.
- The new Roadmap and Progress do not translate every historical Phase/Task/Fix into new objects or
  backfill uncertain Base SHAs.
- Historical A–O/F1 names are evidence inside their enclosing migrated Slice, not new lifecycle
  states and not authorization for more lettered work.
- Pre-migration checkpoint/review annotations already embedded in requirements, Product Experience
  or Architecture are legacy factual annotations, not workflow authority. Do not extend them; A may
  remove or normalize them during a later factual Slice reconciliation without creating a Task only
  for wording cleanup.
- A migrated active Slice may use `READY FOR B READINESS CHECK` once. B then either identifies a
  genuine Required-Outcome blocker or submits the Slice Closure Packet; test-only completeness and
  documentation wording alone do not justify another micro-Task.
