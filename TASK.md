# Phase 22.5-E-F1 — Files Detail Continuation Rendering Correction

This Task follows [the authoritative development workflow](docs/development-workflow.md).

```text
Status: READY FOR HIGH RE-REVIEW (focused correction inside Phase 22.5-E)
Rejected checkpoint: 08dfd4f921728755209b6d52347d28f221121c47
High Audit: FIX REQUIRED — 2026-08-27
Preceding closed checkpoint: 55769be58a75596461879994560a0c58c3a7c9dc (Phase 22.5-D PASS / CLOSED)
Reviewed Phase 22.5-E Task: Task/phase-22.5-e-single-item-metadata-correction-dryrun-continuation.md
```

## Review Finding

Independent High Review of `08dfd4f921728755209b6d52347d28f221121c47` accepted the Application,
API, persistence, and Worker behavior of the single-item Metadata correction DryRun continuation. It
rejected the checkpoint because the promised operator-facing surface does not exist at runtime.

`renderMetadataContinuation` in `mediaflow/interfaces/operator_ui.py:896` builds its section and
`return`s it. Its only caller, `mediaflow/interfaces/operator_ui.py:1253`, invokes it as a statement
and discards the returned node, so nothing is ever attached to `detailContent`. Every sibling
renderer in that file (for example `renderFileReMatchForm`) appends internally; this one does not.

Consequently the Files detail page never renders the continuation heading, the source
Task/TaskItem/correction-identity/snapshot cards, the one-item `DRY_RUN_ONLY` /
`Storage mutation: NONE` disclosure, the `Continue as DryRun` entry point, the queued / running /
completed / failed / stale / cancelled status text, the failure category, failure, recovery and next
action text, the linked Job and Task/Result controls, the single-item retry control, or the stale
requeue control. The only visible trace is one extra `Continuation` column in the Related reviews
table. `confirmMetadataContinuation` and `confirmStaleMetadataContinuation` are therefore
unreachable dead code.

The Web half of the journey required by `TASK.md` (Phase 22.5-E) UX acceptance, by
`docs/product-experience.md` journey D, and by AGENTS.md product rules 5 (Web is the final
management surface) and 6 (API/Web parity) is not delivered.

The only Web coverage,
`tests/test_metadata_correction_continuation.py::test_operator_ui_action_is_explicit_and_stateful`,
asserts substrings that live inside that dead function, so it passes while the section is never
attached. Required test 8 of Phase 22.5-E is therefore not proven.

This is a focused correction inside Phase 22.5-E. Do not expand the scope, change accepted
Application/API/persistence/Worker behavior, or begin a later Slice or Phase.

## User Journey

```text
Files detail
→ open a File whose Metadata correction is resolved and whose source TaskItem is eligible
→ see the continuation section with source Task/TaskItem, correction identity, pinned snapshot,
  one-item scope, DryRun-only authority and zero Storage mutation
→ explicitly confirm Continue as DryRun
→ reload and see queued / running / completed / failed / stale / cancelled state with next action
→ open the linked continuation Job and the new DryRun Task/Result
→ retry only this correction, or explicitly requeue a stale continuation
```

## Required Correction

1. Attach the continuation section to the Files detail page. Follow the existing renderer
   convention in `operator_ui.py`: append inside the render function, or append the returned node at
   the call site. Both current branches (no continuation yet, and an existing continuation) must
   reach the page.
2. Keep the existing visibility predicate unchanged: the section appears only for a
   `metadata_correction` related review with `status === 'resolved'` and either `canContinue` or an
   existing `continuation`, using the exact `correctionVersion` supplied by the API.
3. Keep the already-accepted API payload, permission, identity, and idempotency behavior. The
   submission must continue to send only `reviewId` and `expectedCorrectionVersion` to
   `POST /api/v1/files/{fileId}/continue-dry-run`, and the stale action must continue to use
   `POST /api/v1/jobs/{jobId}/requeue-stale`.
4. Keep rendering read-only. Opening or reloading the File must not submit, queue, requeue, cancel,
   or invoke a Provider; the `Continue as DryRun`, retry, and requeue controls must remain behind
   the existing explicit confirmation step with its keep-unchanged escape.
5. Keep every existing bounded, secret-free string, the DryRun-only and zero-mutation disclosure,
   the duplicate/queue-full conflict `details` rendering, and the text-only DOM helpers. Do not add
   a frontend framework, a second continuation shape, or new API fields.

## Acceptance Criteria

- [x] An eligible resolved correction with no continuation renders the continuation section and one
      `Continue as DryRun` control on the Files detail page.
- [x] That section visibly shows the source Task, source item, correction ID, correction identity,
      configuration snapshot ID and digest, `Items selected: 1`, `Authority: DRY_RUN_ONLY`, and
      `Storage mutation: NONE` before submission.
- [x] A queued, running, completed, failed, stale, and cancelled continuation each renders a
      visibly distinct status line plus its next action, and failure additionally renders the
      bounded error and recovery text.
- [x] The linked continuation Job control is always rendered; the linked Task/Result control is
      rendered exactly when the continuation has a Task.
- [x] The single-item retry control is rendered only for a failed or cancelled continuation whose
      review still reports `canContinue`; the requeue control is rendered only for the stale
      display status.
- [x] Confirmation for both submission and stale requeue still requires an explicit second click and
      still offers an explicit keep-unchanged option.
- [x] Rendering and reloading perform no submission, queue mutation, Provider call, or Storage
      access; the accepted API and Application semantics are unchanged.
- [x] Focused Web regression coverage fails if the continuation section is not attached to
      `detailContent`, and covers the no-continuation, queued/running, completed, failed, stale, and
      cancelled shapes. A substring-only assertion inside the render function is not sufficient
      evidence.
- [x] `tests/test_metadata_correction_continuation.py` and the complete offline suite remain green
      with no weakened or removed assertion.
- [x] RecognitionType C remains C, no execute authority is granted, and no media mutation occurs on
      any path.

## Non-goals

- No change to the accepted admission, idempotency, snapshot pinning, Worker pipeline, persistence
  schema, or API contract from `08dfd4f921728755209b6d52347d28f221121c47`.
- No Provider switching, Provider CRUD, credential UI, or Secret Store.
- No generic Task resume endpoint or UI, sibling replay, or broader per-item checkpoint recovery.
- No organize execution, execute authorization, automatic continuation, or automatic retry.
- No frontend framework, unrelated Web refactor, or Phase 22.6 work.

## Safety and Architecture Invariants

- Rendering and reloading mutate nothing: no Storage, no queue, no Task, no Provider request.
- Only OrganizerExecutor may mutate Storage, and this correction grants no execute authority.
- The exact source configuration snapshot, not current Active configuration, remains the input to a
  continuation.
- Credentials, endpoints, raw Provider responses, headers, cookies, exception text, and private
  paths must not enter Web, API, evidence, logs, tests, or commits.

## Required Tests

1. Focused Web coverage that proves the continuation section is reachable on the Files detail page
   and that would fail against `08dfd4f921728755209b6d52347d28f221121c47`.
2. Focused Web coverage for the no-continuation, queued/running, completed, failed, stale, and
   cancelled control and status shapes, including the retry and requeue visibility rules.
3. Existing Phase 22.5-E API/Worker/persistence tests remain unchanged and green, including
   concurrent duplicate admission, snapshot pinning, source/sibling preservation, and zero mutation.
4. Regression: Phase 21 Metadata correction and Files detail linkage, Phase 22.5-B/C/D evidence and
   recovery, and Phase 22.4 RecognitionType C snapshot behavior remain unchanged.
5. Complete offline suite plus the zero-mutation and forbidden-dependency audits.

## Validation

Run the focused continuation and Files detail Web/API tests, the related Phase 21 and Phase 22
regressions, and the complete offline suite. Run Ruff lint/format, compileall, `pip check`, both
example configuration validations, wheel build/smoke, documentation local-link validation,
`git diff --check`, the FFmpeg/FFprobe production audit, the business-filesystem mutation audit, and
the private configuration checks.

## Documentation

Update `docs/product-experience.md` so the Phase 22.5-E section no longer carries the Web
`FIX REQUIRED` qualifier once the surface is actually delivered, and record the correction in
`docs/progress.md` and `docs/roadmap.md`. Preserve the existing `FIX REQUIRED` record and the
rejected SHA. Keep Provider switching, generic Task resume, and broader per-item checkpoint recovery
explicitly TARGET.

## Closure Checklist

- [x] Implementation workspace/session preflight records worktree, `.git`, index, sandbox, and
      approval mode.
- [x] Implementation capability mode is classified according to the authoritative workflow.
- [x] The rejected Phase 22.5-E checkpoint `08dfd4f921728755209b6d52347d28f221121c47` and its
      `FIX REQUIRED` audit are recorded in `docs/progress.md` and are not amended or rewritten.
- [x] No prior accepted implementation or closure record remains uncommitted before implementation
      begins.
- [x] Implementation and required focused/full quality gates pass with actual evidence.
- [x] Commit manifest contains every required file and no unrelated/private file.
- [x] `config/alist.json` remains ignored, untracked, unstaged, unread, and uncommitted.
- [ ] Coherent correction checkpoint created: `Commit SHA: ________________________________`.
- [ ] High Review inspected that exact SHA: `High Audit: _________________________________`.
- [ ] Progress and roadmap record final Status / Commit SHA / High Audit for Phase 22.5-E closure.
- [ ] Next Slice has not started before every gate above is complete.
- [ ] Required push state is recorded.

## Completion Report

Use the AGENTS.md completion structure and additionally report:

- the exact call-site or renderer change that attaches the section, quoted with file and line;
- the rendered controls and status text for each continuation state;
- the new Web assertion and proof that it fails against the rejected SHA;
- confirmation that no accepted Application/API/persistence/Worker behavior changed;
- zero-mutation, zero-Provider-on-view, and DryRun-only evidence.
