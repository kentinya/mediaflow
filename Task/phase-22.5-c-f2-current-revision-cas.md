# Phase 22.5-C-F2 — Candidate Confirmation Current-Revision CAS

## Independent Review Finding

Phase 22.5-C-F1 fixed the original cross-service evidence overwrite race: two confirmations
against one evidence timestamp now produce one winner and one `409`. Independent review found one
remaining P1 inside the same slice.

During an in-flight Provider details lookup, another connection can edit the same managed revision
from `Validated` to a new `Draft`. The candidate-confirmation CAS currently matches only the
Strategy Test evidence row's old revision version/digest/testedAt. Because the evidence row is not
updated by the Draft edit, the confirmation can still return `200` and write a candidate selection
for the old Validated revision. The row is later projected as stale, but the confirmation response
has already reported success.

The operation must fail closed when the managed revision changes before the durable evidence
replacement commits.

## User Journey

```text
current live NeedConfirm/Ambiguous evidence
→ Provider details lookup is in flight
→ another operator edits the same revision
→ candidate confirmation reaches durable commit
→ confirmation returns a bounded 409
→ Draft and prior evidence remain intact
→ operator reloads, validates, and explicitly reruns the live test
```

## Required Correction

1. Extend the durable candidate-confirmation compare-and-swap so one atomic repository transaction
   requires both:
   - the current managed revision row is still the expected `revision_id`, version, digest, and
     `Validated` status; and
   - the current Strategy Test evidence row still has the expected revision version/digest and
     previous `testedAt`.
2. If either condition fails, raise `ConfigurationVersionConflict` and do not replace the evidence
   row. Preserve the current Draft and prior evidence.
3. Apply the same condition to candidate-confirmation success and Provider-failure replacement.
   Do not cancel or claim to cancel an already-running Provider call.
4. Keep the existing F1 winner/loser CAS behavior, API request shape, permissions, direct
   Provider-ID lookup, C preservation, and zero-Storage boundary unchanged.

## Acceptance Criteria

- [ ] A barrier regression blocks Provider details, edits the same revision through a distinct
      SQLite connection, releases the lookup, and receives `409`, never `200`.
- [ ] The edited Draft remains durable and the pre-edit evidence remains unchanged; no stale
      candidate selection is persisted.
- [ ] The `409` identifies durable state, has `sideEffects=none`, `retrySafe=true`, and directs the
      operator to reload/revalidate/rerun.
- [ ] The same fail-closed behavior applies when the in-flight candidate confirmation would have
      produced Provider-failure evidence.
- [ ] Existing two-confirmation cross-service winner/loser tests, sequential replay, Provider
      failure recovery, authorization, secret redaction, C preservation, and zero-Storage tests
      remain green.
- [ ] The repository operation is atomic and does not introduce another configuration authority,
      distributed lock, reservation UI, automatic retry, or later Phase work.

## Non-goals

- No Provider switching, free-form Metadata correction, cancellation service, cache redesign,
  Storage/media mutation, task/preview/activation changes, or Phase 22.6 work.
- Do not weaken the existing F1 race regression or broaden the client request contract.
- Do not declare Phase 22.5-C or Phase 22 closed from an implementation report.

## Required Validation

Run the new in-flight revision-edit regression repeatedly, the existing Phase 22.5-C-F1
winner/loser tests, Phase 22.5-A/B and Phase 22.4 regressions, the complete offline suite, Ruff
lint/format, compileall, `pip check`, both example validations, wheel build/smoke, documentation
links, `git diff --check`, FFmpeg/FFprobe audit, and business-filesystem mutation audit.

## Completion Report

Use the AGENTS.md Completion Report structure and additionally report:

## Phase 22.5-C-F2 Result

## Current-Revision Race Evidence

## Durable Recovery

## Security / Zero Mutation

## Regression
