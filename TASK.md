# Phase 22.6-G — The Web Checked-Activation Control States and Gates All Three Requirements

This Task follows [the authoritative development workflow](docs/development-workflow.md).

```text
Status: NOT STARTED
Commit SHA: PENDING
High Audit: PENDING
Preceding closed checkpoint: e68e901a73107484dc0521b47b1b0001eed2b853
  (Phase 22.6-F PASS / CLOSED — 2026-08-28)
Preserved rejected checkpoints: 7353b0d22497e6e3e596c93c7052eea34daf27df (Phase 22.6-E),
  90ce13a6c6c39912dd389f71a1189314ff24eb5d (Phase 22.6-A) and
  08dfd4f921728755209b6d52347d28f221121c47 (Phase 22.5-E); never amended, squashed or rewritten
Push gate: NOT BLOCKING — Slice closure does not require a push; every closed Phase 22.6
  checkpoint and its documentation record is still absent from origin/main, and phase-level
  Phase 22.6 closure requires an explicitly authorized push
Phase: 22.6 Naming / Classification / Organize configuration journey (roadmap section 5)
Slice scope: Web-surface parity for the activation gate Phase 22.6-F already enforces on the
  server — the control and its warning state all three requirements before the operator clicks —
  plus two cheap items the Phase 22.6-E-F1 and Phase 22.6-F reviews explicitly deferred to a
  later Slice. No new probe, no remote Storage support, no new gate semantics, no schema marker
  change and no execution
```

## User Problem

Phase 22.6-F made checked activation require three current pieces of evidence for a
Local-destination Draft, but the Web control still decides from two.
`checkedActivationEvidenceIsCurrent` in `mediaflow/interfaces/operator_ui.py` combines only the
Local setup check and the Recognition Strategy Test, so a validated Local Draft whose destination
precheck is missing, stale, failed or `capability_gap` still shows an enabled
`Activate checked revision` button and a compatibility warning that enumerates two requirements.
The operator clicks the button the interface offers and receives a 409 refusal instead of an
activation.

At the guided-setup control site the same predicate simply withholds the `Activate checked Draft`
button with no sentence explaining which requirement is missing, so on that panel the third
requirement is invisible rather than merely mis-stated.

Both are the same defect: the Web surface advertises an action its own server will refuse, and the
recovery arrives only after the failed click. That contradicts the permanent product rule that API
and Web capabilities for one journey use the same behaviour, validation, state and safety rules,
and the rule that recovery must explain what is missing and name the action that continues. The
destination precheck section directly above the control already computes the correct answer, so the
information exists and merely does not reach the control.

Two deferred items are folded in because they are cheap and belong to exactly this code.
`require_current_destination_precheck` reads the `mediaLibraries` section without the guard
`revision_detail` uses, so a document that omits the section raises `ValueError` instead of
reporting the requirement as not applicable. And the Phase 22.6-E-F1 review proved the
`AssertionError` Executor double targets the definition site, so a future module-level import into
`mediaflow/application/configuration_objects.py` would bypass it while the test still passes.

## User Journey

- User goal: see, before clicking, whether checked activation of this Draft is available, and when
  it is not, read which of the three requirements blocks it and what action continues.
- Entry point: the same managed revision view — the guided setup panel and the revision detail
  actions — and the unchanged
  `POST /api/v1/configuration/revisions/<revision-id>/activation` route.
- Visible state: the activation control reflects all three requirements; when the destination
  precheck is the blocking one, one bounded sentence names it beside the control, matching the
  wording the server refusal would have produced.
- Available action: run or rerun the read-only destination precheck, fix the destination
  configuration, or activate unchecked as the explicit compatibility path.
- Success outcome: when all three requirements are current, the control appears and behaves exactly
  as it does today.
- Failure outcome: the checked control is not offered as if it would succeed, and the operator is
  not sent into a refusal to discover the requirement.
- Recovery path: the blocking sentence carries the same single next action as the server refusal —
  rerun the destination precheck on the current version and digest, or correct the destination
  first.

## User-visible Outcome

- The Web activation decision consumes the destination-precheck requirement, so the checked control
  is offered only when the server would accept it.
- When the destination precheck blocks checked activation, the revision-detail warning names that
  requirement instead of enumerating only two, and the guided panel prints one bounded sentence
  instead of silently withholding its button.
- A Draft that configures no Local destination keeps today's wording and today's availability, so
  remote-only configurations are not made to look broken.
- A revision document that omits the `mediaLibraries` section is reported as not applicable rather
  than failing the activation attempt with an internal error.
- Unchecked activation, the server gate semantics, `Active` projection, permissions, evidence
  documents, request fields, response fields, API status codes and both schema markers stay exactly
  as they are.

## Failure and Recovery

| Failure | Visible state | Durable state | Safe to repeat | Explicit action |
| --- | --- | --- | --- | --- |
| Local Draft with no destination precheck | Checked control not offered; one bounded line names the missing precheck | Draft, Active configuration and every evidence record unchanged | Yes | Run the read-only destination precheck on this revision, then activate checked |
| Local Draft whose precheck is stale | Checked control not offered; the line names stale destination evidence | Stale evidence preserved | Yes | Reload the revision and rerun the precheck on the current version and digest |
| Local Draft whose precheck failed | Checked control not offered; the line repeats the stored bounded failure category | Failed evidence preserved | Yes | Follow the stored next action, fix the destination, then rerun the precheck |
| Local Draft whose precheck reports `capability_gap` | Checked control not offered; the line names the capability gap without Storage internals | Completed evidence preserved | Yes | Change the configured operation or the destination Storage, then rerun the precheck |
| Draft with no Local destination | Today's two-requirement wording and today's control availability | Unchanged | Yes | Activate checked under the two existing requirements |
| Revision document omits `mediaLibraries` | Requirement reported as not applicable; no internal error surfaces | Unchanged | Yes | Activate checked under the two existing requirements |
| Guided objects projection unavailable | The existing "Guided configuration is unavailable" message; no checked control is offered on guessed state | Unchanged | Yes | Reload the revision |

## UX Acceptance Criteria

- [ ] The Web checked-activation decision is one shared predicate that includes the destination
      precheck requirement, and both control sites — the guided setup panel and the revision detail
      actions — use it, so the two sites cannot disagree with each other or with the server.
- [ ] When the destination precheck blocks checked activation, exactly one bounded, secret-free
      sentence beside the control names that requirement and the single action that continues, with
      no Storage endpoint, credential, header, cookie, private path, `rootPath` or raw exception
      text.
- [ ] When the requirement is not applicable, the existing two-requirement wording and the existing
      control availability are unchanged.
- [ ] When all three requirements are current, the control, its label and its behaviour are exactly
      today's.
- [ ] The guided panel no longer withholds its checked control silently.
- [ ] Unchecked activation remains available and unchanged as the explicit compatibility path.
- [ ] Every new or changed Web string is proven by a body-scoped operator-UI assertion that fails
      when the line is deleted.

## Technical Scope

- `mediaflow/interfaces/operator_ui.py`
  - Extract the destination-requirement decision already computed inside
    `renderDestinationPrecheck` into one reusable predicate — applicability from
    `guided.objects.storages` and `guided.objects.mediaLibraries`, currency through the existing
    `destinationPrecheckIsCurrent`, `status === 'completed'`, and verdict not `capability_gap` —
    and have both `renderDestinationPrecheck` and `checkedActivationEvidenceIsCurrent` consume it.
    No second copy of the rule.
  - Add the blocking sentence at the guided-setup control site, and extend the revision-detail
    compatibility warning so it names the destination-precheck requirement when that requirement is
    the blocking one, reusing the existing `text` helper, warning/error styles and bounded text
    helpers.
  - No new endpoint call, request field, response field, permission or style.
- `mediaflow/application/configuration_objects.py`
  - Make the applicability rule total: when the revision document omits the `mediaLibraries`
    section, `require_current_destination_precheck` reports not applicable instead of raising,
    matching the guard `revision_detail` already uses. No other gate semantics change.
- `tests/test_operator_ui.py`
  - Body-scoped assertions for the shared predicate, the guided-panel line and the revision-detail
    warning.
- `tests/test_configuration_destination_activation.py`
  - Additive only: new test methods for the omitted-`mediaLibraries` applicability case, the
    module-namespace hardening, and the Runtime-emptiness assertion inside the API case. Existing
    methods stay unmodified, provable by a `git diff` on this file that contains insertions only.
- Documentation: `docs/architecture.md` and `docs/product-experience.md` for the Web control CURRENT
  claim, and `docs/requirements.md` only if a requirement ID still describes the Web activation
  control as gating two requirements. `docs/progress.md` and `docs/roadmap.md` gate records stay
  High-only.

## Non-goals

- No change to the server gate semantics, its refusal wording, its order or its four cases.
- No narrowing of the document-level applicability rule to only the routed destination; that stays a
  deferred observation, not this Slice.
- No remote SMB, OpenList or S3 destination precheck, and no change to the Local-only statement.
- No mutation-based capability probing, no write, no create, no delete and no execution.
- No new evidence key, request field, response field, permission or API status code.
- No schema change: the Configuration marker stays 10 and the Runtime marker stays 22.
- No change to unchecked activation, to `Active` projection semantics or to the two existing
  activation requirements.
- No new Task, Job, authority or queue record, and no Provider, Planner, Executor or Storage
  construction on the activation path.
- No disabled-button or confirmation-dialog redesign, no new CSS and no new operator page.

## Safety and Architecture Invariants

- Scanning, parsing, recognition, metadata, naming, classification, planning and DryRun still mutate
  nothing; only `OrganizerExecutor` may mutate Storage, and this Slice does not touch it.
- The activation gate still performs no Storage, Provider, Planner or Executor construction and no
  probe; it reads only the revision document and the already persisted evidence.
- RecognitionType C stays C through every policy resolution touched by the applicability rule.
- Evidence remains immutable: a refused activation writes nothing and rewrites no stored evidence.
- Configuration displayed as Active stays the exact immutable snapshot consumed by runtime.
- Bounded, secret-free explanations only: no credential, endpoint, Storage `rootPath`, header,
  cookie, private path or raw exception text may reach the Web, API, evidence, logs, tests or
  commits. `config/alist.json` is never read, staged or committed.
- No FFmpeg or FFprobe dependency is introduced.

## Required Tests

1. Shared predicate: a body-scoped assertion proves `checkedActivationEvidenceIsCurrent` consults
   the destination-precheck requirement, and that the predicate body covers Local applicability,
   evidence currency, `completed` status and the `capability_gap` verdict. Deleting any one of those
   conditions fails a named test.
2. Blocked wording, revision detail: the compatibility warning names the destination-precheck
   requirement and its next action, bounded and secret-free.
3. Blocked wording, guided panel: one bounded line states the blocking requirement where the checked
   Draft button is withheld.
4. Not applicable: the two-requirement wording and the control availability for a Draft with no
   Local destination are unchanged, asserted rather than assumed.
5. Falsifiable Web proof: each new Web line and the predicate wiring are proven by deletion, and the
   failing test for each deletion is named in the Completion Report.
6. Applicability totality: `require_current_destination_precheck` on a revision document that omits
   the `mediaLibraries` section reports not applicable and checked activation succeeds under the two
   existing requirements; the same input raises before the fix, so the test is falsifiable.
7. Module-namespace hardening: assert that `mediaflow.application.configuration_objects` exposes no
   `OrganizerExecutor`, `MetadataProviderRegistry` or `OrganizePlanner` module attribute, so the
   `AssertionError` doubles behind the Phase 22.6-E, 22.6-E-F1 and 22.6-F non-construction proofs
   cannot be bypassed by a future module-level import. Prove it bites by adding such an import in a
   probe and observing the failure.
8. API parity plus emptiness: the existing blocked and satisfied API cases keep the current status
   codes and bounded bodies, and both now also assert that a pre-created Runtime database stays
   empty across Tasks, task items and results, the conflict confirmation, metadata correction and
   three review queues, `automation_jobs` and `execution_authorizations`.
9. Contract unchanged: Configuration marker 10 and Runtime marker 22 are asserted;
   `tests/test_configuration_destination.py` and
   `tests/test_configuration_destination_precheck.py` stay byte-identical to
   `c7ec192b3b20f236cca5a70ed59cad43e0851242` and
   `ee5225dd0e74a7382b6747c6315776413f7fd249` respectively; and the Phase 22.6-F suite file changes
   by insertion only.
10. Regression: the complete offline suite plus the Phase 22.3 through 22.6 configuration,
    continuation, RecognitionType C, organizer and conflict group.

## Validation

- `.venv/bin/python -m unittest` for the focused operator-UI, destination, precheck and activation
  tests, then the Phase 22.3 through 22.6 regression group, then the complete offline suite.
- `.venv/bin/python -m ruff check .` and `.venv/bin/python -m ruff format --check .`.
- `.venv/bin/python -m compileall mediaflow tests`.
- `.venv/bin/pip check`.
- CLI validation of both example configurations through `.venv/bin/python -m mediaflow.cli`, once
  with `--config config/mediaflow.phase13.2.example.json config validate` and once with
  `--config config/strategy.example.json config validate`.
- Wheel build with `python -m pip wheel . --no-deps --no-build-isolation -w dist`, isolated install
  and `scripts/wheel_smoke_test.py <wheel>` reporting both schema markers.
- `git diff --check`, the FFmpeg/FFprobe audit, the business-layer filesystem-mutation audit, the
  Markdown local-link check, and confirmation that `config/alist.json` stays ignored and untracked.

## Documentation

- `docs/architecture.md`: record as CURRENT that the Web activation control and its warning reflect
  all three checked-activation requirements for Local destinations; remote precheck, mutation
  probing, duplicate and attachment checks, absolute mounted-path display and execution stay TARGET.
- `docs/product-experience.md`: extend the Phase 22.6-E/F journey section with the pre-click control
  state, the blocking sentence and the unchanged not-applicable wording.
- `docs/requirements.md`: correct only a requirement ID whose CURRENT wording still describes the
  Web activation control as gating two requirements.
- Do not write `docs/progress.md` review records or `docs/roadmap.md` gate rows; both stay
  High-only.

## Closure Checklist

- [ ] One shared Web predicate decides checked activation, includes the destination requirement, and
      is used by `renderDestinationPrecheck` and both control sites.
- [ ] The blocking sentence exists at both control sites, is bounded and secret-free, and names one
      next action identical in meaning to the server refusal.
- [ ] The not-applicable and satisfied paths are exactly today's operator experience.
- [ ] `require_current_destination_precheck` reports not applicable for a document without a
      `mediaLibraries` section instead of raising.
- [ ] The module-namespace hardening test exists and was proven to bite.
- [ ] No evidence key, request field, response field, permission, status code or schema marker
      changed; markers stay 10 and 22.
- [ ] No probe, no Storage/Provider/Planner/Executor construction and no mutation on the gate path.
- [ ] RecognitionType C identity holds; the Phase 22.6-D and 22.6-E suites stay byte-unmodified and
      the Phase 22.6-F suite file is insertion-only.
- [ ] All Required Tests exist, assert rather than assume, and each new Web line is falsifiable.
- [ ] The complete offline suite, lint, format, compileall, `pip check`, both example validations
      and the wheel smoke run pass.
- [ ] Private runtime configuration remains ignored and untracked; no secret is staged or committed.
- [ ] Documentation CURRENT claims match the shipped behaviour.
- [ ] One coherent, buildable, reviewable commit is created, and the Completion Report records
      actual commands and results.
- [ ] The Slice is reported as READY FOR HIGH REVIEW without declaring Phase closure.

## Completion Report

Report, at minimum: changed files; implemented behaviour; commands executed; pass or fail results
with counts; each falsification probe and the exact test it failed; design decisions, especially the
shared-predicate placement and the blocking wording; work intentionally deferred; and risks,
assumptions or newly discovered issues.
