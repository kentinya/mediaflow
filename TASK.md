# Phase 22.3R5-F1 — Behavioral Snapshot Consumption Evidence Correction

## Independent Review Outcome

Phase 22.3R5 is `FIX REQUIRED` on 2026-08-25.

No P0 was found. One P1 remains inside the declared R5 scope: the combined acceptance test
changes only `historyPath` in the later Active revision. That field does not affect Preview
recognition, metadata, naming, classification, planning, or Result content, so the test proves
propagation of the original Job ID/digest but does not prove that the Worker consumed the original
configuration document rather than the later Active document.

The production path currently resolves `job.configuration_snapshot_id` and validates the matching
digest before workflow construction. This correction task must independently prove that behavior
with a configuration difference that changes the Preview outcome. Do not close Phase 22.3 from the
implementation report alone.

## Previous Slice Status

The R5 journey and its API/Worker wiring are otherwise accepted as the current correction baseline:

    Local setup check
    → checked activation
    → queued Preview Job
    → later Active revision
    → production Worker
    → Task/Result and API detail

The existing R5 setup-check, activation, persistence, failure/recovery, zero-mutation, and
optional-dependency isolation tests must remain green. Phase 22.4 remains prohibited.

## User Problem

An operator needs proof that a queued Preview actually executes against the immutable configuration
document saved on that Job. Seeing the original revision ID/digest in Job and Task fields is
insufficient if the executed behavior could have come from a later Active revision.

## Correction Journey

    checked-activate revision A
    → queue Preview pinned to A
    → checked-activate revision B whose behavior differs from A
    → run the production Worker
    → inspect Task/Result behavior and saved identity

## Required Outcome

- Revision A and revision B have the same valid Local setup roots but a deliberately different,
  bounded Preview behavior.
- The queued Job retains A's exact revision ID and digest after B becomes Active.
- The production Worker produces behavior that can only come from A, not B.
- Task and Result retain A's exact revision ID/digest and remain linked correctly.
- Job/Task API detail and the existing Web detail path remain inspectable.
- Preview remains `dry_run`; `execute_authorized` remains false; source and target media trees
  remain byte-for-byte unchanged.

## Failure and Recovery

- If the test accidentally uses B's behavior, it must fail with a clear assertion on a
  configuration-derived Result, TaskItem stage, recognition type, title, classification, naming,
  or destination field.
- If A's saved revision is missing, corrupt, unsupported, or runtime-invalid, preserve the existing
  bounded Worker failure evidence and no-Task/no-media-I/O behavior.
- No automatic retry, requeue, execute, or repair of the original Job is allowed.
- Recovery remains explicit new work under a repaired Active revision.

## Acceptance Criteria

- [ ] The later Active revision changes at least one Preview-consumed behavior while remaining
      valid and setup-checkable.
- [ ] The combined production-entry test asserts one behavior-derived field that differs between
      A and B, and proves the Result came from A.
- [ ] The test still asserts Job → Task → item/Result ID/digest continuity and `dry_run`.
- [ ] The test still asserts API/Task detail visibility and zero media mutation.
- [ ] Existing setup/recovery, saved-revision failure, authority, Web, and complete offline tests
      remain green.

## Technical Scope

1. Modify only the R5 combined acceptance fixture/test and the minimum test helper or production
   wiring needed if the behavior-distinction test exposes a real defect.
2. Prefer a valid recognition-rule or classification/naming change that produces a bounded,
   deterministic difference without network access or real Storage mutation.
3. Keep the production Worker, saved-revision resolver, configuration model, Storage adapters,
   metadata providers, OrganizerExecutor, API permissions, and Web layout unchanged unless the
   new behavior-distinction test demonstrates an actual defect.
4. Update `docs/progress.md` with the independent review result and final correction evidence only
   after the correction passes.

## Non-goals

- No new configuration model, remote Storage editor/check, policy CRUD, Strategy Test UI, browser
  framework, or Phase 22.4 work.
- No new runtime authority, real execute, overwrite, delete, automatic retry, or auto-preview.
- No duplication of the existing saved-revision failure matrix beyond the one regression needed to
  prove behavior consumption.
- Do not mark Phase 22.3 closed until a later independent review returns `PASS / CLOSED`.

## Required Tests

1. R5 combined journey with behavior-distinct revisions A and B.
2. Existing production Web/Worker pin continuity test.
3. Existing saved-revision failure/recovery tests.
4. Related configuration object/snapshot/status/admission/Web tests.
5. Complete offline suite and repository validation commands.

## Validation

Run the focused correction test, related configuration/snapshot/Web tests, and the complete offline
suite. Run Ruff lint/format, compileall, `pip check`, `git diff --check`, documentation local-link,
FFmpeg/FFprobe production, and business-filesystem mutation-boundary audits. Report actual counts.

## Completion Report

Report the behavior difference between A and B, the observed A-derived Result/Task fields, exact
Job/Task pin continuity, API/Web detail evidence, zero-mutation evidence, tests, deviations, and
remaining risks. Do not declare Phase 22.3 closed.
