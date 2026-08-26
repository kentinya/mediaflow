# Phase 22.4-F1 — Web Strategy Evidence Rendering Correction

## Review Finding

The independent review of the Phase 22.4 implementation found two current-scope P1 Web completion
gaps.

First, the API and persisted `RecognitionStrategyTestEvidence` already contain bounded
`matchedRules` and `alternatives`, but the Web renderer only shows the winning `ruleId`, aggregate
score/confidence under a misleading `Priority / score` label, and reasons. It does not render the
bounded matched-rule list or alternatives.

For an ambiguous result, the operator can see that the result is ambiguous but cannot see which
RecognitionTypes/rules tied or what priority/score each candidate had. For a matched result with
multiple matching rules, the operator cannot inspect the rule ordering evidence promised by the
journey. This makes the current Web outcome and recovery path incomplete even though the backend
evidence is durable and reloadable.

Second, the generic revision action treats a current passed Local setup check as sufficient to
label and submit `Activate checked revision`. When Strategy Test evidence is absent, failed, or
stale, that visible action sends `checked=true` and can only fail at the backend gate. The backend
remains fail-closed, but the Web action matrix violates the promised rule that checked activation
is exposed only when both evidence records are current and accepted.

This is a focused correction inside Phase 22.4. Do not expand the scope or begin a later Phase.

## User Journey

```text
Configuration revision
→ open the validated revision
→ run or reload Recognition Strategy Test evidence
→ inspect matched rules and alternatives
→ understand matched / ambiguous / unrecognized outcome
→ correct the Draft when required
→ explicitly Validate, rerun, review, and checked-activate
```

## Required Correction

1. Extend the existing vanilla Web `renderRecognitionStrategyTest` surface to render bounded,
   secret-free `matchedRules` and `alternatives` from the persisted evidence.
2. Show rule ID, RecognitionType, priority, and score for each rendered entry, with a clear
   bounded/truncated indication if the evidence list is limited.
3. Use both current passed Local setup evidence and current completed Strategy Test evidence for
   every Web checked-activation label/action. Do not show or submit a checked action when either
   requirement is absent, failed, or stale.
4. Preserve the existing stale, failure, `sideEffects=none`, `retrySafe`, and `nextAction`
   recovery messaging. Rendering must remain read-only and must not trigger a rerun or activation.
5. Keep the existing API/application/persistence authority. Do not add a second evidence shape,
   browser framework, provider lookup, Storage construction, scan, Preview, organize, execute,
   overwrite, delete, or automatic retry.

## Acceptance Criteria

- [ ] A current completed Strategy Test with multiple matched rules visibly shows each bounded
      matched rule's ID, RecognitionType, priority, and score.
- [ ] An ambiguous Strategy Test visibly shows each bounded alternative's RecognitionType,
      priority, and score, so the operator can diagnose the tie without inspecting API/SQLite.
- [ ] An unrecognized result remains visibly unrecognized and still shows bounded reasons and the
      explicit recovery action; no fabricated winner or policy is displayed.
- [ ] Reloading the revision renders the same persisted evidence without an API mutation or
      background rerun.
- [ ] Stale and failed evidence retains the existing actionable correction/Validate/rerun
      guidance and zero-side-effect/retry-safe fields.
- [ ] No Web control is labelled or submitted as checked activation unless both current passed
      Local setup evidence and current completed Strategy Test evidence are present.
- [ ] When either checked requirement is absent, failed, or stale, the Web shows the applicable
      setup/test recovery action; the existing unchecked compatibility action, when retained,
      remains explicitly labelled as unchecked.
- [ ] Web/API behavior continues to use the same evidence and checked-activation rules; the
      existing explicitly labelled unchecked compatibility path is not broadened.
- [ ] Add focused Web/API regression coverage for matched, ambiguous, unrecognized, stale, and
      failed evidence rendering/action shapes.
- [ ] Existing Phase 22.4 focused tests, complete offline suite, lint/format, compileall,
      `pip check`, diff check, FFmpeg/FFprobe audit, and filesystem mutation-boundary audit remain
      green.

## Non-goals

- No change to RecognitionRule priority semantics or the production recognition engine.
- No new configuration object kinds, metadata/provider work, remote setup, naming/classification/
  organize editing, or task-stage recovery.
- No removal or expansion of the existing explicitly labelled unchecked compatibility activation.
- Do not declare Phase 22.4 or Phase 22 closed from an implementation report.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 22.4-F1 Result

PASS / FAIL

## Web Evidence

## Recovery and Safety

## Regression

## Remaining Phase 22.4 Review Status
