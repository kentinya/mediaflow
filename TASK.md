# Phase 22.3R5 — Checked Local Setup to Pinned DryRun Result Acceptance

## Previous Slice Status

Phase 22.3R4-F1 passed independent review on 2026-08-25. Persisted setup-check recovery and the
enabled Local-backed Web selection/action boundary are accepted. Do not redesign or repeat them.

Phase 22.3 remains open for one final combined acceptance gap: existing tests separately prove
checked activation, Preview Job pinning, and Web → Worker → Task/Result pinning, but the production
journey beginning with successful guided Local setup evidence has not been proven through the same
immutable snapshot chain. Phase 22.4 remains prohibited.

## User Problem

After an operator validates and checks a Local setup, they need confidence that the exact checked
configuration they activate is the one used by the queued DryRun Preview and its eventual Task and
Result—even if another revision becomes Active before the Worker runs. The UI saying “Active” is not
enough unless runtime work proves the same identity.

## User Journey

    open one exact Validated Local setup revision
    → explicitly run Local setup check and receive current passed evidence
    → review and checked-activate that exact revision
    → explicitly queue the first DryRun Preview
    → optionally activate a later valid revision before the Worker claims the queued Job
    → Worker processes the queued Job using its saved snapshot
    → operator opens Job/Task detail and sees the checked revision identity and DryRun result

## User-visible Outcome

- Checked activation, queued Preview Job, Worker-created Task, and Result all belong to the original
  checked immutable revision.
- A later Active revision applies only to new work; it cannot silently rebind the queued Preview.
- Job/Task detail remains inspectable and the Preview result is visibly DryRun.
- No media mutation or execute authority is introduced.

## Failure and Recovery

- Missing, stale, or failed setup evidence cannot checked-activate; preserve existing actionable
  correction/recheck behavior.
- If the queued Job's saved revision is missing, corrupt, unsupported, or runtime-invalid, preserve
  the accepted Phase 22.2 saved-revision failure behavior: fail before workflow construction, persist
  bounded reason/durable state/side effects/retry safety/next action, and perform no media I/O.
- A later unhealthy or different Active revision must not change the queued Job's saved identity.
- Recovery creates explicit new work after configuration repair; it does not rewrite or silently
  retry the original Job.

## UX Acceptance Criteria

- [ ] The production API/Web entry path can run a successful Local setup check and checked-activate
      the exact evidence revision.
- [ ] Queueing Preview after checked activation stores that revision ID and digest on the Job.
- [ ] Activating a second revision before Worker claim does not alter the first Job's saved pin.
- [ ] The production Worker creates a Task with the first Job's exact revision ID and digest.
- [ ] The resulting item/Result remains associated with that Task and reports `dry_run`.
- [ ] API/Web Job and Task detail expose enough saved identity/status to explain which configuration
      ran; no automatic queue, retry, or execute occurs.
- [ ] Storage mutations and execute authorization remain zero/false throughout this journey.

## Technical Scope

1. Inspect and reuse the existing checked activation endpoint, setup-check evidence repository,
   Preview Job admission, immutable Job snapshot fields, production Worker saved-revision resolver,
   Task persistence, Result persistence, and Job/Task Web detail.
2. Add one production-entry-point integration acceptance test that starts from current passed Local
   setup evidence, uses checked activation, queues Preview, changes Active before claim, runs the
   production Worker, and verifies Job → Task → item/Result identity and DryRun behavior.
3. Add the minimum Web/API contract assertions needed to prove the saved revision/status is visible.
4. Modify production wiring only if the combined test reveals a current-scope integration defect;
   use the smallest compatible correction and targeted regression.

## Non-goals

- No new configuration model, remote Storage editor/check, policy CRUD, Strategy Test UI, Phase
  22.4, browser framework, or visual redesign.
- No change to Scanner, Parser, Recognition, Metadata, Naming, Classification, Planner,
  OrganizerExecutor, Storage adapters, setup-check capacity/deadline, or saved-revision semantics
  unless an actual combined-chain defect requires the smallest integration fix.
- No real execute, overwrite, delete, auto-preview, auto-worker, auto-retry, or mutation authority.
- Do not duplicate existing Phase 22.2 failure matrices merely to increase test count.

## Required Tests

1. Guided Local check passed → checked activate → Preview Job stores exact ID/digest.
2. Second activation before claim → original Job pin unchanged.
3. Production Worker → Task pin equals original Job pin, not current Active.
4. Result is `dry_run`, linked to the pinned Task/item, with zero OrganizerExecutor mutation.
5. Job/Task API or Web detail exposes the saved identity/status without secret values.
6. Existing Phase 22.3 setup/recovery/action tests, Phase 22.2 snapshot/authority/saved-revision
   failure tests, and complete offline suite remain green.

## Validation

Run the focused combined journey, related configuration object/snapshot/status/admission/Web tests,
and the complete offline suite. Run Ruff lint/format, compileall, `pip check`, `git diff --check`,
documentation local-link audit, FFmpeg/FFprobe production audit, and the business-filesystem mutation
boundary audit. Report actual collected/passed/failed/skipped counts.

## Documentation

After implementation passes, update factual CURRENT evidence in `docs/progress.md` and only the
minimum architecture/product wording made stale by actual results. Do not mark Phase 22.3 closed;
independent review decides closure. Do not start Phase 22.4.

## Completion Report

Report the exact checked revision, queued Job pin, later Active identity, Worker Task pin, Result
status, zero-mutation evidence, real tests, deviations, and remaining risk. Do not declare Phase
CLOSED.
