# Phase 22.6-I — The Run Verdict Stops Hiding Under "First Sample Destination"

This Task follows [the authoritative development workflow](docs/development-workflow.md).

```text
Status: READY FOR IMPLEMENTATION
Commit SHA: PENDING
High Audit: PENDING
Preceding closed checkpoint: 4455198a6ef3b93fe1e92cef73660039620e756e
  (Phase 22.6-H PASS / CLOSED — 2026-08-28, accepted through Phase 22.6-H-F1)
Preserved rejected checkpoints: d8c2ae04e578955ddbbd29c413f235bf4cf08f42 (Phase 22.6-H),
  b9cc35e2677a35920042b5695f87b50a80025ef0 (Phase 22.6-G),
  7353b0d22497e6e3e596c93c7052eea34daf27df (Phase 22.6-E),
  90ce13a6c6c39912dd389f71a1189314ff24eb5d (Phase 22.6-A) and
  08dfd4f921728755209b6d52347d28f221121c47 (Phase 22.5-E); never amended, squashed or rewritten
Push gate: SATISFIED — every closed Phase 22.6-A through 22.6-G checkpoint and the review records
  through 3ace53c7cdcc3312033f388d8f68d2d7d1a159ae were pushed to origin/main on 2026-08-28 under
  explicit operator authorization. The preserved rejected 22.6-H checkpoint, the 22.6-H-F1 correction
  and the review records after it stay local; Slice closure does not require a push, and phase-level
  Phase 22.6 closure still requires the Final Closure Audit plus a new explicit authorization
Phase: 22.6 Naming / Classification / Organize configuration journey (roadmap section 5)
Slice scope: Web presentation only. In the destination-precheck evidence block, render the run-level
  fields — including the aggregate verdict — above the "First sample destination" heading, render only
  first-sample fields under it, and label the multi-sample verdict as the run verdict. The only
  production file that may change is `mediaflow/interfaces/operator_ui.py`. No evidence key, request
  or response field, aggregation rule, activation gate, category, route, permission, table or schema
  marker may change; markers stay 10 and 22
```

## Why This Slice Exists

Phase 22.6-H-F1 proved two things about completed multi-sample evidence: the run verdict is the most
severe sample's projected outcome, and it is provably different from the top-level first-sample
projection. The Web surface does not yet show that distinction. In
`mediaflow/interfaces/operator_ui.py:765` the heading `First sample destination` is appended *before*
the single definition list that holds every field, so for a multi-sample run the operator reads
`Sample count`, `Status`, `Verdict`, `Message` and `Next action` — all run-level — underneath a
heading that says they describe the first sample, while the genuinely first-sample-only fields
(`Destination path`, `Target exists`, `Projected conflict outcome`) sit in the same list with nothing
separating them.

That is the one place in this journey where the operator decides whether to activate with checks,
and it currently misattributes the evidence that the gate consumes.

## User Problem

An operator prechecks three samples of one RecognitionType. The run verdict is
`manual_confirmation_required` because sample 1 would land on an existing file, while sample 0
projects `ready`. Today both statements appear in one list under "First sample destination". Either
reading is wrong in a way that matters: taken as sample 0's verdict it understates which sample needs
attention, and taken as the run's destination path it overstates how much of the run is ready. The
evidence is correct; only its presentation misattributes it.

## Journey

- User goal: understand, before activating with checks, what the whole precheck run says and what
  only its first sample says.
- Entry point: Web configuration Draft page, destination precheck section (unchanged).
- Visible state: the same evidence values as today. For a multi-sample run, run-level fields render in
  their own list above the "First sample destination" heading, and only first-sample fields render
  under it. Per-sample rows and the collision table stay where they are.
- Available action: unchanged — "Run read-only destination precheck", still read-only.
- Success outcome: the operator can tell at a glance which fields describe the run — including the
  aggregate verdict, labelled as the run verdict — and which describe sample 0 only.
- Failure outcome: unchanged. The stale sentence, the not-ready sentence, the no-authority warning and
  every bounded failure sentence keep their exact current text; a failed sample keeps its own row with
  its index, projected outcome and failure category.
- Recovery path: unchanged — rerun the precheck on the exact revision, or follow the row's stated next
  action.

## UX Acceptance

1. Single-sample rendering is unchanged: no "First sample destination" heading, the same field labels
   in the same order, the same warnings, the label still `Verdict`.
2. Multi-sample rendering: every run-level field is appended before the heading; every
   first-sample-only field is appended after it, into a separate list.
3. Multi-sample rendering names the aggregate — the verdict label must state that it is the run
   verdict (for example `Run verdict (most severe sample)`), and the single-sample label stays
   `Verdict`.
4. The per-sample rows table, the collision table, the `No cross-item destination collision detected.`
   sentence, the stale sentence, the not-ready sentence and the no-authority warning all render
   exactly as they do today, with byte-identical text.
5. No new evidence key, no new API field, no absolute path, no secret, no new page.

Authoritative field split for this Slice:

- Run-level, before the heading: Evidence state, Sample count, Status, verdict field, Destination
  Storage, Storage support, MediaLibrary and Storage-relative root, Destination root exists /
  directory, Required capabilities, Declared destination capabilities, Missing capabilities, Fallback,
  Authority granted, Path scope, Side effects, Retry safe, Message, Next action.
- First sample only, after the heading: Deepest existing ancestor, Directories that would be created,
  Destination path, Target exists, Configured conflict strategy, Projected conflict outcome, Proposed
  relative destination, Read operations.

## Technical Scope

Files this Slice may change — nothing else:

- `mediaflow/interfaces/operator_ui.py`, inside `renderDestinationPrecheck` only.
- `tests/test_operator_ui.py`.
- `TASK.md` (status block and Completion Report).
- `docs/product-experience.md` only if an existing CURRENT sentence would otherwise become inaccurate,
  and then by at most one sentence, quoted verbatim in the Completion Report. If no such sentence
  exists, change no documentation at all.

Explicitly forbidden: `mediaflow/application/**`, `mediaflow/domain/**`,
`mediaflow/infrastructure/**`, `mediaflow/interfaces/service_api.py`, `mediaflow/cli.py`, `scripts/`,
`config/`, `pyproject.toml`, `docs/progress.md` and `docs/roadmap.md` (both review-owned).

Rules:

1. Presentation only. The same evidence keys are read, the same request body is sent, and no value is
   recomputed, re-derived, reordered inside a row, rounded or reformatted on the way to the page.
2. Every bounded sentence, warning and heading that exists today keeps its exact text, except that the
   verdict field label may differ between the single-sample and multi-sample branches as required
   above.
3. Exactly one existing assertion may be replaced: the line in
   `test_destination_precheck_multi_sample_web_surface_is_falsifiable` that pins
   `if (sampleCount > 1) detailContent.append(text('h4', 'First sample destination'));`. Its
   replacement must be equal or stronger and must pin the new structure. Every other assertion in
   `tests/test_operator_ui.py` stays byte-identical, and no test may be deleted or renamed.
4. New tests must be body-scoped the way the module already does it (`_js_function_body` /
   `_js_braced_body`), because the operator UI is a Python `bytes` literal with no JS runtime.
5. No credential, endpoint, Storage `rootPath`, header, cookie, private path or raw exception text may
   enter the page, the tests, the report or the commit.

## Required Tests

All in `tests/test_operator_ui.py`. Every assertion must fail if the behaviour it names is removed.

1. `test_destination_precheck_run_level_summary_precedes_first_sample_block` — inside the
   `renderDestinationPrecheck` body, assert by source position that the run-level verdict field is
   appended before the `'First sample destination'` heading and that `'Destination path'` and
   `'Target exists'` are appended after it, into a list that is not the run-level list; assert the
   heading is still guarded by `sampleCount > 1`; and assert the per-sample rows table still follows
   the first-sample block.
2. `test_destination_precheck_multi_sample_verdict_label_names_the_run` — assert the multi-sample
   branch labels the aggregate as the run verdict, assert the single-sample branch still uses the exact
   label `Verdict`, and assert the choice is guarded by `sampleCount > 1`.
3. The one permitted replacement in
   `test_destination_precheck_multi_sample_web_surface_is_falsifiable`, keeping the rest of that test
   byte-identical.

No other test may be added, renamed or changed.

## Required Falsification Probes

Mutate the shipped tree one edit at a time, run the affected tests, record the actual failing test
names and output, restore with `git checkout -- <file>`, and confirm a clean tree after each probe.
Report every probe, including the control.

1. Append the run-level list after the `'First sample destination'` heading again — Required Test 1
   must fail.
2. Move `'Destination path'` into the run-level list — Required Test 1 must fail.
3. Drop the `sampleCount > 1` guard so the heading and the multi-sample verdict label always render —
   at least one Required Test must fail on the single-sample claim.
4. Use the plain `Verdict` label in the multi-sample branch — Required Test 2 must fail.
5. Delete the `No cross-item destination collision detected.` sentence — the existing Phase 22.6-H
   test `test_destination_precheck_multi_sample_web_surface_is_falsifiable` must still fail, proving no
   existing proof was weakened by the permitted replacement.
6. Control probe: a comment-only edit inside `renderDestinationPrecheck` must fail no test.

## Validation

Run every command and report its actual output:

- `.venv/bin/python -m unittest` (the total must rise from 861 by exactly the number of added tests,
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
- `git diff --exit-code 4455198a6ef3b93fe1e92cef73660039620e756e HEAD -- mediaflow/application
  mediaflow/domain mediaflow/infrastructure mediaflow/interfaces/service_api.py mediaflow/cli.py
  scripts config pyproject.toml` must be empty, proving evidence semantics, the service boundary, the
  CLI and the schema are untouched.
- `git diff --stat 4455198a6ef3b93fe1e92cef73660039620e756e HEAD` must list only
  `mediaflow/interfaces/operator_ui.py`, `tests/test_operator_ui.py`, `TASK.md`, the review-owned
  `docs/progress.md` and `docs/roadmap.md` from the intervening review-record commit, and at most
  `docs/product-experience.md` under the rule above.
- Secret scan of this Slice's own diff.

## Non-goals — must not start

- Any change to evidence keys, the verdict aggregation, the severity map, failure categories, the
  activation gate, request or response fields, permissions, HTTP statuses, routes, tables, migrations
  or schema markers.
- Making the first-sample block index-accurate when sample 0 itself failed. Today the top-level fields
  come from the first sample that projected successfully, so a run whose sample 0 failed shows a later
  sample's destination under the heading. Correcting that needs the evidence to carry the index of the
  details it exposes, which is an application change; the per-sample rows already show sample 0's own
  failure category, so this Slice leaves it alone and reports it as known.
- Closing the residual proof gap recorded in the Phase 22.6-H-F1 review (no multi-sample all-`ready`
  run asserts `verdict == "ready"`). It is not a blocker and not this Slice's business.
- Remote SMB/OpenList/S3 destination prechecks, mutation-based capability probing, multiple
  RecognitionTypes or multiple destination Storages per request, known-media duplicate detection,
  attachment prechecks, absolute mounted-path display, and any execution or authority change.
- Amending, squashing or rewriting any preserved rejected checkpoint; no push, force push,
  `git reset --hard` or destructive `git clean`.

## Closure Checklist

- [ ] Only `mediaflow/interfaces/operator_ui.py`, `tests/test_operator_ui.py`, `TASK.md` and — only
      under the stated rule — `docs/product-experience.md` changed
- [ ] `git diff --exit-code 4455198 HEAD -- mediaflow/application mediaflow/domain
      mediaflow/infrastructure mediaflow/interfaces/service_api.py mediaflow/cli.py scripts config
      pyproject.toml` is empty
- [ ] Multi-sample run-level fields render before the "First sample destination" heading and
      first-sample-only fields after it, per the authoritative field split
- [ ] The multi-sample verdict label names the run verdict; the single-sample label is still `Verdict`
- [ ] Single-sample rendering is unchanged: no heading, same labels, same order, same warnings
- [ ] Every existing bounded sentence, warning, table and heading keeps its exact text
- [ ] Exactly one existing assertion was replaced, by an equal-or-stronger one; every other assertion
      is byte-identical and no test was deleted or renamed
- [ ] All six Required Falsification Probes executed with recorded output, control included, clean tree
      after each
- [ ] Full offline suite green, total risen only by the added tests
- [ ] Markers still 10 and 22; wheel smoke reports Runtime schema 22
- [ ] No credential, endpoint, Storage `rootPath`, header, cookie, private path or raw exception text
      in the page, tests, report or commit; `config/alist.json` still untracked, unstaged, ignored
- [ ] Completion Report filled in with the actual commands, actual output, deviations and risks
- [ ] Status set to READY FOR HIGH REVIEW; not pushed

## Completion Report

To be filled in by the implementation role: Changed Files, Implemented, Tests, Test Results,
Decisions, Remaining Work, Risks.
