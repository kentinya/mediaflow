# Phase 22.5-E — Single-Item Metadata Correction DryRun Continuation

This Task follows [the authoritative development workflow](../docs/development-workflow.md).

```text
Status: NEXT TASK
Preceding reviewed checkpoint: 55769be58a75596461879994560a0c58c3a7c9dc
Preceding High Audit: PASS — 2026-08-26
```

## User Problem

The Files detail journey can persist a manual Metadata correction and move the affected TaskItem
back to a recoverable pending state, but Web/API deliberately stop before continuing processing.
The only existing continuation mechanism is broad Task resume behavior, which may retry sibling
items and therefore is not a safe per-item product action.

This Slice lets an operator explicitly continue exactly one resolved Metadata correction through a
new DryRun pipeline and inspect a new Preview/Result. It does not switch Provider, resume the whole
source Task, or authorize media execution.

## User Journey

This advances `docs/product-experience.md` journey D:

```text
Files detail
→ inspect one resolved Metadata correction and its source Task/TaskItem
→ review the immutable source configuration and DryRun-only consequence
→ explicitly choose Continue as DryRun
→ queue one durable continuation for that item only
→ production pipeline consumes the resolved correction and pinned configuration
→ inspect the new Task/Result/Preview
→ correct and retry that item again if the new attempt fails
```

Entry points:

- authenticated Files API;
- existing vanilla Files detail Web view.

## User-visible Outcome

- An eligible resolved Metadata correction exposes one explicit `Continue as DryRun` action.
- The confirmation states that only the selected item is processed, source media is not mutated,
  and no execute authority is inherited.
- Submission returns one durable queued identity and a link or identifier for its new Task/Result.
- Reloading shows queued/running/completed/failed state without resubmitting.
- Success produces a new explainable DryRun Preview/Result linked to the source File, review,
  TaskItem, and exact source configuration snapshot.
- Source Task state, successful siblings, failed siblings, and source media remain unchanged.

## Failure and Recovery

- Wrong File/review/item linkage, unresolved or superseded correction, ineligible TaskItem state,
  missing/corrupt source snapshot, stale request identity, or malformed input fails before Provider
  or Storage access.
- Duplicate or concurrent submissions for the same resolved correction create at most one active
  continuation. The loser reloads the durable current continuation.
- Queue/claim/worker failure remains durable and actionable. The resolved correction and source
  item are not discarded or falsely marked successful.
- Provider or downstream analysis failure is recorded on the new single-item attempt with bounded,
  secret-free recovery guidance. Retrying it must not replay source siblings.
- Recovery is explicit: inspect the current continuation/result, repair the stated input or runtime
  condition, then retry only this correction when eligible.

## UX Acceptance Criteria

- [ ] Files detail exposes the action only for the exact current resolved correction whose linked
      TaskItem is eligible for Metadata continuation.
- [ ] The action identifies the source Task/item, pinned configuration, selected correction, and
      DryRun-only effect before submission.
- [ ] One explicit submission queues exactly one item; no sibling or previously successful item is
      selected or reprocessed.
- [ ] The worker consumes the exact immutable configuration snapshot associated with the source
      Task and the exact resolved correction.
- [ ] A new Task/Result/Preview is durable, reloadable, and linked back to the source File/review/item.
- [ ] The new attempt is always DryRun, including when the source Task had execute authorization.
- [ ] Queued, running, completed, failed, stale, duplicate, and snapshot-unavailable outcomes are
      visibly distinct and provide an explicit next action.
- [ ] API and Web use the same Application admission, permission, identity, and idempotency rules.
- [ ] RecognitionType C remains C and its configured downstream policy references remain unchanged.
- [ ] Merely viewing/reloading the page performs no Provider request and queues no work.
- [ ] All paths perform zero media mutation and grant no OrganizerExecutor execute authority.

## Technical Scope

1. Add one bounded durable correction-continuation identity that binds:
   - File ID;
   - resolved Metadata correction review ID and immutable correction identity/version;
   - source Task and TaskItem IDs;
   - source configuration snapshot ID and digest;
   - DryRun-only execution mode.
2. Add one Application action that reloads and validates those server-side relationships and queues
   exactly one eligible item. Client input must not select arbitrary Provider, policy, path,
   sibling item, snapshot, or execute mode.
3. Reuse existing Task/Result/Job persistence where it can represent this truthfully. Add the
   smallest migration only if durable linkage/idempotency cannot be expressed in the existing
   schema; do not create a parallel task system.
4. Add one worker command/path that processes only the bound item through the existing production
   Parser → Recognition → TypePolicy → Metadata → Naming → Classification → Planner path using the
   resolved `MetadataCorrectionSelection` and exact pinned snapshot.
5. Persist a new DryRun Task/TaskItem/Result/Preview and bounded source linkage. Preserve the source
   Task and all source sibling states.
6. Add an authenticated Files API action using the existing DryRun submission permission. Return
   bounded conflict/stale/recovery representations from the shared Application behavior.
7. Add the minimal Files detail Web action and status/result rendering using existing text-only DOM
   helpers. Do not add a frontend framework.

## Non-goals

- No Provider switching, Provider CRUD, second Provider implementation, credential UI, Secret
  Store, arbitrary Provider selection, or implicit Provider fallback.
- No generic Task resume endpoint/UI and no reuse of broad resume semantics that can replay siblings.
- No organize execution, execute authorization, automatic continuation, automatic retry, or media
  mutation.
- No new correction fields, candidate matching redesign, cache redesign, or Provider telemetry.
- No Naming/Classification/Organize policy editing, destination correction, automation scheduling,
  Phase 22.6 work, or unrelated refactor.

## Safety and Architecture Invariants

- Parser, Recognition, Metadata, Naming, Classification, Planner, and DryRun continuation do not
  mutate Storage.
- Only OrganizerExecutor may mutate Storage, and this Slice never grants it execute authority.
- Source execute authorization is never copied, inferred, or widened.
- The exact source snapshot, not current Active configuration, is consumed by the new attempt.
- RecognitionType is immutable across reuse of Metadata/Naming/Classification policies.
- One-item continuation cannot select, reset, or replay source siblings.
- Credentials, endpoints, raw Provider responses, headers, cookies, exception text, and private
  paths do not enter API, Web, evidence, logs, tests, or commits.

## Required Tests

Product acceptance:

1. A resolved query correction continues exactly one item and produces a linked new DryRun
   Task/Result/Preview through the production pipeline; source Task/item/siblings remain unchanged.
2. A resolved direct-ID correction uses the production detail path without an extra search and
   preserves RecognitionType C plus all configured policy identities.
3. A source Task with execute authorization still creates a DryRun-only continuation and performs
   zero Storage mutation.
4. Changing Active configuration after the source Task does not change the snapshot consumed by
   continuation; missing/corrupt/unreachable pinned snapshots fail before pipeline construction.
5. Wrong/stale File-review-item linkage, unresolved/superseded correction, ineligible item state,
   or malformed request is rejected before Provider/Storage access.
6. Concurrent duplicate submissions create one durable continuation and one actionable conflict;
   worker claim fencing/idempotency prevents duplicate execution.
7. Provider/downstream failure is durable and actionable; retry remains single-item and never
   replays successful or unrelated siblings.
8. Web visibility, confirmation, payload, queued/running/completed/failed rendering, and links match
   API semantics; page view/reload never auto-submits or invokes the Provider.

Regression:

- Phase 21 Metadata correction, Files detail linkage, and CLI Task resume behavior remain unchanged.
- Phase 22.5-B/C/D live evidence, candidate confirmation, correction, CAS, and recovery remain
  unchanged.
- Phase 22.4 RecognitionType C identity and exact snapshot behavior remain unchanged.
- Complete offline suite and zero-mutation/forbidden-dependency audits.

## Validation

Run focused Application/persistence/worker/API/Web tests, the related Phase 21 and Phase 22
regressions, and the complete offline suite. Run Ruff lint/format, compileall, `pip check`, both
example configuration validations, wheel build/smoke, documentation local-link validation,
`git diff --check`, FFmpeg/FFprobe production audit, business-filesystem mutation audit, and private
configuration checks.

## Documentation

Update product experience, requirements/status, architecture CURRENT/TARGET, roadmap, progress,
and operator guidance only for behavior actually implemented. Preserve historical audit records.
Keep Provider switching, generic Task resume, and broader per-item checkpoint recovery explicitly
TARGET.

## Closure Checklist

- [ ] Implementation workspace/session preflight records worktree, `.git`, index, sandbox, and
      approval mode.
- [ ] Implementation capability mode is classified according to the authoritative workflow.
- [x] Preceding Phase 22.5-D checkpoint `55769be58a75596461879994560a0c58c3a7c9dc`
      is `PASS / CLOSED` after independent High re-review.
- [ ] No prior accepted implementation or closure record remains uncommitted before implementation
      begins.
- [ ] Implementation and required focused/full quality gates pass with actual evidence.
- [ ] Commit manifest contains every required file and no unrelated/private file.
- [ ] `config/alist.json` remains ignored, untracked, unstaged, unread, and uncommitted.
- [ ] Coherent implementation checkpoint created: `Commit SHA: ________________________________`.
- [ ] High Review inspected that exact SHA: `High Audit: _________________________________`.
- [ ] Progress and roadmap record final Status / Commit SHA / High Audit.
- [ ] Next Slice has not started before every gate above is complete.
- [ ] Required push state is recorded.

## Completion Report

Use the AGENTS.md completion structure and additionally report:

- exact one-item admission and idempotency identity;
- pinned snapshot and correction consumption evidence;
- source/sibling preservation and zero-mutation evidence;
- visible success/failure/recovery outcomes;
- Provider search/detail and worker execution counts;
- CURRENT one-item DryRun continuation versus deferred Provider switching/general recovery.
