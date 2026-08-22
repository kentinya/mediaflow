# Phase 18.4.1 — Notification Delivery Lease + Crash Recovery

## Goal

Close the accepted Phase 18.4 crash window where a process can stop after claiming an Outbox row
and leave it permanently `delivering`. Add a bounded delivery lease with safe at-least-once
recovery and auditable duplicate-delivery semantics. Do not start remote organize execution.

## 1. Delivery lease

- Add configurable positive `notifications.deliveryLeaseSeconds`, default 300 seconds.
- A fresh `delivering` row remains exclusively owned and cannot be reclaimed.
- A `delivering` row whose `updatedAt` is older than the lease may be atomically reclaimed.
- Reclaim increments the same attempt counter and preserves delivery/event identity and exact body.
- Concurrent workers must still produce exactly one successful claim.

## 2. Retry and exhaustion

- A reclaimed attempt uses the existing configured maximum-attempt and retry/dead-letter rules.
- Never retry forever and never reset attempts during automatic crash recovery.
- Preserve explicit dead-letter requeue as the only operation that resets attempts.
- Document that a crash after a receiver accepted the request but before local commit may redeliver;
  receivers must deduplicate by stable `X-MediaFlow-Delivery`.

## 3. Visibility

- CLI/API delivery metadata must expose `updatedAt`, attempts, and status, but never body or secrets.
- Add a read-only stale-delivery inspection command or filter if needed for operational diagnosis.
- Resident worker recovery remains bounded and graceful-shutdown compatible.

## 4. Safety

- Recovery may only change notification Outbox state and perform the configured Webhook request.
- It must never call Storage, Metadata, Planner, OrganizerExecutor, or authorize media execution.
- Configuration validation performs no network or Storage access.
- Remote organize/execute, Web UI, inbound Webhooks, and strategy changes remain out of scope.

## Required tests

- Fresh lease is not reclaimed; expired lease is reclaimed.
- Reclaimed attempt preserves IDs/body and increments attempts.
- Concurrent expired claims yield one owner.
- Exhausted reclaimed attempt becomes dead-letter after delivery failure.
- Explicit dead-letter requeue remains distinct and resets attempts.
- Configuration default/custom/invalid lease values.
- CLI/API redacted visibility, restart simulation, zero Storage mutation, and all regressions.

## Documentation and validation

Update README, examples, architecture, progress, roadmap, and product status where relevant. Run all
tests plus formatter, lint, compile, dependency, build, configuration, FFprobe/FFmpeg, and diff
checks.

## Out of scope

- Remote organize/execute authorization and scheduling.
- Web UI, user/role/TLS, inbound Webhooks, email/chat adapters.
- Storage, strategy engines, Planner, or OrganizerExecutor redesign.

## Final report

## Phase 18.4.1 Result

PASS / FAIL

## Lease Recovery

## At-least-once Semantics

## Security and Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
