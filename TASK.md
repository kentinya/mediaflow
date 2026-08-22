# Phase 18.5 — One-time Remote Execute Authorization + Audit

## Goal

Allow the existing authenticated API to queue a real `organize --execute` job only when a local
operator has issued a short-lived, single-use authorization. Do not reuse the ordinary API bearer
token as mutation authority. Preserve OrganizerExecutor as the only Storage mutation boundary.

## 1. Authorization model

- Local CLI issues a cryptographically random one-time token with ID, expiry, maximum item limit,
  created timestamp, status, and optional non-secret actor/note.
- Persist only a SHA-256 token digest; display the raw token exactly once at issuance.
- Statuses: active, consumed, revoked, expired. Expiry is evaluated against UTC.
- Token consumption and execute-authorized Job creation must be one SQLite transaction.
- Concurrent/replayed requests using one token may create exactly one Job.

## 2. API execution boundary

- Keep ordinary Bearer authentication for all `/api/v1` routes.
- `POST /api/v1/jobs` accepts `command=organize` and `execute=true` only with a separate
  `X-MediaFlow-Execution-Token` header and an enabled runtime feature gate.
- Require an explicit positive `limit` not exceeding the authorization maximum.
- Reject missing/invalid/expired/revoked/consumed tokens, body-carried tokens, overwrite/delete,
  and organize without `execute=true`.
- scan/preview remain DryRun and must reject execute authority.
- API cannot issue, list, revoke, or renew execution tokens.

## 3. Worker and persistence

- Persist `executeAuthorized` on AutomationJob with a compatible SQLite v7-to-v8 migration.
- Worker delegates an authorized organize Job to the existing production CLI with `--execute`.
- Worker never infers execute authority from command, configuration, schedule, or API bearer token.
- Scheduler remains restricted to scan/preview and cannot reference authorization tokens.
- Stale execute Job requeue preserves its original authorization but remains explicit and audited.

## 4. Local operator CLI and audit

- Add `mediaflow execution-authorizations issue --ttl-seconds N --max-items N`.
- Add `list`, `show`, and `revoke`; these commands only access SQLite.
- Audit issue/consume/revoke with timestamps and job identity; never persist or print raw tokens
  after issuance.
- Job CLI/API visibility includes execute authorization status but never the token/digest.

## 5. Configuration and safety

- Add `api.remoteExecution.enabled` and bounded maximum TTL; default disabled.
- Config validation needs no API token, execution token, Storage construction, or network access.
- Remote execute keeps all existing conflict, overwrite, delete, attachment, cancellation, task,
  history, and Storage capability checks.
- Notification, strategy, Storage adapters, Planner, and OrganizerExecutor semantics remain intact.

## Required tests

- Disabled feature, missing separate token, invalid/expired/revoked/consumed/replayed token.
- Token digest-only persistence, one-time display, TTL/max-items validation, list/show redaction.
- Atomic concurrent consumption creates exactly one execute-authorized organize Job.
- scan/preview execute rejection; Scheduler organize rejection remains.
- Worker passes `--execute` only for an authorized organize Job and never for other Jobs.
- End-to-end API → Job → Worker real LocalStorage execution with explicit token and limit.
- Existing conflict/no-overwrite safety, cancellation, stale recovery, notifications, DryRun, all
  strategy/Storage regressions, and zero mutation during authorization/config validation.

## Documentation and validation

Update README, examples, configuration, architecture, progress, roadmap, and product status. Run
all tests plus formatter, lint, compile, dependency, build, configuration, FFprobe/FFmpeg, and diff
checks.

## Out of scope

- Scheduled/unattended execute, reusable service execution keys, token renewal, Web UI, users/roles,
  TLS termination, inbound Webhooks, and OrganizerExecutor redesign.

## Final report

## Phase 18.5 Result

PASS / FAIL

## Authorization Model

## Remote Execute

## Audit

## Security and Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
