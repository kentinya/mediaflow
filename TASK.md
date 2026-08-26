# Phase 22 Integration Slice 1 — Phase 22.4 Semantic Reconstruction

## Status

Phase 22.4 implementation reconstruction is complete only when the scoped code, tests, and
documentation represent the final net result of Phase 22.4, Phase 22.4-F1, and Phase 22.4-F2.
Independent High integration review is still required. This Task does not close Phase 22.4.

## Authoritative Inputs

- Baseline: `e28a24aff99c073c67b52351a82cb4a29e163de0`
- Recovery snapshot: `79b27e5`
- Integration branch: `integration/phase-22`
- Archived Task evidence:
  - `Task/phase-22.4-recognition-configuration-and-strategy-test.md`
  - `Task/phase-22.4-f1-web-strategy-evidence-rendering.md`
  - `Task/phase-22.4-f2-strategy-outcome-recovery-guidance.md`

This is a semantic reconstruction of the accepted final implementation state, not a recreation of
the original defective/intermediate commit sequence.

## User Goal and Journey

An operator edits RecognitionType, RecognitionRule, and RecognitionTypePolicy objects inside the
existing managed Draft, validates the exact revision, runs a zero-I/O synthetic Strategy Test
through the production Parser/Recognition/policy resolver, reviews durable bounded evidence and
outcome-specific recovery guidance in Web/API, then may explicitly checked-activate only when both
Local setup and Strategy Test evidence are current.

## Visible Success

- Managed Recognition object CRUD, optimistic versioning, audit, reference validation, and runtime
  consumption share the existing whole-document configuration authority.
- Exact-revision Strategy Test evidence persists and remains visible after reload.
- Web renders matched rules, alternatives, reasons, warnings, and status-specific next action.
- RecognitionType C remains C when downstream Naming/Classification policy A is reused.
- Checked activation requires current successful Local setup evidence and current completed
  Strategy Test evidence.
- Strategy Test constructs neither Storage nor Metadata Provider and performs zero media mutation.

## Failure and Recovery

Invalid or stale revision identity, invalid references, invalid input, disabled/unknown
ResourceLibrary, and engine/configuration failures fail closed with bounded, secret-free evidence.
Draft edits make prior evidence stale. Recovery is explicit: correct the Draft, Validate, rerun the
applicable checks, review the result, and explicitly activate. Nothing retries, activates, previews,
or mutates media automatically.

## Included Scope

Only the final net state of Phase 22.4 plus F1 and F2: Recognition configuration, strategy
selection/consumption, durable evidence, Web evidence rendering, outcome-specific recovery,
checked-activation evidence glue, API/Web exposure, tests, and the three historical Task archives.

## Non-goals

- No Phase 22.5 MetadataPolicy managed editing or effective-policy projection.
- No live Metadata Provider test, candidate explanation/confirmation, or candidate evidence CAS.
- No Provider switching, metadata correction continuation, remote Storage editor, scan, Preview,
  Organizer execution, or media mutation.
- No reconstruction of defective intermediate commits.
- No Phase closure declaration, merge, rebase, push, or work on later slices.

## Acceptance

- Focused Phase 22.4 configuration, persistence, runtime, API, Web, recovery, snapshot, and baseline
  regressions pass.
- Complete offline suite and applicable quality/safety gates pass.
- `git diff e28a24a` contains only Phase 22.4 final net implementation, tests, Task archives, and
  factual documentation.
- `config/alist.json` remains untracked and untouched.
- Independent High integration review remains pending.
