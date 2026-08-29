# Phase 22.6-J — An Undetermined Destination Observation Stops Printing as "NO"

This Task follows [the authoritative development workflow](docs/development-workflow.md).

```text
Status: READY FOR HIGH REVIEW
Commit SHA: PENDING
High Audit: PENDING
Preceding closed checkpoint: 6c0ba745772e315b941c1c3b314ab47e66e8f35a
  (Phase 22.6-I PASS / CLOSED — 2026-08-29)
Preserved rejected checkpoints: d8c2ae04e578955ddbbd29c413f235bf4cf08f42 (Phase 22.6-H),
  b9cc35e2677a35920042b5695f87b50a80025ef0 (Phase 22.6-G),
  7353b0d22497e6e3e596c93c7052eea34daf27df (Phase 22.6-E),
  90ce13a6c6c39912dd389f71a1189314ff24eb5d (Phase 22.6-A) and
  08dfd4f921728755209b6d52347d28f221121c47 (Phase 22.5-E); never amended, squashed or rewritten
Push gate: SATISFIED — every closed Phase 22.6-A through 22.6-G checkpoint and the review records
  through 3ace53c7cdcc3312033f388d8f68d2d7d1a159ae were pushed to origin/main on 2026-08-28 under
  explicit operator authorization. The preserved rejected 22.6-H checkpoint, the 22.6-H-F1 and 22.6-I
  checkpoints and every review record after them stay local; Slice closure does not require a push,
  and phase-level Phase 22.6 closure still requires the Final Closure Audit plus a new explicit
  authorization
Phase: 22.6 Naming / Classification / Organize configuration journey (roadmap section 5)
Slice scope: Web presentation only. In the destination-precheck evidence block, a boolean
  determination the evidence does not carry must render as the bounded text `NOT DETERMINED` instead
  of `NO`, in both the single-sample and the multi-sample branch, for `destinationRootExists`,
  `destinationRootIsDirectory` and `targetExists`. The only production file that may change is
  `mediaflow/interfaces/operator_ui.py`. No evidence key, request or response field, aggregation rule,
  activation gate expression, failure category, route, permission, table or schema marker may change;
  markers stay 10 and 22
```

## Why This Slice Exists

The destination precheck reports FAILED for most misconfigurations, and FAILED evidence usually
carries no observation at all. `_destination_precheck_failure` in
`mediaflow/application/configuration_objects.py` defaults to `result=None`; only two failure paths
attach anything about the root (`:1639` `missing_destination_root` with `(False, False)` and `:1651`
`destination_root_not_directory` with `(True, False)`), and the multi-sample failure path attaches
only `sampleCount`, `items`, `collisions`, `guardMutationCalls` and `authorityGranted`. `targetExists`
appears in COMPLETED payloads only (`:1747` single, `:2047` multi through `first_details`).

The Web block prints those absent determinations as facts. At
`mediaflow/interfaces/operator_ui.py:747` and `:779` it renders
`${result.destinationRootExists === true ? 'YES' : 'NO'} / ${result.destinationRootIsDirectory ===
true ? 'YES' : 'NO'}`, and at `:764` and `:783` it renders
`result.targetExists === true ? 'YES' : 'NO'`. So a run that failed on an invalid rule, a duplicate
destination, a cross-Storage sample set or an unsafe composition tells the operator
`Destination root exists / directory: NO / NO` and `Target exists: NO` — three negatives the precheck
never observed. Absent and `null` genuinely mean *undetermined* in this evidence vocabulary, and
`Target exists: NO` is the most safety-relevant negative in the block: it reads as "nothing would be
overwritten", which is exactly the claim a failed precheck is not entitled to make.

For COMPLETED evidence nothing changes: all three keys are real booleans there, and the two
root-failure categories above keep their genuine `NO / NO` and `YES / NO`.

## User Problem

An operator prechecks a Draft whose classification rule is invalid. The run fails with a bounded
category and a next action, which is correct — but the same page also states that the MediaLibrary
root does not exist and is not a directory, and that the target does not exist. The operator either
goes looking for a root problem that does not exist and stops trusting the evidence, or reads
`Target exists: NO` as an assurance that nothing would be overwritten once the rule is fixed. Neither
statement came from the precheck; both came from the page.

## Journey

- User goal: know what the precheck actually observed, and know when it observed nothing.
- Entry point: Web configuration Draft page, destination precheck section (unchanged).
- Visible state: `YES` when the evidence says `true`, `NO` when the evidence says `false`, and the
  bounded text `NOT DETERMINED` when the evidence carries no boolean for that field.
- Available action: unchanged — "Run read-only destination precheck", still read-only.
- Success outcome: a completed run reads exactly as it does today; a failed run no longer asserts a
  destination-root or target-existence negative that was never observed.
- Failure outcome: unchanged. The bounded failure category, message and next action still render, the
  per-sample rows still carry each sample's own outcome, and the not-ready sentence still appears —
  an undetermined root must keep counting as not ready.
- Recovery path: unchanged — follow the stated next action, or rerun the precheck on the exact
  revision after correcting the Draft.

## UX Acceptance

1. `true` renders `YES` and `false` renders `NO` for all three fields, so every completed run and both
   root-failure categories render exactly as they do today.
2. Any other value — key absent, `null`, or a non-boolean — renders the exact bounded text
   `NOT DETERMINED`.
3. Both branches are covered: the multi-sample run-level `Destination root exists / directory` field
   and its `First sample destination` `Target exists` field, and the single-sample branch's two
   equivalents.
4. Nothing else moves: every other field label, expression, order and list, the per-sample rows table,
   the collision table, `No cross-item destination collision detected.`, the stale sentence, the
   not-ready sentence, the no-authority warning and the `1-8 samples` control stay byte-identical.
5. The not-ready gate expression stays byte-identical, including `!result.destinationRootExists`, so
   an undetermined root still blocks readiness. Presentation may not soften a gate.
6. No new evidence key, no new API field, no new route or page, no absolute path, no secret.

Authoritative mapping for this Slice — the three fields, and nothing else:

| Evidence key | Field label | `true` | `false` | absent / `null` / other |
| --- | --- | --- | --- | --- |
| `destinationRootExists` | Destination root exists / directory (left) | `YES` | `NO` | `NOT DETERMINED` |
| `destinationRootIsDirectory` | Destination root exists / directory (right) | `YES` | `NO` | `NOT DETERMINED` |
| `targetExists` | Target exists | `YES` | `NO` | `NOT DETERMINED` |

## Technical Scope

Files this Slice may change — nothing else:

- `mediaflow/interfaces/operator_ui.py`: the four render sites inside `renderDestinationPrecheck`, plus
  exactly one new script-level helper function named `determinationText`, defined immediately after
  `boundedSetupText`. `boundedSetupText` itself must not change.
- `tests/test_operator_ui.py`.
- `TASK.md` (status block, closure checklist and Completion Report).
- `docs/product-experience.md` only if an existing CURRENT sentence would otherwise become inaccurate,
  and then by at most one sentence, quoted verbatim in the Completion Report. If no such sentence
  exists, change no documentation at all.

Explicitly forbidden: `mediaflow/application/**`, `mediaflow/domain/**`,
`mediaflow/infrastructure/**`, `mediaflow/interfaces/service_api.py`, `mediaflow/cli.py`, `scripts/`,
`config/`, `pyproject.toml`, `docs/progress.md` and `docs/roadmap.md` (both review-owned).

Rules:

1. Presentation only. The same evidence keys are read, the same request body is sent, no value is
   recomputed or re-derived, and no key is added, renamed or defaulted on the way to the page.
2. `determinationText(value)` must be the single place that decides the three-way text, must be used by
   all four render sites, and must map `value === true` to `'YES'`, `value === false` to `'NO'` and
   everything else to `'NOT DETERMINED'`. The literal text is exactly `NOT DETERMINED` — uppercase, no
   punctuation, no explanation appended, and it may not be substituted for the `-` fallback that
   `boundedSetupText` already produces for text fields.
3. `evidence.retrySafe === true ? 'YES' : 'NO'` stays byte-identical everywhere: `document()` always
   supplies a real boolean for it, so it is not an undetermined field. The same applies to every
   `YES`/`NO` render outside `renderDestinationPrecheck` (`renderNamingPreview`,
   `renderClassificationPreview`, `renderOrganizeAuthority`, `renderDestinationPreview`,
   `renderMetadataTestEvidence`, `renderRecognitionStrategyTest`); they are out of scope.
4. No existing assertion in `tests/test_operator_ui.py` may be replaced, weakened, deleted or renamed
   this time. The current assertions anchor on `field(firstList, 'Target exists',` and
   `field(list, 'Target exists',` prefixes and on labels, so they must all still pass unchanged; if one
   does not, the implementation went beyond this Slice.
5. New tests must be body-scoped the way the module already does it (`_js_function_body` /
   `_js_braced_body`), because the operator UI is a Python `bytes` literal with no JS runtime.
6. No credential, endpoint, Storage `rootPath`, header, cookie, private path or raw exception text may
   enter the page, the tests, the report or the commit.

## Required Tests

All in `tests/test_operator_ui.py`, all additive. Every assertion must fail if the behaviour it names
is removed.

1. `test_destination_precheck_absent_determinations_render_as_not_determined` — inside the
   `renderDestinationPrecheck` body, assert that both branches route all three fields through
   `determinationText(...)`, that the multi-sample run-level list and first-sample list and the
   single-sample list each carry their own call, and that no `=== true ? 'YES' : 'NO'` expression
   remains for `result.destinationRootExists`, `result.destinationRootIsDirectory` or
   `result.targetExists` anywhere in the body.
2. `test_determination_text_maps_true_false_and_undetermined_separately` — body-scope
   `determinationText` and assert all three arms exist independently: `=== true` yields `'YES'`,
   `=== false` yields `'NO'`, and the remaining case yields exactly `'NOT DETERMINED'`. Collapsing any
   two arms must fail this test.
3. `test_destination_precheck_not_ready_gate_still_blocks_an_undetermined_root` — assert the not-ready
   gate condition is byte-identical, including `!result.destinationRootExists`, and that the
   `Destination is not ready. Follow the recovery action; no authority was granted.` sentence and its
   `'error'` style are unchanged, so an undetermined root cannot be rendered as ready.

No other test may be added, renamed or changed.

## Required Falsification Probes

Mutate the shipped tree one edit at a time, run the affected tests, record the actual failing test
names and output, restore with `git checkout -- <file>`, and confirm a clean tree after each probe.
Report every probe, including the control.

1. Collapse the undetermined arm of `determinationText` so anything not `true` yields `'NO'` — Required
   Test 2 must fail.
2. Collapse the `false` arm so `false` also yields `'NOT DETERMINED'` — Required Test 2 must fail.
3. Restore the old inline `result.targetExists === true ? 'YES' : 'NO'` expression in the multi-sample
   first-sample list — Required Test 1 must fail.
4. Restore the old inline `result.destinationRootExists === true ? 'YES' : 'NO'` expression in the
   single-sample branch — Required Test 1 must fail.
5. Change the not-ready gate from `!result.destinationRootExists` to
   `result.destinationRootExists === false` — Required Test 3 must fail, proving the gate is pinned and
   that an undetermined root still blocks readiness.
6. Control probe: a comment-only edit inside `renderDestinationPrecheck` must fail no test.

## Validation

Run every command and report its actual output:

- `.venv/bin/python -m unittest` (the total must rise from 863 by exactly the number of added tests,
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
- `git diff --exit-code 6c0ba745772e315b941c1c3b314ab47e66e8f35a HEAD -- mediaflow/application
  mediaflow/domain mediaflow/infrastructure mediaflow/interfaces/service_api.py mediaflow/cli.py
  scripts config pyproject.toml` must be empty, proving evidence semantics, the service boundary, the
  CLI and the schema are untouched.
- `git diff --stat 6c0ba745772e315b941c1c3b314ab47e66e8f35a HEAD` must list only
  `mediaflow/interfaces/operator_ui.py`, `tests/test_operator_ui.py`, `TASK.md`, the review-owned
  `docs/progress.md` and `docs/roadmap.md` from the intervening review-record commit, and at most
  `docs/product-experience.md` under the rule above.
- `git diff 6c0ba745772e315b941c1c3b314ab47e66e8f35a HEAD -- mediaflow/interfaces/operator_ui.py`
  must contain no hunk outside `renderDestinationPrecheck` other than the new `determinationText`
  helper.
- Secret scan of this Slice's own diff.

## Non-goals — must not start

- Any change to evidence keys, payload shape, the verdict aggregation, the severity map, failure
  categories, the activation gate, request or response fields, permissions, HTTP statuses, routes,
  tables, migrations or schema markers. In particular, do not make the application attach
  `destinationRootExists`, `destinationRootIsDirectory` or `targetExists` to failure payloads; this
  Slice fixes how absence is presented, not what is observed.
- Changing the `-` fallback that `boundedSetupText` produces for absent text fields, anywhere.
- Applying the three-way rendering to any other boolean in the page: `Retry safe`, `MediaLibrary
  resolved`, `Overwrite authorized`, `Delete authorized`, `Evidence truncated`, metadata `Enabled` and
  every other `YES`/`NO` outside `renderDestinationPrecheck` are out of scope for this Slice.
- Adding an explanation, tooltip, style or icon to the undetermined state; the bounded text is the
  whole change.
- Making the first-sample block index-accurate. This was previously recorded as a defect and is not
  one: any sample carrying a `failureCategory` makes the whole precheck FAILED through
  `_destination_precheck_failure`, so completed evidence has no failed sample and its top-level details
  always describe sample 0.
- Closing the residual proof gap recorded in the Phase 22.6-H-F1 review (no multi-sample all-`ready`
  run asserts `verdict == "ready"`), pinning single-sample field order, or adding a test that compares
  the two branches' field lists. All three are known, non-blocking, and not this Slice's business.
- Remote SMB/OpenList/S3 destination prechecks, mutation-based capability probing, multiple
  RecognitionTypes or multiple destination Storages per request, known-media duplicate detection,
  attachment prechecks, absolute mounted-path display, and any execution or authority change.
- Amending, squashing or rewriting any preserved rejected checkpoint; no push, force push,
  `git reset --hard` or destructive `git clean`.

## Closure Checklist

- [x] Only `mediaflow/interfaces/operator_ui.py`, `tests/test_operator_ui.py`, `TASK.md` and — only
      under the stated rule — `docs/product-experience.md` changed
- [x] `git diff --exit-code 6c0ba74 HEAD -- mediaflow/application mediaflow/domain
      mediaflow/infrastructure mediaflow/interfaces/service_api.py mediaflow/cli.py scripts config
      pyproject.toml` is empty
- [x] `determinationText` exists once, sits immediately after `boundedSetupText`, and maps `true` /
      `false` / everything else to `YES` / `NO` / `NOT DETERMINED`
- [x] All four render sites use it: run-level and first-sample in the multi-sample branch, both
      equivalents in the single-sample branch
- [x] No `=== true ? 'YES' : 'NO'` expression remains for `destinationRootExists`,
      `destinationRootIsDirectory` or `targetExists`
- [x] `evidence.retrySafe` and every `YES`/`NO` render outside `renderDestinationPrecheck` are
      byte-identical
- [x] The not-ready gate expression, its sentence and its `'error'` style are byte-identical
- [x] Every other field, label, order, list, table, heading and bounded sentence in the precheck block
      is byte-identical
- [x] Zero existing assertions replaced, weakened, deleted or renamed; the three new tests are additive
      and body-scoped
- [x] All six Required Falsification Probes executed with recorded output, control included, clean tree
      after each
- [x] Full offline suite green, total risen from 863 only by the added tests
- [x] Markers still 10 and 22; wheel smoke reports Runtime schema 22
- [x] No credential, endpoint, Storage `rootPath`, header, cookie, private path or raw exception text
      in the page, tests, report or commit; `config/alist.json` still untracked, unstaged, ignored
- [x] Completion Report filled in with the actual commands, actual output, deviations and risks
- [x] Status set to READY FOR HIGH REVIEW; not pushed

## Completion Report

### Changed Files

- `mediaflow/interfaces/operator_ui.py` — +9/-4: the new `determinationText` helper immediately after
  `boundedSetupText`, and the four render sites inside `renderDestinationPrecheck`.
- `tests/test_operator_ui.py` — +61/-0: the three Required Tests, all additive and body-scoped.
- `TASK.md` — status block, closure checklist and this Completion Report.
- No documentation file changed: `docs/product-experience.md` needed no update because no CURRENT
  sentence became inaccurate, and `docs/progress.md` / `docs/roadmap.md` remain review-owned.

### Implemented

- `determinationText(value)` is the single three-way decision: `value === true` → `'YES'`,
  `value === false` → `'NO'`, everything else → exactly `'NOT DETERMINED'`. It is defined
  immediately after `boundedSetupText`, which is unchanged.
- All four render sites use it: the multi-sample run-level
  `Destination root exists / directory` (both halves), the multi-sample first-sample
  `Target exists`, and the single-sample equivalents. `evidence.retrySafe` and every other
  `YES`/`NO` render outside `renderDestinationPrecheck` are byte-identical.
- The not-ready gate still reads `!result.destinationRootExists`, so an undetermined root keeps
  counting as not ready; the sentence and `'error'` style are unchanged.

### Tests and Test Results

- `test_destination_precheck_absent_determinations_render_as_not_determined`
  (`tests/test_operator_ui.py:627`) asserts each branch routes all three fields through
  `determinationText(...)`, that each of the four render sites carries its own call (counts of 2 per
  key), and that no `=== true ? 'YES' : 'NO'` expression remains for the three keys in the body.
- `test_determination_text_maps_true_false_and_undetermined_separately`
  (`tests/test_operator_ui.py:662`) body-scopes the helper and pins all three arms, plus the helper's
  position after `boundedSetupText`.
- `test_destination_precheck_not_ready_gate_still_blocks_an_undetermined_root`
  (`tests/test_operator_ui.py:673`) pins the gate expression, sentence and `'error'` style
  byte-identically.

Commands actually run, with results:

- Focused modules (`test_operator_ui`, `test_configuration_destination_precheck`,
  `test_configuration_destination_activation`): 52 tests, 0 failures.
- Complete offline suite: `Ran 866 tests ... OK (skipped=7)` — 863 before, +3 tests, zero deletions.
- `ruff check .`: All checks passed; `ruff format --check .`: 308 files already formatted.
- `compileall -q mediaflow tests`: passed; `pip check`: No broken requirements found.
- Both example `config validate` runs: `Configuration valid`.
- Wheel build plus isolated `scripts/wheel_smoke_test.py`: exit 0, Runtime schema 22;
  Configuration marker 10 remains asserted by the unchanged suite.
- `git diff --check`: clean; FFmpeg/FFprobe audit: zero hits; business-layer filesystem-mutation
  audit: only Storage-mediated `resolver.rename(...)` references; `config/alist.json` ignored,
  untracked and unstaged; 120 tracked Markdown files, 25 links, 0 broken; secret scan of added
  lines: no matches.
- `git diff --exit-code 6c0ba74 HEAD -- mediaflow/application mediaflow/domain
  mediaflow/infrastructure mediaflow/interfaces/service_api.py mediaflow/cli.py scripts config
  pyproject.toml`: empty. The `operator_ui.py` diff contains only the helper hunk and the three
  `renderDestinationPrecheck` hunks.

### Falsification Probes

Each probe mutated `mediaflow/interfaces/operator_ui.py` once, ran the affected tests, recorded the
failure, then restored with `git checkout -- mediaflow/interfaces/operator_ui.py` from the staged
intended implementation and confirmed the worktree matched the staged file byte-for-byte.

| Probe | Temporary change | Result |
| --- | --- | --- |
| 1 | Undetermined arm of `determinationText` collapsed so non-`true` yields `'NO'` | Required Test 2 failed at `tests/test_operator_ui.py:666` |
| 2 | `false` arm collapsed so `false` also yields `'NOT DETERMINED'` | Required Test 2 failed at `tests/test_operator_ui.py:666` |
| 3 | Old inline `result.targetExists === true ? 'YES' : 'NO'` restored in the multi-sample first-sample list | Required Test 1 failed (determination call missing) |
| 4 | Old inline root expression restored in the single-sample branch | Required Test 1 failed (single-branch determination call missing) |
| 5 | Not-ready gate changed to `result.destinationRootExists === false` | Required Test 3 failed (gate expression not byte-identical) |
| 6 (control) | Comment-only line inside `renderDestinationPrecheck` | No test failed; the full operator-UI module ran 27 tests OK |

### Decisions

- One helper owns the three-way mapping so every render site and every future site stays consistent;
  `boundedSetupText`'s `-` fallback for text fields is untouched.
- The not-ready gate is deliberately not softened: presentation now says `NOT DETERMINED`, but the
  readiness decision still treats an absent root as blocking.
- No documentation change was needed; the existing CURRENT sentences remain accurate.

### Remaining Work

- Nothing inside this Slice. The known non-goals listed above were not started: no evidence payload
  change, no `YES`/`NO` change outside `renderDestinationPrecheck`, no explanation/tooltip/style for
  the undetermined state.
- No push was performed; this checkpoint stays local pending High review.

### Risks, Assumptions and Newly Discovered Issues

- Failed evidence that carries no observation now renders `NOT DETERMINED` for the three fields,
  while the two genuine root-failure categories (`missing_destination_root`,
  `destination_root_not_directory`) keep their real `NO` / `YES` values because those keys are real
  booleans there; completed evidence is unchanged.
- Per the workflow, this commit does not contain its own SHA; the full SHA is reported in the
  review handoff and will be recorded by High in `docs/progress.md` after review.
