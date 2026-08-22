# Phase 18.6 — API Principals, RBAC + Security Audit

## Goal

Replace the single all-powerful API identity with configuration-driven principals and least-
privilege roles, and persist a redacted security audit for API access. Keep the Phase 18.5 one-time
execution authorization as an additional mandatory gate for real organization.

## 1. Principals and roles

- Configure unique API principals with ID, environment-owned Bearer `tokenEnv`, enabled flag, and
  roles selected from viewer, operator, executor, auditor, and admin.
- Normalize roles into explicit permissions: read, submit DryRun, cancel Job, remote execute, and
  read security audit.
- Resolve token values only at API startup. Reject literal tokens, duplicate IDs/tokenEnv names,
  unknown roles, empty roles, invalid environment names, and missing enabled-principal secrets.
- Keep legacy `api.tokenEnv` compatibility as one admin principal, but reject mixing legacy and new
  principal configuration. Examples must use the new principal form.

## 2. Authorization boundary

- All `/api/v1` endpoints require an authenticated principal and route-specific permission.
- viewer is read-only; operator may submit scan/preview and cancel; executor may additionally submit
  organize only with the existing valid one-time token; auditor may read security audit; admin has
  all permissions.
- Return stable 401 for authentication failure and 403 for insufficient permission.
- Compare presented tokens safely and never expose token values or environment names in API output.
- API still cannot issue/revoke execution authorizations or resolve conflicts.

## 3. Persistent security audit

- Upgrade SQLite compatibly to v9 and append API request audit records with ID, UTC timestamp,
  principal ID when known, method, normalized route, action, outcome, HTTP status, request ID, and
  bounded source address.
- Audit successful and denied `/api/v1` access, including authentication and permission failures.
- Never persist headers, bearer/execution tokens, request bodies, query strings, cookies, secrets,
  media payloads, or exception text.
- Audit persistence failure must fail closed for mutation requests and must not leak details.

## 4. Visibility and CLI

- Add admin/auditor-only `GET /api/v1/security-audit` with bounded results.
- Add local `mediaflow security-audit list [--limit N]` without constructing Storage.
- API responses may identify the authenticated principal but never return credential configuration.

## 5. Safety and compatibility

- Default configuration remains loopback-oriented and remote execution remains disabled.
- RBAC never bypasses one-time execution authorization, conflicts, overwrite/delete protection,
  Task execute authority, Storage capabilities, or OrganizerExecutor.
- Scheduler stays scan/preview-only. No strategy, Storage, Planner, or execution semantic changes.

## Required tests

- Role/permission matrix for every read/write/execute/audit route.
- Invalid/missing/disabled principals, unknown roles, duplicates, legacy compatibility and mixing.
- 401 vs 403 behavior and constant-time credential comparison boundary.
- Successful/denied audit records, redaction, ordering/limit and v8-to-v9 migration.
- Security-audit API permission and local CLI zero-Storage behavior.
- Executor role still requires and atomically consumes a Phase 18.5 one-time token.
- Audit write failure fails closed before mutation Job creation.
- All automation, notification, execution authorization, DryRun, strategy and Storage regressions.

## Documentation and validation

Update README, examples, configuration, architecture, progress, roadmap, and product status. Run
all tests plus formatter, lint, compile, dependency, build, configuration, FFprobe/FFmpeg, and diff
checks.

## Out of scope

- Database-managed users/passwords, login/session/cookies, token rotation endpoints, OIDC/OAuth,
  TLS termination, Web UI, scheduled execute, and OrganizerExecutor redesign.

## Final report

## Phase 18.6 Result

PASS / FAIL

## Principals and RBAC

## Security Audit

## Security and Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
