# Phase 22.6-N — Prove The Multi-Sample Verdict In Both Directions

This Task follows [the authoritative development workflow](docs/development-workflow.md).

```text
Status: NOT STARTED
Commit SHA: PENDING
High Audit: PENDING
Baseline for this Slice (BASE): the review-record commit that is `HEAD` when work starts — the
  2026-08-29 record that closed Phase 22.6-M. It changes only `docs/progress.md`, `docs/roadmap.md`
  and `TASK.md`. Record that SHA in the Completion Report as BASE and anchor EVERY identity command
  on BASE. Do not anchor identity commands on an older SHA: that is what made two Phase 22.6-L-F1
  checklist boxes literally false
Preceding closed checkpoint: 03e64d40023753be13b2cce18b8c5a63492d344a
  (Phase 22.6-M — PASS / CLOSED, 2026-08-29)
Preserved rejected checkpoints: 74919a33ac5ec9cde5b104a591ef3fdfb25a1bf3 (Phase 22.6-L),
  d8c2ae04e578955ddbbd29c413f235bf4cf08f42 (Phase 22.6-H),
  b9cc35e2677a35920042b5695f87b50a80025ef0 (Phase 22.6-G),
  7353b0d22497e6e3e596c93c7052eea34daf27df (Phase 22.6-E),
  90ce13a6c6c39912dd389f71a1189314ff24eb5d (Phase 22.6-A) and
  08dfd4f921728755209b6d52347d28f221121c47 (Phase 22.5-E); never amended, squashed or rewritten
Push gate: SATISFIED — every checkpoint through af9ca9a was pushed to origin/main on 2026-08-28 and
  2026-08-29 under explicit operator authorization. The rejected 74919a3, the review record cf99c6b,
  the accepted b198c96, the 22.6-L closure record 32e6e76, the accepted 03e64d4 and the 2026-08-29
  22.6-M closure record are NOT pushed and need no push: Slice closure does not require one, and
  phase-level Phase 22.6 closure still requires the Final Closure Audit plus a new explicit
  authorization
Phase: 22.6 Naming / Classification / Organize configuration journey (roadmap section 5)
Slice scope: prove the multi-sample destination-precheck verdict in the two directions no test
  currently observes — an all-`ready` multi-sample run must report `verdict == "ready"`, and a
  capability gap must override otherwise-`ready` rows. Tests only: exactly two added tests in
  `tests/test_configuration_destination_precheck.py`, ZERO added or deleted production lines, and no
  documentation, Web, API, schema-marker, route or permission change; markers stay 10 and 22
```

## Why This Slice Exists

The multi-sample verdict is computed in one expression
(`mediaflow/application/configuration_objects.py:2043-2045`):

```python
verdict = (
    "capability_gap" if any_missing else max(outcomes, key=lambda value: severity[value])
)
```

Review probing at Phase 22.6-M measured that this expression is only half-proved. Replacing the whole
expression with the constant `"manual_confirmation_required"` leaves the full suite at `Ran 872 tests
... OK`, because no test runs a multi-sample precheck in which every sample is `ready` and then
asserts the verdict, and no test observes `capability_gap` on a multi-sample run at all. The opposite
directions are already covered: substituting `min` for `max`, or hard-coding `"ready"`, each fails
three existing multi-sample tests.

That matters to the operator, not only to the test count. `verdict` is the run-level sentence the Web
panel and the activation gate read: an inflated verdict would tell an operator that a clean 3-sample
batch needs manual confirmation, and a swallowed `capability_gap` would tell an operator that a
HardLink destination is `ready` when the destination Storage cannot hard-link at all. Both are
"Configuration displayed as Active must be what runtime consumes" failures in miniature, and both are
currently unobserved by any test.

This Slice adds the two missing observations. It writes no production line: the behaviour is already
correct, and the gap is purely one of proof.

## Journey Framing

- **User problem**: the operator cannot trust a run-level destination verdict that no test pins in
  the clean case or in the capability-gap case.
- **Entry point**: unchanged — Web operator panel, managed configuration revision, read-only
  destination precheck over 1-8 samples.
- **Visible state**: unchanged — the run-level verdict line, the six-column per-sample table, the
  collision table and the capability fields.
- **Available action**: unchanged — run precheck, read the verdict, then either activate or correct
  the configuration.
- **Success outcome**: unchanged — an all-`ready` batch reports `ready`; the operator may proceed.
- **Failure outcome**: unchanged — a capability gap reports `capability_gap` with
  `missingStorageCapabilities` and `requiredByOperation`, and the activation gate keeps refusing.
- **Recovery path**: unchanged — the operator changes the organize operation or the destination
  Storage, then reruns the precheck.

## UX Acceptance

1. No user-visible change whatsoever. `mediaflow/interfaces/operator_ui.py`,
   `mediaflow/interfaces/service_api.py` and every other production file stay byte-identical to BASE.
2. An offline multi-sample run whose every sample is `ready` reports `verdict == "ready"` — not an
   inflated severity — with `sampleCount == 3`, `collisions == []`, `status == "completed"`, and every
   row `projectedOutcome == "ready"`, `failureCategory is None`, `nextAction is None`.
3. An offline multi-sample run whose destination Storage cannot satisfy the required capability
   reports `verdict == "capability_gap"` even though every row is `projectedOutcome == "ready"`, with
   `missingStorageCapabilities == ["can_hard_link"]` and `requiredByOperation == "hard_link"`.
4. Both new runs stay read-only: `guardMutationCalls` values are all `0`, `authorityGranted` is
   `"none"`, and the destination tree snapshot is byte-identical before and after.
5. The ten-key per-sample row shape closed at Phase 22.6-M, the severity map, failure categories, the
   collision table, `failures[0]` selection, the activation gate, permissions, HTTP statuses, routes,
   tables, migrations and both schema markers (Configuration 10, Runtime 22) stay unchanged.
6. `docs/product-experience.md` and `docs/architecture.md` stay byte-identical; their CURRENT text
   already describes verdict aggregation, and this Slice only proves it.
7. Test totals become exactly `874` full and `60` focused — two added tests, none removed, renamed or
   split.

## Technical Scope

Files this Slice may change — nothing else:

- `tests/test_configuration_destination_precheck.py`: exactly two added tests, zero deleted or
  modified existing lines.
- `TASK.md` (status block, closure checklist and Completion Report).

Explicitly forbidden: every file under `mediaflow/`, every other test module (including
`tests/test_operator_ui.py` and `tests/test_configuration_destination_activation.py`), `docs/**`
(including the review-owned `docs/progress.md` and `docs/roadmap.md`), `scripts/`, `config/`,
`pyproject.toml` and the Chinese requirements specification.

Rules:

1. Zero production lines. `git diff --numstat BASE HEAD -- mediaflow` must print NOTHING. If the
   implementer believes a production change is needed to make either test pass, stop and report
   instead of editing: both directions were verified reachable against the shipped code.
2. No existing test, helper, fixture or assertion may be renamed, deleted, weakened, reordered or
   added to. The two new tests must build their own documents and run their own
   `tempfile.TemporaryDirectory()` roots, reusing the module's existing helpers (`_document`,
   `_tree_snapshot`, `_open`) as-is.
3. Subscript, not `.get`, for every new assertion, so a missing key raises `KeyError`.
4. Offline only: no TMDB, SMB, OpenList or S3 service, and no Storage type beyond the `local`
   fixtures the module already builds. The capability gap must be produced exactly as
   `test_capability_gap_hardlink_cleanup_and_declared_read_only` (`:979-1014`) already does — set
   `organizePolicies[0]["operation"] = "HARD_LINK"` and wrap the run in
   `patch.object(LocalStorage, "_can_hard_link", return_value=False)`. Do not add a new fake Storage,
   a new capability flag or a new patch target.
5. No credential, endpoint, Storage `rootPath` value, header, cookie, private path or raw exception
   text may enter the tests, the report or the commit.

## Required Test Changes

Exactly two added tests in `tests/test_configuration_destination_precheck.py`, both inserted
immediately after `test_destination_precheck_rows_share_one_key_shape_across_branches` (after `:977`)
and before `test_capability_gap_hardlink_cleanup_and_declared_read_only` (`:979`). Line numbers are
BASE line numbers.

1. **`test_multi_sample_all_ready_verdict_is_ready_not_inflated`** — three samples that all project
   `ready`. Use the three distinct-destination samples of
   `test_multiple_samples_success_most_severe_verdict_and_distinct_rows` (`:248-272`) but do NOT
   pre-create any target file, so no sample hits `DESTINATION_EXISTS`. Snapshot the destination tree
   with `self._tree_snapshot` before the run. Assert, by direct subscript:
   - `evidence.status.value == "completed"`;
   - `result["verdict"] == "ready"` — the assertion this Slice exists for;
   - `result["sampleCount"] == 3` and `result["collisions"] == []`;
   - `[row["index"] for row in result["items"]] == [0, 1, 2]`;
   - `[row["projectedOutcome"] for row in result["items"]] == ["ready", "ready", "ready"]`;
   - every row has `failureCategory is None`, `message is None`, `nextAction is None` and
     `targetExists` false;
   - three distinct `destinationPath` values;
   - `result["authorityGranted"] == "none"`, `set(result["guardMutationCalls"].values()) == {0}`, and
     the tree snapshot equals the pre-run snapshot.
2. **`test_multi_sample_capability_gap_overrides_ready_rows`** — two samples that would each project
   `ready`, run against a `HARD_LINK` organize policy with `_can_hard_link` patched to `False`.
   Assert, by direct subscript:
   - `evidence.status.value == "completed"`;
   - `result["verdict"] == "capability_gap"` — proving the guard, not the severity `max`, decides;
   - `result["missingStorageCapabilities"] == ["can_hard_link"]` and
     `result["requiredByOperation"] == "hard_link"`;
   - `result["sampleCount"] == 2` and `result["collisions"] == []`;
   - every row still reports `projectedOutcome == "ready"` and `failureCategory is None` — the point
     being that the run-level verdict overrides uniformly `ready` rows rather than being derived from
     them;
   - `result["authorityGranted"] == "none"`, `set(result["guardMutationCalls"].values()) == {0}`, and
     the destination tree snapshot is byte-identical before and after.

Both tests must close their repository in a `finally:` block, exactly as every existing test in the
module does.

## Required Falsification Probes

Mutate the tree one edit at a time, run `tests.test_configuration_destination_precheck`, record the
actual failing test names and output, restore with `git checkout -- <file>` — not an inverse patch —
and confirm a clean tree after each probe. Report every probe, including the control.

1. Replace the whole `verdict = (...)` expression (`configuration_objects.py:2043-2045`) with the
   constant `"manual_confirmation_required"` — `test_multi_sample_all_ready_verdict_is_ready_not_inflated`
   AND `test_multi_sample_capability_gap_overrides_ready_rows` must FAIL. At BASE this mutation leaves
   the full suite at `Ran 872 tests ... OK`; quote both the BASE and the post-Slice result.
2. Replace the same expression with the constant `"overwrite_requires_confirmation"` — the all-`ready`
   test must FAIL, proving the new assertion pins the value and not merely "some verdict".
3. Drop the capability guard, i.e. `verdict = max(outcomes, key=lambda value: severity[value])` —
   `test_multi_sample_capability_gap_overrides_ready_rows` must FAIL with `ready` observed where
   `capability_gap` is required.
4. Invert the guard to `verdict = "capability_gap" if not any_missing else max(...)` — the all-`ready`
   test must FAIL, proving the two new tests bracket the guard from both sides.
5. Replace `max` with `min` — record which tests fail. Expect existing severity tests, not the new
   ones, to catch this; report the actual names rather than a prediction.
6. Set the severity map's `"ready"` to `5` — record which tests fail. This is expected to be caught by
   the existing mixed-severity tests and NOT by the new all-`ready` test (a single distinct outcome
   makes `max` indifferent); state that honestly rather than claiming new coverage.
7. Drop the `if row["projectedOutcome"] is not None` filter from the `outcomes` comprehension
   (`:2040-2042`) — record which tests fail.
8. Control probe: a comment-only edit inside the multi-sample verdict block must fail no test
   (`Ran 24 tests ... OK`).

## Validation

Run every command and report its actual output:

- `.venv/bin/python -m unittest` — exactly `874` tests, `OK`, with only the existing 7 skips.
- `.venv/bin/python -m unittest tests.test_operator_ui
  tests.test_configuration_destination_precheck tests.test_configuration_destination_activation` —
  exactly `60` tests, `OK`.
- `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .`.
- `.venv/bin/python -m compileall -q mediaflow tests` and `.venv/bin/python -m pip check`.
- CLI `config validate` on `config/mediaflow.phase13.2.example.json` and
  `config/strategy.example.json`.
- Wheel build, isolated install and `scripts/wheel_smoke_test.py` (report the markers; Configuration
  10 and Runtime 22 must be unchanged).
- `git diff --check`; FFmpeg/FFprobe audit; business-layer filesystem-mutation audit;
  `git check-ignore config/alist.json` plus empty `git ls-files` and `git diff --cached` for it;
  Markdown local-link check (`TASK.md` changes). Report the count of tracked `.md` files from
  `git ls-files -z '*.md'`, not a `find` sweep that includes `.venv/`.
- Identity, all anchored on BASE: `git diff --exit-code BASE HEAD -- mediaflow scripts config
  pyproject.toml docs 影视媒体资源自动整理系统需求规格说明书.md` must be EMPTY;
  `git diff --numstat BASE HEAD -- mediaflow` must print nothing; `git diff --numstat BASE HEAD` must
  list only `tests/test_configuration_destination_precheck.py` and `TASK.md`.
- No `result` size measurement is required: production is byte-identical to BASE, so the Phase 22.6-M
  measurement (`11049` bytes for the eight-sample worst case, limit `32768`) still stands. Say so
  explicitly instead of re-deriving it.
- Secret scan of this Slice's own diff.

## Non-goals — must not start

- Any production change at all, including "harmless" reformatting, comments, type hints, extracting
  the verdict expression into a helper, or renaming `any_missing`, `outcomes` or `severity`.
- Changing the severity map, adding a verdict value, changing `capability_gap` precedence, run-level
  field order or names, `failures[0]` selection, the collision table, `boundedSetupText`, the Web
  table, its column count, labels or styles; touching `service_api.py`, routes, permissions, HTTP
  statuses, schema markers, tables or migrations.
- Any documentation change. Both CURRENT paragraphs already describe verdict aggregation. The
  still-undocumented items recorded at Phase 22.6-M — the uniform ten-key row shape, and the absence
  of a destination-side truncation ladder (the 32 KiB cap is enforced by raising `ValueError`, with
  76% headroom measured) — are known, non-blocking and NOT this Slice's business.
- Adding, renaming, deleting, splitting or reordering any test other than the two new ones, and any
  change to `tests/test_operator_ui.py` or `tests/test_configuration_destination_activation.py`.
- Closing the other residual proof gaps recorded in 22.6-H-F1 and 22.6-I: run-level field ORDER of
  the single-sample `result` stays unpinned, and no test pins the `YES`/`NO` renders outside the
  determination fields. Both are known and non-blocking.
- Remote SMB/OpenList/S3 destination prechecks, mutation-based capability probing, multiple
  RecognitionTypes or multiple destination Storages per request, known-media duplicate detection,
  attachment prechecks and absolute mounted-path display — all six are recorded in `docs/roadmap.md`
  as deferred out of Phase 22.6 — and any execution or authority change.
- Amending, squashing or rewriting any preserved rejected checkpoint; no push, force push,
  `git reset --hard` or destructive `git clean`.

## Closure Checklist

- [ ] Zero production change: `git diff --numstat BASE HEAD -- mediaflow` prints nothing, and the
      BASE identity diff over `mediaflow scripts config pyproject.toml docs` and the requirements
      specification is EMPTY.
- [ ] `test_multi_sample_all_ready_verdict_is_ready_not_inflated` exists, asserts
      `verdict == "ready"` on a three-sample all-`ready` offline run, and pins every row's
      `projectedOutcome`, `failureCategory`, `message` and `nextAction` by direct subscript.
- [ ] `test_multi_sample_capability_gap_overrides_ready_rows` exists, asserts
      `verdict == "capability_gap"` with `missingStorageCapabilities == ["can_hard_link"]` and
      `requiredByOperation == "hard_link"` while every row is still `projectedOutcome == "ready"`.
- [ ] Both new runs proved read-only: all `guardMutationCalls` `0`, `authorityGranted` `"none"`,
      destination tree snapshot byte-identical before and after.
- [ ] No existing test, helper or assertion was renamed, deleted, weakened, reordered or added to.
- [ ] Full suite `874` `OK (skipped=7)`, focused `60` `OK`.
- [ ] All eight probes ran one at a time with `git checkout --` restores, actual failing test names
      recorded; probes 1-4 failed their named new tests, probes 5-7 reported their real observed
      results without overclaiming, and the control failed nothing.
- [ ] Static, dependency, CLI, wheel, schema-marker, whitespace, FFmpeg, mutation-boundary, Markdown
      link, alist-ignore and secret gates all pass.
- [ ] One coherent commit at the end; no push.
- [ ] Completion Report filled in with actual command output.

## Completion Report

> Fill this in at the checkpoint. Report what actually happened, not what was intended. If any item
> was skipped or failed, say so explicitly.

### Changed Files

### Implemented

### Tests

### Test Results

### Falsification Probes

### Validation Evidence

### Decisions

### Remaining Work

### Risks
