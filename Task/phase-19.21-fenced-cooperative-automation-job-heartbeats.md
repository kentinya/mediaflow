# Phase 19.21 — Fenced Cooperative Automation Job Heartbeats

## Goal

Prevent an old Worker from refreshing or completing a Job after that Job has
been explicitly requeued and claimed again. Add bounded cooperative heartbeats
so stale visibility reflects recent workflow item boundaries without claiming
to interrupt in-flight external calls.

## Scope

### 1. Persisted opaque claim fencing

- Migrate the Runtime schema forward by one version.
- Add a nullable opaque cryptographically random claim token to AutomationJob
  persistence.
- Every successful Pending → Running claim creates a new token.
- Requeue clears the old token; a later claim receives a different token.
- Terminal Worker writes require both Running status and the matching token.
- A stale Worker with an obsolete token must fail closed and must not change the
  Job owned by another Worker.
- Tokens are internal authority: never expose them through CLI, API, UI, logs,
  notifications, configuration snapshots, errors, or audit records.

### 2. Cooperative heartbeat

- Add one repository operation that atomically verifies Job ID, Running status,
  and claim token, refreshes `updated_at`, and returns cancellation state.
- The Worker invokes it through its existing cooperative callback before/between
  workflow items and once after the handler returns before terminal commit.
- Do not create a background heartbeat thread.
- Do not claim that heartbeat remains fresh during a blocking Metadata/Storage
  call; stale age remains an observation.

### 3. Fenced terminal completion

- Replace the Worker's unconditional terminal update with a conditional fenced
  completion operation.
- Completed, Failed, and Cancelled behavior and notification semantics otherwise
  remain unchanged.
- If ownership is lost, the old Worker must not publish a terminal notification
  for the newer claim and must return the currently persisted Job state.

### 4. Explicit stale requeue compatibility

- Keep requeue local-only and explicitly age-guarded.
- Requeue must atomically clear claim ownership.
- No API or UI requeue/retry/recovery control is added.
- No automatic requeue or timeout cancellation is added.

### 5. Safety and redaction

This phase must not change Parser, Recognition, Metadata, Naming,
Classification, Planner, OrganizerExecutor, or Storage behavior.

Claim tokens must be structurally excluded from all operator-facing
serialization. Existing DryRun and explicit execute boundaries remain intact.

## Tests

Add focused tests covering:

- schema migration from the current version and fresh-database creation
- each claim receives a non-empty unique opaque token
- cooperative heartbeat refreshes only the matching Running claim
- heartbeat observes cancellation atomically
- wrong/old token cannot heartbeat or complete
- requeue clears ownership and a second claim gets a different token
- old Worker cannot overwrite the second Worker's state or publish its terminal
  notification
- successful/failing/cancelled Worker terminal behavior remains compatible
- API, UI, CLI, logs, notifications, snapshots, and errors never expose token
- stale query responds to heartbeat age while retaining its configured bound
- no Storage or media workflow semantic changes
- all existing automation, task, API/UI, persistence, and safety regressions

Run all tests plus configured formatter, linter, compile, dependency,
configuration, forbidden-dependency, and isolated wheel gates.

## Documentation

Update:

- `README.md`
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/progress.md`
- `docs/roadmap.md`
- `docs/release.md` if operator guidance changes

## Out of Scope

- automatic stale recovery or lease expiry
- background heartbeat threads
- API/UI requeue, retry, force-cancel, or recovery
- distributed leader election or Worker registry
- rollback or exactly-once external Storage guarantees
- Task heartbeat redesign
- OIDC, Secret Store, TLS, or UI redesign

## Completion Report

Finish with:

## Phase 19.21 Result

PASS / FAIL

## Claim Fencing

## Cooperative Heartbeat

## Redaction

## Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
