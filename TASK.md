# Phase 22.6-G-F1 — The Checked-Activation Blocking Sentence Cannot Silently Disappear

This Task follows [the authoritative development workflow](docs/development-workflow.md).

```text
Status: READY FOR HIGH REVIEW
Commit SHA: PENDING
High Audit: PENDING
Checkpoint under correction: b9cc35e2677a35920042b5695f87b50a80025ef0
  (Phase 22.6-G FIX REQUIRED — 2026-08-28)
Preceding closed checkpoint: e68e901a73107484dc0521b47b1b0001eed2b853
  (Phase 22.6-F PASS / CLOSED — 2026-08-28)
Preserved rejected checkpoints: b9cc35e2677a35920042b5695f87b50a80025ef0 (Phase 22.6-G),
  7353b0d22497e6e3e596c93c7052eea34daf27df (Phase 22.6-E),
  90ce13a6c6c39912dd389f71a1189314ff24eb5d (Phase 22.6-A) and
  08dfd4f921728755209b6d52347d28f221121c47 (Phase 22.5-E); never amended, squashed or rewritten
Push gate: NOT BLOCKING — Slice closure does not require a push; every closed Phase 22.6
  checkpoint and its documentation record is still absent from origin/main, and phase-level
  Phase 22.6 closure requires an explicitly authorized push
Phase: 22.6 Naming / Classification / Organize configuration journey (roadmap section 5)
Slice scope: evidence only. Add the missing falsifiable operator-UI assertions for the Web
  blocking sentence, its two error styles, the shared predicate's return contract and the blocked
  branch's render payload, and record the Completion Report the rejected checkpoint omitted.
  No production file may change: `mediaflow/`, `scripts/`, `config/` and `pyproject.toml` must stay
  byte-identical to b9cc35e2677a35920042b5695f87b50a80025ef0
```

## Why This Correction Exists

The independent review of `b9cc35e2677a35920042b5695f87b50a80025ef0` found the shipped behaviour
correct — one shared Web predicate, wording byte-equal to the server refusal, total applicability,
a hardened module namespace, markers 10 and 22, 849 offline tests green — and rejected it for one
reason: the sentence the Slice exists to put in front of the operator is proven by nothing.

Three independent probes each left the complete suite green:

- deleting all three ``message = `Checked activation blocked: ${nextAction}.` `` assignments
  (`mediaflow/interfaces/operator_ui.py:705`, `:708`, `:716`);
- dropping `message` from the predicate's return object (`:719`);
- replacing the blocked branch's payload at `:727` with a fixed `'Checked activation blocked.'`
  literal, which also discards the `error` style.

The first two are not cosmetic. With `message` null or undefined, `renderDestinationPrecheck` prints
the `text` helper's bare `-`, and the `!requirement.message` guard inside
`destinationPrecheckBlocksCheckedActivation` returns null, so the guided panel silently withholds
its button again and the revision-detail warning falls back to enumerating two requirements — the
exact pre-Slice defect, restored at all three surfaces with every gate green. At parent `f601606`
the four full sentences were asserted verbatim; those assertions are among the 21 lines the rejected
checkpoint deleted from `tests/test_operator_ui.py`, so proof strength decreased on precisely the
strings the Slice changed.

## User Problem

The operator-visible recovery sentence *is* the product outcome of Phase 22.6-G. An unguarded string
can be removed by any later Slice without a single test failing, which returns the operator to
either an offered button the server refuses or a withheld button with no explanation. The Slice's
own Required Test 5 and UX acceptance criterion demand that each new or changed Web string fail a
named test when deleted; that guarantee is missing, so the journey is not durable.

## User Journey

Unchanged from Phase 22.6-G, and deliberately so. This correction adds no user-visible change; it
makes the shipped journey non-regressible.

- User goal: see, before clicking, whether checked activation is available, and when it is not, read
  which requirement blocks it and what action continues.
- Entry point: the managed revision view — guided setup panel and revision detail actions — and the
  unchanged `POST /api/v1/configuration/revisions/<revision-id>/activation` route.
- Visible state, action, success, failure and recovery: exactly as shipped at
  `b9cc35e2677a35920042b5695f87b50a80025ef0`.

The acceptance question for this Slice is therefore not "what does the operator see" but "can the
operator's sentence disappear without a test failing".

## User-visible Outcome

- No user-visible change. Every Web string, style, predicate, gate, evidence document, request
  field, response field, permission, API status code and both schema markers stay exactly as
  shipped.
- After this correction, deleting or weakening any single one of the four blocking-sentence
  assignments, either `style = 'error'` assignment, the `message` entry of the predicate's return
  object, or the render payload of the blocked branch fails a named test.
- The four sentences an operator can actually read are recoverable from `tests/test_operator_ui.py`
  alone, so a future reviewer can check the wording against the server refusal without reading the
  embedded JavaScript.

## Failure and Recovery

This Slice changes no runtime behaviour, so the operator-facing failure and recovery rows of
Phase 22.6-G stand unchanged. The rows below state the regression this correction must make
impossible.

| Failure | Visible state | Durable state | Safe to repeat | Explicit action |
| --- | --- | --- | --- | --- |
| A later change deletes one blocking-sentence assignment | Precheck section prints a bare `-`; guided panel silently withholds its button; revision detail falls back to two requirements | Server gate, Active configuration and every evidence record unchanged; activation still refused with its bounded reason | Yes | The named operator-UI test fails before the change can ship |
| A later change drops `message` from the predicate's return object | The same three surfaces degrade even though all four assignments still exist | Unchanged | Yes | The named return-contract test fails |
| A later change replaces the blocked branch payload with a fixed literal | The sentence loses its next action and its red error style | Unchanged | Yes | The named render-payload test fails |
| A later change deletes a `style = 'error'` assignment | A failed or capability-gap block renders as a yellow warning instead of an error | Unchanged | Yes | The named style test fails |

## UX Acceptance Criteria

- [x] Nothing an operator sees changes: no sentence is reworded, restyled, moved, added or removed.
- [x] Each of the four composed blocking sentences is proven by a body-scoped assertion that fails
      when that single assignment is deleted — not merely when all of them are.
- [x] The failed case's complete composed template, including its bounded failure category, its
      `; ${nextAction}.` tail and its fallback next action, is asserted in full rather than by
      prefix.
- [x] Both `style = 'error'` assignments are proven, so a blocked failure or capability gap cannot
      silently degrade to a warning style.
- [x] The predicate's return object is proven to carry `message` and `style`, so a value that is
      assigned but never delivered fails a test.
- [x] The blocked branch's render payload is proven, so substituting a fixed literal fails a test.
- [x] No assertion is weakened, deleted or made less specific anywhere in `tests/`.

## Technical Scope

- `tests/test_operator_ui.py` — additive assertions only, inside the two existing Phase 22.6-G
  tests (`test_destination_precheck_is_reachable_read_only_and_actionable` and
  `test_checked_activation_controls_share_destination_precheck_gate`) or in one new focused test in
  the same class. Keep using the existing `_js_function_body` / `_js_braced_body` helpers and the
  existing body-scoped style; add no JavaScript runtime, no new dependency and no new test file.
- `TASK.md` — the Completion Report, naming for each falsification probe the exact test that failed.
- Nothing else. No production file, no documentation file, no script, no configuration.

## Non-goals

- No production behaviour change of any kind. If a sentence, style or predicate looks improvable,
  record it in the Completion Report and leave it alone.
- No change to the server gate, its four refusal cases, its order or its wording; no change to
  evidence documents, request fields, response fields, permissions or API status codes.
- No schema change: the Configuration marker stays 10 and the Runtime marker stays 22.
- No documentation edit. The `docs/architecture.md` and `docs/product-experience.md` CURRENT claims
  were independently verified accurate at the rejected checkpoint. `docs/progress.md` and
  `docs/roadmap.md` gate records stay High-only.
- No refactor of the `text` helper's `-` fallback, and no narrowing of the document-level
  applicability rule; both stay recorded observations.
- Not the next feature Slice: remote SMB/OpenList/S3 destination prechecks, mutation-based
  capability probing, duplicate and cross-item collision detection, attachment prechecks, absolute
  mounted-path display and any execution change must not start.

## Safety and Architecture Invariants

- This Slice touches no production code, so every safety invariant is preserved by construction —
  and that must be **proven** by a byte-identity check against
  `b9cc35e2677a35920042b5695f87b50a80025ef0`, not asserted in prose.
- Scanning, parsing, recognition, metadata, naming, classification, planning and DryRun still mutate
  nothing; only `OrganizerExecutor` may mutate Storage, and it is untouched.
- The activation gate still performs no probe and constructs no Storage, Provider, Planner or
  Executor; evidence stays immutable; configuration displayed as Active stays the exact snapshot
  runtime consumes; RecognitionType C stays C.
- Bounded, secret-free explanations only: no credential, endpoint, Storage `rootPath`, header,
  cookie, private path or raw exception text may reach the Web, API, evidence, logs, tests or
  commits. `config/alist.json` is never read, staged or committed.
- No FFmpeg or FFprobe dependency is introduced.

## Required Tests

1. Missing-evidence sentence: a body-scoped assertion inside
   `destinationPrecheckActivationRequirement` proves the branch assigns
   ``message = `Checked activation blocked: ${nextAction}.` `` together with
   `nextAction = 'run the read-only destination precheck on this revision, then activate checked';`,
   such that deleting only that message assignment fails a named test.
2. Stale sentence: the same guarantee for
   `nextAction = 'reload this revision and rerun the destination precheck on its current version and
   digest';`.
3. Capability-gap sentence: the same guarantee for
   `nextAction = 'change the configured operation or destination Storage, then rerun the precheck';`,
   plus its `style = 'error';`.
4. Failed sentence: the complete composed template
   ``message = `Checked activation blocked: destination precheck failed
   (${boundedSetupText(evidence.failureCategory)}); ${nextAction}.` `` is asserted in full, together
   with the fallback next action `correct the destination configuration, then rerun the precheck` and
   its `style = 'error';`. Truncating the template to the currently asserted prefix must fail.
5. Return contract: the predicate's return object literal is proven to carry `message` and `style`,
   so dropping either key fails a named test even when all four assignments remain.
6. Render payload: `renderDestinationPrecheck`'s blocked branch is proven with its payload —
   `text('p', activation.message, activation.style)` — so replacing it with a fixed literal or a
   different style fails a named test. Asserting only the `else if (!activation.satisfied)` condition
   prefix is not sufficient.
7. Falsification evidence, actually run and reported: at minimum these six probes, each followed by a
   byte-identical restore and a clean `git status --short` — (a) delete only the missing-evidence
   message assignment; (b) delete only the stale message assignment; (c) delete only the
   capability-gap message assignment; (d) truncate the failed template to
   `Checked activation blocked: destination precheck failed (`; (e) drop `message` from the return
   object; (f) replace the blocked branch payload with
   `text('p', 'Checked activation blocked.', 'warning')`. Each must fail, and the Completion Report
   must name the exact failing test for each.
8. No production change: `git diff b9cc35e2677a35920042b5695f87b50a80025ef0 <this checkpoint> --stat`
   lists only `tests/test_operator_ui.py` and `TASK.md`, and `mediaflow/`, `scripts/`, `config/` and
   `pyproject.toml` are byte-identical between the two commits.
9. Contract unchanged: Configuration marker 10 and Runtime marker 22 are asserted;
   `tests/test_configuration_destination.py` stays byte-identical to
   `c7ec192b3b20f236cca5a70ed59cad43e0851242`,
   `tests/test_configuration_destination_precheck.py` to
   `ee5225dd0e74a7382b6747c6315776413f7fd249`, and
   `tests/test_configuration_destination_activation.py` to
   `b9cc35e2677a35920042b5695f87b50a80025ef0`.
10. Regression: the complete offline suite plus the Phase 22.3 through 22.6 configuration,
    continuation, RecognitionType C, organizer and conflict group. No test count may decrease.

## Validation

- `.venv/bin/python -m unittest` for the focused operator-UI tests, then the Phase 22.3 through 22.6
  regression group, then the complete offline suite.
- `.venv/bin/python -m ruff check .` and `.venv/bin/python -m ruff format --check .`.
- `.venv/bin/python -m compileall mediaflow tests`.
- `.venv/bin/pip check`.
- CLI validation of both example configurations through `.venv/bin/python -m mediaflow.cli`, once
  with `--config config/mediaflow.phase13.2.example.json config validate` and once with
  `--config config/strategy.example.json config validate`.
- Wheel build with `python -m pip wheel . --no-deps --no-build-isolation -w dist`, isolated install
  and `scripts/wheel_smoke_test.py <wheel>` reporting both schema markers.
- `git diff --check`, the FFmpeg/FFprobe audit, the business-layer filesystem-mutation audit, the
  Markdown local-link check, and confirmation that `config/alist.json` stays ignored and untracked.

## Documentation

- None. No documentation file may change in this correction. The CURRENT claims recorded at the
  rejected checkpoint were independently verified accurate, and `docs/progress.md` and
  `docs/roadmap.md` remain High-only.

## Closure Checklist

- [x] All four composed blocking sentences, both `style = 'error'` assignments, the `message` and
      `style` return-contract entries and the blocked branch's render payload are each proven by a
      named, body-scoped assertion.
- [x] All six falsification probes were run, each failed a named test, each was followed by a
      byte-identical restore and a clean `git status --short`, and the Completion Report names the
      failing test for every one.
- [x] No production file changed; `mediaflow/`, `scripts/`, `config/` and `pyproject.toml` are
      byte-identical to `b9cc35e2677a35920042b5695f87b50a80025ef0`.
- [x] No existing assertion was deleted, weakened or made less specific, and no test count decreased.
- [x] Both frozen suites and the Phase 22.6-F activation suite stay byte-identical to their pinned
      SHAs; markers stay 10 and 22.
- [x] The complete offline suite, lint, format, compileall, `pip check`, both example validations and
      the wheel smoke run pass.
- [x] Private runtime configuration remains ignored and untracked; no secret is staged or committed.
- [x] One coherent, buildable, reviewable commit is created on top of
      `b9cc35e2677a35920042b5695f87b50a80025ef0`, which is never amended, squashed or rewritten.
- [x] The Completion Report is written into this file, and the Slice is reported as
      READY FOR HIGH REVIEW without declaring Phase closure.

## Completion Report

### Changed Files

- `tests/test_operator_ui.py` — +58/-0. Added one focused test,
  `test_destination_precheck_blocking_sentence_contract_is_body_scoped`
  (`tests/test_operator_ui.py:474` onward). No existing assertion was modified, deleted or
  weakened.
- `TASK.md` — status header, acceptance/closure checklist and this Completion Report.
- Nothing else. `mediaflow/`, `scripts/`, `config/` and `pyproject.toml` are byte-identical to
  `b9cc35e2677a35920042b5695f87b50a80025ef0`.

### Assertions Added and Shipped Lines They Guard

All assertions reuse the existing `_js_function_body` / `_js_braced_body` helpers and are
branch-scoped inside `destinationPrecheckActivationRequirement` or body-scoped inside
`renderDestinationPrecheck`:

1. Missing-evidence branch: `nextAction = 'run the read-only destination precheck on this
   revision, then activate checked';` together with
   ``message = `Checked activation blocked: ${nextAction}.`;``
   (`mediaflow/interfaces/operator_ui.py:704-705`; assertion at `tests/test_operator_ui.py:485`).
2. Stale branch: `nextAction = 'reload this revision and rerun the destination precheck on its
   current version and digest';` together with the same composed message
   (`operator_ui.py:707-708`; assertion at `tests/test_operator_ui.py:494`).
3. Failed branch: the complete composed template
   ``message = `Checked activation blocked: destination precheck failed (${boundedSetupText(evidence.failureCategory)}); ${nextAction}.`;``,
   the two-line fallback
   `nextAction = boundedSetupText(evidence.nextAction, 'correct the destination configuration, then rerun the precheck');`
   exactly as shipped, and `style = 'error';`
   (`operator_ui.py:711-714`; assertions at `tests/test_operator_ui.py:504-511`).
4. Capability-gap branch: `nextAction = 'change the configured operation or destination Storage,
   then rerun the precheck';`, the composed message, and `style = 'error';`
   (`operator_ui.py:716-718`; assertions at `tests/test_operator_ui.py:517-519`).
5. Return contract: the exact return literal
   `return {applicable, evidence, current, completed, capabilityGap, satisfied, nextAction, message, style};`
   (`operator_ui.py:719`; assertion at `tests/test_operator_ui.py:521`).
6. Render payload:
   `else if (!activation.satisfied) detailContent.append(text('p', activation.message, activation.style));`
   (`operator_ui.py:727`; assertion at `tests/test_operator_ui.py:526`).

Branch scoping is the point: the three simple blocking sentences are byte-identical, so only
extracting each `if` branch separately proves that deleting one assignment fails a named test
rather than requiring all three to be deleted together.

### Tests and Test Results

Commands actually run, with results:

- Environment preflight: worktree, `.git` directory and index all writable (Git-writable / Full
  Access); HEAD `ed17ebbc19b2a35813fb26f448080992ffe63ba2`; initial `git status --short` empty.
- Focused run (both existing Phase 22.6-G tests plus the new test): `Ran 3 tests ... OK`.
- Full operator-UI class: `Ran 21 tests ... OK` (20 before this Slice).
- Phase 22.3-22.6 configuration, continuation, RecognitionType C, organizer and conflict group
  (15 modules): `Ran 229 tests ... OK`.
- Complete offline suite: `Ran 850 tests ... OK (skipped=7)` — 849 before, +1 new test, no test
  removed.
- `ruff check .`: `All checks passed!`; `ruff format --check .`: `308 files already formatted`.
- `compileall -q mediaflow tests`: passed; `pip check`: `No broken requirements found`.
- Both example validations through `.venv/bin/python -m mediaflow.cli`: `Configuration valid`
  for `config/mediaflow.phase13.2.example.json` and `config/strategy.example.json`.
- Wheel: `python -m pip wheel . --no-deps --no-build-isolation -w dist` succeeded; isolated
  `scripts/wheel_smoke_test.py dist/mediaflow-0.1.0-py3-none-any.whl` exited 0 and reported
  Supported/Runtime/Backup schema 22. Configuration marker 10 is asserted by the byte-unchanged
  `tests/test_configuration_destination_activation.py:462`
  (`CONFIGURATION_SCHEMA_VERSION == 10`).
- `git diff --check`: clean.
- Markdown local-link check over the 120 tracked `.md` files: 25 local links, 0 broken.
- FFmpeg/FFprobe audit: zero hits under `mediaflow/` and `pyproject.toml`.
- Business-layer filesystem-mutation audit: only Storage-mediated `resolver.rename(...)` calls in
  `mediaflow/application` and `mediaflow/domain`; no direct filesystem mutation.
- Private configuration: `git check-ignore config/alist.json` matches; `git ls-files -- config/alist.json`
  and `git diff --cached -- config/alist.json` are both empty.
- Frozen suites: `tests/test_configuration_destination.py` is byte-identical to
  `c7ec192b3b20f236cca5a70ed59cad43e0851242`; `tests/test_configuration_destination_precheck.py`
  to `ee5225dd0e74a7382b6747c6315776413f7fd249`;
  `tests/test_configuration_destination_activation.py` to
  `b9cc35e2677a35920042b5695f87b50a80025ef0`.

### Six Falsification Probes

Each probe temporarily edited exactly one shipped line in
`mediaflow/interfaces/operator_ui.py`, ran the same three focused tests, confirmed the new test
failed while the two existing Phase 22.6-G tests stayed green, then restored the line and verified
`git diff --exit-code -- mediaflow/interfaces/operator_ui.py` (empty) and `git status --short`
(only `tests/test_operator_ui.py`, because `TASK.md` had not yet been edited during the probe
phase).

| Probe | Temporary change | Failing test and assertion |
| --- | --- | --- |
| (a) missing-evidence sentence | delete only the missing branch's ``message = `Checked activation blocked: ${nextAction}.`;`` | `test_destination_precheck_blocking_sentence_contract_is_body_scoped`, `tests/test_operator_ui.py:485` |
| (b) stale sentence | delete only the stale branch's message assignment | same test, `tests/test_operator_ui.py:494` |
| (c) capability-gap sentence | delete only the capability-gap branch's message assignment | same test, `tests/test_operator_ui.py:517` |
| (d) failed template truncation | truncate to ``message = `Checked activation blocked: destination precheck failed (`;`` | same test, `tests/test_operator_ui.py:504` (full-template assertion) |
| (e) return contract | drop `message` from the return object literal | same test, `tests/test_operator_ui.py:521` (return-contract assertion) |
| (f) render payload | replace the blocked branch with `text('p', 'Checked activation blocked.', 'warning')` | same test, `tests/test_operator_ui.py:526` (render-payload assertion) |

### Byte-identity Proof

- `git diff --exit-code b9cc35e2677a35920042b5695f87b50a80025ef0 -- mediaflow scripts config pyproject.toml`
  exits 0 with no output, and the same `--stat` is empty.
- After every probe restore the `operator_ui.py` diff was empty.
- One wording note: the Task's Required Test 8 literal command
  `git diff b9cc35e <this checkpoint> --stat` cannot list only `tests/test_operator_ui.py` and
  `TASK.md`, because High's task-definition commit `ed17ebb`
  (`docs(review): record Phase 22.6-G FIX REQUIRED and define 22.6-G-F1`) already sits between
  `b9cc35e` and this checkpoint and changed `TASK.md`, `docs/progress.md` and `docs/roadmap.md`.
  The correction commit itself changes only `tests/test_operator_ui.py` and `TASK.md` relative to
  its parent, and all production directories are byte-identical to `b9cc35e`, which satisfies the
  requirement's intent.

### Decisions

- A new focused test was added instead of editing the two existing Phase 22.6-G tests, so no
  existing assertion was touched and the review diff is purely additive.
- Each of the three identical blocking messages is asserted inside its own extracted branch body,
  which is what makes deleting a single assignment fail independently.
- The failed branch's fallback `nextAction` is asserted in its exact shipped two-line form because
  `boundedSetupText(evidence.nextAction,` wraps onto the next line.
- No production line, documentation file, script, configuration or dependency was changed; no
  JavaScript runtime or new test file was added.

### Remaining Work

- Nothing remains inside this Slice. Phase 22.6 stays open; the next legal boundary is High's to
  authorize after review. Remote SMB/OpenList/S3 prechecks, mutation-based capability probing,
  duplicate and cross-item collision detection, attachment prechecks, absolute mounted-path
  display and any execution change remain TARGET and were not started.
- No push was performed; the push gate stays `NOT BLOCKING` and Phase 22.6 closure push requires
  explicit authorization.

### Risks, Assumptions and Newly Discovered Issues

- Required Test 8's literal diff cannot be reproduced exactly for the reason documented above;
  the production byte-identity and the correction commit's two-file manifest are the equivalent
  proof.
- The complete suite still emits the pre-existing `ResourceWarning: unclosed database` already
  recorded as a deferred non-blocking observation from earlier Phases; this Slice adds nothing.
- During the probe phase `git status --short` showed only `tests/test_operator_ui.py`; the final
  pre-commit status shows `tests/test_operator_ui.py` and `TASK.md`.
- Per the workflow, this commit does not contain its own SHA; the full 40-character SHA is
  reported in the review handoff and will be recorded by High in `docs/progress.md` after review.
