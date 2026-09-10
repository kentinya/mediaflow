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
- `mediaflow/application/operations_lifecycle.py` — backend-computed Task/Job lifecycle
  projection, cooperative Task pause/cancel controls and their stale/duplicate/unsupported
  rejection
- `tests/test_operations_workspace.py` — focused Python proof for filters, filter-bound
  cursors, projection, RBAC, stale/duplicate admission, audit normalization, sibling
  preservation and zero-mutation reads
- `web/src/entities/operations/lifecycle.ts` — strict frontend model for the authoritative
  control projection
- `web/src/entities/operations/lifecycle.test.ts`
- `web/src/entities/operations/task.test.ts`
- `web/src/entities/operations/job.test.ts`
- `web/src/entities/operations/worker.test.ts`
- `web/src/shared/api/operations-api.test.ts`
- `web/src/features/operations/OperationsRouter.test.tsx` — component/router journeys

**Modified files:**
- `mediaflow/interfaces/service_api.py` — Task/Job bounded status+command filters with
  filter-bound cursors, lifecycle projection on Task/Job documents, general cooperative Task
  `pause`/`cancel`/`resume` routes with optimistic version rejection, normalized audit routes
- `mediaflow/interfaces/pagination.py` — optional filter scope for Task/Job collection cursors
- `mediaflow/infrastructure/sqlite_runtime.py` — repository-level status/command filtering for
  `list_tasks`/`list_jobs` plus the bounded command-family matcher
- `mediaflow/domain/task_persistence.py`, `mediaflow/domain/automation.py` — repository
  protocol signatures for the new filter parameters
- `web/src/entities/operations/task.ts`, `job.ts`, `worker.ts` — fail-closed normalization
- `web/src/entities/shared/normalize.ts` — strict boolean/enum/optional-text primitives
- `web/src/shared/api/api-client.ts` — Job list filters, single `mutateLifecycle` boundary
- `web/src/shared/navigation/destination-model.ts` (+ test) — Operations route/search allowlists
- `web/src/features/operations/TaskListPage.tsx`, `JobListPage.tsx`,
  `TaskDetailPage.tsx`, `JobDetailPage.tsx` — URL-driven backend filters and
  projection-driven controls
- `web/src/features/dashboard/DashboardView.tsx` — actionable count and failure links
- `web/src/features/library/LibraryLanding.tsx` — bounded Operations cross-link
- `web/src/shared/ui/styles.css` — linked count-cell presentation
- `web/src/shared/auth/AuthBoundary.test.tsx`, `web/tests/e2e/deep-link.spec.ts` — obsolete
  "Operations Migration" expectations corrected
- `web/tests/e2e/operations.spec.ts`, `web/tests/fake-server.mjs` — built-artifact proof and a
  fake that mirrors the authoritative Python contract

### Implemented

- **Authoritative backend contract (B blocker 1).** `GET /api/v1/tasks` and `GET /api/v1/jobs`
  now accept bounded `status` and `command` filters executed in SQL, echo the submitted filter,
  and mint cursors whose scope is the submitted filter state. A cursor replayed against a
  different filter (including "no filter") is rejected with 400 before any page is produced.
  `POST /api/v1/tasks/{id}/pause` is new; `POST /api/v1/tasks/{id}/cancel` is now general
  (manual Scan tasks keep their existing specialized path) and both accept an optional
  `{"expectedUpdatedAt": …}` body that fences stale and duplicate submissions with 409.
- **Authoritative lifecycle projection.** Task and Job documents carry a `lifecycle` block
  computed for the exact authenticated principal and the exact current state/version:
  `permitted`, `terminal`, `knownEffects`, `nextAction`, `pauseRequested`/
  `cancellationRequested`, effect certainty derived only from recorded Result evidence, and an
  `actions` list where each entry states `available`, `unavailableReason`, method, bounded
  durable outcome, side effects and next action. V2 renders a button only for an advertised
  available action.
- **Cooperative control semantics.** Pause stays a durable request acknowledged only at a
  supported item boundary; cancel marks the Task cancelled, cancels non-terminal items and
  preserves completed siblings; neither claims to interrupt an in-flight call or undo an
  effect. `resume` is advertised **unavailable** with an actionable reason (see Decisions).
- **Strict frontend boundary (B blocker 3).** Every Operations model now fails closed: unknown
  statuses/commands/conditions, coerced booleans, contradictory progress/terminal pairs, a
  contradiction between uncertain-effect evidence and effect certainty, a stale or cross-object
  lifecycle projection and an actionable control for a read-only principal are all rejected as
  malformed instead of being rendered.
- **Operator entry and filtering (B blocker 2).** Task and Job lists submit status and
  work-kind filters to the backend and reflect them in the URL; Dashboard count cells link to
  the exact backend filter and recent failures link to the exact Task/Job detail; the Library
  landing offers bounded Operations cross-links; the route/search allowlists accept only
  bounded filter tokens on the Operations routes.
- **Truthful T4 evidence (B blocker 4).** `format:check` is clean, the obsolete
  `AuthBoundary`/Playwright "Operations Migration" expectations are corrected, and every
  Required Tests command below was executed and reported with real totals.

### Tests and Results

```text
python3 scripts/check_governance.py                                    → PASS
npm --prefix web ci (run as: env -u NODE_ENV npm --prefix web ci)       → PASS
    (this shell exports NODE_ENV=production, which makes npm omit
     devDependencies and leaves web/node_modules unusable; with the
     variable unset the install is complete, 180 packages)
npm --prefix web run format:check                                      → PASS (all files formatted)
npm --prefix web run typecheck                                         → PASS (0 errors)
npm --prefix web run lint                                              → PASS (0 problems)
npm --prefix web run test -- --run                                     → PASS (255 tests, 23 files)
npm --prefix web run build                                             → PASS
npm --prefix web run test:e2e -- operations.spec.ts dashboard.spec.ts
    deep-link.spec.ts                                                  → PASS (35 passed)
npm --prefix web run test:e2e                                          → PASS (73 passed)
.venv/bin/python -m unittest tests.test_operator_observability
    tests.test_operator_job_cancellation tests.test_task_pause_resume
    tests.test_processing_worker_readiness tests.test_api_security
    tests.test_dashboard tests.test_v2_ui
    tests.test_operations_workspace                                    → PASS (85 tests)
.venv/bin/python -m unittest discover -s tests                         → 1428 ran, 6 failed,
                                                                         7 skipped; the 6
                                                                         failures are
                                                                         PRE-EXISTING/UNRELATED
                                                                         (see Risks)
.venv/bin/ruff format --check .                                        → PASS (303 files)
.venv/bin/ruff check .                                                 → PASS
.venv/bin/python -m compileall -q mediaflow tests scripts              → PASS
.venv/bin/python -m pip check                                          → PASS
.venv/bin/mediaflow --config config/strategy.example.json config validate
                                                                       → PASS
.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json
    config validate                                                    → PASS
git diff --check                                                       → PASS
python3 scripts/docker_release_security_smoke_test.py                  → FAIL / PRE-EXISTING /
                                                                         UNRELATED (see Risks)
```

New focused coverage: `tests/test_operations_workspace.py` (11 tests) proves filtering,
unknown/repeated query rejection, filter-bound cursors, projection by principal and state,
withheld resume, uncertain-effect reporting, durable pause and duplicate/stale rejection,
general cancel with terminal safety and successful-sibling preservation, empty-body
compatibility, Job cancel fencing, normalized audit routes, and that seven Operations reads
create no Task/Job and only the pre-existing normalized request audit.
`OperationsRouter.test.tsx` (8 tests) plus the entity and API-client suites (52 new tests)
prove the same rules through the real router, and `operations.spec.ts` (19 built-artifact
browser tests) proves filtering, paging boundaries, detail separation, Worker states,
permitted/read-only/terminal control matrices, exactly one authenticated mutation with the
displayed version, no automatic replay, keyboard operation, narrow/wide layout and
credential-free URLs, DOM and console.

### Decisions

1. **Resume is advertised unavailable, not fabricated.** The existing architecture has no
   durable queued command that continues one exact paused Task scope: the resident Worker
   executes a fresh queued workflow, and paused-scope continuation with pinned configuration
   and successful-item exclusions is implemented only as the operator CLI workflow. Rather
   than admit work the Worker cannot honour, the projection states `available: false` with the
   reason and the concrete next action, and `POST /api/v1/tasks/{id}/resume` refuses with 409
   `resume_unavailable` without any Provider/Storage work. Pause and cancel are fully
   available and durably admitted.
2. **Task command filtering uses the command family.** A Task command is either a base work
   kind or a derived `<kind>:<source identity>` continuation, so `?command=retry-failed`
   selects both the exact command and its own family. Job commands are exact members of the
   existing `AutomationCommand` set.
3. **Cursors are optionally scoped rather than newly scoped.** `tasks`/`jobs` cursors gain an
   optional filter scope so the unfiltered collection keeps its pre-existing contract while
   every filtered read is strictly bound; the API passes the filter digest whenever a filter
   is submitted and additionally rejects unscoped cursors in that case.
4. **Effect certainty is claimed only from a complete Result view.** The Task detail derives
   certainty from the Results it can prove are the whole set; a partial page reports
   `unknown` rather than implying the unseen effects are safe to repeat.
5. **One mutation boundary.** All four lifecycle controls go through a single
   `mutateLifecycle` client function that always sends one authenticated POST with the exact
   version read, and every TanStack mutation is configured with `retry: false`. Rejections
   surface only the backend's normalized reason token plus project-authored copy.
6. **Filters are URL state.** The lists treat the URL search as the single source of truth for
   the submitted filters so a deep entry, the rendered page and a reconnect continuation
   cannot disagree; detail routes carry only `q_status`/`q_command` back to their list.

### Remaining In-Slice Work

- **RO-3, RO-4:** bounded manual Scan/Preview and Web-native manual Organize remain later
  Slice 33 Tasks.
- **RO-5, RO-6:** scheduled Automation operation and Notification operation remain later
  Slice 33 Tasks.
- **RO-2 remainder:** the media-level recovery destinations a Task detail can hand off to are
  Slice 34 surfaces and are linked, not implemented, here.

### Risks / Deviations

- **Pre-existing Python failures (6), unrelated to this Task.** `tests.test_api_credentials`
  (2), `tests.test_final_integration` (1), `tests.test_resource_library_pipeline` (1) and
  `tests.test_runtime_storage_configuration` (2) fail in this root working directory. Proof of
  pre-existence: the Task Base commit `aae640b` was exported to an isolated directory and
  executed with this repository's private root-CWD runtime state present — the same 6 fail —
  while removing the private `.mediaflow/` runtime directory makes the same Task Base code
  pass. The private runtime state was preserved, not deleted. `FAIL / PRE-EXISTING /
  UNRELATED`; the PASS judgement is B's.
- **Docker release-security smoke FAIL / PRE-EXISTING / UNRELATED, not UNAVAILABLE.** Docker
  is available and the script runs, but `docker compose up -d --no-build` fails with
  `invalid mount config for type "bind": bind source path does not exist:
  /tmp/mediaflow-smoke-security-*/mediaflow.json`. Running the identical script at Task Base
  `aae640b` in a detached worktree produces the same failure, so it is not caused by this
  Task. Not inferred as passing.
- **`resume` remains a CLI workflow.** Per Task scope, an unsupported transition is advertised
  unavailable with an actionable reason instead of being fabricated; if the Slice requires a
  Web resume, the durable Worker command for paused-scope continuation has to be designed
  separately.
- **Backward compatibility.** An empty body on `POST /api/v1/tasks/{id}/cancel` and on
  `POST /api/v1/jobs/{id}/cancel` still succeeds; V1 `/ui` and `/api/v1/scans/{id}/cancel`
  are untouched. Cursors minted before this change without a filter scope are rejected only
  when a filter is submitted.

### Checkpoint

The implementation checkpoint `00f03e0003e81efdb62deb36a02683a3a338478c` is the coherent
correction commit for this Task; the follow-up `docs(task)` commit records this report and the
SHA itself and changes no product behavior. The reviewed range is
`aae640bd7111e9089bb67eb5fef8dbf50c2d85b8..HEAD`.

```text
Status: READY FOR B REVIEW
Head SHA: 00f03e0003e81efdb62deb36a02683a3a338478c
```

## B Review Result

```text
Reviewed: aae640bd7111e9089bb67eb5fef8dbf50c2d85b8..7ea6c2717af6bb752a56bd980f1a080f3d84d819
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- The Operations Web surface is not integrated with the authoritative backend contract. Evidence:
  `mediaflow/interfaces/service_api.py` accepts only `limit` and `cursor` on Task/Job collections,
  exposes no general Task `pause` or `resume` route, and routes Task `cancel` only through the manual
  Scan service; meanwhile the new Web client sends Task `status`, calls `/tasks/{id}/pause` and
  `/tasks/{id}/resume`, and the fake server fabricates those capabilities. The Task and Job action
  helpers also derive cancel/pause/resume solely from frontend status instead of consuming a
  backend-computed action projection for the exact principal/state/version. Implement the scoped
  backend status/command filtering and filter-bound cursors, authoritative lifecycle projection,
  and only the safe durable control behavior required by this Task; make V2 consume that real
  projection and prove permission, stale/duplicate, audit, preservation and zero-mutation rules
  against the Python API rather than only the Playwright fake.
- Required operator entry and filtering behavior is incomplete. Evidence: `TaskListPage` exposes
  status only, `JobListPage` exposes neither status nor command/work-kind filtering,
  `DashboardView` renders recent Task/Job failures as plain text rather than exact safe detail/list
  links, and `LibraryLanding` contains no bounded Operations cross-link. Add the required
  backend-submitted status/command controls and actionable Dashboard/Library links with the route
  and search allowlists required by the Acceptance Criteria.
- The frontend response boundary is not strict and the required focused proof is absent. Evidence:
  Task/Job/Worker normalizers cast arbitrary strings to enum types, coerce malformed booleans with
  `Boolean(...)`, coerce arbitrary Worker command values with `String(...)`, and do not reject the
  required contradictory states; the checkpoint adds no Operations unit/component/router test
  files and its four Operations browser tests cover only landing/list/detail navigation, not the
  required filtering, paging, action matrix, exact mutation/no-retry, malformed/auth failure,
  keyboard or responsive cases. Make normalization fail closed for the modeled contract and add
  the focused Python, frontend and built-artifact tests enumerated by this Task.
- The T4 checkpoint evidence is not truthful or complete. Evidence from B's rerun:
  `npm --prefix web run format:check` fails on
  `src/entities/operations/job.ts`, `src/entities/operations/task.ts` and
  `tests/e2e/operations.spec.ts`; `npm --prefix web run test -- --run` reports 190 passed and one
  failed, where `AuthBoundary.test.tsx` still expects `Operations Migration`; and the required
  focused Playwright command reports 18 passed and two failed for the same obsolete Operations
  Migration expectation. These failures are caused by this Task, not the reported pre-existing
  React/deep-link issues. The Completion Report also omits the two config validations and Docker
  security smoke result, and reports checkpoint SHA
  `1c5d5e9673603ce757ba1d072a41a7ba9a2344c4`, which exists but is not an ancestor of actual
  `HEAD` `7ea6c2717af6bb752a56bd980f1a080f3d84d819`. Correct the regressions, run and report every exact
  Required Tests command with actual totals/skips/unavailable gates, and create a new coherent
  checkpoint whose reported SHA is the real committed Head.

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
