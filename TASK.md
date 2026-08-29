# Phase 22.6-L — Each Failing Destination Precheck Sample Carries Its Own Recovery Action

This Task follows [the authoritative development workflow](docs/development-workflow.md).

```text
Status: READY FOR IMPLEMENTATION
Commit SHA: PENDING
High Audit: PENDING
Preceding closed checkpoint: f2db70b28edb8f753ebed0d3805be7143b521264
  (Phase 22.6-K PASS / CLOSED — 2026-08-29)
Baseline for this Slice: the review-record commit that is `HEAD` when work starts. Its parent is
  f2db70b28edb8f753ebed0d3805be7143b521264 and it changed only `docs/progress.md`,
  `docs/roadmap.md` and `TASK.md`, so no code differs between them. Record that SHA in the
  Completion Report as BASE, use BASE for file-scope commands and f2db70b for code byte-identity
  commands
Preserved rejected checkpoints: d8c2ae04e578955ddbbd29c413f235bf4cf08f42 (Phase 22.6-H),
  b9cc35e2677a35920042b5695f87b50a80025ef0 (Phase 22.6-G),
  7353b0d22497e6e3e596c93c7052eea34daf27df (Phase 22.6-E),
  90ce13a6c6c39912dd389f71a1189314ff24eb5d (Phase 22.6-A) and
  08dfd4f921728755209b6d52347d28f221121c47 (Phase 22.5-E); never amended, squashed or rewritten
Push gate: SATISFIED for Slice closure — Phase 22.6-A through 22.6-G and their review records were
  pushed to origin/main on 2026-08-28 under explicit operator authorization. The 22.6-H through
  22.6-K checkpoints, the preserved rejected 22.6-H checkpoint and every review record after them
  stay local; Slice closure does not require a push, and phase-level Phase 22.6 closure still
  requires the Final Closure Audit plus a new explicit authorization
Phase: 22.6 Naming / Classification / Organize configuration journey (roadmap section 5)
Slice scope: one evidence key plus its rendering. Every failing per-sample destination row must
  carry its own bounded `nextAction`, taken from the existing category-to-action map that already
  produces the run-level action, and the Web rows table must render it as a sixth `Next action`
  column. The sentence set itself must not change, so every existing run-level action stays
  byte-identical. Only `mediaflow/application/configuration_objects.py` (two row builders) and
  `mediaflow/interfaces/operator_ui.py` (the rows-table expression) may change in production; no
  request or response field, aggregation rule, activation gate, failure category, route,
  permission, table or migration may change; markers stay 10 and 22
```

## Why This Slice Exists

Phase 22.6-K made every failing sample's own bounded `message` visible, so the page now explains
*what* each sample got wrong. It still explains *what to do* only once, for one sample.

`_run_multi_destination_precheck` picks the run-level recovery action from the lowest-index failure
only: `index, category, message = failures[0]` and then
`self._destination_sample_next_action(category)`
(`mediaflow/application/configuration_objects.py:2013-2029`). The per-sample rows built by
`_destination_sample_failure_row` (`:2229-2242`) carry `index`, `failureCategory` and `message` — and
no action at all. A run mixing kinds of failure therefore prints one action that resolves one sample
and misdirects the others.

That mix is reachable today, not hypothetical. Composition failures are collected before probing
(`:1405-1425`, `precomposed_rows`) and merged into the same row list (`:1860`,
`rows = list(precomposed_rows)`), while storage-level per-sample failures are produced during probing
(`:1888-1917`) — including `missing_destination_root` and `destination_root_not_directory` raised by
`_probe_destination_sample` against each sample's own resolved MediaLibrary root (`:2086-2096`). The
run-level constraint is a single destination *Storage* (`:1485-1500`,
`multiple_destination_storages`), not a single MediaLibrary, so two samples can legitimately resolve
to two MediaLibrary roots on the same Local Storage, one of which does not exist.

`AGENTS.md` product rule 1 says recovery must state "the explicit action that continues or resolves
the item", and rule 2 says one item must not block the diagnosis and safe recovery of another. One
action per run does not satisfy either for a mixed run.

## User Problem

An operator prechecks a Draft with several samples. Sample 0 fails composition, sample 1 resolves
fine but its MediaLibrary root does not exist. The page names both causes (Phase 22.6-K) but offers a
single action — "correct the destination or conflict policy, then rerun precheck" — which is right for
sample 0 and wrong for sample 1, whose root has to be created out of band or whose
`MediaLibrary.rootPath` has to be corrected. The operator edits policies that were never broken,
reruns, and meets the same second failure with the same misdirection.

## Journey

- User goal: know, per failing sample, the one action that resolves that sample.
- Entry point: Web configuration Draft page, destination precheck section (unchanged).
- Visible state: the per-sample rows table gains a sixth `Next action` column carrying each failing
  row's own bounded action; successful rows and pre-22.6-L evidence render the existing `-` fallback.
- Available action: unchanged — "Run read-only destination precheck", still read-only, still no
  authority granted.
- Success outcome: a completed run reads as today with `-` in the new column.
- Failure outcome: every failing sample shows its own category, its own message and its own action;
  the run-level `Failure category`, `Message` and `Next action` still describe the lowest-index
  failure, unchanged in wording and position.
- Recovery path: an operator can resolve all reported samples from one run instead of discovering the
  next misdirection one rerun later.

## UX Acceptance

1. The per-sample rows table renders exactly six columns, in this order: `Sample`, `Destination`,
   `Projected outcome`, `Failure category`, `Message`, `Next action`.
2. The sixth cell renders `boundedSetupText(item.nextAction)` — each row's own action, never
   `evidence.nextAction`. A row without one renders `-`, so evidence written before this Slice keeps
   rendering.
3. Every action sentence a page can show is one of the sentences that already ship in
   `_destination_sample_next_action`; no sentence is added, reworded or truncated, and the page maps
   nothing itself.
4. The run-level `Failure category`, `Message` and `Next action` fields keep their labels,
   expressions and positions in both branches; the new column is additional.
5. Nothing else moves: the `Per-sample destination rows` heading, the
   `if (Array.isArray(result.items))` guard, the first five columns and their cell expressions, the
   collision table, the `No cross-item destination collision detected.` sentence, the stale sentence,
   the not-ready gate and its sentence, the no-authority warning, the `1-8 samples` control, every
   field list and the Phase 22.6-J `determinationText` call sites stay byte-identical.
6. No absolute path, host path, `rootPath` *value*, credential, endpoint or raw exception text reaches
   the page: the actions are fixed, ASCII, secret-free constants. Two of them name the configuration
   field `MediaLibrary.rootPath` by name, which is guidance, not a disclosed path, and stays as it is.

## Technical Scope

Files this Slice may change — nothing else:

- `mediaflow/application/configuration_objects.py`, and only these two builders:
  - `_destination_sample_failure_row` (`:2229-2242`) gains exactly one key, `"nextAction"`, whose
    value must be `ConfigurationObjectService._destination_sample_next_action(category)` — the same
    helper the run level already calls at `:2023`. Reference it through the class name, the idiom the
    builder already uses for `_bounded_utf8`. Wrapping it in `_bounded_utf8(..., 500)` is permitted
    (an identity for these constants) but not required.
  - `_destination_sample_resolution_row` (`:2244-2257`) gains `"nextAction": None`.
  - `_destination_sample_next_action` (`:2273-2289`) must stay byte-identical: no entry added,
    removed or reworded, and no new category. Composition categories keep falling through to the
    existing default sentence — that is correct, because the row's own `message` already names the
    failing policy, and it is what keeps every existing run-level action byte-identical.
  - No other line of the file may change. `failures[0]`, `precomposed_rows[0]`, the verdict
    aggregation, the severity map, the failure categories and the activation gate stay as they are.
- `mediaflow/interfaces/operator_ui.py`: only the per-sample rows-table expression at `:806-814` —
  `'Next action'` appended to the header list and `boundedSetupText(item.nextAction)` appended to the
  row mapper.
- `tests/test_operator_ui.py`: the changes named below.
- `tests/test_configuration_destination_precheck.py`: exactly two added tests, named below.
- `docs/product-experience.md` and `docs/architecture.md`: the bounded CURRENT refresh named below.
- `TASK.md` (status block, closure checklist and Completion Report).

Explicitly forbidden: `mediaflow/domain/**`, `mediaflow/infrastructure/**`,
`mediaflow/interfaces/service_api.py`, `mediaflow/cli.py`, `scripts/`, `config/`, `pyproject.toml`,
`docs/progress.md` and `docs/roadmap.md` (both review-owned).

Rules:

1. Additive payload only. `result` is persisted as a JSON document validated only against
   `CONFIGURATION_STRATEGY_RESULT_LIMIT = 32 * 1024`
   (`mediaflow/domain/configuration_management.py:32`, `:350-357`), and
   `mediaflow/interfaces/service_api.py:601` returns `evidence.document()` verbatim, so the new row
   key reaches API and Web with no interface change. Report the encoded `result` size for an
   eight-sample run and confirm it stays far below the limit.
2. `git diff BASE HEAD -- mediaflow/application/configuration_objects.py` must contain **zero deleted
   lines** and at most four added lines. That is the mechanical proof that no existing sentence,
   selection rule or category moved.
3. Backward compatibility is part of the Slice: evidence written before it has rows without
   `nextAction`, and the page must render `-` for them through the unchanged `boundedSetupText`. Do
   not migrate, backfill or re-derive stored evidence.
4. Exactly two existing assertions may be replaced, and only these two: the five-column header
   strings in `test_destination_precheck_multi_sample_web_surface_is_falsifiable`
   (`tests/test_operator_ui.py:546-549`) and in
   `test_destination_precheck_per_sample_rows_carry_each_sample_message` (`:691-694`), each extended
   to the six-column list. Every other existing assertion in every test module must still pass
   unchanged; if one does not, the implementation went beyond this Slice.
5. New Web tests must be body-scoped the way `tests/test_operator_ui.py` already does it
   (`_js_function_body` / `_js_braced_body`), because the operator UI is a Python `bytes` literal with
   no JS runtime.
6. The new evidence tests must reuse the existing offline fixtures of
   `tests/test_configuration_destination_precheck.py`, must stay offline (no TMDB, SMB, OpenList, S3),
   and must assert only what the production code actually does.
7. No credential, endpoint, Storage `rootPath`, header, cookie, private path or raw exception text may
   enter the page, the evidence, the tests, the documentation, the report or the commit.

## Required Tests

All three are additive. Every assertion must fail if the behaviour it names is removed.

1. `test_destination_precheck_per_sample_rows_carry_their_own_next_action` in
   `tests/test_configuration_destination_precheck.py` — one offline multi-sample precheck whose rows
   end in at least two *different* mapped situations, for example: sample 0 fails composition (its
   category comes from `_destination_failure_details` (`:2377-2399`) — a policy error code, or
   `invalid_input` — none of which is in the map, so it falls through to the default sentence), sample 1
   resolves to a MediaLibrary whose Storage-relative root does not exist (category
   `missing_destination_root`, which has its own sentence), sample 2 succeeds. Do not hardcode a guessed
   composition category: read it from the row and assert the fall-through. Both samples must resolve to
   the same Storage — a second Storage returns run-level `multiple_destination_storages`
   (`:1485-1500`) — and no two samples may compose the same destination, because a collision returns
   earlier (`:1987-2005`). Assert that both failing rows carry a non-null `nextAction`, that the two
   sentences differ, that each equals
   `ConfigurationObjectService._destination_sample_next_action(row["failureCategory"])`, that the
   successful row's `nextAction` is `None`, that the run-level `next_action` still equals the
   lowest-index failing row's `nextAction`, and that no row's `nextAction` contains any fixture's
   configured `rootPath` value or any absolute path.
2. `test_destination_sample_next_action_sentences_are_bounded_unchanged_constants` in
   `tests/test_configuration_destination_precheck.py` — pin the complete action vocabulary as shipped
   at `f2db70b`: the six mapped categories (`missing_destination_root`,
   `destination_root_not_directory`, `read_only_violation`, `permission_denied`, `unavailable`,
   `timeout`) with their exact sentences, and the default sentence for an unmapped category. Assert
   each sentence is ASCII, non-empty and at most 500 bytes, and contains no `/`, no `\` and no `://`.
   Note that two sentences legitimately name the configuration field `MediaLibrary.rootPath`; that
   literal field name is not a path and must not be forbidden — only real path, endpoint and credential
   values are. Rewording any sentence must fail this test.
3. `test_destination_precheck_per_sample_rows_render_each_sample_next_action` in
   `tests/test_operator_ui.py` — inside the `renderDestinationPrecheck` body, assert that the rows
   header list is exactly
   `['Sample', 'Destination', 'Projected outcome', 'Failure category', 'Message', 'Next action']` in
   that order; slice the rows expression between that header and its closing `])));` and assert that
   it contains `boundedSetupText(item.nextAction)` exactly once, positioned after
   `boundedSetupText(item.message)`, and contains no `evidence.nextAction`; and assert that the
   run-level `field(runList, 'Next action', ...)` and single-sample `field(list, 'Next action', ...)`
   lines both still exist unchanged.

No other test may be added, renamed or changed.

## Required Documentation Refresh

Both CURRENT statements are now incomplete and must describe the shipped behaviour at this
checkpoint. Add at most three sentences each; do not touch either TARGET paragraph, add sections or
restructure.

- `docs/product-experience.md:301-302` currently says each sample keeps "index, Storage-relative
  destination, projected outcome and, when present, its bounded failure category". Extend it to state
  that the row also carries the sample's own bounded message and its own bounded recovery action, that
  undetermined observations render as `NOT DETERMINED` rather than `NO` (Phase 22.6-J), and that the
  run-level summary describes the lowest-index failing sample only.
- `docs/architecture.md` CURRENT destination-precheck paragraph (`:1108-1161`, which stops at Phase
  22.6-H) — state that `result.items[]` carries per-sample `failureCategory`, `message` and
  `nextAction`, that the action comes from the same `_destination_sample_next_action` map as the
  run-level action, and that the Web rows table renders all six columns read-only.

Every sentence must be true at the checkpoint, path-free and secret-free. Quote both final sentences
verbatim in the Completion Report.

## Required Falsification Probes

Mutate the shipped tree one edit at a time, run the affected tests, record the actual failing test
names and output, restore with `git checkout -- <file>`, and confirm a clean tree after each probe.
Report every probe, including the control.

1. Remove `'Next action'` from the rows-table header list — Required Test 3 must fail.
2. Remove the sixth cell from the row mapper — Required Test 3 must fail.
3. Point the sixth cell at `boundedSetupText(evidence.nextAction)` — Required Test 3 must fail,
   proving the column carries the row's own action and not the run-level one.
4. Move `'Next action'` before `'Message'` in the header list — Required Test 3 must fail, proving
   column order is pinned.
5. Make `_destination_sample_failure_row` store `"nextAction": None` — Required Test 1 must fail.
6. Make `_destination_sample_failure_row` store the default sentence for every category, ignoring the
   map — Required Test 1 must fail, proving each row carries the action for its own category.
7. Reword one mapped sentence in `_destination_sample_next_action` (for example drop a word from the
   `missing_destination_root` sentence) — Required Test 2 must fail, proving the vocabulary is pinned
   against silent drift.
8. Control probe: a comment-only edit inside the rows-table block must fail no test.

## Validation

Run every command and report its actual output:

- `.venv/bin/python -m unittest` — the total must be exactly `871` (868 at `f2db70b` plus the three
  Required Tests) with zero deleted tests and zero skips beyond the existing 7.
- `.venv/bin/python -m unittest tests.test_operator_ui
  tests.test_configuration_destination_precheck tests.test_configuration_destination_activation` —
  the focused total must be exactly `57` (54 at `f2db70b` plus three).
- `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .`.
- `.venv/bin/python -m compileall -q mediaflow tests` and `.venv/bin/python -m pip check`.
- CLI `config validate` on `config/mediaflow.phase13.2.example.json` and
  `config/strategy.example.json`.
- Wheel build, isolated install and `scripts/wheel_smoke_test.py` (report the markers; Configuration
  10 and Runtime 22 must be unchanged).
- `git diff --check`; FFmpeg/FFprobe audit; business-layer filesystem-mutation audit;
  `git check-ignore config/alist.json` plus empty `git ls-files` and `git diff --cached` for it;
  Markdown local-link check (two documentation files change this Slice).
- `git diff --exit-code f2db70b28edb8f753ebed0d3805be7143b521264 HEAD -- mediaflow/domain
  mediaflow/infrastructure mediaflow/interfaces/service_api.py mediaflow/cli.py scripts config
  pyproject.toml` must be empty, proving the service boundary, the CLI and the schema are untouched.
- `git diff BASE HEAD -- docs/progress.md docs/roadmap.md` must be empty (both review-owned).
- `git diff BASE HEAD -- mediaflow/application/configuration_objects.py` must show zero deleted lines
  and at most four added lines, all inside the two named row builders.
- `git diff --stat BASE HEAD` must list only `mediaflow/application/configuration_objects.py`,
  `mediaflow/interfaces/operator_ui.py`, `tests/test_operator_ui.py`,
  `tests/test_configuration_destination_precheck.py`, `docs/product-experience.md`,
  `docs/architecture.md` and `TASK.md`.
- `git diff BASE HEAD -- mediaflow/interfaces/operator_ui.py` must contain exactly one hunk, in the
  rows-table expression.
- Report the encoded `result` size of an eight-sample all-failing precheck (the same measurement the
  earlier Slices reported) and confirm it stays far below
  `CONFIGURATION_STRATEGY_RESULT_LIMIT = 32 * 1024`. One extra bounded sentence per failing row must
  not move the document near its persistence limit.
- Secret scan of this Slice's own diff.

## Non-goals — must not start

- Adding, rewording, splitting or extending any sentence in `_destination_sample_next_action`, or
  adding categories to it. Per-category differentiation beyond what already ships is a later decision,
  not this Slice; two composition failures legitimately share one action.
- Deriving or mapping actions in JavaScript, or letting the page truncate, style, icon, link, sort,
  filter or group the new column. The `-` fallback of `boundedSetupText` stays as it is.
- Any change to `failures[0]` selection, `precomposed_rows[0]`, verdict aggregation, the severity map,
  failure categories, the activation gate, request or response fields, permissions, HTTP statuses,
  routes, tables, migrations or schema markers.
- Adding `nextAction` anywhere else: not to the collision rows, not to run-level fields, not to a new
  API field, not to the single-sample field list.
- Backfilling, migrating or re-deriving evidence written before this Slice.
- Closing the residual proof gaps recorded earlier: no multi-sample all-`ready` run asserts
  `verdict == "ready"`, single-sample field order is unpinned, no test compares the two branches' field
  lists, and no test pins the `YES`/`NO` renders outside the determination fields. All four are known,
  non-blocking, and not this Slice's business.
- Remote SMB/OpenList/S3 destination prechecks, mutation-based capability probing, multiple
  RecognitionTypes or multiple destination Storages per request, known-media duplicate detection,
  attachment prechecks and absolute mounted-path display — all six are recorded in `docs/roadmap.md`
  as deferred out of Phase 22.6 — and any execution or authority change.
- Amending, squashing or rewriting any preserved rejected checkpoint; no push, force push,
  `git reset --hard` or destructive `git clean`.

## Closure Checklist

- [ ] `_destination_sample_failure_row` stores `nextAction` from
      `_destination_sample_next_action(category)` for the row's own category.
- [ ] `_destination_sample_resolution_row` stores `"nextAction": None`.
- [ ] `_destination_sample_next_action` is byte-identical to `f2db70b`.
- [ ] `configuration_objects.py` shows zero deleted lines and at most four added lines.
- [ ] The rows table renders six columns, `'Next action'` sixth, from
      `boundedSetupText(item.nextAction)`.
- [ ] Only the two permitted header-assertion sites in `tests/test_operator_ui.py` were edited.
- [ ] Three Required Tests exist, are named as specified, and fail for the mutations named in the
      probes.
- [ ] All eight probes were run one at a time on the shipped tree, with actual failing test names, and
      the control probe failed nothing.
- [ ] Full suite `871`, focused `57`, both green.
- [ ] Static, dependency, CLI, wheel, schema-marker, whitespace, FFmpeg, mutation-boundary, Markdown
      link, alist-ignore and secret gates all pass.
- [ ] `docs/product-experience.md` and `docs/architecture.md` CURRENT text describes the six-column
      surface in at most three sentences each; no TARGET section changed.
- [ ] `docs/progress.md`, `docs/roadmap.md` and every forbidden path are untouched.
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

| # | Mutation | Module run | Actual failing tests | Expected |
| - | -------- | ---------- | -------------------- | -------- |

### Validation Evidence

### Decisions

### Remaining Work

### Risks
