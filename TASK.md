# Phase 22.6-F — Checked Activation Requires Current Local Destination Precheck Evidence

This Task follows [the authoritative development workflow](docs/development-workflow.md).

```text
Status: READY FOR COMMIT
Commit SHA: PENDING
High Audit: PENDING
Preceding closed checkpoint: ee5225dd0e74a7382b6747c6315776413f7fd249
  (Phase 22.6-E PASS / CLOSED — 2026-08-28, accepted through the Phase 22.6-E-F1 correction)
Preserved rejected checkpoints: 7353b0d22497e6e3e596c93c7052eea34daf27df (Phase 22.6-E),
  90ce13a6c6c39912dd389f71a1189314ff24eb5d (Phase 22.6-A) and
  08dfd4f921728755209b6d52347d28f221121c47 (Phase 22.5-E); never amended, squashed or rewritten
Push gate: NOT BLOCKING — Slice closure does not require a push; every closed Phase 22.6 checkpoint
  and its documentation record is still absent from origin/main, and phase-level Phase 22.6 closure
  requires an explicitly authorized push
Phase: 22.6 Naming / Classification / Organize configuration journey (roadmap section 5)
Slice scope: combined activation evidence for Local destinations only — checked activation consumes
  the destination precheck evidence that Phase 22.6-E already produces; no new probe, no remote
  Storage support, no schema marker change and no execution
```

## User Problem

An operator can still activate a Draft whose destination has never been observed.
`activate_checked` requires a current Local setup check and a current Recognition Strategy Test, but
the Phase 22.6-E destination precheck is advisory only: the operator may skip it, ignore a
`capability_gap` verdict or a bounded failure, or edit the Draft until the evidence is stale, and
checked activation still succeeds. The questions the precheck answers — does the composed
Storage-relative path resolve, which directories would be created, does the destination Storage
declare the capability the configured operation needs — therefore have no effect on the gate that
protects the media library.

The product requirement is explicit that checked activation requires both the current Local check
and the destination evidence, so `Active` means a configuration whose destination was actually
observed on that exact revision. Today the Web view shows the precheck result next to an activation
control that ignores it, which is the weaker half of a safety promise the operator reasonably reads
as enforced.

This Slice closes that gap for Local destinations only, using evidence that already exists. It adds
no probe, no capability mutation, no remote support and no new persisted state.

## User Journey

- User goal: activate a Draft only when its Local destination has actually been observed on this
  exact revision, and understand immediately what is missing when it has not.
- Entry point: the same managed revision view, and checked activation through the Web control or
  `POST /api/v1/configuration/revisions/<revision-id>/activation` with `checked: true`.
- Visible state: the destination precheck section keeps showing current or stale, status, verdict,
  bounded message and next action, and now also states whether checked activation is satisfied,
  blocked or not applicable for this Draft.
- Available action: run the read-only destination precheck on the exact version and digest, then
  activate checked; or fix the destination configuration first and rerun the precheck.
- Success outcome: once the precheck evidence for this revision is current, completed and free of a
  capability gap, checked activation behaves exactly as it does today.
- Failure outcome: checked activation is refused before any activation happens, the previous Active
  configuration and every stored evidence record stay unchanged, and the refusal names which
  requirement is missing, stale or failed.
- Recovery path: the refusal carries one explicit next action — rerun the destination precheck on
  the current version and digest, or correct the destination configuration and then rerun it.

## User-visible Outcome

- Checked activation of a Draft that configures a Local destination requires three current pieces of
  evidence instead of two: the Local setup check, the Recognition Strategy Test and the destination
  precheck.
- The refusal distinguishes four cases in bounded, secret-free language: no destination precheck was
  run for this revision, the stored precheck is stale after an edit, the stored precheck failed with
  its bounded category, and the stored precheck completed with a `capability_gap` verdict.
- A Draft that configures no Local destination is explicitly reported as not applicable and keeps
  today's two-gate behaviour, so remote-only configurations are never made unactivatable by a
  requirement this Phase cannot yet satisfy.
- Unchecked activation, `Active` projection, permissions, evidence documents, request fields, API
  status codes and both schema markers stay exactly as they are.

## Failure and Recovery

| Failure | Visible state | Durable state | Safe to repeat | Explicit action |
| --- | --- | --- | --- | --- |
| No destination precheck exists for the revision | Refusal naming the missing destination precheck; the section still reads `not run` | Draft, Active configuration and every other evidence record unchanged | Yes | Run the read-only destination precheck on this revision, then activate checked |
| Stored precheck is stale after an edit | Refusal naming stale destination evidence; the section reads `stale` | Draft, Active configuration and the stale evidence preserved | Yes | Reload the revision and rerun the destination precheck on the current version and digest |
| Stored precheck failed | Refusal repeating the stored bounded failure category | Draft, Active configuration and the failed evidence preserved | Yes | Follow the stored next action, fix the destination, then rerun the precheck |
| Stored precheck completed with `capability_gap` | Refusal naming the capability gap without echoing Storage internals | Draft, Active configuration and the completed evidence preserved | Yes | Change the configured operation or the destination Storage, then rerun the precheck |
| Draft configures no Local destination | The section reports the requirement as not applicable | Unchanged | Yes | Activate checked under the existing Local check and Strategy Test gates |

## UX Acceptance Criteria

- [ ] The revision view states, for the current Draft, whether the destination precheck requirement
      for checked activation is satisfied, blocked or not applicable, using the already projected
      revision, evidence, MediaLibrary and Storage data.
- [ ] Each of the four blocked cases renders one bounded, secret-free sentence naming the single
      action that continues, with no Storage endpoint, credential, header, cookie, private path or
      raw exception text.
- [ ] A refused checked activation leaves the operator on the same revision with the previous Active
      configuration intact and no partial activation visible anywhere.
- [ ] A satisfied requirement produces exactly today's activation result, with no extra confirmation
      step and no new field in the activation response.
- [ ] The Web and API surfaces refuse the same cases with the same reasons and the same permissions.
- [ ] The not-applicable case is visible rather than silent, so a remote-only Draft cannot look
      broken.
- [ ] Every new Web string is proven by a body-scoped operator-UI assertion that fails when the line
      is deleted.

## Technical Scope

- `mediaflow/application/configuration_objects.py`
  - Add one `require_current_destination_precheck(revision)` helper beside the existing
    `require_current_local_check` and `require_current_strategy_test`, raising
    `ConfigurationActivationConflict` with a bounded message and an explicit next action for the
    missing, stale, failed and `capability_gap` cases.
  - Add a document-level applicability rule: the requirement applies when the revision document
    declares at least one MediaLibrary whose `storageId` names a Storage whose `type` is `local`.
    Any other document, including one with no MediaLibrary, is not applicable.
  - Call the new helper from `activate_checked` after the two existing requirements so the existing
    refusal order and messages are preserved.
- `mediaflow/interfaces/operator_ui.py`
  - Extend `renderDestinationPrecheck` with the activation-requirement state derived from data the
    view already receives: the revision summary, the projected evidence and the projected
    `mediaLibraries` and `storages` objects, whose `type` field survives remote redaction.
  - Reuse the existing warning and error styles and the existing bounded text helpers.
- `tests/test_configuration_destination_precheck.py`
  - Add the activation-gate tests listed under Required Tests, including the not-applicable case and
    the unchanged behaviour of unchecked activation.
- `tests/test_operator_ui.py`
  - Add body-scoped assertions for the new activation-requirement lines.
- `tests/test_service_api.py`
  - Add the API refusal test for one blocked case and one satisfied case, asserting the existing
    activation-conflict status code and bounded body.
- Documentation: `docs/architecture.md`, `docs/product-experience.md`, `docs/requirements.md` if a
  requirement ID needs its CURRENT wording corrected, and the Chinese requirements specification
  status line. `docs/progress.md` and `docs/roadmap.md` gate records stay High-only.

## Non-goals

- No remote SMB, OpenList or S3 destination precheck, and no change to the Local-only support
  statement.
- No mutation-based capability probing, no write, no create, no delete and no execution.
- No duplicate media, cross-item collision or attachment precheck.
- No absolute mounted-path display and no Storage `rootPath` exposure.
- No new evidence key, request field, response field, permission or API status code.
- No schema change: the Configuration marker stays 10 and the Runtime marker stays 22.
- No change to unchecked activation, to `Active` projection semantics or to the two existing
  activation requirements.
- No new Task, Job, authority or queue record, and no Provider, Planner, Executor or Storage
  construction on the activation path.
- The four non-blocking observations deferred by the Phase 22.6-E and Phase 22.6-E-F1 reviews stay
  deferred, except that a later Slice may harden the Executor double target.

## Safety and Architecture Invariants

- Scanning, parsing, recognition, metadata, naming, classification, planning and DryRun still mutate
  nothing; only `OrganizerExecutor` may mutate Storage, and this Slice does not touch it.
- The activation gate performs no Storage, Provider, Planner or Executor construction and no probe;
  it reads only the revision document and the already persisted evidence.
- RecognitionType C stays C through every policy resolution touched by the applicability rule.
- Evidence remains immutable: a refused activation writes nothing and rewrites no stored evidence.
- Configuration displayed as Active stays the exact immutable snapshot consumed by runtime.
- Bounded, secret-free explanations only: no credential, endpoint, Storage `rootPath`, header,
  cookie, private path or raw exception text may reach the Web, API, evidence, logs, tests or
  commits. `config/alist.json` is never read, staged or committed.
- No FFmpeg or FFprobe dependency is introduced.

## Required Tests

1. Missing evidence: checked activation of a Local-destination Draft with no destination precheck is
   refused with the bounded missing-evidence message and next action; the revision stays
   Draft or Validated, the previous Active revision is unchanged, and every other evidence record is
   untouched.
2. Stale evidence: a completed precheck followed by a document edit that changes version and digest
   is refused with the stale wording, and the stale evidence is preserved rather than deleted.
3. Failed evidence: a stored precheck with a bounded failure category refuses activation and the
   refusal names that category.
4. Capability gap: a completed precheck whose verdict is `capability_gap` refuses activation even
   though the evidence is current and completed.
5. Satisfied requirement: a current completed precheck with verdict `ready` activates exactly as
   today, and a conflict projection of `skip`, `rename`, `overwrite_requires_confirmation` or
   `manual_confirmation_required` does not block activation.
6. Not applicable: a Draft whose only MediaLibrary points at a non-Local Storage, and a Draft with
   no MediaLibrary at all, both activate under the two existing requirements with the new helper
   raising nothing.
7. Requirement order preserved: a Draft missing the Local setup check or the Strategy Test still
   fails with the existing message before the destination requirement is evaluated, and unchecked
   activation ignores all three.
8. Zero authority and zero construction on the activation path: `AssertionError` doubles on the
   Provider registry, the Executor and `OrganizePlanner.plan` are never called during a refused or
   a successful checked activation, no Storage adapter is constructed, and a pre-created Runtime
   database stays empty across Tasks, task items and results, the conflict confirmation,
   metadata correction and three review queues, `automation_jobs` and `execution_authorizations`.
9. Falsifiable Web proof: body-scoped assertions inside `renderDestinationPrecheck` for each new
   activation-requirement line, each proven by deleting the line and observing the failure.
10. API parity: the blocked case returns the existing activation-conflict status code with a bounded
    body and no secret, and the satisfied case returns today's activation response unchanged; the
    permission requirement is identical to the current activation route.
11. Contract unchanged: Configuration marker 10 and Runtime marker 22 are asserted, and the Phase
    22.6-D and Phase 22.6-E suites stay byte-unmodified and green.
12. Regression: the complete offline suite plus the Phase 22.3 through 22.6 configuration,
    continuation, RecognitionType C, organizer and conflict group.

## Validation

- `.venv/bin/python -m unittest` for the focused destination, precheck, operator-UI and service-API
  tests, then the Phase 22.3 through 22.6 regression group, then the complete offline suite.
- `.venv/bin/python -m ruff check .` and `.venv/bin/python -m ruff format --check .`.
- `.venv/bin/python -m compileall mediaflow tests`.
- `.venv/bin/pip check`.
- CLI validation of both example configurations through `.venv/bin/python -m mediaflow.cli`, once
  with `--config config/mediaflow.phase13.2.example.json config validate` and once with
  `--config config/strategy.example.json config validate`.
- Wheel build, isolated install and smoke run reporting both schema markers.
- `git diff --check`, the FFmpeg/FFprobe audit, the business-layer filesystem-mutation audit, the
  Markdown local-link check, and confirmation that `config/alist.json` stays ignored and untracked.

## Documentation

- `docs/architecture.md`: move combined activation evidence for Local destinations from TARGET to
  CURRENT and keep remote precheck, mutation probing, duplicate and attachment checks, absolute
  mounted-path display and execution as TARGET.
- `docs/product-experience.md`: extend the Phase 22.6-E journey section with the enforced activation
  requirement, the four blocked cases and the not-applicable case.
- `docs/requirements.md`: correct the CURRENT wording of any activation requirement ID that still
  describes destination evidence as advisory.
- The Chinese requirements specification: update only the implementation-status sentence.
- Do not write `docs/progress.md` review records or `docs/roadmap.md` gate rows; both stay
  High-only.

## Closure Checklist

- [ ] `require_current_destination_precheck` exists, is called from `activate_checked` after the two
      existing requirements, and covers the missing, stale, failed and `capability_gap` cases.
- [ ] The applicability rule is document-level, Local-only and explicit about not applicable.
- [ ] The Web view shows satisfied, blocked or not applicable with bounded, secret-free text.
- [ ] Web and API refuse identically, with unchanged permissions and status codes.
- [ ] No evidence key, request field, response field or schema marker changed; markers stay 10
      and 22.
- [ ] No probe, no Storage/Provider/Planner/Executor construction and no mutation on the gate path.
- [ ] RecognitionType C identity holds and the Phase 22.6-D and 22.6-E suites stay byte-unmodified.
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
with counts; design decisions, especially the applicability rule and the refusal wording; work
intentionally deferred; and risks, assumptions or newly discovered issues.
