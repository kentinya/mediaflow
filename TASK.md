# Phase 22.6-H-F1 — Prove the Run Verdict Is the Most Severe Sample, Not the First

This Task follows [the authoritative development workflow](docs/development-workflow.md).

```text
Status: READY FOR IMPLEMENTATION
Commit SHA: PENDING
High Audit: PENDING
Rejected checkpoint under correction: d8c2ae04e578955ddbbd29c413f235bf4cf08f42
  (Phase 22.6-H FIX REQUIRED — 2026-08-28 independent High review; preserved as-is)
Preceding closed checkpoint: 5ca1247156e6de4615dff53f5fc8e421bd8bf264
  (Phase 22.6-G PASS / CLOSED — 2026-08-28, accepted through Phase 22.6-G-F1)
Preserved rejected checkpoints: d8c2ae04e578955ddbbd29c413f235bf4cf08f42 (Phase 22.6-H),
  b9cc35e2677a35920042b5695f87b50a80025ef0 (Phase 22.6-G),
  7353b0d22497e6e3e596c93c7052eea34daf27df (Phase 22.6-E),
  90ce13a6c6c39912dd389f71a1189314ff24eb5d (Phase 22.6-A) and
  08dfd4f921728755209b6d52347d28f221121c47 (Phase 22.5-E); never amended, squashed or rewritten
Push gate: SATISFIED — every closed Phase 22.6-A through 22.6-G checkpoint, the preserved rejected
  checkpoints above and the review records through 3ace53c7cdcc3312033f388d8f68d2d7d1a159ae were
  pushed to origin/main on 2026-08-28 under explicit operator authorization, so no accepted
  checkpoint is unpushed. The rejected 22.6-H checkpoint and this correction stay local; a rejected
  checkpoint is never pushed as a closure, and phase-level Phase 22.6 closure still requires the
  Final Closure Audit and a new explicit authorization
Phase: 22.6 Naming / Classification / Organize configuration journey (roadmap section 5)
Slice scope: EVIDENCE ONLY. Supply the missing falsifiable proof that the multi-sample destination
  precheck reports the most severe sample's projected outcome as the run verdict — not the first
  sample's — and that the aggregate verdict is distinguishable from the top-level first-sample
  projection. No production file may change:
  `git diff --exit-code d8c2ae04e578955ddbbd29c413f235bf4cf08f42 HEAD -- mediaflow scripts config
  pyproject.toml` must be empty. Markers stay 10 and 22
```

## Why This Slice Exists

Phase 22.6-H shipped behaviour that looks correct, with one piece of evidence missing.
`_run_multi_destination_precheck` in `mediaflow/application/configuration_objects.py` aggregates the
run verdict as `max(outcomes, key=lambda value: severity[value])`, but the Task's Required Test 1,
`test_multiple_samples_success_most_severe_verdict_and_distinct_rows`, asserts the per-sample
outcomes `["manual_confirmation_required", "ready", "ready"]` — the most severe sample is at index 0.
Replacing that aggregation with `outcomes[0]` leaves the complete offline suite green
(`Ran 859 tests … OK (skipped=7)`), so nothing in the repository distinguishes "report the most
severe sample" from "report the first sample".

That contradicts the Phase 22.6-H Task rule "Every test below must assert, not assume, and must fail
if the behaviour it names is removed", Required Test 1's own parenthetical "prove the aggregation
with a mix, not with three identical outcomes", and the ticked Closure Checklist item "All eleven
Required Tests exist and assert rather than assume".

## User Problem

An operator prechecking several samples of one RecognitionType sees one run verdict next to the
per-sample rows, and checked activation consumes exactly that completed evidence. If the second
sample of a run needs manual confirmation while the first is ready, a run verdict copied from the
first sample would present the run as safe and invite an activation the worst sample does not
support. The line under correction is therefore safety-relevant, and its correctness must be proven
rather than assumed.

## Journey

Unchanged from Phase 22.6-H. Entry point, visible state, available action, success outcome, failure
outcome and recovery path all stay exactly as shipped: this Slice adds test evidence and changes no
operator-visible behaviour.

## Blocking Finding To Fix

1. The most-severe verdict aggregation is not falsifiable. The suite must fail when the shipped
   aggregation is replaced by the first sample's outcome, by the last sample's outcome, or by the
   least severe outcome, and the aggregate verdict must be provably distinct from the top-level
   first-sample projection on the same completed evidence.

## Technical Scope

Files this Slice may change — nothing else:

- `tests/test_configuration_destination_precheck.py` (additive only)
- `TASK.md` (status block and Completion Report)

Explicitly forbidden: any file under `mediaflow/`, `scripts/`, `config/`, `pyproject.toml` and any
file under `docs/`. `docs/progress.md` and `docs/roadmap.md` remain owned by the review role.

Rules:

1. Additive only. `test_multiple_samples_success_most_severe_verdict_and_distinct_rows` and every
   other existing test keeps its current assertions; no assertion may be deleted, weakened, renamed,
   reordered or moved into a helper that changes what it proves.
2. Reuse the module's existing offline harness: temporary directories, Local storages, one
   RecognitionType, no network, no metadata Provider, no Executor, no Task or queue.
3. The new proof must keep asserting zero mutation the way the module already does — guard mutation
   counters all zero and the destination tree snapshot unchanged before and after the run — and must
   assert `authorityGranted == "none"`.
4. Evidence must stay bounded and secret-free: no credential, endpoint, Storage `rootPath`, header,
   cookie, private path or raw exception text in the test, its fixtures, the report or the commit.

## Required Tests

Both tests live in `tests/test_configuration_destination_precheck.py`. Every assertion must fail if
the behaviour it names is removed.

1. `test_multi_sample_verdict_is_most_severe_not_first_or_last_sample` — at least three samples of
   one RecognitionType against one destination Storage, arranged so the most severe projected outcome
   belongs to a sample that is neither the first nor the last requested sample (with three samples
   that means index 1). Assert:
   - evidence `status` is COMPLETED and `failure_category` is `None`;
   - `sampleCount` equals the number of requested samples and `collisions == []`;
   - the full per-sample `projectedOutcome` list, so the ordering of the proof is visible and pinned;
   - `result["verdict"]` equals the most severe of those outcomes;
   - `result["verdict"] != items[0]["projectedOutcome"]` and
     `result["verdict"] != items[-1]["projectedOutcome"]`;
   - the samples resolve to distinct destinations, and the severe sample's row carries its own
     `plannerConflicts` evidence for why it is severe;
   - `authorityGranted == "none"`, all guard mutation counters zero, destination tree unchanged.
2. `test_multi_sample_top_level_keys_describe_the_first_sample` — on completed multi-sample evidence
   whose severe sample is not sample 0, assert that the top-level keys still describe the first
   requested sample while the run verdict does not: top-level destination path equals
   `items[0]["destinationPath"]`, the top-level conflict projection equals
   `items[0]["projectedOutcome"]`, top-level `targetExists` matches sample 0, and the aggregate
   `verdict` differs from the top-level projection. This test may reuse the fixture of test 1 but
   must not replace any of its assertions.

No other test may be added, renamed or changed.

## Required Falsification Probes

Mutate the shipped production tree one edit at a time, run the affected tests, record the actual
failing test names and output, restore with `git checkout -- <file>`, and confirm a clean tree after
each probe. Report every probe, including the control.

1. Replace `max(outcomes, key=lambda value: severity[value])` with `outcomes[0]` — Required Test 1
   must appear among the failures.
2. Replace it with `outcomes[-1]` — Required Test 1 must appear among the failures.
3. Replace it with `min(outcomes, key=lambda value: severity[value])` — Required Test 1 must appear
   among the failures.
4. Compose the result from a later sample instead of the first (for example `resolutions[-1]` where
   the result currently takes `resolutions[0]`) — Required Test 2 must fail.
5. Control probe: a comment-only edit on the aggregation line must fail no test at all.

## Validation

Run every command and report its actual output:

- `.venv/bin/python -m unittest` (full offline suite; the total must rise from 859 by exactly the
  number of added tests, with zero deletions).
- `.venv/bin/python -m unittest tests.test_configuration_destination_precheck
  tests.test_configuration_destination_activation tests.test_operator_ui`.
- `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .`.
- `.venv/bin/python -m compileall -q mediaflow tests` and `.venv/bin/python -m pip check`.
- CLI `config validate` on `config/mediaflow.phase13.2.example.json` and
  `config/strategy.example.json`.
- Wheel build, isolated install and `scripts/wheel_smoke_test.py` (report the schema markers; they
  must stay Configuration 10 and Runtime 22).
- `git diff --check`; FFmpeg/FFprobe audit; business-layer filesystem-mutation audit;
  `git check-ignore config/alist.json` plus empty `git ls-files` and `git diff --cached` for it.
- `git diff --exit-code d8c2ae04e578955ddbbd29c413f235bf4cf08f42 HEAD -- mediaflow scripts config
  pyproject.toml` must be empty, proving the production tree is byte-identical to the rejected
  checkpoint. Do not scope this diff to `docs`: the review-record commit sits between the two
  checkpoints and legitimately changes `docs/progress.md`, `docs/roadmap.md` and `TASK.md`. Instead
  confirm with `git diff --stat d8c2ae04e578955ddbbd29c413f235bf4cf08f42 HEAD` that exactly those
  three files plus `tests/test_configuration_destination_precheck.py` appear.
- Secret scan of this Slice's own diff.

## Documentation

No documentation change is required or permitted. The CURRENT claims added by Phase 22.6-H to
`docs/architecture.md`, `docs/product-experience.md` and `docs/requirements.md` were independently
verified to match shipped behaviour, and this Slice changes no behaviour.

## Non-goals — must not start

- Any production change, including the aggregation line itself, the severity map, the Web
  "First sample destination" heading placement, the post-loop guard-counter recheck, the redundant
  API shape checks, the `plan.target` / `composition.target` duality, the normalized-input selection
  rule and the unreachable defensive assert. All of these were reviewed and either accepted or
  recorded as non-blocking observations for a later Slice; they are not this Slice's business.
- Any change to the activation gate, the failure categories, evidence keys, request or response
  fields, permissions, HTTP statuses, routes, tables, migrations or schema markers.
- Remote SMB/OpenList/S3 destination prechecks, mutation-based capability probing, multiple
  RecognitionTypes or multiple destination Storages per request, known-media duplicate detection,
  attachment prechecks, absolute mounted-path display, and any execution or authority change.
- Amending, squashing or rewriting `d8c2ae04e578955ddbbd29c413f235bf4cf08f42` or any preserved
  rejected checkpoint; no push, force push, `git reset --hard` or destructive `git clean`.

## Closure Checklist

- [ ] This Slice's own commit changes only `tests/test_configuration_destination_precheck.py` and
      `TASK.md`
- [ ] `git diff --exit-code d8c2ae04e578955ddbbd29c413f235bf4cf08f42 HEAD -- mediaflow scripts config
      pyproject.toml` is empty
- [ ] Both Required Tests exist, assert rather than assume, and place the most severe sample neither
      first nor last
- [ ] All five Required Falsification Probes were executed with recorded output: probes 1–3 each fail
      Required Test 1, probe 4 fails Required Test 2, the control probe fails nothing, and the tree is
      clean after each
- [ ] No existing assertion was deleted, weakened, renamed or reordered; zero test deletions
- [ ] Full offline suite green, total risen only by the added tests
- [ ] Configuration marker 10 and Runtime marker 22 unchanged; wheel smoke reports Runtime schema 22
- [ ] No file under `docs/`, `mediaflow/`, `scripts/`, `config/` or `pyproject.toml` changed
- [ ] No credential, endpoint, Storage `rootPath`, header, cookie, private path or raw exception text
      in the tests, evidence, report or commit; `config/alist.json` still untracked, unstaged, ignored
- [ ] Completion Report filled in with the actual commands, actual output, deviations and risks
- [ ] Status set to READY FOR HIGH REVIEW with this Slice's checkpoint SHA recorded; not pushed

## Completion Report

To be filled in by the implementation role: Changed Files, Implemented, Tests, Test Results,
Decisions, Remaining Work, Risks.
