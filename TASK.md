# Phase 22.6-H — One Precheck, Several Samples, No Silent Destination Collision

This Task follows [the authoritative development workflow](docs/development-workflow.md).

```text
Status: READY FOR IMPLEMENTATION
Commit SHA: PENDING
High Audit: PENDING
Preceding closed checkpoint: 5ca1247156e6de4615dff53f5fc8e421bd8bf264
  (Phase 22.6-G PASS / CLOSED — 2026-08-28, accepted through Phase 22.6-G-F1)
Preserved rejected checkpoints: b9cc35e2677a35920042b5695f87b50a80025ef0 (Phase 22.6-G),
  7353b0d22497e6e3e596c93c7052eea34daf27df (Phase 22.6-E),
  90ce13a6c6c39912dd389f71a1189314ff24eb5d (Phase 22.6-A) and
  08dfd4f921728755209b6d52347d28f221121c47 (Phase 22.5-E); never amended, squashed or rewritten
Push gate: SATISFIED — every closed Phase 22.6-A through 22.6-G checkpoint, the preserved rejected
  checkpoints above and the review records through 3ace53c7cdcc3312033f388d8f68d2d7d1a159ae were
  pushed to origin/main on 2026-08-28 under explicit operator authorization, so no accepted
  checkpoint is unpushed. This Slice's own checkpoint stays local until its closure and a new
  explicit authorization; phase-level Phase 22.6 closure still requires the Final Closure Audit
Phase: 22.6 Naming / Classification / Organize configuration journey (roadmap section 5)
Slice scope: extend the existing read-only Local destination precheck from one sample to a bounded
  list of up to 8 samples under one RecognitionType, keep every item's state, outcome and recovery
  independent, and detect cross-item destination collisions with the production Planner's
  claimed-destination rule. Local-only, read-only, zero mutation, no new endpoint, permission,
  evidence table or schema marker. `require_current_destination_precheck` must stay byte-identical
  to 5ca1247156e6de4615dff53f5fc8e421bd8bf264, and the markers must stay 10 and 22
```

## Why This Slice Exists

Phase 22.6-E through 22.6-G made a single composed destination provable before activation: one
RecognitionType, one sample, one Storage-relative destination, a conflict projection against what
already exists on disk, a declared-versus-required capability comparison, and a Web control that
refuses checked activation with a bounded sentence when that evidence is missing, stale, failed or
reports a capability gap.

A configuration that is safe for one file can still be unsafe for a library. When a NamingPolicy
omits a distinguishing variable — no resolution, no version, no episode — two different source files
compose the *same* destination. Nothing in the current precheck can see this: it composes one
destination, finds nothing at that path, and reports `ready`. The operator then activates a
configuration that provably cannot organize two distinct inputs to two distinct destinations, and
the collision first becomes visible during execution, where the configured ConflictStrategy silently
skips an item, invents a renamed path, or — under Overwrite — replaces media the operator never
intended to lose. That is exactly the outcome the safety rules forbid.

The production Planner already answers this question. `OrganizePlanner.plan` accepts
`claimed_destinations` and emits `ConflictType.TARGET_COLLISION` when a target is already claimed by
a different source; the precheck passes `claimed_destinations=None` today
(`mediaflow/application/configuration_objects.py:1603`). This Slice supplies it from several samples
in one exact-revision run, so a collision is discovered while nothing has been touched and while the
configuration is still a Draft.

## User Problem

An operator preparing a revision for checked activation cannot tell whether the configured
NamingPolicy and ClassificationPolicy keep distinct inputs distinct. The precheck proves one
destination; the library holds thousands. There is no offline, zero-mutation way to ask "do these
representative files land in different places?", and no bounded explanation of what to change when
they do not.

## User Journey

- User goal: before checked activation, prove that this exact revision composes distinct
  destinations for several representative inputs, and see any collision together with the change
  that resolves it.
- Entry point: unchanged — the destination-precheck section of the Web revision detail, and
  `POST /api/v1/configuration/revisions/{revisionId}/destination-precheck` with the existing
  `MANAGE_CONFIGURATION` permission.
- Visible state: the precheck section states how many samples the stored evidence covers, keeps the
  existing single-destination block (explicitly labelled as the first sample when more than one was
  requested), lists every sample's own composed destination and projected outcome, and states either
  the detected cross-item collisions or, explicitly, that none were detected.
- Available action: the operator supplies one sample object or a JSON array of up to eight sample
  objects for one RecognitionType and runs the same read-only precheck.
- Success outcome: `completed` evidence bound to the exact version and digest, one row per sample,
  no collision, and checked activation still available.
- Failure outcome: a bounded failure category with an explicit recovery action — including the two
  new categories `duplicate_destination` and `multiple_destination_storages` — and checked
  activation refused by the unchanged gate.
- Recovery path: the evidence names which samples collided and at which destination, so the operator
  corrects the NamingPolicy or ClassificationPolicy in the Draft and reruns the precheck. Nothing
  was mutated, the prior Active configuration is untouched, and rerunning is always safe.

## User-visible Outcome

1. The precheck answers a library-shaped question instead of a single-file question, without
   touching a byte on disk and without granting any authority.
2. A configuration that maps two distinct inputs to one destination cannot reach checked activation
   silently: the evidence is `failed` with category `duplicate_destination`, and the existing Web
   sentence and server refusal repeat that category with the recovery action.
3. Every sample keeps its own destination, projected outcome and failure; one sample's failure never
   hides, overwrites or blocks the diagnosis of another.

## Failure and Recovery

| Situation | Visible outcome | Recovery |
| --- | --- | --- |
| Two or more samples compose the same destination | evidence `failed`, category `duplicate_destination`, collision rows naming the destination and the colliding sample indexes, every sample row retained | add a distinguishing naming variable or correct the naming/classification policy so distinct inputs compose distinct destinations, then rerun the precheck |
| Samples route to MediaLibraries on different destination Storages | evidence `failed`, category `multiple_destination_storages`, bounded message naming only Storage `id` and `type` | narrow the samples to one destination Storage and precheck each destination Storage separately, then rerun |
| One sample fails to compose (policy, naming, classification or path failure) | evidence `failed` with that sample's existing bounded category, that sample's row carrying its own bounded message, and the other samples' rows retained | fix the composition for the named sample in this Draft, rerun destination preview, then rerun the precheck |
| More than eight samples, an empty array, a non-object element, or both `sample` and `samples` | bounded HTTP 400 `invalid_request`, no evidence written, any previous evidence preserved | send one sample object or an array of one to eight sample objects, then rerun |
| Unchanged Phase 22.6-E/F/G situations (missing root, non-directory root, non-Local Storage, capacity, timeout, capability gap, stale evidence) | unchanged bounded categories, verdicts and sentences | unchanged recovery actions |

## UX Acceptance Criteria

1. The Web sample control accepts either one sample object or a JSON array of up to eight samples,
   its label says so, and a bounded helper line explains that an array detects cross-item
   destination collisions before activation.
2. The Web precheck section shows the sample count, and when more than one sample was requested the
   existing single-destination block is explicitly labelled as describing the first sample.
3. The Web precheck section renders one row per sample with that sample's index, Storage-relative
   destination, projected outcome and — when present — its bounded failure category.
4. The Web precheck section renders a cross-item collision section that either lists each colliding
   destination with its colliding sample indexes, or states explicitly that no cross-item
   destination collision was detected. A bare `-` is not an acceptable rendering of this safety
   signal.
5. A `duplicate_destination` or `multiple_destination_storages` evidence blocks checked activation
   through the existing predicate, and the existing blocked sentence repeats the bounded category
   and the stored recovery action.
6. Every new or changed Web string is proven by a body-scoped operator-UI assertion that fails when
   that line is deleted, in the Phase 22.6-G-F1 style, and the failing test is named in the
   Completion Report.
7. No new secret surface: destination values stay Storage-relative and bounded, and no credential,
   endpoint, `rootPath`, header, cookie, private path or raw exception text reaches Web, API,
   evidence, logs or tests.
8. The single-sample journey is unchanged for an operator who never supplies an array: same request,
   same evidence keys, same sentences.

## Technical Scope

Exactly these files may change:

- `mediaflow/application/configuration_objects.py`
  - `destination_precheck(...)` accepts `samples: Sequence[Mapping[str, object]] | None = None`
    alongside the existing `sample`; exactly one of the two must be supplied, and the `sample` path
    keeps byte-identical behaviour and evidence for the single-sample case.
  - Per-sample validation reuses `_validate_destination_request` with a label naming the index
    (`destination precheck sample[<index>]`); the bound is one to eight samples.
  - One RecognitionType applies to every sample in the request.
  - Each sample is composed through the existing `_resolve_destination`, in request order, with its
    own normalized input and its own bounded failure category and message on failure. A failing
    sample makes the run `failed` with that sample's category while every other sample's row is
    retained.
  - All samples must resolve to the same destination Storage. Otherwise the run is `failed` with
    category `multiple_destination_storages`, a bounded message naming only Storage `id` and `type`,
    and a bounded recovery action. The existing `unsupported_storage_type` and
    `invalid_configuration` checks stay ahead of any probe.
  - `_run_destination_precheck` keeps one capacity lease, one `_ReadOnlyDestinationStorage` guard,
    one worker submission and one overall timeout for the whole run, and calls the production
    `OrganizePlanner().plan(...)` once per sample with `claimed_destinations` accumulating
    `{composed target: synthetic source}` from the samples already planned, plus a distinct bounded
    synthetic source per sample (`destination-precheck-source-<index>.mkv`). Distinct synthetic
    sources are what make `ConflictType.TARGET_COLLISION` observable.
  - New `result` keys: `sampleCount`; `items`, one bounded row per sample in request order with
    `index`, `relativeDestination`, `destinationPath`, `targetExists`, `plannerConflicts`,
    `projectedOutcome`, `proposedRelativeDestination`, `failureCategory` and `message`; and
    `collisions`, one bounded row per destination claimed by more than one sample with
    `destinationPath` and `itemIndexes`. Existing top-level keys keep their meaning and describe the
    first requested sample.
  - Any collision makes the run `failed` with category `duplicate_destination`, a bounded message
    and a bounded recovery action, while `items` and `collisions` are retained in the evidence.
  - On a completed run the verdict rule is unchanged for capability gaps (`capability_gap` when any
    required capability is missing); otherwise the verdict is the most severe per-sample projected
    outcome in exactly this order, most severe first: `manual_confirmation_required`,
    `overwrite_requires_confirmation`, `rename`, `skip`, `ready`. Every sample keeps its own
    `projectedOutcome`.
- `mediaflow/interfaces/service_api.py` — the destination-precheck route accepts exactly two request
  shapes, `{expectedVersion, expectedDigest, recognitionType, sample}` and
  `{expectedVersion, expectedDigest, recognitionType, samples}`; both or neither, a non-list
  `samples`, an empty array, more than eight entries, or a non-object element is a bounded
  `ValueError`. No new route, status code or permission.
- `mediaflow/interfaces/operator_ui.py` — sample control label and bounded helper line, array/object
  dispatch onto `samples`/`sample`, sample count, first-sample labelling, per-sample rows and the
  collision section. The activation predicate
  `destinationPrecheckActivationRequirement` and its four blocked branches must not change.
- `tests/test_configuration_destination_precheck.py`, `tests/test_operator_ui.py` and
  `tests/test_configuration_destination_activation.py` — additive tests only; no existing assertion
  may be deleted or weakened.
- `docs/architecture.md`, `docs/product-experience.md`, `docs/requirements.md` — CURRENT text for
  this behaviour only, moving Local cross-item collision detection from TARGET to CURRENT and
  leaving remote prechecks, mutation probing, attachment prechecks, absolute mounted-path display
  and execution as TARGET.
- `TASK.md` — status line and Completion Report.

No new file, module, dependency, endpoint, permission, evidence table, migration or schema marker.
`docs/progress.md` and `docs/roadmap.md` remain High-only. The root Chinese requirements
specification is not edited.

## Non-goals

Do not start any of the following; they remain TARGET for later Slices:

- remote SMB/OpenList/S3 destination prechecks, or any change that makes a non-Local destination
  Storage prechecked;
- mutation-based capability probing, or any relaxation of "an unsupported capability is a failure
  with no fallback";
- more than one RecognitionType per precheck request, or samples routed to more than one destination
  Storage in one request;
- `ConflictType.DUPLICATE_MEDIA` / known-media detection, media identity lookup, or any metadata
  provider call;
- attachment, subtitle, NFO or sidecar prechecks;
- absolute or mounted destination path display;
- changing which verdicts block checked activation, the gate order, or
  `require_current_destination_precheck` in any way;
- per-sample concurrency, a second capacity lease, or a per-sample timeout;
- narrowing the document-level applicability rule to the routed destination;
- any execution, authority, overwrite or delete change; any Task, Job or Executor construction;
- schema marker changes, new evidence tables or migrations.

## Safety and Architecture Invariants

1. Every probe goes through the existing `_ReadOnlyDestinationStorage` guard; all mutation counters
   stay zero across a multi-sample run and a counted mutation still raises the read-only violation.
2. The precheck constructs no Provider, Executor, Task, Job or execution authority, and the ten
   Runtime tables stay empty on both the success and the failure paths.
3. `authorityGranted` stays `none`; no overwrite, delete or execute authority is granted or implied.
4. Composition, path safety and conflict projection stay in the production
   `OrganizePlanner`/`ConflictResolver`/naming/classification code; the precheck adds no second
   implementation of destination composition or conflict semantics.
5. All evidence values stay bounded and secret-free, and destination paths stay Storage-relative.
6. RecognitionType identity is preserved: a sample recognized as C stays C in every row.
7. `CONFIGURATION_SCHEMA_VERSION` stays 10 and `RUNTIME_SCHEMA_VERSION` stays 22.
8. `config/alist.json` stays untracked, unstaged and ignored; no FFmpeg/FFprobe dependency or call
   is added.

## Required Tests

Every test below must assert, not assume, and must fail if the behaviour it names is removed.

1. Multi-sample success: three distinct samples produce `completed` evidence with `sampleCount: 3`,
   three `items` rows with distinct destinations and their own projected outcomes, `collisions`
   empty, and an aggregated verdict equal to the most severe per-sample outcome (prove the
   aggregation with a mix, not with three identical outcomes).
2. Cross-item collision: two samples composing the same destination produce `failed` evidence with
   category `duplicate_destination`, a `collisions` row naming the destination and both sample
   indexes, all `items` rows retained, and a bounded recovery action; `activate_checked` is then
   refused with that category and next action through the unchanged gate.
3. Per-sample isolation: when the second of three samples fails to compose, the run is `failed` with
   that sample's bounded category, that sample's row carries its own bounded message, and the first
   and third rows keep their own observations.
4. Same-Storage restriction: samples routed by ClassificationPolicy to MediaLibraries on different
   Storages produce `failed` with category `multiple_destination_storages`, a bounded message and
   recovery action, and no value beyond Storage `id` and `type` in the evidence.
5. Single-sample backward compatibility: the existing single-sample request produces the same
   top-level result keys, verdict, message and next action as before, plus `sampleCount: 1`, one
   `items` row and an empty `collisions`.
6. Zero mutation and no construction across a multi-sample run: every guard mutation counter is
   zero, `authorityGranted` is `none`, the Runtime tables are empty, and Provider/Executor doubles
   that raise on use are never called.
7. Request bounds: nine samples, an empty array, a non-list `samples`, both `sample` and `samples`,
   neither, and a non-object element are each a bounded HTTP 400 that writes no evidence and leaves
   previously stored evidence unchanged.
8. Web parity and falsifiability: the Web sends `samples` for an array and `sample` for an object,
   and each new Web string — the control label, the helper line, the sample count, the first-sample
   label, the per-sample rows and both collision-section branches including the explicit
   "no cross-item destination collision detected" line — is proven by a body-scoped operator-UI
   assertion that fails when the line is deleted.
9. Gate unchanged: `require_current_destination_precheck` is byte-identical to
   `5ca1247156e6de4615dff53f5fc8e421bd8bf264` (prove it in the Completion Report with a
   path-scoped diff), and both new categories are refused by its existing `failed` branch.
10. Stored-evidence compatibility: an evidence row written without `sampleCount`, `items` or
    `collisions` still renders in the Web section and still satisfies the activation gate, so a
    database written by the previous build is not broken.
11. Regression: the complete offline suite plus the Phase 22.6-D/E/F/G suites stay green with zero
    deletions, markers 10 and 22 are asserted, and RecognitionType C identity regressions still
    pass.

## Required Falsification Probes

Run each probe, record the named failing test, restore the line, and confirm a clean tree:

1. Pass `claimed_destinations=None` again — Required Test 2 must fail.
2. Use one identical synthetic source for every sample — Required Test 2 must fail.
3. Remove the same-destination-Storage check — Required Test 4 must fail.
4. Let a failing sample replace the other samples' rows instead of keeping them — Required Test 3
   must fail.
5. Delete the explicit "no cross-item destination collision detected" Web line — Required Test 8
   must fail.
6. Delete the per-sample rows Web line — Required Test 8 must fail.
7. Raise the sample bound above eight — Required Test 7 must fail.

## Validation

Run and report all of it:

- `.venv/bin/python -m unittest` (complete offline suite; report the count and compare with 850).
- The focused modules: `tests.test_configuration_destination_precheck`,
  `tests.test_configuration_destination_activation`, `tests.test_operator_ui`,
  `tests.test_configuration_destination`.
- `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .`.
- `.venv/bin/python -m compileall -q mediaflow tests` and `.venv/bin/python -m pip check`.
- CLI `config validate` on `config/mediaflow.phase13.2.example.json` and
  `config/strategy.example.json`.
- Wheel build, isolated install and `scripts/wheel_smoke_test.py` (report the schema markers).
- `git diff --check`; FFmpeg/FFprobe audit; business-layer filesystem-mutation audit;
  `git check-ignore config/alist.json` plus empty `git ls-files` and `git diff --cached` for it.
- Path-scoped byte-identity diff proving `require_current_destination_precheck` is unchanged.

## Documentation

Update only the CURRENT text this Slice makes true:

- `docs/architecture.md`: the destination precheck now accepts one RecognitionType with one to eight
  samples, composes each through the same production path, detects cross-item `TARGET_COLLISION`
  through `claimed_destinations`, keeps per-sample state, and remains Local-only, read-only and
  zero-mutation with markers 10 and 22.
- `docs/product-experience.md`: the journey step, the per-sample independent state and the two new
  bounded failure/recovery rows.
- `docs/requirements.md`: move Local cross-item collision detection from TARGET to CURRENT in the
  Phase 22.6 paragraph, keeping remote prechecks, mutation probing, attachment prechecks, absolute
  mounted-path display and execution as TARGET.

No CURRENT claim may describe behaviour this Slice does not ship.

## Closure Checklist

- [ ] Multi-sample composition, per-sample rows, collision detection and both new bounded categories
      are implemented in the application layer and reach the API and the Web.
- [ ] Every sample keeps independent state, outcome and recovery; no sample hides another.
- [ ] `require_current_destination_precheck` is byte-identical, and both new categories are refused
      by its existing failed branch.
- [ ] Single-sample requests are unchanged, and evidence written by the previous build still renders
      and still gates.
- [ ] All eleven Required Tests exist and assert rather than assume; every new Web line is
      falsifiable and its failing test is named in the Completion Report.
- [ ] All seven falsification probes were run, each failed a named test, each was restored, and the
      tree was clean afterwards.
- [ ] The guard counted zero mutations; no Provider, Executor, Task, Job or authority was
      constructed; Runtime tables stayed empty; `authorityGranted` stayed `none`.
- [ ] Markers stay 10 and 22; no migration, new table, new endpoint or new permission was added.
- [ ] The complete offline suite, lint, format, compileall, `pip check`, both example validations
      and the wheel smoke run pass, with no test deleted and no count decrease.
- [ ] Documentation CURRENT claims match the shipped behaviour; `docs/progress.md` and
      `docs/roadmap.md` were not touched.
- [ ] Private runtime configuration remains ignored and untracked; no secret is staged or committed.
- [ ] One coherent, buildable, reviewable commit is created on top of
      `5ca1247156e6de4615dff53f5fc8e421bd8bf264`, which is never amended, squashed or rewritten.
- [ ] The Completion Report is written into this file and the Slice is reported as
      READY FOR HIGH REVIEW without declaring Phase closure.

## Completion Report

Fill in before requesting review, with actual commands and actual results:

### Changed Files

### Implemented

### Assertions Added and Shipped Lines They Guard

### Tests and Test Results

### Falsification Probes

| Probe | Temporary change | Failing test and assertion |
| --- | --- | --- |

### Decisions

### Remaining Work

### Risks, Assumptions and Newly Discovered Issues
