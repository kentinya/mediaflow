# Phase 22.4-F2 — Strategy Outcome Recovery Guidance Correction

## Review Finding

Independent review of Phase 22.4-F1 confirmed that bounded matched-rule/alternative evidence is now
visible and every checked-activation Web entry uses the same current Local-check plus Strategy-Test
gate. Those accepted F1 behaviors must not be reimplemented.

One current-scope P1 recovery defect remains. A completed Strategy Test always persists
`nextAction="review the result, then explicitly checked-activate this revision"`, and the Web run
message always says to review before activation, even when the actual recognition outcome is
`ambiguous` or `unrecognized`. The production engine already supplies bounded reasons and warnings,
but the Web does not render the warnings. The operator can inspect the competing rules after F1,
but the visible recovery guidance still points toward activation instead of explaining how to
correct and retest the Draft.

This is the only blocker in this correction slice. Do not expand the scope or begin a later Phase.

## User Problem

When a synthetic Strategy Test is ambiguous or unrecognized, the operator can see the evidence but
is told to proceed toward activation and cannot see the existing warning that manual correction is
required. The result is diagnosable but not actionable.

## User Journey

```text
Validated configuration revision
→ run or reload Recognition Strategy Test
→ inspect outcome, matched rules, alternatives, reasons, and warnings
→ matched: review and explicitly activate when appropriate
→ ambiguous/unrecognized: edit the Draft, Validate, explicitly rerun, and review again
```

## User-visible Outcome

- `matched` evidence retains a bounded review/activation next action.
- `ambiguous` evidence explicitly tells the operator to correct rule priority/conditions, Validate,
  and rerun Strategy Test; competing evidence remains visible.
- `unrecognized` evidence explicitly tells the operator to correct the ResourceLibrary/rule match,
  Validate, and rerun Strategy Test; no winner or policy is fabricated.
- Existing bounded warnings are rendered as text beside reasons after reload.

## Failure and Recovery

- Failed and stale Strategy Test evidence keeps its existing correction/Validate/rerun guidance.
- Ambiguous and unrecognized are completed analysis outcomes, not infrastructure failures, but each
  must have an outcome-specific recovery instruction.
- Rendering remains read-only. No rerun, validation, activation, scan, Preview, or media mutation
  occurs automatically.
- The existing explicitly labelled unchecked compatibility activation remains unchanged. This
  correction does not redefine checked-activation eligibility; it corrects operator guidance.

## UX Acceptance Criteria

- [ ] After a matched test, persisted/API/Web `nextAction` describes review and explicit activation.
- [ ] After an ambiguous test, persisted/API/Web guidance says to inspect competing evidence,
      correct rule priority/conditions, Validate, and explicitly rerun.
- [ ] After an unrecognized test, persisted/API/Web guidance says to correct the ResourceLibrary or
      recognition rules, Validate, and explicitly rerun.
- [ ] The immediate Web completion notice is outcome-aware and does not recommend activation for
      ambiguous or unrecognized results.
- [ ] Bounded `warnings` are rendered with bounded reasons through text-only DOM construction and
      survive revision reload without a mutation or background rerun.
- [ ] Existing failed/stale evidence still shows category, side effects, retry safety, and its
      explicit recovery action.
- [ ] F1 matched-rule/alternative rendering and the shared dual-evidence checked-activation gate
      remain unchanged.

## Technical Scope

1. Derive a bounded, status-specific `RecognitionStrategyTestEvidence.next_action` from the real
   `RecognitionStatus` in the existing application service.
2. Render existing bounded recognition warnings in the existing vanilla Web Strategy Test surface.
3. Make the explicit post-run Web message outcome-aware using the returned persisted result.
4. Add focused persistence/API/Web regressions for matched, ambiguous, unrecognized, failed, stale,
   and reload behavior. Preserve the existing C-identity and zero-Storage regressions.
5. Run the focused configuration/Web/snapshot tests, complete offline suite, lint/format,
   compileall, `pip check`, diff check, FFmpeg/FFprobe audit, and business-filesystem mutation audit.

## Technical Acceptance Criteria

- [ ] Status-specific guidance is produced by the existing application evidence path and is the
      same value returned by API, stored in SQLite, and shown by Web after reload.
- [ ] Guidance and warning fields are bounded and secret-free; dynamic Web content uses
      `textContent`/existing safe helpers, never HTML injection.
- [ ] Strategy Test still constructs no Storage or Provider and performs zero media mutation.
- [ ] Recognition engine priority/status semantics, checked activation requirements, immutable
      Active/runtime snapshot behavior, and RecognitionType C preservation do not change.
- [ ] All required tests and quality gates pass with actual current-run evidence.

## Non-goals

- No change to RecognitionRule evaluation, ambiguity thresholds, or policy resolution.
- No requirement that every Strategy Test be matched before activation; the operator may
  intentionally test a negative case.
- No removal or expansion of unchecked compatibility activation and no new acknowledgement model.
- No Metadata/provider, remote Storage, Naming/Classification/Organize, scan, Preview, execute,
  task-stage recovery, browser framework, or later-Phase work.
- Do not declare Phase 22.4 or Phase 22 closed from an implementation report.

## Completion Report

Use the AGENTS.md Completion Report structure and additionally report:

## Phase 22.4-F2 Result

PASS / FAIL

## Outcome Guidance

## Recovery and Safety

## Regression

## Remaining Phase 22.4 Review Status
