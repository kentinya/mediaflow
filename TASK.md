# Phase 22.6-O — Reconcile Phase 22.6 CURRENT Documentation Before Final Closure

This Task follows [the authoritative development workflow](docs/development-workflow.md).

```text
Status: NOT STARTED
Commit SHA: PENDING
High Audit: PENDING
Baseline for this Slice (BASE): the Phase 22.6-N PASS review-record commit that is HEAD when work
  starts. Record its full SHA in the Completion Report and anchor every identity command on it
Preceding accepted checkpoint: 5884905c2105cf8ff78ff10d1b872875045769d7
  (Phase 22.6-N — PASS / CLOSED, 2026-08-29)
Phase: 22.6 Naming / Classification / Organize configuration journey
Slice scope: documentation only. Reconcile stale CURRENT claims in requirements, Product Experience
  and Architecture with the already accepted Phase 22.6-A through 22.6-N behavior. Zero production,
  test, schema, route, permission, configuration, script, roadmap or progress change
Next gate: independent High Review of this Slice, then a separate phase-level Final Closure Audit;
  this Slice MUST NOT declare Phase 22.6 PASS / CLOSED and MUST NOT define or begin Phase 23
```

## Why This Slice Exists

Phase 22.6-N is independently accepted, and every implementation/evidence Slice from 22.6-A through
22.6-N now has its own High PASS. The runtime journey is therefore ready for phase-level closure
inspection, but several stable CURRENT documents still contain pre-Phase-22.6 status sentences:

- `docs/requirements.md` still says Phase 22.6-E awaits High Review and elsewhere says the whole
  Naming/Classification/Organize journey is unimplemented;
- `docs/architecture.md` still calls managed Phase 22.6 configuration later work and closes its
  destination-precheck narrative only at Phase 22.6-E even though the paragraph describes later
  accepted slices;
- `docs/product-experience.md` labels the complete destination-precheck journey as only E/F and its
  opening sentence still says one sample before the same section describes the accepted 1-8 sample
  behavior.

Those statements predate Phase 22.6-N and were explicitly outside that test-only Slice. They are not
a reason to reopen N, but documentation accuracy is a mandatory Final Closure condition. This Slice
corrects only those facts and records the already-shipped row/verdict contract; it changes no runtime
behavior and does not itself close the Phase.

## Journey Framing

- **User problem**: operators and reviewers cannot tell which Phase 22.6 behavior is CURRENT when
  stable documents simultaneously describe the implemented journey and call it unimplemented.
- **Entry point**: the canonical requirements, Product Experience and Architecture documents.
- **Visible state**: one consistent account of the accepted Local, bounded, read-only configuration
  journey through Phase 22.6-N and its explicitly deferred boundaries.
- **Available action**: read the exact CURRENT capability and use its documented recovery/actions;
  no product control changes.
- **Success outcome**: all three documents agree with actual code, tests and accepted checkpoint
  history, without claiming phase-level closure before the Final Closure Audit.
- **Failure outcome**: any stale status, invented capability, omitted safety boundary or premature
  phase-closure claim blocks this Slice.
- **Recovery path**: correct only the inaccurate documentation sentence, rerun documentation and
  regression gates, and resubmit this same Slice for High Review.

## Acceptance Criteria

1. `docs/requirements.md` no longer says Phase 22.6-E awaits review, that Phase 22.6 is unimplemented,
   or that its Naming/Classification/Organize journey has not started. It states instead that A-N
   have independent Slice PASS while the phase-level Final Closure Audit remains pending.
2. The requirements CURRENT block accurately summarizes the accepted Local-only precheck: 1-8
   samples under one RecognitionType, independent rows/recovery, same-Storage requirement,
   cross-item collision detection, most-severe run verdict, capability-gap precedence, checked
   activation, and zero mutation/authority.
3. `docs/product-experience.md` identifies the destination-precheck/activation section as the
   accepted E-N journey, says the input is one sample or a bounded array of up to eight, and states
   both verdict directions proved in N: uniformly ready rows produce `ready`; any missing required
   capability produces `capability_gap` even when all rows are otherwise ready.
4. Product Experience retains the full user journey: entry point, visible run summary and per-item
   rows, collision/failure outcomes, explicit recovery, stale evidence behavior, checked-activation
   refusal and safe retry. No user-visible feature is invented.
5. `docs/architecture.md` no longer calls managed Phase 22.6 configuration later work. Its CURRENT
   destination-precheck section identifies A-N as Slice-accepted and Phase closure as pending, and
   records the uniform ordered row contract:
   `index`, `relativeDestination`, `destinationPath`, `targetExists`, `plannerConflicts`,
   `projectedOutcome`, `proposedRelativeDestination`, `failureCategory`, `message`, `nextAction`.
6. Architecture records the existing verdict rule without changing it: `capability_gap` has
   run-level precedence; otherwise the most severe non-null projected outcome wins. It must not claim
   that a filter, truncation ladder or remote capability exists when code does not provide it.
7. All three documents retain these explicit TARGET/non-claims: remote SMB/OpenList/S3 destination
   precheck, mutation-based capability probing, multiple RecognitionTypes or destination Storages per
   request, known-media duplicate detection, attachment precheck and absolute mounted-path display.
   Provider switching, generic Task resume, per-item checkpoint recovery and unattended execute also
   remain outside Phase 22.6.
8. No phase-level closure claim is added. The only allowed next gate is the separate Phase 22.6 Final
   Closure Audit after this Slice receives independent PASS.
9. No production or test file changes. Full/focused totals stay exactly 874/60 with seven full-suite
   skips; Configuration marker remains 10 and Runtime marker remains 22.

## Technical Scope

Files this Slice may change — nothing else:

- `docs/requirements.md`;
- `docs/product-experience.md`;
- `docs/architecture.md`;
- `TASK.md` (status, closure checklist and Completion Report only after implementation begins).

Explicitly forbidden:

- every file under `mediaflow/` and `tests/`;
- `docs/progress.md` and `docs/roadmap.md` (the High review record already owns their current gate);
- `scripts/`, `config/`, `pyproject.toml`, the canonical Chinese product specification and all files
  under `Task/`;
- schema markers, migrations, routes, permissions, API/Web/CLI behavior, evidence fields or ordering;
- any production comment, formatting or type-only change.

## Required Documentation Changes

### 1. Requirements

Update only the Phase 22.6 CURRENT/status paragraphs around the existing overview, NamingPolicy
configuration section and Managed Configuration section. Preserve all stable requirement IDs and
normative product rules. The following stale phrases must have zero matches after the Slice:

- `Phase 22.6-E 等待独立 High Review`;
- `下一 Phase 22.6 Naming/Classification/Organize 配置旅程尚未实现`;
- the unqualified statement that Phase 22.6 Naming/Classification/Organize remains unfinished.

Replace them with precise Slice-vs-Phase language: A-N are independently accepted; Phase 22.6 itself
is still open pending this documentation Slice and the later Final Closure Audit.

### 2. Product Experience

Rename the current destination-precheck section so it covers Phase 22.6-E through N. Correct the
opening single-sample sentence to the real one-or-1-8 input. Add only the missing CURRENT facts needed
for closure: uniform row contents, run-level verdict directions, and N's accepted proof checkpoint.
Keep the checked-activation behavior and all failure/recovery text semantically unchanged.

### 3. Architecture

In the CURRENT destination-precheck narrative, add the exact ordered ten-key row contract and the
two-sided verdict rule already implemented and tested. Replace the E-only terminal acceptance
sentence with an A-N Slice-acceptance statement plus an explicit pending Final Closure Audit. In the
later Configuration CURRENT summary, replace the stale claim that Phase 22.6 remains later work with
the accepted bounded scope and the six deferred capabilities. Do not alter TARGET architecture.

## Required Verification

Run and report actual output:

- `rg` negative checks for every stale phrase named above and the architecture phrase
  `Naming/Classification/Organize configuration (Phase 22.6) remain later work`;
- `rg` positive checks for Phase 22.6-N checkpoint
  `5884905c2105cf8ff78ff10d1b872875045769d7`, pending Final Closure Audit, the ten ordered row keys,
  `ready`, `capability_gap`, and all six deferred destination capabilities;
- Markdown local-link audit using exactly the tracked `.md` paths from `git ls-files -z '*.md'`;
- `.venv/bin/python -m unittest tests.test_operator_ui
  tests.test_configuration_destination_precheck tests.test_configuration_destination_activation`
  — exactly 60 tests, OK;
- `.venv/bin/python -m unittest` — exactly 874 tests, OK, seven skips;
- `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .`;
- `.venv/bin/python -m compileall -q mediaflow tests` and `.venv/bin/python -m pip check`;
- both example `config validate` commands;
- wheel build and `scripts/wheel_smoke_test.py`, retaining markers 10 / 22;
- `git diff --check`, FFmpeg/FFprobe audit, business-layer filesystem-mutation audit,
  `config/alist.json` ignored/untracked/unstaged checks and Slice-diff credential scan;
- identity against BASE: the complete diff lists only the three named CURRENT documents and
  `TASK.md`; diffs over `mediaflow`, `tests`, `scripts`, `config`, `pyproject.toml`,
  `docs/progress.md`, `docs/roadmap.md`, the Chinese requirements specification and `Task/` are empty.

No result-size measurement is required because production is byte-identical. Record that Phase
22.6-M's measured 11049-byte eight-sample result and 32768-byte limit remain unchanged; do not turn
the known absence of a destination-side truncation ladder into this Slice's implementation work.

## Non-goals — Must Not Start

- Phase 22.6 Final Closure Audit or any `PASS / CLOSED` claim for the whole phase.
- Any Phase 23 capability or any of Roadmap sections 6-8.
- New production behavior, tests, evidence fields, UI labels, API payloads, routes, permissions,
  schema/table/migration changes or marker bumps.
- Closing non-blocking proof observations: single-sample run-level field order, other `YES`/`NO`
  render sites, or the semantically redundant non-null outcomes filter.
- Adding a destination-result truncation ladder or changing the 32 KiB limit.
- Implementing any of the six deferred destination capabilities, Provider switching, generic Task
  resume, per-item Processing Checkpoint recovery, manual organize or unattended execute.
- Push, force push, amend, squash, history rewrite, `git reset --hard` or destructive clean.

## Closure Checklist

- [ ] Only the three named CURRENT documents and `TASK.md` changed.
- [ ] Every stale phrase has zero matches; every required positive CURRENT fact is present.
- [ ] A-N are recorded as Slice PASS while Phase 22.6 remains open pending Final Closure Audit.
- [ ] Product Experience describes the real one-or-1-8 entry, visible state, outcomes and recovery.
- [ ] Architecture records the exact ten-key row order and two-sided verdict rule without inventing
      runtime behavior.
- [ ] All six deferred destination capabilities and broader later-work boundaries remain explicit.
- [ ] Production/tests/schema/roadmap/progress/specification/history are byte-identical to BASE.
- [ ] Focused 60 and full 874/7-skips suites pass; all static, package, Markdown and safety gates pass.
- [ ] One coherent documentation-only checkpoint is created; no push.
- [ ] Completion Report records BASE, exact diff, actual commands/results and remaining Final Closure
      gate.

## Completion Report

> Fill this in at the checkpoint. Report actual results and any deviation. Do not mark Phase 22.6
> closed and do not define Phase 23.

### Changed Files

### Implemented

### Tests

### Test Results

### Documentation Evidence

### Validation Evidence

### Decisions

### Remaining Work

### Risks
