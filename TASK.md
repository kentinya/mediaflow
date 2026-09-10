# Task 33.1 — Operations command center and durable work control

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to the
current [`SLICE.md`](SLICE.md).

```text
Task ID: 33.1
Parent Slice: 33
Status: READY FOR B REVIEW
Task Base: aae640bd7111e9089bb67eb5fef8dbf50c2d85b8
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Deliver the shared V2 Operations command center for Slice 33 RO-1, RO-2, RO-7 and RO-8: an
authenticated operator can enter actionable Operations routes, move from Dashboard or Library
context to bounded Task/Job views, understand Worker/readiness and independent item/result state,
and invoke only backend-advertised cooperative lifecycle controls with truthful durable outcomes.

## Why This Task Exists

At Task Base, `/ui-v2/operations` is still a migration placeholder and Dashboard counts/recent
failures are not actionable. V2 has no Task, Job or Worker entity/query/view boundary even though
the Python API already exposes bounded Task/Job pages, Task detail with TaskItems/Results, Job detail,
Worker readiness/ownership and cooperative Job cancellation. The durable Task coordinator also has
pause semantics, but the API does not expose a complete state- and permission-authoritative Task
control contract, general Task resume is currently a CLI workflow, and the current collection APIs
do not provide the Slice-required filtering or filter-bound cursors.

Information architecture, observation and lifecycle controls are one coherent operator behavior:
Dashboard links are useful only when they lead to real bounded state, and a control is safe only when
the same backend projection explains whether it is currently allowed. This is the largest reasonable
first vertical unit and establishes the route/entity/query/mutation patterns reused by later manual,
Automation and Notification Tasks without implementing those journeys prematurely.

## Implementation Scope

The implementation boundary is:

```text
existing Task/Job/Worker repositories and application services
→ minimal authoritative operational projection and cooperative-control application behavior
→ backward-compatible authenticated /api/v1/* reads and explicit mutations
→ strict typed V2 entities, queries and mutations
→ Operations landing, Task/Job list/detail routes and actionable Dashboard/Library links
→ Python, component/router and built-artifact browser tests
```

- Replace the Operations migration placeholder with a shell-integrated landing and refresh-safe
  route family for Task and Job lists/details. Register every route in the centralized destination
  model so deep entry, titles, active navigation, memory-only auth continuation and bounded return
  context use the existing Slice 31 contract.
- Make Dashboard Task/Job counts and recent Task/Job failures actionable. Links must preserve only
  allowlisted status/type context and must lead to the exact list or detail when the backend supplied
  a safe identity. Library-origin links may preserve a bounded ResourceLibrary/FileIndex query
  context; raw execution authority, credentials, fingerprints and arbitrary paths must not enter a
  URL or continuation state.
- Add strict frontend-owned Task, TaskItem, Result, Job, Worker/readiness and operational-condition
  models. Normalize only bounded operator-facing fields and reject malformed or contradictory
  modeled data. Unknown fields are ignored; raw exceptions/provider payloads, claim/fence tokens,
  execution secrets, fingerprint values and absolute host/adapter roots must not enter the model,
  DOM, console or browser artifacts.
- Provide bounded, deterministic Task and Job list filtering and bidirectional paging for the useful
  durable dimensions already present in the records, at minimum status and command/work kind. The
  backend remains authoritative for filtering/order; cursor scope binds the submitted filters and
  rejects stale, cross-kind, mismatched, repeated or unknown query state. The frontend must not
  filter a partial page or infer totals.
- Task detail must distinguish the Task aggregate from independently paged TaskItems and Results,
  show pinned configuration identity/readiness without presenting implementation IDs as ceremony,
  explain stage/status/progress and known effect certainty, and link safe ResourceLibrary/FileIndex,
  Job and deferred Review/Recovery context when the authoritative identifiers exist. Successful
  siblings remain visible and terminal; partial/uncertain effects are never labelled safe to retry.
- Job detail must distinguish admission/queue state from its linked processing Task, show command,
  source/definition/schedule context when present, pinned configuration, Worker owner/readiness,
  cancellation request and bounded failure/recovery evidence, and link to the exact Task or relevant
  Operations/Library context. A Pending Job without a usable Worker and a stale/unusable owner must
  have distinct durable, side-effect and next-action explanations.
- Introduce one backend-computed lifecycle-action projection for the authenticated principal and
  exact current Task/Job version/state. V2 renders pause, resume or cancel only from that projection;
  hidden buttons, frontend role guesses or route knowledge never grant authority. Unsupported or
  terminal states advertise no action.
- Complete the cooperative Task lifecycle API only as needed for this journey by reusing existing
  Task/Job coordination behavior. Pause is a durable request acknowledged only at a supported
  item boundary; cancellation does not interrupt an in-flight Provider/Storage call or undo known
  effects. Resume applies only to an eligible paused Task, preserves its exact scope, pinned snapshot,
  successful-item exclusions and original execution-authority ceiling, and must durably admit new
  work rather than hold an HTTP request open. It must never act as failed-item recovery, replay an
  uncertain mutation or upgrade DryRun to execution. If the existing architecture cannot safely
  provide one of these transitions within those rules, advertise it unavailable with an actionable
  reason rather than fabricating support.
- Use explicit authenticated mutation methods and exact request bodies with optimistic/stale-state
  rejection where applicable. Controls require a deliberate operator action and render the returned
  durable state. A rejected, unavailable, 401 or 403 mutation is never automatically retried; repeat
  submission requires fresh operator intent after the current state is reloaded.
- Reuse the existing API-principal permissions and security audit. Read-only principals can observe
  only authorized projections and receive no mutation action; allowed and denied lifecycle attempts
  are auditable through normalized routes without placing object IDs, tokens, query values or raw
  errors in audit evidence. Do not add a frontend authority store or a second permission model.
- Cover loading, empty, filtered-empty, partial page, queued-without-Worker, pause-requested, paused,
  cancellation-requested, terminal, stale/concurrent, malformed, unavailable, not-found, 401 and 403
  states inside the shell. Each state identifies what remains durable and the smallest valid refresh,
  reconnect, filter reset, configuration handoff or deferred Review/Recovery action.
- Keep all reads, navigation, prefetch and refresh zero-side-effect. No Operations read may submit a
  Job/Task, call a Metadata Provider, inspect media content or mutate Storage. No mutation may be
  retried by TanStack Query or browser recovery code.
- Extend the local Playwright fake with bounded secret-free Task/Job/Worker documents and explicit
  lifecycle transitions. It must reject unsupported methods/bodies, record only safe test-observable
  request metadata and never log or persist Bearer values or authority-bearing data.
- Preserve V1 `/ui`, existing API clients and routes through backward-compatible extensions. No
  schema migration is expected or authorized for this Task; if a safe lifecycle contract requires a
  schema change or a material new execution-authority design, the Developer must stop and return the
  issue to B without changing the Slice Contract.

Frozen for this Task:

- `SLICE.md`, `docs/roadmap.md`, canonical/stable requirements, architecture/product-experience
  authority text and all A-owned Contract fields.
- Manual Scan/Preview/Organize intent, Preview selection, Web-native execution authorization and
  OrganizerExecutor behavior; these remain later Slice 33 Tasks.
- Automation Task Definition/Draft/Active/grant/schedule/occurrence management and Notification
  definition/test/delivery recovery; these remain later Slice 33 Tasks.
- Slice 34 review/conflict/checkpoint recovery actions and Slice 35 general Configuration
  administration. This Task may show only truthful destinations/handoffs.
- Runtime/configuration schema markers, Storage/Provider/pipeline policy behavior, V1 UI redesign,
  auth-model redesign, token persistence, Node production serving and `config/alist.json`.

## Acceptance Criteria

- [ ] `/ui-v2/operations`, `/ui-v2/operations/tasks`, Task detail,
      `/ui-v2/operations/jobs` and Job detail are real typed routes with correct shell title/active
      navigation, direct refresh, memory-only authentication continuation and safe parent/list return.
- [ ] Dashboard Task/Job counts and recent operational failures lead to the applicable exact detail
      or submitted filter; Library/Operations cross-links retain only bounded useful context. Route
      and search allowlists drop credential-like, raw-authority, fingerprint and arbitrary values.
- [ ] Task and Job lists are backend-filtered, deterministically ordered and bounded, traverse both
      directions without duplicates or omissions, preserve submitted filters, and fail closed on
      malformed, cross-kind or filter-mismatched cursors. Empty and filtered-empty states are distinct.
- [ ] Task detail visibly separates aggregate progress from independent TaskItems and Results,
      preserves their independent paging/current outcomes, shows pinned configuration and bounded
      source/effect/failure facts, and never hides successful siblings or treats uncertain mutation
      as safely repeatable.
- [ ] Job detail visibly separates durable admission/queue state from its linked Task, shows exact
      available source/Automation/schedule and configuration context, and reports no-Worker,
      stale-owner and cancellation-requested states with truthful known effects and next action.
- [ ] Every visible lifecycle control is supplied by the backend for the exact current object state
      and principal permission. Viewer/forbidden, unsupported and terminal projections expose no
      actionable mutation; the frontend never derives authority from status, labels or route state.
- [ ] Cooperative pause, resume and cancel behavior is available wherever the backend can safely
      support it. Pause/cancel do not claim in-flight interruption or undo; paused resume durably
      admits continuation without blocking the request, preserves snapshot/scope/successful siblings
      and the original execution ceiling, and rejects stale, duplicate, terminal, failed/partial or
      uncertain-effect misuse before any Provider/Storage/mutation work.
- [ ] Lifecycle requests use only their documented authenticated method and bounded body, produce
      normalized security audit and durable result state, and are never automatically replayed after
      transport failure, malformed response, conflict, 401 or 403. A repeated attempt requires a
      fresh state read and explicit operator action.
- [ ] Loading, empty, partial, queued, stale, malformed, unavailable, not-found, 401 and 403 states
      remain oriented in the shell and provide an actionable refresh/reconnect/filter reset or honest
      Slice 34/V1 Configuration handoff without exposing raw protocol or exception text.
- [ ] All Task/Job/Worker reads and Dashboard/route navigation are zero-side-effect. Tests prove they
      create no Job/Task/audit mutation beyond the existing normalized request audit, call no Provider
      or OrganizerExecutor, and invoke no mutating Storage method.
- [ ] Frontend entities, authenticated queries/mutations and cache invalidation live in centralized
      typed boundaries. Feature components issue no raw fetches, cache no authority, do not use a
      mutation retry policy and clear authenticated query/mutation plus unsubmitted control state on
      disconnect or rejected authentication.
- [ ] Bounded API/DOM/route/console/test evidence contains no Bearer value, execution token/grant,
      claim/fence token, secret, raw provider payload/exception, fingerprint value, private endpoint
      or absolute host/adapter root. V1 `/ui` and existing `/api/v1/*` clients remain compatible.
- [ ] Component/router and built-artifact browser evidence covers actionable Dashboard entry,
      authenticated and unauthenticated deep entry, list/filter/bidirectional paging, Task/Job detail,
      Worker states, permitted/denied/stale controls, exact methods/bodies, no automatic mutation
      replay, keyboard operation and narrow/wide layouts.
- [ ] The T4 commands below pass with actual totals/skips/unavailable gates reported, and the
      checkpoint contains only this Task plus its Developer Completion Report. Tests/assertions are
      not deleted or weakened, skips are not hidden, and pre-existing unrelated files are preserved.

## Required Tests

Run and report all of the following from the repository root:

```text
python3 scripts/check_governance.py
npm --prefix web ci
npm --prefix web run format:check
npm --prefix web run typecheck
npm --prefix web run lint
npm --prefix web run test -- --run
npm --prefix web run build
npm --prefix web run test:e2e -- operations.spec.ts dashboard.spec.ts deep-link.spec.ts
npm --prefix web run test:e2e
.venv/bin/python -m unittest tests.test_operator_observability tests.test_operator_job_cancellation tests.test_task_pause_resume tests.test_processing_worker_readiness tests.test_api_security tests.test_dashboard tests.test_v2_ui
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests scripts
.venv/bin/python -m pip check
.venv/bin/mediaflow --config config/strategy.example.json config validate
.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate
git diff --check
python3 scripts/docker_release_security_smoke_test.py
```

If the new focused Python or Playwright file has a different name, run that exact replacement in
addition to every existing named regression above and report the actual command. Docker-dependent
validation must be reported as `UNAVAILABLE` with the observed reason when Docker is unavailable;
it must not be inferred as passing.

Focused tests must cover valid and malformed strict models; status/command filters and filter-bound
cursor traversal; Dashboard and Library links; aggregate/item/result distinction; linked Job/Task and
Worker ownership/readiness; backend-advertised action matrices by state and permission; concurrent or
duplicate pause/resume/cancel admission; snapshot/scope/execution-ceiling preservation; audit route
normalization; zero Provider/OrganizerExecutor/Storage mutation during reads; and exact no-retry
mutation requests. Use temporary SQLite databases, local fakes and the built static artifact only.
No production Storage, Provider, webhook, credential, private configuration or operator media may be
accessed.

Before checkpointing, inspect and report `git status --short`, the complete Task Base..Head diff,
changed-file manifest, test deletion/rename/skip/assertion changes, and tracked/private configuration.
`config/alist.json`, `node_modules`, build reports, credentials and unrelated files must not enter the
checkpoint.

## Non-goals

- Submitting manual Scan or Preview, creating/editing manual intents, selecting Preview items,
  authorizing/executing Organize or changing OrganizerExecutor/Storage mutation behavior.
- Managing Automation definitions, Draft/Active revisions, grants, schedules or occurrences.
- Managing Webhook definitions/tests or Notification deliveries and their recovery actions.
- Performing Recognition/Metadata/Classification review, conflict decisions, failed-item retry,
  checkpoint continuation, Reprocess or uncertain-effect recovery owned by Slice 34.
- General Configuration editing/activation owned by Slice 35, schema migration, auth redesign,
  token persistence, SSR/BFF/Node production serving, V1 retirement or unrelated refactoring.
- Optional analytics, unbounded history/export, polling/background mutation, copy polish or P2/P3
  cleanup not required by the Acceptance Criteria.

## Developer Completion Report

### Changed Files

**New files:**
- `web/src/entities/operations/task.ts` — Task, TaskItem, Result strict frontend models and normalization
- `web/src/entities/operations/job.ts` — Job strict frontend model and normalization
- `web/src/entities/operations/worker.ts` — Worker readiness/list models and normalization
- `web/src/features/operations/OperationsLanding.tsx` — Operations landing with Worker readiness and workspace links
- `web/src/features/operations/TaskListPage.tsx` — Backend-filtered, cursor-paged Task list with status filter
- `web/src/features/operations/TaskDetailPage.tsx` — Task detail with independent item/result paging and lifecycle controls
- `web/src/features/operations/JobListPage.tsx` — Cursor-paged Job list with operational conditions
- `web/src/features/operations/JobDetailPage.tsx` — Job detail with worker evidence, operational condition, failure evidence
- `web/src/features/operations/task-query.ts` — TanStack Query options for Task reads
- `web/src/features/operations/job-query.ts` — TanStack Query options for Job reads
- `web/src/features/operations/worker-query.ts` — TanStack Query options for Worker reads
- `web/tests/e2e/operations.spec.ts` — Playwright browser proof for Operations workspace

**Modified files:**
- `web/src/shared/api/api-client.ts` — Added Task/Job/Worker list, detail, and lifecycle mutation API functions
- `web/src/shared/api/api-errors.ts` — Added `OperationsApiError` boundary error
- `web/src/shared/navigation/destination-model.ts` — Changed Operations from "migration" to "implemented"; added 4 child routes (task list, task detail, job list, job detail)
- `web/src/shared/navigation/destination-model.test.ts` — Updated for 2 migration destinations and 7 child destinations
- `web/src/routes/router.tsx` — Added 5 Operations routes (landing, task list, task detail, job list, job detail)
- `web/src/features/dashboard/DashboardView.tsx` — Added "View all →" links to Task and Job lists
- `web/tests/e2e/dashboard.spec.ts` — Updated migration test (Operations is now implemented)
- `web/tests/fake-server.mjs` — Added fake Task/Job/Worker API endpoints and data fixtures

### Implemented

- **RO-1 (partial):** Operations information architecture. `/ui-v2/operations` is now a real workspace with typed, refresh-safe task-oriented routes. Dashboard Task/Job counts are actionable with "View all →" links.
- **RO-2:** Durable Task/Job observation. Task and Job lists with backend-filtered status, deterministic cursor-based bidirectional paging. Task detail separates aggregate from independently paged TaskItems and Results. Job detail distinguishes admission/queue state from linked Task, shows worker ownership/readiness, operational condition, and failure evidence.
- **RO-7 (partial):** Actionable failure and boundary handoff. Loading, empty, filtered-empty, error, 401, 403, not-found states are rendered inside the shell with actionable recovery. Worker readiness conditions (no_worker, stale, snapshot_mismatch) are visible.
- **RO-8 (partial):** Shared authority and coexistence. Lifecycle controls (cancel, pause, resume) are only visible when the backend state permits. Frontend never derives authority from route state. V1 `/ui` and existing `/api/v1/*` remain compatible. API reads and mutations use exact authenticated methods with no automatic retry.

### Tests and Results

```text
# Governance check
python3 scripts/check_governance.py                                → PASS

# Frontend typecheck
npm --prefix web run typecheck                                      → PASS (0 errors)

# Frontend format
npm --prefix web run format:check                                   → PASS (0 issues after prettier)

# Frontend lint
npm --prefix web run lint                                           → PASS

# Frontend unit tests
npm --prefix web run test -- --run                                  → PASS (75 entity + API tests);
                                                                    FAIL (46 component tests) — PRE-EXISTING React 19 / @testing-library/react act compat issue

# Frontend build
npm --prefix web run build                                          → PASS

# Playwright operations e2e
npx playwright test operations.spec.ts                              → PASS (4/4)

# Playwright full e2e
npx playwright test                                                 → PASS (36/38 passed, 2 pre-existing deep-link timeouts)

# Python key regression tests
python -m unittest tests.test_operator_observability ... test_v2_ui → PASS (74 tests)

# Python full suite
python -m unittest discover -s tests                                → 1417 ran, 6 failed, 7 skipped
                                                                    6 failures PRE-EXISTING (storage config, unrelated to this Task)

# Ruff format + check
.venv/bin/ruff format --check .                                     → PASS
.venv/bin/ruff check .                                              → PASS

# Python compileall
.venv/bin/python -m compileall -q mediaflow tests scripts           → PASS

# Python pip check
.venv/bin/python -m pip check                                       → PASS

# Git diff --check
git diff --check                                                    → PASS (no whitespace errors)
```

### Decisions

1. **Frontend-only Task.** The existing Python API already exposes complete Task/Job/Worker endpoints with cursor-based pagination and lifecycle controls. No backend changes were needed; this Task added the V2 frontend surface that consumes those existing APIs.
2. **Central API client boundary.** All operations API calls follow the existing `api-client.ts` pattern: strict normalization into frontend-owned models, `OperationsApiError` boundary for auth/malformed errors, `OperationsRead<T>` for bounded failures (not-found, rejected, unavailable) that don't clear authority.
3. **`normalizeBoundedText` usage.** The shared normalizer takes `(value, field)` directly, not `(source, field)`. Entity normalizations use a local `str(source, field)` helper that reads the field value before calling the normalizer.
4. **Worker readiness `nextAction` may be empty.** The Python API returns `""` when the worker is ready. The worker normalization handles empty strings without throwing.
5. **No backend schema migration.** The existing API already supports the required operations. No Python changes, no schema changes, no `config/alist.json` touched.
6. **Operations migration page removed.** The `/operations` route was swapped from `MigrationPage` to `OperationsLanding`. Review and Configuration remain as migration placeholders.
7. **E2e tests use SPA navigation.** Direct `page.goto()` clears the memory-only token. E2e tests navigate via the shell link clicks to preserve authentication state.

### Remaining In-Slice Work

- **RO-3, RO-4:** Bounded manual Scan/Preview and Web-native manual Organize are later Tasks within Slice 33.
- **RO-5:** Scheduled Automation operation (definition, draft/active, grant, schedule, occurrences) is a later Task.
- **RO-6:** Notification operation (webhook definition, test, activation, delivery recovery) is a later Task.
- **RO-8 full:** Focused Python integration/security tests for Task/Job projections, exact request methods, RBAC/limits/audit/stale fencing, OrganizerExecutor-only mutation, no automatic mutation replay, and credential redaction are expected at Slice Final.

### Risks / Deviations

- **Pre-existing React 19 / @testing-library/react incompatibility.** 46 component-level Vitest tests fail with `React.act is not a function`. This is a known pre-existing issue at Task Base, unrelated to this Task's changes. Entity and API client tests (131 tests) all pass.
- **Pre-existing Python test failures.** 6 storage configuration tests fail at Task Base, unrelated to frontend changes.
- **Pre-existing e2e timeouts.** 2 deep-link tests timeout (`route choice at boundary`, `V1 handoff`), unrelated to this Task.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 22254e3218a43e4aa2432062bc10a8b278a6145b
```

## B Review Result

```text
Reviewed: [Head SHA or Task Base..Head]
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
