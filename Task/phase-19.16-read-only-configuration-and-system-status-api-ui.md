# Phase 19.16 — Read-only Configuration and System Status API/UI

## Goal

Expose a bounded, precomputed, secret-free view of the configuration already loaded by production so
operators can verify system/library/policy wiring in the existing authenticated UI. Add no edit,
connectivity test, workflow, or execution controls.

## 1. Safe configuration snapshot

- Build one immutable snapshot during API bootstrap from normalized `RuntimeConfiguration` models.
- Include application/Python/Schema/platform/maintenance-lock support and configuration-valid status.
- Include bounded summaries for configured Storages, ResourceLibraries, MediaLibraries, Recognition
  types/rules/type-policy references, and Metadata/Naming/Classification/Organize policies.
- Exclude every root/display/media path, rule pattern/value, naming template body, classification path,
  endpoint/URL, environment variable name/value, credentials, webhook details, and arbitrary options.
- Expose counts and safe IDs/types/statuses/reference IDs only; enforce deterministic ordering and a
  hard per-section bound.

## 2. Authenticated read-only API

- Add `GET /api/v1/system/status` using existing READ permission and security audit behavior.
- Return only the injected immutable snapshot; do not reload configuration per request.
- Reject other methods and query parameters before any snapshot/repository access.
- The endpoint performs no repository read except the existing normalized security audit write.

## 3. Operator UI

- Add a System tab using the existing same-origin, CSP, no-store, in-memory bearer, and text-node-only UI.
- Display compatibility cards and compact tables for Storages, Libraries, recognition mappings, and
  policy catalogs, with explicit text that paths/templates/secrets are intentionally hidden.
- Provide explicit refresh only. Add no polling, edit/apply, secret status/value, Storage check, scan,
  backup/restore, migration, Task/Job, Scheduler, or execution controls.

## 4. Safety

- Construct no Storage adapters, MetadataProvider, Scanner, workflow, Scheduler worker, Notification
  worker, OrganizerExecutor, backup/restore, preflight, or migration rehearsal service.
- Do not change Parser, Recognition, Metadata, Naming, Classification, Planner, Executor, or config models.
- Snapshot/API/UI output must remain secret- and path-free even with hostile configured strings.

## Required tests

- Snapshot covers all safe sections, deterministic ordering, hard bounds, C downstream references, and
  current version/Schema/platform support.
- Hostile paths/templates/rules/URLs/env names/secrets/options never appear in snapshot/API/UI/audit.
- API authentication/RBAC, wrong method/query rejection, response allowlist, and zero repository reads.
- Bootstrap injects the production snapshot without Storage/provider/workflow construction.
- UI System tab fetch/refresh, text-node rendering, safe empty/error states, and absence of controls.
- Existing API/UI/security/configuration/runtime/media regressions and quality gates pass.

## Documentation

Update README, requirements, architecture, progress, roadmap, and configuration documentation.

## Out of scope

Configuration editing/apply/rollback, full rule/template/path display, secret status, connectivity tests,
live health checks, polling, metrics, OIDC, TLS, Task controls, database controls, and media execution.

## Final report

## Phase 19.16 Result

PASS / FAIL

## System Snapshot

## API and UI

## Redaction and Authorization

## Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
