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

This correction changes the files listed below relative to the B-reviewed head
`d877dc19e49e1f9156f53b2f3ed40857a15dbc20` (Task Base `aae640b` plus the previously reviewed
implementation). Paragraph at the end of this section names what the first reviewed round
contributed and this correction keeps.

**Modified files:**
- `mediaflow/application/operations_lifecycle.py` — execution-path-scoped control matrix,
  atomic compare-and-set admission, bounded secret-free Task/TaskItem/Result/Job/manual-Scan
  operator projections
- `mediaflow/infrastructure/sqlite_runtime.py` — `pause_task_if_current`,
  `cancel_task_if_current`, `claim_manual_scan_cancellation` and a compare-and-set Job
  cancellation that binds state, the unset request flag and the observed version
- `mediaflow/domain/task_persistence.py` — concrete CAS protocol methods, the manual-Organize
  command marker, `TaskControlOutcome`-free `PersistentTask | None` contract
- `mediaflow/domain/automation.py` — `AutomationJobControlConflict`, `job_control_version`,
  CAS `request_job_cancellation` signature
- `mediaflow/application/task_runtime.py` — `cancellation_observed` boundary signal and the
  `finish` fence that never resurrects a durably cancelled Task
- `mediaflow/application/automation.py`, `mediaflow/application/automation_definition_execution.py`
  — version-passing Job cancel and definition-scoped boundary observation
- `mediaflow/final_cli.py` — durable-cancel observation in every workflow stop function and the
  queued-workflow rule that reports a cancelled Task as a cancelled Job
- `mediaflow/interfaces/service_api.py` — bounded `/api/v1/operations/*` read alias, bounded
  control responses, redacted compatibility documents, atomic manual-Scan claim
- `tests/test_operations_workspace.py` — concurrent-request, live-handler/lock-preservation,
  unsupported-path and hostile-historical-record proof
- `web/src/entities/operations/task.ts`, `job.ts`, `worker.ts`, `lifecycle.ts` (+ tests) —
  digest-free, failure-evidence-only models aligned with the bounded contract
- `web/src/features/operations/TaskDetailPage.tsx`, `JobDetailPage.tsx` — render normalized
  failure evidence and Storage-relative sources instead of raw errors, digests and display roots
- `web/src/shared/api/api-client.ts` (+ test) — reads `/api/v1/operations/*`
- `web/src/features/operations/OperationsRouter.test.tsx`, `web/src/shared/auth/AuthBoundary.test.tsx`
  — router journeys, the hostile-record DOM proof and the Operations readiness URL
- `web/tests/e2e/operations.spec.ts`, `web/tests/fake-server.mjs` — built-artifact hostile-record
  proof and a fake that serves the bounded Operations documents

Unchanged from the first round and still part of the Task: the filter-bound cursor scope in
`mediaflow/interfaces/pagination.py`, the destination-model allowlists, the Dashboard/Library
links, list pages, styles and the remaining entity/API tests listed in the previous report.

### Implemented

- **Atomic, execution-path-truthful lifecycle controls (B blocker 1, first half).** Pause,
  cancel and the manual-Scan cancellation are now single compare-and-set transitions
  (`UPDATE … WHERE <identity> AND <cancellable state> AND <request flag unset> AND <observed
  version>`); two concurrent submissions of the same version admit exactly one control and
  refuse the other 409 with the durable reason. A control is advertised only for an
  `executionPath` that really observes it: the operator/Worker workflow path (all of its stop
  functions poll the durable pause request and the durable cancellation), the manual Scan
  service (its own durable cancellation request), and not at all for the synchronous manual
  Organize Task that observes neither.
- **Cooperative cancellation observed at the supported boundary (B blocker 1, second half).**
  `cancel_task_if_current` marks the Task and its non-terminal items cancelled in one
  transaction and releases only the locks that belong to no in-flight item; an item that is
  already being processed keeps its confinement lock, completes under its own Result, and
  releases the lock itself. Every CLI/Worker workflow stop function now polls
  `cancellation_observed`, so the accepted cancellation stops the loop at an item boundary; the
  queued-workflow wrapper and the definition-scoped runner report the owning Job as *cancelled*
  instead of *completed*; and `finish()` refuses to overwrite a durably cancelled Task, so a late
  completion can never resurrect it. For a claimed Job the bound control version is its
  immutable claim time, because `updated_at` advances with Worker liveness heartbeats.
- **Bounded, secret-free Operations projection (B blocker 2).** The V2 workspace reads the new
  `/api/v1/operations/{tasks,jobs,workers}` alias, which serves explicit allowlisted documents:
  raw durable errors become normalized failure evidence, and configuration digests, definition
  fingerprints, source fingerprints/occurrences and configured display roots are absent. The
  pre-existing `/api/v1/*` compatibility documents keep their historical keys (the V1 operator
  UI still renders `source_display`, and a pre-existing configuration-pin test asserts the
  pinned digest) but no longer echo a raw durable error, and the claim/fence/scope/fingerprint
  values are gone from them as well.
- **Strict frontend boundary aligned with the real contract.** Every Operations model fails
  closed on unknown statuses/commands/conditions, coerced booleans, contradictory
  progress/terminal pairs, contradictory uncertain-effect evidence, a stale or cross-object
  lifecycle projection, or an actionable control for a read-only principal; the models no longer
  carry a digest, and the TaskItem checkpoint model now matches the keys
  `ProcessingCheckpoint.summary()` really sends (the previous model demanded three keys the API
  never produced, which would have made every real Task detail malformed).
- **Operator entry, filtering and truthful evidence (unchanged from the reviewed round):**
  backend status/command filters with filter-bound cursors, actionable Dashboard/Library links,
  URL-driven filters, no automatic mutation replay, normalized audit routes and keyboard/
  responsive built-artifact proof.

### Tests and Results

```text
python3 scripts/check_governance.py                                    → PASS
npm --prefix web ci (run as: env -u NODE_ENV npm --prefix web ci)       → PASS
    (this shell exports NODE_ENV=production, which makes npm omit
     devDependencies and leaves web/node_modules unusable; with the
     variable unset the install is complete)
npm --prefix web run format:check                                      → PASS (all files formatted)
npm --prefix web run typecheck                                         → PASS (0 errors)
npm --prefix web run lint                                              → PASS (0 problems)
npm --prefix web run test -- --run                                     → PASS (259 tests, 23 files)
npm --prefix web run build                                             → PASS
npm --prefix web run test:e2e -- operations.spec.ts dashboard.spec.ts
    deep-link.spec.ts                                                  → PASS (36 passed)
npm --prefix web run test:e2e                                          → PASS (74 passed)
.venv/bin/python -m unittest tests.test_operator_observability
    tests.test_operator_job_cancellation tests.test_task_pause_resume
    tests.test_processing_worker_readiness tests.test_api_security
    tests.test_dashboard tests.test_v2_ui
    tests.test_operations_workspace                                    → PASS (94 tests)
.venv/bin/python -m unittest discover -s tests                         → 1437 ran, 6 failed,
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
python3 scripts/docker_release_security_smoke_test.py                  → PASS over the
                                                                         committed implementation
                                                                         checkpoint (see Risks for
                                                                         why it is run after the
                                                                         commit)
```

New focused coverage added by this correction (all passing):

- `tests/test_operations_workspace.py` — 20 tests. Nine of them are new here: two-thread
  concurrent pause/cancel/Job-cancel admission (`[200, 409]` exactly once each, with the durable
  reason on the loser), live-handler cancellation on an execute-authorized Task (in-flight lock
  preserved, idle lock released, the in-flight item's own outcome recorded, the late `finish()`
  refused), the manual Scan path (pause withheld with a reason, cooperative cancel still
  available, POST pause 409 with no durable change), the synchronous manual-Organize Task (both
  controls withheld, 409s, no lock release, execute authority untouched), the hostile
  historical-record sweep over the Operations reads (credentials, private paths, source
  fingerprints and the configuration digest absent; bounded failure evidence present; the
  compatibility read no longer echoes the raw record), the Worker/Job cancellation rule, and the
  zero-side-effect plus fingerprint-free `operations` read set with normalized audit routes.
- Frontend: entity/model suites prove the digest-free and raw-error-free boundary (including a
  hostile payload that must not reach the model), the router suite proves the same rule through
  the real router/DOM, and `operations.spec.ts` adds a built-artifact test that opens a Task
  whose record still carries a credential, a private path and a fingerprint and asserts the DOM,
  the console and the fetched URLs contain none of them while the read targets
  `/api/v1/operations/…`.

### Decisions

1. **Cancel is a durable cooperative transition, not an immediate teardown.** The accepted
   control marks the Task and its non-terminal items cancelled in one transaction but releases
   only the locks of items that are not in flight; the item being processed keeps its
   confinement lock, records its own Result and releases the lock itself. This is what makes the
   advertised outcome true: no further item is admitted, an in-flight Provider/Storage call is
   never interrupted, no completed effect is undone, and no later completion can overwrite the
   cancellation (`finish` returns the durable cancelled Task unchanged).
2. **Controls are scoped to the execution path that observes them.** `executionPath` is derived
   from existing durable records (a manual Scan scope row, the `manual_organize` command, or an
   operator/Worker workflow). Pause is advertised only where a workflow stop function polls
   `pause_requested`; the manual Scan Task is offered the cancellation its own service observes;
   the synchronous manual-Organize Task is offered neither with an actionable reason. A Task
   kind whose path cannot observe a control never receives a button for it.
   A cancelled Task keeps the aggregate counters it had when the cancellation was accepted —
   the durable item and Result rows are the authoritative per-item state, and the detail page
   renders them independently rather than recomputing an aggregate that would imply the
   cancelled work finished.
3. **Each control binds the version the operator really acted on.** A Task's `updated_at` only
   moves on semantic transitions, so it is bound exactly. A claimed Job advances `updated_at`
   with Worker liveness heartbeats, which is not a state transition, so `job_control_version`
   publishes and binds its immutable claim time instead — otherwise a running Job could never be
   cancelled from the Web despite a fresh read.
4. **The Operations projection gets its own bounded read alias instead of mutating the legacy
   documents.** `GET /api/v1/tasks|jobs|workers` keep their historical keys because the V1
   operator UI renders `source_display` and a pre-existing configuration-pin test asserts the
   pinned digest; removing those from the legacy reads would break V1 compatibility, which the
   Task explicitly forbids. The V2 workspace therefore reads `/api/v1/operations/…`, which is
   an explicit allowlist with no raw error, no digest/fingerprint and no display root. The
   legacy reads were still improved: the raw durable error is replaced by its normalized
   message plus bounded evidence, and claim/fence/scope/fingerprint values are gone.
5. **Structured failure evidence is scrubbed, not trusted.** A legacy or externally written row
   can hold anything in `error`, `failure_*` or a stored failure envelope, so the bounded
   projection redacts credential-shaped text and absolute file paths before publishing it, and
   otherwise classifies into the closed operator-facing vocabulary. The compatibility `error`
   key keeps its name but carries that normalized message.
6. **Resume is still advertised unavailable, not fabricated** (unchanged reason: no durable
   queued continuation of one exact paused scope exists; the operator CLI workflow owns it).
7. **Unchanged from the reviewed round:** command-family Task filtering, optionally scoped
   cursors, effect certainty only from a provably complete Result view, one
   retry-disabled `mutateLifecycle` client boundary, and URL-as-state filters.

### Remaining In-Slice Work

- **RO-3, RO-4:** bounded manual Scan/Preview and Web-native manual Organize remain later
  Slice 33 Tasks.
- **RO-5, RO-6:** scheduled Automation operation and Notification operation remain later
  Slice 33 Tasks.
- **RO-2 remainder:** the media-level recovery destinations a Task detail can hand off to are
  Slice 34 surfaces and are linked, not implemented, here.

### Risks / Deviations

- **Pre-existing Python failures (6), unrelated to this Task — re-proved this round.**
  `tests.test_api_credentials` (2), `tests.test_final_integration` (1),
  `tests.test_resource_library_pipeline` (1) and `tests.test_runtime_storage_configuration` (2)
  fail in this root working directory. Direct proof (re-run by this correction, not inherited
  from the previous report): the Task Base commit `aae640b` was checked out into a detached
  worktree, this repository's private root-CWD runtime state was copied in, and the four
  affected modules produced exactly the same 6 failures with identical assertion messages
  (`Ran 23 tests … FAILED (failures=6)`); the private runtime state was preserved and the
  temporary worktree plus its copy were removed afterwards. The failures are driven by private
  local runtime configuration that exists only in this root working directory (a local Storage
  and ResourceLibrary the ignored runtime state points at, whose exact paths are deliberately
  not repeated here) and no changed module is exercised by their failing assertions.
  `FAIL / PRE-EXISTING / UNRELATED`; the PASS judgement is B's.
- **Docker release-security smoke now PASSES, but only over a committed tree.** The harness
  builds its candidate image from `git archive HEAD`, so it cannot see uncommitted work. It was
  therefore run *after* the implementation checkpoint was committed and it passed end to end
  (build, image/Compose inspection, four-service stack, RBAC/redaction probes, managed
  activation, Worker restart, durable-evidence scan). The previous round's failure
  (`invalid mount config … bind source path does not exist`) was environmental and did not
  reproduce.
- **Residual compatibility surface B may want to rule on.** The legacy
  `GET /api/v1/tasks/{id}` and `GET /api/v1/jobs/{id}` documents still carry
  `configuration_snapshot_digest` (a pre-existing configuration-pin test asserts the exact
  value) and the task-item `source_display` the V1 operator UI renders. The V2 Operations
  workspace never reads those documents, and its own projection carries neither. Removing them
  from the legacy reads would require changing that pre-existing test and the V1 UI contract,
  which is a B/A decision rather than a Developer choice.
- **Compatibility change on the legacy reads.** Their `error` values are now the normalized
  failure message instead of the raw durable string (the credential/path leak B demonstrated),
  and the internal claim/fence/scope/fingerprint keys are no longer published. No existing test
  asserts those raw values; the normalized evidence is additive (`failure`).
- **`resume` remains a CLI workflow.** Per Task scope, an unsupported transition is advertised
  unavailable with an actionable reason instead of being fabricated; if the Slice requires a
  Web resume, the durable Worker command for paused-scope continuation has to be designed
  separately.
- **Backward compatibility.** An empty body on `POST /api/v1/tasks/{id}/cancel` and on
  `POST /api/v1/jobs/{id}/cancel` still succeeds (it then binds state and the request flag
  atomically); V1 `/ui`, `/api/v1/scans/{id}/cancel` and the pre-existing compatibility
  documents are untouched apart from the redaction above. Cursors minted before this change
  without a filter scope are rejected only when a filter is submitted.

### Checkpoint

The implementation checkpoint `16dc2864b1c8fade8c7b8fb7fccb3ca44f54fddb` (recorded above as
`Head SHA`) is the coherent correction commit for this Task: it carries the code and the tests
of this correction, and it is the SHA the release-security smoke ran against. The
follow-up `docs(task)` commit records this report and the SHA itself and changes no product
behavior, so the reviewed range is
`aae640bd7111e9089bb67eb5fef8dbf50c2d85b8..HEAD` with HEAD being that docs commit (a direct
child of the implementation checkpoint).

```text
Status: READY FOR B REVIEW
Head SHA: 16dc2864b1c8fade8c7b8fb7fccb3ca44f54fddb
```

## B Review Result

```text
Reviewed: aae640bd7111e9089bb67eb5fef8dbf50c2d85b8..d877dc19e49e1f9156f53b2f3ed40857a15dbc20
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Lifecycle controls are not concurrency-fenced or truthfully coupled to every execution path for
  which they are advertised. Evidence: `TaskLifecycleService` checks `updated_at` in a separate read
  before repository mutation; B's two-thread barrier probe submitted the same version twice and
  both calls succeeded for both `pause` and `cancel`. Job cancellation uses the same separate
  version check and its repository update does not compare the expected version or require
  `cancellation_requested=0`. More critically, general Task cancel immediately marks the Task/items
  cancelled and releases locks, while active Worker/CLI loops observe Job cancellation and/or
  `pause_requested`, not the Task's cancelled status. B's state probe produced
  `after_web_cancel=cancelled` followed by `after_inflight_finish=completed`, proving in-flight work
  can overwrite the advertised durable cancellation; for execute-authorized work this also releases
  confinement locks before the real execution boundary has stopped. Pause is advertised for every
  running Task even though `ManualScanService` never observes or acknowledges a Task pause request.
  Make each advertised action specific to an execution path that really cooperates with it, bind
  expected version/state/request flags in one atomic compare-and-set transition, and ensure an
  accepted pause/cancel is observed at the supported boundary without premature lock release or a
  later completion overwriting it. Add deterministic concurrent-request and live-handler tests,
  including execute-authorized/lock preservation and unsupported Task kinds.
- The Operations projection exposes fields that this Task explicitly forbids from API/model/DOM
  evidence. Evidence: Task and Job models retain `configuration_snapshot_digest`, the detail pages
  render that digest, and Worker models retain the Active snapshot digest; `_job_document()` starts
  from the generic dataclass projection, which also retains `definition_fingerprint` and
  `source_scope`. Task/TaskItem/Result/Job raw `error` strings are normalized and rendered directly.
  B inserted a historical Task error containing `Authorization: Bearer topsecret` and
  `/home/alice/private.mkv`; `GET /api/v1/tasks/{id}` returned both values verbatim with HTTP 200,
  together with the configured snapshot fingerprint. Replace the generic/raw Operations response
  fields with bounded secret-free operator projections, remove fingerprint/digest and absolute
  host/adapter-root values from frontend models and rendering, and use normalized failure evidence
  rather than raw durable errors. Add hostile historical-record tests that inspect the real API,
  normalized models, DOM, console and browser artifacts for credentials, fingerprints and paths.

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
