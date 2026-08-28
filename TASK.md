# Phase 22.6-E-F1 — Destination Precheck Required-Test Evidence and Outcome Correction

This Task follows [the authoritative development workflow](docs/development-workflow.md).

```text
Status: NOT STARTED
Commit SHA: PENDING
High Audit: PENDING
Rejected checkpoint under correction: 7353b0d22497e6e3e596c93c7052eea34daf27df
  (Phase 22.6-E FIX REQUIRED — 2026-08-28; preserved, never amended, squashed or rewritten)
Preceding closed checkpoint: c7ec192b3b20f236cca5a70ed59cad43e0851242
  (Phase 22.6-D PASS / CLOSED — 2026-08-28)
Earlier preserved rejected checkpoints: 90ce13a6c6c39912dd389f71a1189314ff24eb5d (Phase 22.6-A) and
  08dfd4f921728755209b6d52347d28f221121c47 (Phase 22.5-E); never amended, squashed or rewritten
Push gate: NOT BLOCKING — Slice closure does not require a push; the closed 22.6-D checkpoint, the
  rejected 22.6-E checkpoint and their docs records are not in origin/main, and the phase-level
  Phase 22.6 closure requires an explicitly authorized push
Phase: 22.6 Naming / Classification / Organize configuration journey (roadmap section 5)
Correction scope: evidence only, plus the minimal production change that removes one documented but
  unreachable projected conflict outcome so implementation, tests and documentation agree
```

## User Problem

The Phase 22.6-E checkpoint ships a working read-only destination precheck. Independent review
verified the behaviour it promises: the destination Storage adapter is built from the unmodified
revision document, its declared capabilities are read before wrapping, every probe runs inside a
`ReadOnlyStorageGuard` subclass whose seven mutation counters are asserted zero, and the production
`OrganizePlanner.plan` and `ConflictResolver.apply_configured` are reused per configured
ConflictStrategy. None of that is in question here.

What is missing is proof of four things the Task itself required, so today's correct behaviour is
undefended and one documented outcome cannot happen at all:

1. Required Test 10 demanded that "creates no Task, Job, queue entry, plan record or execution
   authority, constructs no Provider client or Executor" be "asserted, not assumed". No test in
   `tests/test_configuration_destination_precheck.py` references `MetadataProviderRegistry`,
   `OrganizerExecutor`, or any Task/Job/queue state; the only injected doubles cover
   `RuntimeConfiguration.create_storages` on composition-failure and `unsupported_storage_type`
   paths. Phase 22.6-D proved the same class of claim with four injected `AssertionError` doubles in
   `tests/test_configuration_destination.py`, so the standard already exists in this repository. A
   later Slice can add a Provider client or an Executor construction to this path with every gate
   green.
2. Required Test 4 enumerated `relativeDestination` and `destinationPath` among the fields that "are
   all asserted", and no test asserts either. These two keys are the operator's answer to "where
   would this file go", and `renderDestinationPrecheck` in `mediaflow/interfaces/operator_ui.py`
   reads `result.destinationPath` directly and routes a falsy value into the red
   "Destination is not ready" banner. A swapped or misspelled key would change the Web verdict
   while the whole suite stays green.
3. Required Test 4 also demanded "both a fully missing subtree and a partially existing subtree".
   The fully missing case is executed — in the capability-gap and Storage-error tests only the
   MediaLibrary root exists — but neither test asserts `deepestExistingAncestor` or
   `directoriesToCreate`. The multi-entry "directories that would be created" list the operator
   reads before activating is unproven.
4. Required Test 5 ended "An unsafe composition yields `invalid`", and `docs/progress.md` recorded
   `invalid` among the reported projected outcomes. That branch cannot be reached:
   `_resolve_destination` raises the bounded `unsafe_destination` failure whenever
   `compose_destination` reports an unsafe composition, before any Storage adapter is constructed,
   and `OrganizePlanner.plan` derives `ConflictType.INVALID_DESTINATION` from that same
   `composition.safe` check on the same inputs. The earlier refusal is the safer behaviour and is
   already asserted, so the projection must stop advertising an outcome no input can produce.

## User Journey

Unchanged from Phase 22.6-E; this Task only makes the already-shipped journey provable and stops it
advertising an unreachable outcome:

```text
Configuration → open a Draft revision → the composed destination preview already shows the exact
   Storage-relative path this revision produces
→ run the read-only destination precheck for the same RecognitionType and sample
→ read, bound to the exact revision: which destination Storage was probed and that it is Local,
   whether the MediaLibrary root exists and is a directory, which ancestor directories already
   exist and which would have to be created, whether the composed target already exists, what the
   configured ConflictStrategy would do about it (including the concrete rename candidate), and
   whether the destination Storage actually declares the capability the OrganizePolicy requires
→ if something is missing, unsupported, or would block, correct that object or path in the same
   Draft → rerun the precheck → Validate and activate
```

No new entry point, request field, permission, evidence key, state, or schema marker is introduced.

## User-visible Outcome

Operator-visible behaviour stays identical to `7353b0d22497e6e3e596c93c7052eea34daf27df` except that
the projected conflict outcome list contains only outcomes an input can actually produce. What
changes is durable protection of the shipped behaviour:

- the composed `relativeDestination` and `destinationPath` the operator reads, and the Web field
  that renders the destination path, are provably the composed values Phase 22.6-D accepted, so a
  renamed or swapped evidence key fails the suite instead of silently flipping the Web banner to
  "Destination is not ready";
- the "directories that would be created" list is proven for a fully missing destination subtree as
  well as a partially existing one, so the operator's pre-activation answer is defended in both
  shapes;
- the precheck's zero-authority promise is asserted: no Provider client, no Executor, no Task, Job,
  queue entry or execution authority is constructed on this path, and a future edit that introduces
  one fails immediately;
- an unsafe composition keeps its single documented answer — the bounded `unsafe_destination`
  failure, refused before any Storage adapter exists — and no evidence advertises a projected
  `invalid` outcome that cannot occur.

## Failure and Recovery

| Failure class | Visible state | Durable state / side effects | Retry safe | Recovery | If recovery also fails |
|---|---|---|---|---|---|
| Unsafe composed destination | Failed precheck evidence with the bounded `unsafe_destination` category and the offending object named | Revision document, version, digest and all other evidence rows unchanged; no Storage adapter constructed, no probe performed | Yes | Correct the NamingPolicy, ClassificationPolicy or MediaLibrary rootPath in the same Draft, then rerun the precheck | The revision stays Draft and editable; the previous current evidence stays inspectable and attributed to its exact revision |
| Planner defensively reports an invalid destination | Failed precheck evidence in the same bounded category, never a `completed` ready or conflict verdict | Nothing created or mutated; guard mutation counters remain zero | Yes | Fix the destination composition in the Draft and rerun; the message states which object to correct | The precheck keeps refusing; activation is not reached with an unsafe destination |
| A future edit constructs a Provider client, Executor, Task, Job or queue entry on this path | Focused test fails naming the forbidden construction | No product change; nothing ships with hidden execution authority | Yes | Remove the construction from the precheck path and rerun the focused test | The suite keeps failing; the read-only precheck cannot ship with execute authority |
| A future edit renames or drops a composed evidence field or the create list | Focused test fails on the exact expected composed values or the ordered create list | No product change; the Web destination-path field cannot silently go falsy | Yes | Restore the evidence key or the create-list computation and rerun | The suite keeps failing; the Web section cannot ship reading a missing key |

Retry alone is never the recovery text: each row states what is durable, what is safe to repeat, and
the single explicit action that continues.

## UX Acceptance Criteria

- [ ] A focused test asserts the exact composed `relativeDestination` and `destinationPath` returned
      by a successful precheck, equal to the values Phase 22.6-D already accepted for the same
      revision and sample, with `destinationPath` asserted to start with the MediaLibrary
      `rootPath`.
- [ ] A body-scoped operator-UI assertion proves the rendered destination-path field inside
      `renderDestinationPrecheck` reads `result.destinationPath`, so the red
      "Destination is not ready" banner cannot be driven by a renamed key. If the existing focused
      UI test already asserts this inside that function body, state that and do not duplicate it.
- [ ] A focused test with only the MediaLibrary root existing asserts `deepestExistingAncestor` is
      that root, asserts the complete ordered `directoriesToCreate` list including both missing
      levels, and asserts `targetExists` is false. The existing partial-ancestor assertions stay.
- [ ] A focused test proves the precheck constructs no Provider client and no Executor and creates
      no Task, Job, queue entry or execution authority, for a successful run and for at least one
      failure category, using injected `AssertionError` doubles the way
      `tests/test_configuration_destination.py` does. The production `OrganizePlanner` and
      `ConflictResolver` are deliberately excluded from those doubles because this Slice must reuse
      them; the test states that distinction.
- [ ] `authorityGranted` stays `none`, the seven guard mutation counters stay asserted zero, and the
      destination tree is asserted byte-identical in the new tests.
- [ ] No evidence document reports a projected conflict outcome that no input can produce; an unsafe
      composition has exactly one documented answer and it is asserted.
- [ ] No new request field, evidence key, permission, API status, activation semantic, or schema
      marker is introduced; configuration marker stays 10 and the Runtime marker stays 22.

Batch per-item independence does not apply: the precheck evaluates one RecognitionType and one
sample per request, and this Task adds no batch surface.

## Technical Scope

Evidence first, with one bounded production change:

```text
tests/test_configuration_destination_precheck.py → the four missing Required Test proofs
tests/test_operator_ui.py                        → body-scoped destination-path proof if absent
mediaflow/application/configuration_objects.py   → remove the unreachable `invalid` projection only
docs/*                                           → correction record and accurate CURRENT claims
```

- Add the non-construction proof with injected `AssertionError` doubles for the Provider registry
  and the Executor on the module path that `mediaflow/application/configuration_objects.py` actually
  resolves, plus an assertion that no Task/Job/queue/plan/execution row exists after the run (an
  absent runtime database, or empty task and job tables where one is already present). Cover a
  success path and at least one failure path.
- Assert the composed evidence fields against the Phase 22.6-D accepted composed values rather than
  recomputing them in the test, so the two Slices cannot drift apart silently.
- Add the fully missing subtree assertions where that shape is already exercised, or in a dedicated
  focused test if that keeps the existing tests readable.
- Resolve the unreachable outcome by making `ConflictType.INVALID_DESTINATION` an explicit defensive
  refusal that maps to the existing bounded `unsafe_destination` failure category instead of a
  `completed` evidence document with a projected `invalid` outcome, and remove `invalid` from the
  documented outcome list. Prove the defensive path with a narrowly injected planner double that
  returns a plan carrying that conflict for an otherwise safe composition. If instead a real
  revision document and sample can reach `invalid` with a safe composition, keep the branch, prove
  it with that document, and report which resolution was taken and why.
- Change nothing else in the precheck: no new probe, no new category, and no capability-comparison,
  guard, planner, resolver, Storage, activation or execution change.

## Non-goals

- No remote SMB / OpenList / S3 destination precheck, and no non-Local destination Storage support.
- No mutation-based capability probing; declared capability comparison stays declaration-only.
- No duplicate-media or cross-item collision detection, and no attachment or sidecar precheck.
- No absolute mounted-path display, and no reading or displaying `storages[].rootPath`.
- No combined activation evidence, no activation-gate change, and no execution or Task/Job creation.
- No new evidence key, request field, API route, permission, response status, or schema marker.
- No change to the guard, the capability comparison, the bounded failure categories, the probe
  budget, the capacity lease or the timeout behaviour.
- No rewrite of the Phase 22.6-E implementation-evidence record, the preserved `FIX REQUIRED`
  records, or any rejected checkpoint SHA.
- The four non-blocking review observations are deliberately deferred and must not be addressed
  here: the `NO / NO` destination-root rendering for categories decided before any probe; the
  `relativeDestination` / `destinationPath` naming divergence from the Phase 22.6-D
  `rootRelativeDestination` / `composedStorageRelativeDestination` names, which the Phase 22.6-E
  Task mandated; the theoretical same-location branch for a Storage literally named
  `destination-precheck-source`; and the pre-existing `ResourceWarning: unclosed database` that the
  byte-unmodified Phase 22.6-D suite emits identically.

## Safety and Architecture Invariants

- Scanner, Parser, Recognition, Metadata, Naming, Classification, Planner and DryRun mutate nothing;
  the precheck stays a read-only probe behind the `ReadOnlyStorageGuard` subclass.
- Only OrganizerExecutor may mutate Storage; this Task grants no execute, overwrite or delete
  authority, and `authorityGranted` stays `none`.
- Overwrite and Manual projections remain projections that require explicit operator confirmation
  later; nothing here confirms them.
- RecognitionType C remains C even when its RecognitionTypePolicy references NamingPolicy A and
  ClassificationPolicy A, and the precheck evidence keeps reporting C.
- Anything shown as Active remains the exact immutable snapshot consumed by runtime; the precheck
  keeps refusing a non-Draft/Validated revision and keeps its exact version/digest CAS.
- No FFmpeg or FFprobe dependency, and no filesystem access outside Storage interfaces.
- Credentials, endpoints, raw exception text, headers, cookies and private paths must not enter Web,
  API, evidence, logs, tests or commits. `config/alist.json` is never read, staged or committed.

## Required Tests

1. Non-construction proof: with injected `AssertionError` doubles for the Provider registry and the
   Executor, a successful precheck and at least one failure category both complete, and no Task,
   Job, queue entry, plan record or execution authority exists afterwards. The production planner
   and conflict resolver are excluded from the doubles by design.
2. Falsification of that proof: temporarily construct a Provider client or an Executor on the
   precheck path, show the new test fails, revert, show it passes and `git status` is clean. Record
   both runs.
3. Composed field proof: a successful precheck asserts the exact `relativeDestination` and
   `destinationPath` values, consistent with the Phase 22.6-D accepted composition, and asserts
   `destinationPath` begins with the MediaLibrary `rootPath`.
4. Web field proof: the destination-path field inside `renderDestinationPrecheck` is asserted to
   read `result.destinationPath` with a body-scoped assertion, or the existing body-scoped coverage
   is identified precisely if it already holds.
5. Fully missing subtree: with only the MediaLibrary root present, `deepestExistingAncestor` is that
   root, `directoriesToCreate` is the complete ordered multi-entry list, `targetExists` is false,
   the guard counters are zero, and the destination tree is unchanged.
6. Partially existing subtree: the existing single-entry create-list assertions remain and are not
   weakened.
7. Unreachable outcome resolution: an `INVALID_DESTINATION` conflict on an otherwise safe
   composition yields the bounded `unsafe_destination` failure with no `completed` ready or conflict
   verdict, and no documented outcome list still advertises `invalid`. If reachability is
   demonstrated instead, the real document proving it is asserted.
8. Unchanged contract: configuration schema marker stays 10, Runtime marker stays 22, the API's
   `400`, `409` and `503` behaviour and `MANAGE_CONFIGURATION` enforcement are unchanged, and the
   `tests/test_configuration_destination.py` Phase 22.6-D suite stays byte-unmodified and green.
9. Regression: the Phase 22.6-A/B/C/D configuration suites, the Phase 22.3/22.4/22.5 configuration
   and continuation regressions, the RecognitionType C regression, the marker upgrade tests, and the
   complete offline suite pass with no weakened, skipped or removed assertion.

## Validation

Run the focused destination precheck, destination preview and operator UI tests, the Phase
22.6-A/B/C configuration suites, the Phase 22.3/22.4/22.5 configuration and continuation
regressions, the RecognitionType C regression, the schema marker upgrade tests, and the complete
offline suite. Run Ruff lint and format, `compileall`, `pip check`, both example configuration
validations, the wheel build plus the isolated installed-wheel smoke test, documentation local-link
validation, `git diff --check`, the FFmpeg/FFprobe production audit, the business-layer
filesystem-mutation audit, and the private configuration checks. Report the deliberate falsification
runs explicitly — the temporary Provider/Executor construction that must fail the non-construction
test, and its removal — including the restoration and a clean `git status`. All destination I/O uses
temporary directories only; no real Storage, Provider or production data is used, and
`config/alist.json` is never read.

## Documentation

Record the correction implementation evidence in `docs/progress.md` beneath the preserved Phase
22.6-E `FIX REQUIRED` review record, and state exactly what now proves the four previously unproven
claims, including the resolution of the unreachable `invalid` outcome. Update the Phase 22.6-E gate
in `docs/roadmap.md` with the resulting status. Keep `docs/product-experience.md`,
`docs/requirements.md` and `docs/architecture.md` CURRENT claims accurate, changing them only where
they overstate coverage or still list a projected outcome that cannot occur. Keep remote destination
prechecks, mutation-based capability probing, duplicate and cross-item collision detection,
attachment prechecks, absolute mounted-path display, combined activation evidence and execution
explicitly TARGET. Never rewrite historical Phase evidence, the preserved `FIX REQUIRED` records, or
any rejected checkpoint SHA.

## Closure Checklist

- [ ] Workspace preflight records worktree, `.git`, index, sandbox, and approval mode.
- [ ] Capability mode is classified as Git-writable / Full Access or Git-read-only /
      workspace-write.
- [ ] The preceding dependent Slice is `PASS / CLOSED` with its commit SHA recorded
      (`c7ec192b3b20f236cca5a70ed59cad43e0851242`, Phase 22.6-D).
- [ ] The rejected Phase 22.6-E checkpoint `7353b0d22497e6e3e596c93c7052eea34daf27df` is preserved
      and not amended, squashed, or rewritten.
- [ ] Implementation and all required focused/full quality gates pass with actual evidence,
      including the non-construction falsification and its restoration.
- [ ] `git status` and the commit manifest contain every required file and no unrelated or private
      file.
- [ ] Private runtime configuration remains ignored and untracked; no secret is staged or committed.
- [ ] A coherent, buildable commit has been created: `Commit SHA: ________________________________`.
- [ ] High Review inspected that exact SHA and returned: `High Audit: ___________________________`.
- [ ] `docs/progress.md` records Status / Commit SHA / High Audit.
- [ ] `docs/roadmap.md` records the resulting Phase gate.
- [ ] The next Slice has not started before every preceding gate is complete.
- [ ] Required major-closure/integration push is recorded, or push is explicitly not required.

## Completion Report

Use the AGENTS.md completion structure and additionally report:

- the exact non-construction evidence: which doubles were injected, where they resolve, which runs
  they covered, and the falsification failure text with the temporary construction in place;
- the asserted composed `relativeDestination` and `destinationPath` values and how they were tied to
  the Phase 22.6-D accepted composition;
- the fully missing subtree assertions, including the exact ordered `directoriesToCreate` list;
- which resolution was chosen for the unreachable `invalid` projection, the production diff it
  required, and what now proves an unsafe or invalid destination has exactly one documented answer;
- confirmation that no evidence key, request field, API contract, permission, activation semantic or
  schema marker changed, or the exact minimal change if one proved necessary;
- CURRENT versus remaining TARGET for the Phase 22.6 destination journey and the exact next journey
  gap.
