# Phase 18.4.1 — Notification Delivery Lease + Crash Recovery

## Goal

Close the accepted Phase 18.4 crash window where a process can stop after claiming an Outbox row
and leave it permanently `delivering`. Add a bounded delivery lease with safe at-least-once
recovery and auditable duplicate-delivery semantics. Do not start remote organize execution.

## Scope

- Configurable positive `notifications.deliveryLeaseSeconds`, default 300 seconds.
- Fresh claims remain exclusive; expired `delivering` rows may be atomically reclaimed.
- Reclaim preserves delivery/event/body identity, increments attempts, and uses existing retry and
  dead-letter rules without automatic attempt reset.
- Stable `X-MediaFlow-Delivery` documents at-least-once receiver deduplication.
- CLI/API expose redacted operational metadata and read-only stale inspection.
- No Storage, strategy, Planner, OrganizerExecutor, or remote execution changes.

## Validation

Fresh/expired lease, restart, concurrent reclaim, exhausted attempt, explicit dead-letter requeue,
configuration default/custom/invalid values, visibility, zero mutation, all regressions and quality
checks.

## Result

PASS — implemented and accepted before Phase 18.5.
