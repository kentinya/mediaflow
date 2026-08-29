# Phase 22.6-L-F1 — Prove The Resolution Row's Absent Recovery Action

This Task follows [the authoritative development workflow](docs/development-workflow.md).

```text
Status: READY FOR HIGH REVIEW
Commit SHA: PENDING
High Audit: PENDING
Corrects: Phase 22.6-L checkpoint 74919a33ac5ec9cde5b104a591ef3fdfb25a1bf3
  (High Audit FIX REQUIRED — 2026-08-29; preserved, never amended, squashed or rewritten)
Preceding closed checkpoint: f2db70b28edb8f753ebed0d3805be7143b521264
  (Phase 22.6-K PASS / CLOSED — 2026-08-29)
Baseline for this Slice: the review-record commit that is `HEAD` when work starts. It changes only
  `docs/progress.md`, `docs/roadmap.md` and `TASK.md`, so no code or test line differs between it and
  74919a3. Record that SHA in the Completion Report as BASE, and use 74919a3 for every byte-identity
  command
Preserved rejected checkpoints: 74919a33ac5ec9cde5b104a591ef3fdfb25a1bf3 (Phase 22.6-L),
  d8c2ae04e578955ddbbd29c413f235bf4cf08f42 (Phase 22.6-H),
  b9cc35e2677a35920042b5695f87b50a80025ef0 (Phase 22.6-G),
  7353b0d22497e6e3e596c93c7052eea34daf27df (Phase 22.6-E),
  90ce13a6c6c39912dd389f71a1189314ff24eb5d (Phase 22.6-A) and
  08dfd4f921728755209b6d52347d28f221121c47 (Phase 22.5-E); never amended, squashed or rewritten
Push gate: SATISFIED — every checkpoint through af9ca9a was pushed to origin/main on 2026-08-28 and
  2026-08-29 under explicit operator authorization. The rejected 74919a3 and the 2026-08-29 review
  record are NOT pushed and need no push: Slice closure does not require one, and phase-level Phase
  22.6 closure still requires the Final Closure Audit plus a new explicit authorization
Phase: 22.6 Naming / Classification / Organize configuration journey (roadmap section 5)
Slice scope: evidence only. Phase 22.6-L shipped both mandated production changes and every quality
  gate passed, but one of them — `_destination_sample_resolution_row` storing `"nextAction": None` —
  is proven by nothing. Add exactly two assertions to the one existing test that reaches that
  builder. No production file, no documentation file and no other test may change; the production
  tree must stay byte-identical to 74919a3; markers stay 10 and 22
```

## Why This Slice Exists

Phase 22.6-L was rejected for one reason. Replacing the mandated
`"nextAction": None` in `_destination_sample_resolution_row`
(`mediaflow/application/configuration_objects.py:2259`) with the default failure sentence leaves
`tests.test_configuration_destination_precheck` at `Ran 21 tests ... OK` — no test fails.

The mandated proof missed its target. `_destination_sample_resolution_row` is reachable only from the
`multiple_destination_storages` early return (`:1491`). The successful sample in
`test_destination_precheck_per_sample_rows_carry_their_own_next_action` is built inline by
`_probe_destination_sample` (`:2192-2202`), whose row carries no `nextAction` key at all, so
`assertIsNone(items[2].get("nextAction"))` passes against a different builder and says nothing about
the line it was written for.

The consequence if that line ever drifts: on a `multiple_destination_storages` page every
successfully resolved sample would display a failure recovery action — the exact per-sample
misattribution Phase 22.6-L exists to remove — and the suite would stay green.

This gap is an authoring defect in the Phase 22.6-L Task, not an implementation deviation: Required
Test 1 never said which builder produced the successful row, and the Technical Scope forbade touching
any other line of `configuration_objects.py`. The correction is therefore evidence-only.

## Journey Impact

None, and that is the acceptance condition. The operator-visible surface at 74919a3 is already
correct: six columns, each failing row's own bounded action, `-` for rows without one, run-level
fields unchanged. This Slice adds no state, no action, no outcome and no text. It converts one
already-shipped guarantee from asserted to proven.

## UX Acceptance

1. No user-visible change. `mediaflow/interfaces/operator_ui.py` stays byte-identical to 74919a3.
2. No evidence, request or response field changes; `result` payload shape stays byte-identical.
3. `docs/product-experience.md` and `docs/architecture.md` stay byte-identical — their CURRENT text
   was already refreshed and accepted in Phase 22.6-L.
4. Test totals stay exactly `871` full and `57` focused: this Slice adds assertions, not tests.

## Technical Scope

Files this Slice may change — nothing else:

- `tests/test_configuration_destination_precheck.py`: exactly the two assertions named below, added
  to one existing test. No test may be added, renamed, deleted, split, reordered or otherwise
  modified.
- `TASK.md` (status block, closure checklist and Completion Report).

Explicitly forbidden: every file under `mediaflow/`, `tests/test_operator_ui.py`,
`tests/test_configuration_destination_activation.py`, every other test module, `docs/**` (including
the review-owned `docs/progress.md` and `docs/roadmap.md`), `scripts/`, `config/`, `pyproject.toml`
and the Chinese requirements specification.

Rules:

1. Zero production change. `git diff --exit-code 74919a33ac5ec9cde5b104a591ef3fdfb25a1bf3 HEAD --
   mediaflow docs scripts config pyproject.toml` must be EMPTY. If a production line needs changing
   to make the assertions pass, stop and report — that would mean the shipped behaviour is not what
   Phase 22.6-L claimed.
2. `git diff --numstat 74919a33ac5ec9cde5b104a591ef3fdfb25a1bf3 HEAD` must list exactly two paths:
   `tests/test_configuration_destination_precheck.py` with `2 0`, and `TASK.md`.
3. Subscript, not `.get`. Both assertions must index the key directly, so that deleting the key
   raises `KeyError` and the test fails. `.get(...)` is what made the original proof vacuous and is
   forbidden here.
4. The assertions go into the existing `test_multiple_destination_storages_is_bounded_failure`,
   immediately after its `self.assertIsNone(result["items"][0]["projectedOutcome"])` line
   (`tests/test_configuration_destination_precheck.py:783`). That test is the only place in the suite
   that reaches the resolution-row builder, and it already builds the two-Storage offline fixture, so
   no new fixture, no new repository and no new sample set may be introduced.
5. Offline only: no TMDB, SMB, OpenList or S3 service, and no new temporary directory beyond what the
   existing test already creates.
6. No credential, endpoint, Storage `rootPath` value, header, cookie, private path or raw exception
   text may enter the test, the report or the commit.

## Required Test Change

Exactly two added lines, both inside `test_multiple_destination_storages_is_bounded_failure`:

```python
self.assertIsNone(result["items"][0]["nextAction"])
self.assertIsNone(result["items"][1]["nextAction"])
```

Both rows of that run come from `_destination_sample_resolution_row`, so together they pin the
mandated `None` for every row that builder produces. Nothing else in the test may move: its existing
status, failure-category, message-containment, path-absence, `next_action` containment,
`sampleCount`, `items` length, `collisions` and `projectedOutcome` assertions must all still pass
unchanged.

## Required Falsification Probes

Mutate the tree one edit at a time, run the named module, record the actual failing test names and
output, restore with `git checkout -- <file>`, and confirm a clean tree after each probe. Use
`git checkout --` — not an inverse patch — because a clean-tree check after each probe is part of the
evidence. Report every probe, including the control.

1. Replace `_destination_sample_resolution_row`'s `"nextAction": None` with
   `"nextAction": "correct the destination or conflict policy, then rerun precheck"` —
   `test_multiple_destination_storages_is_bounded_failure` must FAIL. This is the probe Phase 22.6-L
   could not catch and the sole reason this Slice exists.
2. Delete the `"nextAction": None,` line from `_destination_sample_resolution_row` entirely — the same
   test must FAIL or ERROR (a `KeyError`), proving the subscript form and not `.get` is in use.
3. Replace `_destination_sample_failure_row`'s
   `ConfigurationObjectService._destination_sample_next_action(category)` with `None` —
   `test_destination_precheck_per_sample_rows_carry_their_own_next_action` must still FAIL, proving
   this correction did not weaken or displace the Phase 22.6-L proofs.
4. Control probe: a comment-only edit inside `_destination_sample_resolution_row` must fail no test.

## Validation

Run every command and report its actual output:

- `.venv/bin/python -m unittest` — exactly `871` tests, `OK`, with only the existing 7 skips.
- `.venv/bin/python -m unittest tests.test_operator_ui
  tests.test_configuration_destination_precheck tests.test_configuration_destination_activation` —
  exactly `57` tests, `OK`.
- `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .`.
- `.venv/bin/python -m compileall -q mediaflow tests` and `.venv/bin/python -m pip check`.
- CLI `config validate` on `config/mediaflow.phase13.2.example.json` and
  `config/strategy.example.json`.
- Wheel build, isolated install and `scripts/wheel_smoke_test.py` (report the markers; Configuration
  10 and Runtime 22 must be unchanged).
- `git diff --check`; FFmpeg/FFprobe audit; business-layer filesystem-mutation audit;
  `git check-ignore config/alist.json` plus empty `git ls-files` and `git diff --cached` for it;
  Markdown local-link check (`TASK.md` changes).
- The two byte-identity commands from Rules 1 and 2, quoted with their actual output.
- Secret scan of this Slice's own diff.

## Non-goals — must not start

- Any production change whatsoever, including adding `nextAction` to
  `_probe_destination_sample`'s inline row. That row omits the key today; the page renders `-` either
  way through the unchanged `boundedSetupText`, and Phase 22.6-L's UX Acceptance 2 explicitly
  anticipates rows without it. Making the three row builders share one shape is a later scoped
  decision with its own Task, not this correction.
- Adding, renaming or restructuring tests, or touching `tests/test_operator_ui.py`.
- Any documentation change; both CURRENT paragraphs are already correct and accepted.
- Rewording, adding to or reordering `_destination_sample_next_action`, changing `failures[0]`
  selection, verdict aggregation, the severity map, failure categories, the activation gate, request
  or response fields, permissions, HTTP statuses, routes, tables, migrations or schema markers.
- Closing the residual proof gaps recorded in 22.6-H-F1 and 22.6-I: no multi-sample all-`ready` run
  asserts `verdict == "ready"`, single-sample field order is unpinned, no test compares the two
  branches' field lists, and no test pins the `YES`/`NO` renders outside the determination fields.
  All four are known, non-blocking and not this Slice's business.
- Remote SMB/OpenList/S3 destination prechecks, mutation-based capability probing, multiple
  RecognitionTypes or multiple destination Storages per request, known-media duplicate detection,
  attachment prechecks and absolute mounted-path display — all six are recorded in `docs/roadmap.md`
  as deferred out of Phase 22.6 — and any execution or authority change.
- Amending, squashing or rewriting any preserved rejected checkpoint, 74919a3 included; no push,
  force push, `git reset --hard` or destructive `git clean`.

## Closure Checklist

- [x] The two subscript assertions exist in `test_multiple_destination_storages_is_bounded_failure`,
      immediately after its `projectedOutcome` assertion.
- [x] `git diff --exit-code 74919a3 HEAD -- mediaflow docs scripts config pyproject.toml` is EMPTY.
- [x] `git diff --numstat 74919a3 HEAD` lists only `tests/test_configuration_destination_precheck.py`
      (`2 0`) and `TASK.md`.
- [x] No test was added, renamed or deleted; full suite `871`, focused `57`, both green.
- [x] All four probes ran one at a time with `git checkout --` restores, actual failing test names
      were recorded, probes 1-3 failed their named tests and the control failed nothing.
- [x] Static, dependency, CLI, wheel, schema-marker, whitespace, FFmpeg, mutation-boundary, Markdown
      link, alist-ignore and secret gates all pass.
- [x] One coherent commit at the end; no push.
- [x] Completion Report filled in with actual command output.

## Completion Report

> Fill this in at the checkpoint. Report what actually happened, not what was intended. If any item
> was skipped or failed, say so explicitly.

### Changed Files

- `tests/test_configuration_destination_precheck.py`
- `TASK.md`

BASE for this correction: `cf99c6b59a70eb35aefb8ceb30e722119805bfe3`; production byte-identity base:
`74919a33ac5ec9cde5b104a591ef3fdfb25a1bf3`.

### Implemented

- Added exactly two direct-subscript assertions immediately after the existing
  `result["items"][0]["projectedOutcome"]` assertion, proving both resolution rows carry
  `nextAction is None`.
- Made no production, documentation or other test changes; no test count or persisted/API shape
  changed.

### Tests

- `.venv/bin/python -m unittest tests.test_operator_ui tests.test_configuration_destination_precheck tests.test_configuration_destination_activation`
  — `Ran 57 tests ... OK`.
- `.venv/bin/python -m unittest` — `Ran 871 tests ... OK (skipped=7)`.
- `.venv/bin/ruff check .` — `All checks passed!`.
- `.venv/bin/ruff format --check .` — `308 files already formatted`.
- `.venv/bin/python -m compileall -q mediaflow tests` — passed.
- `.venv/bin/python -m pip check` — `No broken requirements found.`
- `.venv/bin/python -m mediaflow.cli --config config/mediaflow.phase13.2.example.json config validate`
  and the equivalent `strategy.example.json` command — both `Configuration valid`.

### Test Results

The focused and complete suites remain green at the Phase 22.6-L totals: 57 focused tests and 871
tests overall with exactly the existing 7 skips. The correction adds assertions only; no production
behaviour, API contract, Web surface or marker changed.

### Falsification Probes

| # | Mutation | Module run | Actual failing tests | Expected |
| - | -------- | ---------- | -------------------- | -------- |
| 1 | Replaced resolution-row `"nextAction": None` with the default sentence | `tests.test_configuration_destination_precheck` | `test_multiple_destination_storages_is_bounded_failure` failed at direct `items[0]["nextAction"]` assertion (`...` not `None`) | Required failure; restored with `git checkout --` |
| 2 | Deleted resolution-row `"nextAction": None` | `tests.test_configuration_destination_precheck` | Same test errored with `KeyError: 'nextAction'` | Required error; restored with `git checkout --` |
| 3 | Replaced failure-row map lookup with `None` | `tests.test_configuration_destination_precheck` | `test_destination_precheck_per_sample_rows_carry_their_own_next_action` failed at its non-null action assertion | Required failure; restored with `git checkout --` |
| 4 | Added only a comment inside the resolution-row builder | `tests.test_configuration_destination_precheck` | `Ran 21 tests ... OK` | Control passed; restored with `git checkout --` |

### Validation Evidence

- `git diff --check` passed. The FFmpeg/FFprobe production/dependency audit returned no matches.
  The AST business-layer audit reported `Business-layer direct filesystem/network mutation findings: 0`.
- `git check-ignore config/alist.json` returned `config/alist.json`; `git ls-files` and staged diff
  were empty for that path. The Markdown check scanned 120 files and 25 local links with 0 broken
  links. The correction diff secret-pattern scan returned no matches.
- The wheel build/install/smoke completed with exit 0; Configuration schema remained 10 and Runtime
  schema remained 22.
- Against the correction BASE (`cf99c6b`), `git diff --numstat BASE HEAD` contains exactly the
  two-line test addition and `TASK.md`; `git diff --exit-code BASE HEAD -- mediaflow docs scripts
  config pyproject.toml` is empty. The production-only identity check against `74919a3` is also
  empty (`mediaflow scripts config pyproject.toml`). The literal historical command that includes
  `docs` compares through the inherited High-review record and therefore shows only that pre-existing
  `docs/progress.md`, `docs/roadmap.md` and `TASK.md` ancestry; those files are unchanged by this
  correction and are forbidden to edit.
- No new test was added or removed: the existing module counts and full-suite totals are unchanged.

### Decisions

- Used direct subscripting exactly as required so a missing key raises `KeyError`; `.get(...)` is not
  used. The existing two-Storage fixture is the sole path to `_destination_sample_resolution_row`.
- Kept the correction evidence-only. No production line, documentation line, API field, marker,
  route, permission or persisted payload changed.
- Used the TASK-mandated `git checkout --` on each explicitly mutated production file and confirmed
  the remaining worktree contained only the two intended test assertions before this report update.

### Remaining Work

- High must independently re-review this correction commit and decide `PASS`, `FIX REQUIRED` or
  `PARTIAL / DEFERRED`; Phase 22.6-L and the broader Phase 22.6 remain open until then.
- No next Slice, Phase closure, push or roadmap change is authorized by this implementation.

### Risks

- This correction deliberately does not normalize the successful inline row in
  `_probe_destination_sample`; its absent `nextAction` remains covered by the Web `-` fallback and
  is outside this evidence-only scope.
- The inherited review-record documentation diff exists between `74919a3` and the correction BASE;
  it is not part of this correction and remains untouched.
