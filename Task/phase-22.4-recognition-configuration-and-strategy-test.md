# Phase 22.4 — Recognition Configuration + Synthetic Strategy Test Journey

## Baseline and Scope Decision

Phase 22.3R5-F1 received independent `PASS / CLOSED` on 2026-08-25. The next roadmap item is
Phase 22.4. This Task is one medium vertical slice: it extends the existing managed whole-document
Draft/Validated/Active authority with operator-facing RecognitionType, RecognitionRule, and
RecognitionTypePolicy editing and an exact-revision synthetic Strategy Test. It does not create a
second configuration store or change runtime snapshot pinning.

## User Problem

An operator can currently edit recognition JSON only in the advanced whole-document editor and
activate it without seeing how the real Parser and Recognition engine resolve a representative
path. Invalid references, priority outcomes, and accidental RecognitionType identity changes are
therefore hard to diagnose before new work consumes the Active snapshot.

## User Journey

    Configuration Web view
    → open an editable managed revision
    → create/update/delete RecognitionType, RecognitionRule, or RecognitionTypePolicy
    → Validate the exact Draft
    → enter a bounded synthetic media path and choose an enabled ResourceLibrary
    → run the real Parser → RecognitionRule → RecognitionTypePolicy path with zero I/O
    → inspect matched rule/type, priority/score explanations, downstream policy references,
      revision identity, side effects, and safe recovery
    → checked-activate only when both Local setup and Strategy Test evidence are current
    → new runtime work consumes the immutable Active revision through the existing snapshot path

## Visible Success Outcome

- Web and API expose the three recognition object collections from one immutable revision read.
- Guided object changes remain optimistic-version checked, audited, and return the revision to
  Draft; whole-document validation remains the canonical cross-reference validator.
- Strategy Test consumes the exact Validated revision ID/version/digest and an enabled
  ResourceLibrary, uses the production parser/recognition/policy resolver, and persists bounded
  secret-free evidence visible after reload.
- Evidence distinguishes matched, ambiguous, and unrecognized outcomes and shows bounded reasons,
  matched rules/alternatives, resolved policy IDs, and whether RecognitionType identity survived
  downstream policy reuse.
- Checked activation requires current passed Local setup evidence and current completed Strategy
  Test evidence. Active/runtime publication remains the existing immutable snapshot path.

## Failure and Recovery

- Invalid object shape, unsafe regex, missing reference, duplicate ID, stale version/digest, wrong
  revision status, disabled/unknown ResourceLibrary, or oversized/NUL path fails closed.
- Engine/configuration failures persist bounded failed evidence with exact revision identity,
  `sideEffects=none`, `retrySafe=true`, and an explicit correction/rerun action.
- Draft edits make prior evidence visibly stale. No test, validation, activation, Preview, retry,
  provider request, scan, plan, execute, or file mutation occurs automatically.
- Recovery is: correct the Draft, Validate it, explicitly rerun Strategy Test (and Local setup when
  stale), review the evidence, then explicitly checked-activate.

## Acceptance Criteria

- [ ] RecognitionType/Rule/TypePolicy CRUD is available through authenticated API and Web, with
      bounded validation, optimistic versions, audit, and reference-blocked deletion.
- [ ] Cross-object output/type/policy references and rule priority semantics are validated by the
      canonical runtime validator before Strategy Test or activation.
- [ ] Synthetic Strategy Test uses the exact revision and real production Parser, RecognitionRule
      engine, and RecognitionTypePolicy resolver without constructing Storage or Provider adapters.
- [ ] Success and actionable failure evidence is durable, bounded, secret-free, reloadable, and
      stale when revision version/digest changes.
- [ ] Checked activation rejects absent, failed, or stale Strategy Test evidence in addition to the
      accepted Local setup requirement.
- [ ] A regression proves RecognitionType C can resolve NamingPolicy A and ClassificationPolicy A
      while the result remains RecognitionType C.
- [ ] Web exposes entry, state, actions, outcomes, failures, and explicit recovery without requiring
      CLI or direct API composition.
- [ ] Existing immutable Active/Job/Worker pinning, default DryRun, and zero-mutation boundaries
      remain green.

## Technical Scope

1. Extend the managed revision projection/editor for only `recognitionTypes`, `recognitionRules`,
   and `recognitionTypePolicies`.
2. Add one bounded exact-revision Strategy Test application service/evidence record and SQLite
   persistence owned by the configuration repository.
3. Add authenticated API and existing vanilla Web UI surfaces using the same application service.
4. Tighten checked activation to require current Strategy Test evidence as well as current Local
   setup evidence.
5. Add focused Engine/Persistence/API/Web/runtime and C-identity regressions; update factual
   progress only after implementation tests pass.

## Non-goals

- No Metadata Provider/Policy, Naming, Classification, Organize, Schedule, remote Storage, or secret
  editing UI.
- No live metadata lookup, NFO/file read, directory scan, Storage construction, Planner,
  OrganizerExecutor, Preview queue, execute authority, overwrite, delete, or automatic activation.
- No browser framework, generic form builder, configuration-store replacement, or unrelated
  refactor.
- Do not declare Phase 22.4 or the broader Phase 22 closed from the implementation report.

## Required Validation

Run focused recognition configuration/Strategy Test/API/Web tests, related configuration snapshot
and runtime pin tests, the complete offline suite, Ruff lint/format, compileall, `pip check`,
`git diff --check`, documentation links, FFmpeg/FFprobe production audit, and business-filesystem
mutation-boundary audit. Report actual counts and skips.
