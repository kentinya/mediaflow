# Phase 18.4 — Durable Notification Outbox + Signed Webhooks

## Goal

Add asynchronous, durable notifications for accepted Automation Job and Scheduler events. Persist
an Outbox before delivery, send signed Webhooks through a dedicated NotificationWorker, and apply
bounded retry/dead-letter behavior. Do not block media workflows on network delivery and do not
expose remote organization execution.

## 1. Notification events and configuration

- Support events: `job.completed`, `job.failed`, `job.cancelled`, and `schedule.emitted`.
- Configure multiple Webhooks with unique ID, HTTPS URL, enabled flag, subscribed events,
  `secretEnv`, timeout, maximum attempts, and base/max retry delays.
- Secrets remain environment-owned; config validation checks names but needs no secret value.
- Reject literal secrets, credentials in URLs, fragments, unsupported schemes/events, duplicate IDs,
  invalid retry values, and unknown fields that imply execute behavior.

## 2. Durable Outbox

- Persist one delivery per matching Webhook/event with deterministic idempotency identity.
- Statuses: pending, delivering, retry, delivered, dead-letter.
- Store canonical event JSON, attempts, next-attempt, timestamps, and redacted failure category.
- Atomically claim due deliveries so multiple NotificationWorkers cannot send the same claim.
- Existing Job/Schedule success must not be changed by notification availability or delivery failure.
- Upgrade SQLite compatibly and preserve all accepted Task/Job/Schedule state.

## 3. Signed Webhook delivery

- Send deterministic UTF-8 JSON with content type, event ID/type, UTC timestamp, and delivery ID.
- Sign `timestamp + '.' + exact body` using HMAC-SHA256 and the configured environment secret.
- Never persist/log/return the secret, Authorization, response body, cookies, or signed URL data.
- Treat 2xx as delivered; retry timeout/connection/429/5xx with bounded exponential delay.
- Treat other 4xx as dead-letter; never retry forever and never follow cross-host redirects.
- Inject transport in tests; unit tests make no Internet requests.

## 4. Worker, CLI, and API

- Add `mediaflow notifications list [--status ...] [--limit N]`.
- Add `mediaflow notification-worker run-next` and bounded resident `run` with graceful shutdown.
- Add explicit dead-letter requeue; no silent automatic resurrection.
- Add authenticated read-only `GET /api/v1/notifications`.
- CLI/API output contains delivery metadata and redacted categories only.

## 5. Integration and safety

- AutomationWorker publishes a terminal event after durable Job state; Scheduler publishes an event
  after durable job/audit emission. Publishing only writes the Outbox.
- Notification delivery never calls Storage, Metadata, strategy engines, Planner, or Executor.
- Notification failures never authorize, retry, or alter media operations.
- No implicit overwrite/delete and no remote OrganizerExecutor execute mode.
- Existing DryRun, cancellation, scheduling, audit, and RecognitionType C behavior remain unchanged.

## Required tests

- Configuration validation and secret ownership/redaction.
- Outbox idempotency, persistence, atomic claim, ordering, filter/limit, and v6-to-v7 migration.
- Exact canonical body/signature/header verification and Unicode payload.
- 2xx, 4xx, 429, 5xx, timeout/connection, exponential retry cap, maximum attempts/dead-letter.
- Multiple subscriptions, disabled/unsubscribed Webhooks, terminal Job and schedule events.
- Resident worker polling/failure isolation/graceful stop and explicit dead-letter requeue.
- CLI/API visibility, zero Storage mutation/network-free config validation, and full regressions.

## Documentation and validation

Update all current docs and configuration examples. Run all tests and configured quality, build,
dependency, configuration, FFprobe/FFmpeg, and diff checks.

## Out of scope

- Remote organize/execute, inbound Webhooks, Web UI, user/role/TLS work.
- Email/chat-specific providers, templates, notification aggregation, and media-server refresh.
- Strategy, Storage, Planner, or OrganizerExecutor redesign.

## Final report

## Phase 18.4 Result

PASS / FAIL

## Notification Outbox

## Signed Webhooks

## Retry and Dead-letter

## Security and Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
