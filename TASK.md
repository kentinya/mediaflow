# Phase 19.1 — Minimal Secure Operator Web UI

## Goal

Serve a dependency-free operator UI from the existing MediaFlow WSGI service. The UI is a thin
client over existing Dashboard, conflict confirmation, metadata review, and classification review
APIs. It must not duplicate application decisions or widen execution authority.

## Scope

- Serve same-origin HTML, CSS, and JavaScript from the existing API process, with no external
  assets, frontend framework, build step, or third-party runtime dependency.
- Keep the bearer token in browser memory only. Never use browser storage, cookies, URLs, DOM
  output, logs, or persisted application state for credentials.
- Render the existing Dashboard and pending conflict, metadata, and classification review queues.
- Load bounded detail records and submit only existing safe decisions: conflict `skip`/`rename`, a
  persisted `candidateRank`, or a persisted `choiceRank`.
- Preserve API RBAC, authenticated actor identity, validation, atomic persistence, and audit as the
  sole authority.
- Apply no-store caching and strict browser security headers.

## Safety boundaries

- Do not expose Overwrite, custom paths/provider IDs/library IDs, actor injection, execute flags,
  Task resume, Job submission/cancellation, execution authorization, or policy editing.
- Static UI access performs no repository, Storage, Provider, Task/Job, or execution operation.
- Review decisions remain persistence-only and never resume Tasks automatically.
- Do not change Parser, Recognition, Metadata, Naming, Classification, Planner, or Executor.
- RecognitionType C behavior and all existing CLI/API behavior remain unchanged.

## Required tests

- UI document/assets, content types, method handling, no-store and security headers.
- No external assets and no credential persistence/cookie/query/DOM disclosure mechanism.
- Dashboard plus all three review list/detail flows use bounded existing API requests.
- Generated decisions contain only the exact supported fields and values.
- 401/403/API errors and untrusted values render safely using text nodes.
- Static routes perform zero repository, Storage, provider, Task/Job, or execution calls.
- Existing API/RBAC and three review decision workflows regress.
- Run the complete suite plus formatter, lint, compile, build/configuration and FFprobe audits.

## Documentation

Update README, configuration, architecture, progress, roadmap, and product status with the UI URL,
authentication model, supported operations, deployment limitations, and safety boundaries.

## Out of scope

User database/login sessions, cookies, OIDC, token persistence, policy/storage/library editors,
task/job controls, real execution, Overwrite, Scheduler management, live push, and frontend
frameworks.

## Final report

## Phase 19.1 Result

PASS / FAIL

## Operator UI

## Authentication and Security

## Review Workflows

## Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
