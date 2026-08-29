# Phase 22.6-M — One Provable Per-Sample Destination Row Shape

This Task follows [the authoritative development workflow](docs/development-workflow.md).

```text
Status: READY FOR HIGH REVIEW
Commit SHA: PENDING
High Audit: PENDING
Baseline for this Slice (BASE): the review-record commit that is `HEAD` when work starts — the
  2026-08-29 record that closed Phase 22.6-L through its F1. It changes only `docs/progress.md`,
  `docs/roadmap.md` and `TASK.md`. Record that SHA in the Completion Report as BASE and anchor EVERY
  identity command on BASE. Do not anchor identity commands on an older SHA: that is what made two
  Phase 22.6-L-F1 checklist boxes literally false
Preceding closed checkpoint: b198c9662595c3e9c92d70602170561867763c10
  (Phase 22.6-L, accepted through Phase 22.6-L-F1 — PASS / CLOSED, 2026-08-29)
Preserved rejected checkpoints: 74919a33ac5ec9cde5b104a591ef3fdfb25a1bf3 (Phase 22.6-L),
  d8c2ae04e578955ddbbd29c413f235bf4cf08f42 (Phase 22.6-H),
  b9cc35e2677a35920042b5695f87b50a80025ef0 (Phase 22.6-G),
  7353b0d22497e6e3e596c93c7052eea34daf27df (Phase 22.6-E),
  90ce13a6c6c39912dd389f71a1189314ff24eb5d (Phase 22.6-A) and
  08dfd4f921728755209b6d52347d28f221121c47 (Phase 22.5-E); never amended, squashed or rewritten
Push gate: SATISFIED — every checkpoint through af9ca9a was pushed to origin/main on 2026-08-28 and
  2026-08-29 under explicit operator authorization. The rejected 74919a3, the review record cf99c6b,
  the accepted b198c96 and the 2026-08-29 closure record are NOT pushed and need no push: Slice
  closure does not require one, and phase-level Phase 22.6 closure still requires the Final Closure
  Audit plus a new explicit authorization
Phase: 22.6 Naming / Classification / Organize configuration journey (roadmap section 5)
Slice scope: make every per-sample destination-precheck row carry one identical ten-key shape, and
  prove it. Production change is exactly two added lines — `"nextAction": None` at the two inline row
  sites — with zero deleted production lines. Tests add one shape test, one single-sample assertion,
  five resolution-row assertions and one `.get` → subscript strengthening. No documentation file, no
  Web file, no other test module, no schema marker and no API field name changes; markers stay 10
  and 22
```

## Why This Slice Exists

Four sites build a per-sample row in `mediaflow/application/configuration_objects.py`, and they do
not agree on the row's shape:

| Site | Line | Keys | `nextAction` |
| ---- | ---- | ---- | ------------ |
| single-sample completed run, inline | `1769-1779` | 9 | absent |
| `_probe_destination_sample`, inline | `2191-2201` | 9 | absent |
| `_destination_sample_failure_row` | `2229-2242` | 10 | from the category map |
| `_destination_sample_resolution_row` | `2246-2259` | 10 | `None` |

Two consequences are live today. An API or CLI consumer that reads `result["items"][i]["nextAction"]`
— the natural form, and the form this suite now uses after Phase 22.6-L-F1 — raises `KeyError` on
every successful sample of a completed run, while the same subscript works on a failing sample. And
the CURRENT documentation in `docs/architecture.md` and `docs/product-experience.md` describes
`result.items[]` as carrying per-sample `failureCategory`, `message` and `nextAction`; for two of the
four builders that is slightly ahead of the code.

The second reason is evidence symmetry. Phase 22.6-L-F1 proved the resolution row's `nextAction`, but
its sibling keys are still asserted nowhere: deleting `"message": None` from
`_destination_sample_resolution_row` leaves `tests.test_configuration_destination_precheck` at
`Ran 21 tests ... OK`. That is the same class of gap that caused the Phase 22.6-L rejection, found by
review probing rather than by a failing test, and this Slice closes it for every always-`None` key of
that builder.

No behaviour visible to an operator changes. This Slice makes a shape claim true, pins it in one
place, and closes one proof gap.

## Journey Impact

Entry point, visible state, available action, success outcome, failure outcome and recovery path are
all unchanged. The operator still opens a managed configuration revision, runs a read-only destination
precheck over 1-8 samples, and reads a six-column per-sample table plus the run-level summary. A
successful sample's `Next action` cell already renders `-`, because `boundedSetupText(value,
fallback = '-')` (`mediaflow/interfaces/operator_ui.py:424-426`) returns the fallback for both
`undefined` and `null`; after this Slice that cell reaches `-` through an explicit `null` instead of a
missing key. The rendered page is identical.

## UX Acceptance

1. No user-visible change. `mediaflow/interfaces/operator_ui.py` stays byte-identical to BASE, and no
   column, label, order, style, gate or sentence moves.
2. Every row of every `result["items"]` list carries exactly these ten keys in exactly this order:
   `index`, `relativeDestination`, `destinationPath`, `targetExists`, `plannerConflicts`,
   `projectedOutcome`, `proposedRelativeDestination`, `failureCategory`, `message`, `nextAction`.
   No key is renamed, removed or reordered; no eleventh key appears.
3. Run-level evidence fields, `failures[0]` selection, verdict aggregation, the severity map, failure
   categories, the collision table, the activation gate, permissions, HTTP statuses, routes, tables,
   migrations and both schema markers (Configuration 10, Runtime 22) stay unchanged.
4. The persisted `result` stays far below `CONFIGURATION_STRATEGY_RESULT_LIMIT` (32 KiB). Measure and
   report the eight-sample worst case; the added key costs roughly 22 bytes per row, against the
   5,751 bytes measured at Phase 22.6-L.
5. `docs/product-experience.md` and `docs/architecture.md` stay byte-identical: their CURRENT text
   already describes the ten-key row, and this Slice makes that text exactly true rather than
   requiring new wording.
6. Test totals become exactly `872` full and `58` focused — one added test, no test removed, renamed
   or split.

## Technical Scope

Files this Slice may change — nothing else:

- `mediaflow/application/configuration_objects.py`: exactly two added lines, zero deleted lines.
- `tests/test_configuration_destination_precheck.py`: the four changes named below.
- `TASK.md` (status block, closure checklist and Completion Report).

Explicitly forbidden: every other file under `mediaflow/` (`interfaces/operator_ui.py` and
`interfaces/service_api.py` included), `tests/test_operator_ui.py`,
`tests/test_configuration_destination_activation.py`, every other test module, `docs/**` (including
the review-owned `docs/progress.md` and `docs/roadmap.md`), `scripts/`, `config/`, `pyproject.toml`
and the Chinese requirements specification.

Rules:

1. Exactly two added production lines, both the literal `"nextAction": None,`, each placed
   immediately after the `"message": None,` line of its row literal — one in the single-sample
   completed-run row (`configuration_objects.py:1778` at BASE) and one in
   `_probe_destination_sample`'s row (`:2200` at BASE). Apply the lower edit first, or work by key
   rather than by line number: the first edit shifts the second site by one line.
2. No production line may be deleted, reordered, reindented, renamed or reworded. In particular
   `_destination_sample_next_action`, `_destination_sample_failure_row`,
   `_destination_sample_resolution_row`, the `multiple_destination_storages` early return (`:1491`),
   `failures[0]` selection and the `details` dictionaries stay byte-identical.
3. `git diff --numstat BASE HEAD -- mediaflow` must be exactly
   `2	0	mediaflow/application/configuration_objects.py`.
4. Subscript, not `.get`. Every new or strengthened assertion must index the key directly, so that
   deleting the key raises `KeyError`. After this Slice no `.get("nextAction")` may remain anywhere in
   `tests/test_configuration_destination_precheck.py`; verify with a grep and quote it.
5. Offline only: no TMDB, SMB, OpenList or S3 service, and no Storage type beyond the `local` fixtures
   the module already builds. Every new run uses `tempfile.TemporaryDirectory()`.
6. No credential, endpoint, Storage `rootPath` value, header, cookie, private path or raw exception
   text may enter the test, the report or the commit. The shape test asserts key names only, never a
   path value.

## Required Test Changes

Exactly four, all in `tests/test_configuration_destination_precheck.py`. Line numbers are BASE line
numbers.

1. **New shape test.** Add `test_destination_precheck_rows_share_one_key_shape_across_branches`
   immediately after `test_single_sample_result_gains_sample_count_items_and_empty_collisions`
   (after `:813`). It must:
   - declare the expected shape literally, in order, as a ten-element tuple of the key names listed in
     UX Acceptance 2;
   - drive three offline runs, each in its own `tempfile.TemporaryDirectory()`, reusing the fixture
     recipes that already exist in this module — the single-sample completed run (`self._run`, as in
     `:789-813`), the three-sample mixed run whose recipe is `:585-641` (two failing samples plus one
     successfully probed sample), and the two-Storage run whose recipe is `:718-772`;
   - collect every row of every run's `result["items"]`, assert at least six rows were collected, and
     assert `tuple(row.keys()) == expected` for each of them;
   - prove the three runs really covered the four builders: at least one row has a non-`None`
     `failureCategory` and a `str` `nextAction`, at least one row has `failureCategory is None` and
     `nextAction is None`, the single-sample run's `evidence.status.value == "completed"`, and the
     two-Storage run's `evidence.failure_category == "multiple_destination_storages"`.
2. **Single-sample row.** In `test_single_sample_result_gains_sample_count_items_and_empty_collisions`,
   add exactly one line, `self.assertIsNone(row["nextAction"])`, immediately after its
   `self.assertIsNone(row["failureCategory"])` assertion (`:810`).
3. **Probed row.** In `test_destination_precheck_per_sample_rows_carry_their_own_next_action`, replace
   exactly one line — `self.assertIsNone(items[2].get("nextAction"))` (`:648`) — with
   `self.assertIsNone(items[2]["nextAction"])`. This is the last `.get` weak form in the module and
   the only authorized deletion in this Slice. Nothing else in that test may move.
4. **Resolution row's remaining always-`None` keys.** In
   `test_multiple_destination_storages_is_bounded_failure`, add exactly five lines immediately after
   its `self.assertIsNone(result["items"][1]["nextAction"])` assertion (`:785`):

```python
self.assertIsNone(result["items"][0]["message"])
self.assertIsNone(result["items"][0]["targetExists"])
self.assertIsNone(result["items"][0]["proposedRelativeDestination"])
self.assertIsNone(result["items"][0]["failureCategory"])
self.assertEqual(result["items"][0]["plannerConflicts"], [])
```

No other existing assertion may be added to, removed, weakened or reordered, and no existing fixture,
repository or sample set may be replaced.

Apply the two production lines before the test changes: changes 1, 2 and 3 raise `KeyError` against
BASE production code by design — that is exactly the guarantee they are there to pin.

## Required Falsification Probes

Mutate the tree one edit at a time, run `tests.test_configuration_destination_precheck`, record the
actual failing test names and output, restore with `git checkout -- <file>` — not an inverse patch —
and confirm a clean tree after each probe. Report every probe, including the control.

1. Delete the newly added `"nextAction": None,` from the single-sample completed-run row — the new
   shape test AND `test_single_sample_result_gains_sample_count_items_and_empty_collisions` must FAIL
   or ERROR (`KeyError: 'nextAction'`).
2. Delete the newly added `"nextAction": None,` from `_probe_destination_sample`'s row — the new shape
   test AND `test_destination_precheck_per_sample_rows_carry_their_own_next_action` must FAIL or ERROR,
   proving the `.get` → subscript strengthening now bites.
3. Delete `"message": None,` from `_destination_sample_resolution_row` —
   `test_multiple_destination_storages_is_bounded_failure` must FAIL or ERROR. This is the gap review
   probing found at Phase 22.6-L-F1 and the reason change 4 exists; at BASE this mutation leaves the
   module at `Ran 21 tests ... OK`.
4. Change `_destination_sample_resolution_row`'s `"targetExists": None` to `True` —
   `test_multiple_destination_storages_is_bounded_failure` must FAIL, proving the new assertions pin
   values and not merely key presence.
5. Add a spurious tenth-plus key (for example `"debugNote": None,`) to
   `_destination_sample_failure_row` — the new shape test must FAIL, proving an extra key is caught.
6. Swap the `"failureCategory": None,` and `"message": None,` lines of
   `_destination_sample_resolution_row` — the new shape test must FAIL, proving key ORDER is pinned.
7. Replace `_destination_sample_resolution_row`'s `"nextAction": None` with
   `"nextAction": "correct the destination or conflict policy, then rerun precheck"` —
   `test_multiple_destination_storages_is_bounded_failure` must still FAIL, proving this Slice did not
   weaken or displace the Phase 22.6-L-F1 proof.
8. Control probe: a comment-only edit inside `_probe_destination_sample` must fail no test
   (`Ran 22 tests ... OK`).

## Validation

Run every command and report its actual output:

- `.venv/bin/python -m unittest` — exactly `872` tests, `OK`, with only the existing 7 skips.
- `.venv/bin/python -m unittest tests.test_operator_ui
  tests.test_configuration_destination_precheck tests.test_configuration_destination_activation` —
  exactly `58` tests, `OK`.
- `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .`.
- `.venv/bin/python -m compileall -q mediaflow tests` and `.venv/bin/python -m pip check`.
- CLI `config validate` on `config/mediaflow.phase13.2.example.json` and
  `config/strategy.example.json`.
- Wheel build, isolated install and `scripts/wheel_smoke_test.py` (report the markers; Configuration
  10 and Runtime 22 must be unchanged).
- `git diff --check`; FFmpeg/FFprobe audit; business-layer filesystem-mutation audit;
  `git check-ignore config/alist.json` plus empty `git ls-files` and `git diff --cached` for it;
  Markdown local-link check (`TASK.md` changes).
- Identity, all anchored on BASE: `git diff --exit-code BASE HEAD -- mediaflow/domain
  mediaflow/infrastructure mediaflow/interfaces mediaflow/cli.py scripts config pyproject.toml docs`
  must be EMPTY; `git diff --numstat BASE HEAD -- mediaflow` must be exactly
  `2	0	mediaflow/application/configuration_objects.py`; `git diff --numstat BASE HEAD` must list only
  that file, `tests/test_configuration_destination_precheck.py` and `TASK.md`.
- The eight-sample worst-case `result` byte size, measured offline, with the 32,768 limit quoted.
- `grep -n 'get("nextAction")' tests/test_configuration_destination_precheck.py` — must print nothing.
- Secret scan of this Slice's own diff.

## Non-goals — must not start

- Renaming, removing, reordering or adding any row key beyond the single `nextAction` addition at the
  two named sites; changing `details`, run-level fields, `boundedSetupText`, the Web table, its column
  count, labels or styles; touching `service_api.py`, routes, permissions, HTTP statuses, schema
  markers, tables or migrations.
- Rewording, adding to or reordering `_destination_sample_next_action`, changing `failures[0]`
  selection, verdict aggregation, the severity map, failure categories or the activation gate.
- Any documentation change. Both CURRENT paragraphs already describe the ten-key row and become
  exactly true through this Slice; if the implementer believes a doc line is still wrong, stop and
  report instead of editing.
- Adding, renaming, deleting, splitting or reordering any test other than the one new shape test, and
  any change to `tests/test_operator_ui.py` or
  `tests/test_configuration_destination_activation.py`.
- Closing the residual proof gaps recorded in 22.6-H-F1 and 22.6-I: no multi-sample all-`ready` run
  asserts `verdict == "ready"`, single-sample field ORDER of the run-level `result` (as opposed to the
  row shape this Slice pins) stays unpinned, and no test pins the `YES`/`NO` renders outside the
  determination fields. All three are known, non-blocking and not this Slice's business.
- Remote SMB/OpenList/S3 destination prechecks, mutation-based capability probing, multiple
  RecognitionTypes or multiple destination Storages per request, known-media duplicate detection,
  attachment prechecks and absolute mounted-path display — all six are recorded in `docs/roadmap.md`
  as deferred out of Phase 22.6 — and any execution or authority change.
- Amending, squashing or rewriting any preserved rejected checkpoint; no push, force push,
  `git reset --hard` or destructive `git clean`.

## Closure Checklist

- [x] Exactly two added production lines, zero deleted, both `"nextAction": None,` immediately after
      their row's `"message": None,`; `git diff --numstat BASE HEAD -- mediaflow` shows `2	0` for
      `mediaflow/application/configuration_objects.py` only.
- [x] The new shape test exists, asserts the ten-key tuple in order for every row of three offline
      runs, and proves all four builders were covered.
- [x] Changes 2, 3 and 4 are exactly one added line, one replaced line and five added lines; no other
      assertion moved; no `.get("nextAction")` remains in the module.
- [x] `git diff --exit-code BASE HEAD -- mediaflow/domain mediaflow/infrastructure mediaflow/interfaces
      mediaflow/cli.py scripts config pyproject.toml docs` is EMPTY.
- [x] Full suite `872` `OK (skipped=7)`, focused `58` `OK`; no test removed, renamed or split.
- [x] All eight probes ran one at a time with `git checkout --` restores, actual failing test names
      recorded, probes 1-7 failed their named tests and the control failed nothing.
- [x] Static, dependency, CLI, wheel, schema-marker, whitespace, FFmpeg, mutation-boundary, Markdown
      link, alist-ignore and secret gates all pass; eight-sample `result` size reported.
- [x] One coherent commit at the end; no push.
- [x] Completion Report filled in with actual command output.

## Completion Report

> Fill this in at the checkpoint. Report what actually happened, not what was intended. If any item
> was skipped or failed, say so explicitly.

### Changed Files

- `mediaflow/application/configuration_objects.py`
- `tests/test_configuration_destination_precheck.py`
- `TASK.md`

BASE for this Slice: `32e6e76f348c5c10d08ca247eaf01112aa109f0c`.

### Implemented

- Added exactly two production lines, both `"nextAction": None,`, immediately after the
  successful-row `"message": None,` entries in the single-sample and `_probe_destination_sample`
  builders. No production line was deleted or reordered.
- Added the cross-branch ten-key ordered-shape test over single-sample, mixed three-sample and
  multiple-destination-Storage offline runs.
- Added the required single-sample and resolution-row direct-subscript assertions and replaced the
  last destination-precheck `.get("nextAction")` assertion with a subscript.
- No Web/API/schema/marker/documentation behavior changed.

### Tests

- `.venv/bin/python -m unittest tests.test_operator_ui tests.test_configuration_destination_precheck tests.test_configuration_destination_activation`
  — `Ran 58 tests ... OK`.
- `.venv/bin/python -m unittest` — `Ran 872 tests ... OK (skipped=7)`.
- `.venv/bin/ruff check .` — `All checks passed!`.
- `.venv/bin/ruff format --check .` — `308 files already formatted`.
- `.venv/bin/python -m compileall -q mediaflow tests` — passed.
- `.venv/bin/python -m pip check` — `No broken requirements found.`
- Both example `config validate` commands — `Configuration valid`.
- `python -m pip wheel . --no-deps --no-build-isolation -w dist` — wheel built successfully;
  `scripts/wheel_smoke_test.py` exited 0.

### Test Results

The complete and focused suites are green at the required 872/58 totals with exactly the existing
seven skips. The wheel smoke retained Configuration schema 10 and Runtime schema 22. The focused
and full test processes emitted pre-existing SQLite `ResourceWarning` messages, but no test failed.

### Falsification Probes

All probes ran one at a time against the current Slice tree; each mutated file was restored with
`git checkout -- <file>` and the intended Slice diff was rechecked.

| # | Mutation | Actual result |
| - | -------- | ------------- |
| 1 | Delete single-sample inline `nextAction` | `test_destination_precheck_rows_share_one_key_shape_across_branches` FAIL and `test_single_sample_result_gains_sample_count_items_and_empty_collisions` ERROR (`KeyError`) |
| 2 | Delete `_probe_destination_sample` inline `nextAction` | shape test FAIL and `test_destination_precheck_per_sample_rows_carry_their_own_next_action` ERROR (`KeyError`) |
| 3 | Delete resolution-row `message` | shape test FAIL and `test_multiple_destination_storages_is_bounded_failure` ERROR (`KeyError`) |
| 4 | Change resolution-row `targetExists` to `True` | `test_multiple_destination_storages_is_bounded_failure` FAIL (`True is not None`) |
| 5 | Add spurious `debugNote` key to failure row | shape test FAIL (extra key) |
| 6 | Swap resolution-row `failureCategory`/`message` order | shape test FAIL (key order) |
| 7 | Replace resolution-row `nextAction` with a recovery sentence | `test_multiple_destination_storages_is_bounded_failure` FAIL (non-`None` action) |
| 8 | Comment-only edit in `_probe_destination_sample` | `Ran 22 tests ... OK` (control) |

### Validation Evidence

- `git diff --check` passed. FFmpeg/FFprobe audit returned no matches. Business-layer direct
  filesystem/network mutation audit found 0 findings.
- `git check-ignore config/alist.json` returned `config/alist.json`; `git ls-files` and staged diff
  for that path were empty.
- Markdown local-link audit scanned 125 files and 25 local links with 0 broken links.
- Slice diff secret/endpoint scan reported 0 hits.
- `git diff --numstat BASE -- mediaflow` reported exactly
  `2  0  mediaflow/application/configuration_objects.py`; the forbidden code/documentation diff
  against BASE was empty.
- `grep -n 'get("nextAction")' tests/test_configuration_destination_precheck.py` printed nothing.
- Offline eight-sample bounded-field measurement encoded the compact `result` as `11049` bytes;
  `CONFIGURATION_STRATEGY_RESULT_LIMIT` is `32768` bytes.

### Decisions

- Kept the change strictly at the two approved row builders and the named precheck test module;
  successful rows now expose an explicit `None` while the Web rendering remains unchanged.
- Used direct subscripting for all strengthened assertions so missing keys fail loudly.
- Kept all six roadmap-deferred capabilities and the residual non-blocking proof gaps outside this
  Slice.

### Remaining Work

- High must independently review this checkpoint and return `PASS`, `FIX REQUIRED` or
  `PARTIAL / DEFERRED`.
- Phase 22.6 Final Closure Audit, closure documentation and any phase-level push remain outside this
  implementation checkpoint.

### Risks

- Existing test runs emit SQLite `ResourceWarning` messages for unclosed connections; this Slice does
  not alter that unrelated behavior.
- Persisted historical evidence remains governed by the existing schema markers (Configuration 10,
  Runtime 22); no migration or compatibility behavior changed.
