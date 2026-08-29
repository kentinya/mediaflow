# Phase 22.6-K — Each Destination Precheck Sample Shows Its Own Failure Message

This Task follows [the authoritative development workflow](docs/development-workflow.md).

```text
Status: READY FOR HIGH REVIEW
Commit SHA: PENDING
High Audit: PENDING
Preceding closed checkpoint: ccbddf2af92c1abf18d1162d0a6c37da9ee0a7cd
  (Phase 22.6-J PASS / CLOSED — 2026-08-29)
Preserved rejected checkpoints: d8c2ae04e578955ddbbd29c413f235bf4cf08f42 (Phase 22.6-H),
  b9cc35e2677a35920042b5695f87b50a80025ef0 (Phase 22.6-G),
  7353b0d22497e6e3e596c93c7052eea34daf27df (Phase 22.6-E),
  90ce13a6c6c39912dd389f71a1189314ff24eb5d (Phase 22.6-A) and
  08dfd4f921728755209b6d52347d28f221121c47 (Phase 22.5-E); never amended, squashed or rewritten
Push gate: SATISFIED — every closed Phase 22.6-A through 22.6-G checkpoint and the review records
  through 3ace53c7cdcc3312033f388d8f68d2d7d1a159ae were pushed to origin/main on 2026-08-28 under
  explicit operator authorization. The preserved rejected 22.6-H checkpoint, the 22.6-H-F1, 22.6-I
  and 22.6-J checkpoints and every review record after them stay local; Slice closure does not
  require a push, and phase-level Phase 22.6 closure still requires the Final Closure Audit plus a
  new explicit authorization
Phase: 22.6 Naming / Classification / Organize configuration journey (roadmap section 5)
Slice scope: Web presentation only. The per-sample destination rows table inside
  `renderDestinationPrecheck` must carry a fifth `Message` column rendering each sample's own bounded
  `items[].message`, so a failing sample no longer hides another failing sample's diagnosis. The only
  production file that may change is `mediaflow/interfaces/operator_ui.py`, and only its rows-table
  expression. No evidence key, request or response field, aggregation rule, activation gate
  expression, failure category, route, permission, migration or schema marker may change; markers
  stay 10 and 22
```

## Why This Slice Exists

A multi-sample precheck evaluates every sample. `_run_multi_destination_precheck` in
`mediaflow/application/configuration_objects.py` appends one row per sample (`:1882-1920`), and each
failing sample keeps its own bounded explanation: `_destination_sample_failure_row` stores
`"message": self._bounded_utf8(message, 384)` (`:2229-2242`), and `_destination_failure_details`
(`:2378-2399`) composes messages that name the exact failing policy, such as
`ClassificationPolicy 'movies-by-genre' failed (invalid_rule)` or
`NamingPolicy 'movie-standard' failed (...)`. `tests/test_configuration_destination_precheck.py:522`
already asserts one of those per-sample messages.

The run-level failure, however, is only the lowest-index one: `failures[0]` supplies the evidence
`failureCategory`, `message` and `nextAction` (`:2009-2029`), and the pre-composition path uses
`precomposed_rows[0]` the same way (`:1430-1446`).

The Web block renders four columns only —
`table(['Sample', 'Destination', 'Projected outcome', 'Failure category'], ...)` at
`mediaflow/interfaces/operator_ui.py:807-813` — so `items[].message` is persisted, returned by the
API and asserted in tests, yet appears nowhere on the page. A run where sample 0 and sample 2 fail
for different reasons shows sample 2's category but never its explanation, and the only `Message`
field on the page belongs to sample 0. That is exactly the batch rule in `AGENTS.md`: one item must
not hide the diagnosis of another.

## User Problem

An operator prechecks a Draft with a set of samples. Two samples fail for different reasons — one
violates its ClassificationPolicy, another its NamingPolicy. The page names the first sample's cause
in `Message` and `Next action`, and the rows table shows each sample's category, but the second
sample's own sentence — the one that names its failing policy — is invisible. The operator fixes what
the page explained, reruns, and is met by a second failure they were never shown, one rerun later
than necessary.

## Journey

- User goal: diagnose every failing sample from one precheck run, not one sample per rerun.
- Entry point: Web configuration Draft page, destination precheck section (unchanged).
- Visible state: the per-sample rows table gains a `Message` column carrying each sample's own bounded
  message; rows with no message render the existing `-` fallback.
- Available action: unchanged — "Run read-only destination precheck", still read-only.
- Success outcome: for a completed run the table reads as today with a `-` in the new column; for a
  failed run every failing sample's own explanation is visible beside its own category.
- Failure outcome: unchanged. The run-level bounded category, message and next action still describe
  the lowest-index failure, the collision table is unchanged, and the not-ready sentence still appears.
- Recovery path: strengthened — the operator can correct every reported sample before rerunning, and
  the run-level next action still states the explicit action for the reported failure.

## UX Acceptance

1. The per-sample rows table renders exactly five columns, in this order:
   `Sample`, `Destination`, `Projected outcome`, `Failure category`, `Message`.
2. The fifth cell renders `boundedSetupText(item.message)` — each row's own message, never
   `evidence.message`. A row without a message renders `-`, the fallback the page already uses.
3. The run-level `Message` and `Next action` fields keep their current labels, expressions and
   positions in both the multi-sample and the single-sample list; the new column is additional, not a
   replacement.
4. Nothing else moves: the `Per-sample destination rows` heading, the `if (Array.isArray(result.items))`
   guard, the first four columns and their cell expressions, the collision table, the
   `No cross-item destination collision detected.` sentence, the stale sentence, the not-ready gate and
   sentence, the no-authority warning, the `1-8 samples` control and every field list stay
   byte-identical.
5. The Phase 22.6-J rendering is untouched: `determinationText` and its six call sites stay
   byte-identical.
6. No new evidence key, no new API field, no new route or page, no absolute path, no secret. The
   message is already bounded to 384 bytes by the application; the page adds no truncation, tooltip,
   icon or style of its own.

## Technical Scope

Files this Slice may change — nothing else:

- `mediaflow/interfaces/operator_ui.py`: only the per-sample rows-table expression at `:807-813`
  (header list plus one added cell in the row mapper).
- `tests/test_operator_ui.py`: the two changes named below.
- `tests/test_configuration_destination_precheck.py`: exactly one added test, named below.
- `TASK.md` (status block, closure checklist and Completion Report).
- `docs/product-experience.md` only if an existing CURRENT sentence would otherwise become inaccurate,
  and then by at most one sentence, quoted verbatim in the Completion Report. If no such sentence
  exists, change no documentation at all.

Explicitly forbidden: `mediaflow/application/**`, `mediaflow/domain/**`,
`mediaflow/infrastructure/**`, `mediaflow/interfaces/service_api.py`, `mediaflow/cli.py`, `scripts/`,
`config/`, `pyproject.toml`, `docs/progress.md` and `docs/roadmap.md` (both review-owned).

Rules:

1. Presentation only. The same evidence keys are read, the same request body is sent, no value is
   recomputed, re-derived, reordered or defaulted on the way to the page, and no application code
   changes. Probes 5 and 6 below temporarily edit application code and must be restored immediately;
   they are probes, not changes.
2. Exactly one existing assertion may be replaced, and only this one: the header assertion inside
   `test_destination_precheck_multi_sample_web_surface_is_falsifiable`
   (`tests/test_operator_ui.py:546-549`), which pins
   `detailContent.append(table(['Sample', 'Destination', 'Projected outcome', 'Failure category'],`
   and must be extended to the five-column list. Every other existing assertion in both test modules
   must still pass unchanged; if one does not, the implementation went beyond this Slice.
3. New tests must be body-scoped the way `tests/test_operator_ui.py` already does it
   (`_js_function_body` / `_js_braced_body`), because the operator UI is a Python `bytes` literal with
   no JS runtime.
4. The new evidence-level test must reuse the existing offline fixtures and helpers of
   `tests/test_configuration_destination_precheck.py`, must stay offline (no TMDB, SMB, OpenList or S3),
   and must assert only what the current production code already does.
5. No credential, endpoint, Storage `rootPath`, header, cookie, private path or raw exception text may
   enter the page, the tests, the report or the commit.

## Required Tests

Both tests are additive. Every assertion must fail if the behaviour it names is removed.

1. `test_destination_precheck_per_sample_rows_carry_each_sample_message` in
   `tests/test_operator_ui.py` — inside the `renderDestinationPrecheck` body, assert that the rows
   table header list is exactly
   `['Sample', 'Destination', 'Projected outcome', 'Failure category', 'Message']` in that order, that
   the row mapper's fifth cell is `boundedSetupText(item.message)`, that the rows-table expression
   contains no `evidence.message`, that the `Per-sample destination rows` heading and the
   `if (Array.isArray(result.items)) {` guard are unchanged, and that the run-level
   `field(runList, 'Message', boundedSetupText(evidence.message));` and
   `field(list, 'Message', boundedSetupText(evidence.message));` both still exist. Moving `Message`
   to another column position, dropping the cell, or pointing the cell at `evidence.message` must all
   fail this test.
2. `test_destination_precheck_multi_sample_independent_failures_keep_their_own_message` in
   `tests/test_configuration_destination_precheck.py` — run one multi-sample precheck in which at least
   two samples end with a non-null `failureCategory` and with two *different* bounded `message` values
   (any offline-reachable combination is acceptable, for example one sample failing its
   ClassificationPolicy and one failing its NamingPolicy). Assert that each failing row keeps its own
   `failureCategory` and its own `message`, that the two messages differ, that
   `evidence.failure_category` and the run-level `message` equal the lowest-index failing sample's, and
   that the higher-index sample's message equals neither the run-level `message` nor the run-level
   `nextAction` — that is, it exists only in its own row, which is why the Web column is required.

No other test may be added, renamed or changed.

## Required Falsification Probes

Mutate the shipped tree one edit at a time, run the affected tests, record the actual failing test
names and output, restore with `git checkout -- <file>`, and confirm a clean tree after each probe.
Report every probe, including the control.

1. Remove `'Message'` from the rows-table header list — Required Test 1 must fail.
2. Remove the fifth cell from the row mapper — Required Test 1 must fail.
3. Point the fifth cell at `boundedSetupText(evidence.message)` — Required Test 1 must fail, proving
   the column carries the row's own message and not the run-level one.
4. Move `'Message'` to the front of the header list — Required Test 1 must fail, proving column order
   is pinned.
5. In `mediaflow/application/configuration_objects.py`, make `_destination_sample_failure_row` store
   `"message": None` — Required Test 2 must fail. Restore immediately; this is a probe, not a change,
   and `git diff` must be empty afterwards.
6. In `mediaflow/application/configuration_objects.py`, change the run-level failure selection from
   `failures[0]` to `failures[-1]` (`:2015`) — Required Test 2 must fail, proving the run-level message
   is pinned to the lowest-index failing sample. Restore immediately.
7. Control probe: a comment-only edit inside `renderDestinationPrecheck` must fail no test.

## Validation

Run every command and report its actual output:

- `.venv/bin/python -m unittest` (the total must rise from 866 by exactly the number of added tests,
  with zero deletions).
- `.venv/bin/python -m unittest tests.test_operator_ui
  tests.test_configuration_destination_precheck tests.test_configuration_destination_activation`.
- `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .`.
- `.venv/bin/python -m compileall -q mediaflow tests` and `.venv/bin/python -m pip check`.
- CLI `config validate` on `config/mediaflow.phase13.2.example.json` and
  `config/strategy.example.json`.
- Wheel build, isolated install and `scripts/wheel_smoke_test.py` (report the markers; Configuration
  10 and Runtime 22 must be unchanged).
- `git diff --check`; FFmpeg/FFprobe audit; business-layer filesystem-mutation audit;
  `git check-ignore config/alist.json` plus empty `git ls-files` and `git diff --cached` for it;
  Markdown local-link check.
- `git diff --exit-code ccbddf2af92c1abf18d1162d0a6c37da9ee0a7cd HEAD -- mediaflow/application
  mediaflow/domain mediaflow/infrastructure mediaflow/interfaces/service_api.py mediaflow/cli.py
  scripts config pyproject.toml` must be empty, proving evidence semantics, the service boundary, the
  CLI and the schema are untouched and that probes 5 and 6 were restored.
- `git diff --stat ccbddf2af92c1abf18d1162d0a6c37da9ee0a7cd HEAD` must list only
  `mediaflow/interfaces/operator_ui.py`, `tests/test_operator_ui.py`,
  `tests/test_configuration_destination_precheck.py`, `TASK.md` and — under the rule above — at most
  `docs/product-experience.md`.
- `git diff ccbddf2af92c1abf18d1162d0a6c37da9ee0a7cd HEAD --
  mediaflow/interfaces/operator_ui.py` must contain exactly one hunk, in the rows-table expression.
- Secret scan of this Slice's own diff.

## Non-goals — must not start

- Adding a per-sample `nextAction` to evidence, or deriving one in the page from the category. The
  category-to-action map lives in `_destination_sample_next_action`; duplicating it in JavaScript is
  forbidden, and extending the evidence payload is a later Slice, not this one.
- Any change to evidence keys, payload shape, the verdict aggregation, the severity map, failure
  categories, `failures[0]` selection, the activation gate, request or response fields, permissions,
  HTTP statuses, routes, tables, migrations or schema markers.
- Any further column, sort, filter, click handler, row selection, truncation, tooltip, icon or style in
  the rows table; the fifth column is the whole change. The `-` fallback of `boundedSetupText` stays as
  it is.
- Changing the run-level `Message`, `Next action` or any other field in either list, the collision
  table, the stale/not-ready/no-authority sentences, or the Phase 22.6-J `determinationText` rendering.
- Closing the residual proof gaps recorded earlier: no multi-sample all-`ready` run asserts
  `verdict == "ready"`, single-sample field order is unpinned, no test compares the two branches' field
  lists, and no test pins the `YES`/`NO` renders outside the determination fields. All four are known,
  non-blocking, and not this Slice's business.
- Remote SMB/OpenList/S3 destination prechecks, mutation-based capability probing, multiple
  RecognitionTypes or multiple destination Storages per request, known-media duplicate detection,
  attachment prechecks, absolute mounted-path display, and any execution or authority change.
- Amending, squashing or rewriting any preserved rejected checkpoint; no push, force push,
  `git reset --hard` or destructive `git clean`.

## Closure Checklist

- [x] Only `mediaflow/interfaces/operator_ui.py`, `tests/test_operator_ui.py`,
      `tests/test_configuration_destination_precheck.py`, `TASK.md` and — only under the stated rule —
      `docs/product-experience.md` changed
- [x] `git diff --exit-code ccbddf2 HEAD -- mediaflow/application mediaflow/domain
      mediaflow/infrastructure mediaflow/interfaces/service_api.py mediaflow/cli.py scripts config
      pyproject.toml` is empty, proving probes 5 and 6 were restored
- [x] The rows table renders exactly five columns in the mandated order, with
      `boundedSetupText(item.message)` as the fifth cell and no `evidence.message` in the expression
- [x] The run-level `Message` and `Next action` fields are byte-identical in both branches
- [x] The `Per-sample destination rows` heading, the `Array.isArray(result.items)` guard, the first four
      columns, the collision table, every bounded sentence, the not-ready gate and the Phase 22.6-J
      `determinationText` call sites are byte-identical
- [x] Exactly one existing assertion replaced — the header assertion named in Rule 2 — and no other
      assertion weakened, deleted or renamed
- [x] Both Required Tests added, body-scoped where applicable, and the evidence-level test stays offline
- [x] All seven Required Falsification Probes executed with recorded output, control included, clean
      tree after each
- [x] Full offline suite green, total risen from 866 only by the added tests
- [x] Markers still 10 and 22; wheel smoke reports Runtime schema 22
- [x] No credential, endpoint, Storage `rootPath`, header, cookie, private path or raw exception text
      in the page, tests, report or commit; `config/alist.json` still untracked, unstaged, ignored
- [x] Completion Report filled in with the actual commands, actual output, deviations and risks
- [x] Status set to READY FOR HIGH REVIEW; not pushed

## Completion Report

### Changed Files

- `mediaflow/interfaces/operator_ui.py` — +3/-2, exactly one hunk in the per-sample rows-table
  expression: the header list gains `'Message'` and the row mapper gains
  `boundedSetupText(item.message)` as the fifth cell.
- `tests/test_operator_ui.py` — +24/-1: the new Required Test 1 and the one permitted header
  assertion extension (four → five columns).
- `tests/test_configuration_destination_precheck.py` — +53/-0: the new Required Test 2.
- `TASK.md` — status block, closure checklist and this Completion Report.
- No documentation file changed: `docs/product-experience.md` needed no update because no CURRENT
  sentence became inaccurate, and `docs/progress.md` / `docs/roadmap.md` remain review-owned.

### Implemented

- The per-sample destination rows table now renders exactly five columns in order:
  `Sample`, `Destination`, `Projected outcome`, `Failure category`, `Message`.
- The fifth cell renders `boundedSetupText(item.message)` — each row's own bounded message; rows
  without a message render the existing `-` fallback. The rows-table expression contains no
  `evidence.message`.
- The run-level `Message` and `Next action` fields, the `Per-sample destination rows` heading, the
  `Array.isArray(result.items)` guard, the first four columns, the collision table, every bounded
  sentence, the not-ready gate and the Phase 22.6-J `determinationText` call sites are byte-identical.

### Tests and Test Results

- `test_destination_precheck_per_sample_rows_carry_each_sample_message`
  (`tests/test_operator_ui.py:688`) pins the five-column header in order, the fifth cell
  `boundedSetupText(item.message)` (exactly once, after the failure-category cell), the absence of
  `evidence.message` in the rows expression, the unchanged heading/guard, and both run-level
  `Message` fields.
- `test_destination_precheck_multi_sample_independent_failures_keep_their_own_message`
  (`tests/test_configuration_destination_precheck.py:532`) runs one offline multi-sample precheck in
  which sample 0 fails with `invalid_input` and sample 1 with `invalid_rule`, each row keeps its own
  category and message, the two messages differ, and the run-level category/message equal the
  lowest-index failing sample while the higher-index message equals neither the run-level message
  nor the run-level next action.

Commands actually run, with results:

- Focused modules (`test_operator_ui`, `test_configuration_destination_precheck`,
  `test_configuration_destination_activation`): 54 tests, 0 failures.
- Complete offline suite: `Ran 868 tests ... OK (skipped=7)` — 866 before, +2 tests, zero deletions.
- `ruff check .`: All checks passed; `ruff format --check .`: 308 files already formatted.
- `compileall -q mediaflow tests`: passed; `pip check`: No broken requirements found.
- Both example `config validate` runs: `Configuration valid`.
- Wheel build plus isolated `scripts/wheel_smoke_test.py`: exit 0, Runtime schema 22;
  Configuration marker 10 remains asserted by the unchanged suite.
- `git diff --check`: clean; FFmpeg/FFprobe audit: zero hits; business-layer filesystem-mutation
  audit: only Storage-mediated `resolver.rename(...)` references; `config/alist.json` ignored,
  untracked and unstaged; 120 tracked Markdown files, 25 links, 0 broken; secret scan of added
  lines: no matches.
- `git diff --exit-code ccbddf2 HEAD -- mediaflow/application mediaflow/domain
  mediaflow/infrastructure mediaflow/interfaces/service_api.py mediaflow/cli.py scripts config
  pyproject.toml`: empty, proving probes 5 and 6 were restored. The `operator_ui.py` diff is exactly
  one hunk in the rows-table expression.

### Falsification Probes

Each probe mutated one shipped line, ran the affected test, recorded the failure, then restored with
`git checkout -- <file>` (from the staged intended implementation for `operator_ui.py`; from HEAD for
the application file) and confirmed a clean, intended tree.

| Probe | Temporary change | Result |
| --- | --- | --- |
| 1 | Remove `'Message'` from the rows-table header list | Required Test 1 failed at `tests/test_operator_ui.py:695` |
| 2 | Remove the fifth cell from the row mapper | Required Test 1 failed at `tests/test_operator_ui.py:699` |
| 3 | Point the fifth cell at `boundedSetupText(evidence.message)` | Required Test 1 failed at `tests/test_operator_ui.py:699` |
| 4 | Move `'Message'` to the front of the header list | Required Test 1 failed at `tests/test_operator_ui.py:695` |
| 5 | `_destination_sample_failure_row` stores `"message": None` | Required Test 2 failed at `tests/test_configuration_destination_precheck.py:575` |
| 6 | Run-level selection changed from `failures[0]` to `failures[-1]` | Required Test 2 failed at `tests/test_configuration_destination_precheck.py:578` |
| 7 (control) | Comment-only line inside `renderDestinationPrecheck` | No test failed; the full operator-UI module ran 28 tests OK |

### Decisions

- The fifth cell reuses the existing `boundedSetupText` fallback so a completed row without a message
  renders `-` exactly like every other optional text field; no new truncation, tooltip or style was
  added.
- The permitted assertion replacement only extends the header list, preserving every other assertion
  and keeping the proof body-scoped.

### Remaining Work

- Nothing inside this Slice. The known non-goals were not started: no per-sample `nextAction`
  evidence, no extra columns/sort/filter/click handling, no run-level field or sentence changes, and
  no Phase 22.6-J rendering change.
- No push was performed; this checkpoint stays local pending High review.

### Risks, Assumptions and Newly Discovered Issues

- Failing rows always carry their bounded message today (`_destination_sample_failure_row`); the new
  column renders it, and the `-` fallback covers any future row type without one.
- Per the workflow, this commit does not contain its own SHA; the full SHA is reported in the
  review handoff and will be recorded by High in `docs/progress.md` after review.
