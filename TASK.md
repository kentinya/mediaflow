# Task 33.1 — Operations command center and durable work control

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to the
current [`SLICE.md`](SLICE.md).

```text
Task ID: 33.1
Parent Slice: 33
Status: FIX REQUIRED
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

This third correction round changes the files listed below relative to the second corrected
checkpoint `4289d1456593dcfac43d51355e8d12647a3a71bc` (Task Base `aae640b` plus all previously
reviewed rounds). It fixes exactly the two new B blockers and their direct root causes.

**Modified files:**
- `mediaflow/infrastructure/sqlite_runtime.py` — `complete_claimed_job` is now one
  database-atomic statement: the same `UPDATE` reads the row's *current* cancellation flag in
  `CASE` expressions and folds it into the terminal outcome (status → `cancelled`, request flag
  kept, the arriving commit's error/failure evidence preserved), so no read-then-write seam
  exists; the definition occurrence is finalized from the outcome actually committed, read back
  inside the same transaction
- `mediaflow/application/operations_lifecycle.py` — `_bounded_evidence_text` fails closed on
  the full forbidden shape set (any `scheme://` endpoint, absolute POSIX path segment with or
  without a dotted file name, Windows drive/adapter root, UNC root) by replacing the whole
  evidence field with a bounded operator-safe constant; `_bounded_identity_path` applies the
  same shape detection
- `tests/test_operator_job_cancellation.py` — deterministic two-connection
  cancel-versus-terminal-commit test over real separate `SQLiteTaskRepository` connections
- `tests/test_operations_workspace.py` — the encoded-envelope hostile job now carries the
  endpoint, the absolute host directories and the Windows adapter root; field-level assertions
  prove the bounded constant replaces those fields while the credential-only field keeps its
  per-token redaction
- `web/src/entities/operations/task.test.ts`, `web/src/entities/operations/job.test.ts` — the
  model-level hostile record now carries the endpoint/directory/Windows-root forms and must
  expose none of them
- `web/src/features/operations/OperationsRouter.test.tsx` — the router/DOM proof uses the same
  extended hostile record
- `web/tests/fake-server.mjs`, `web/tests/e2e/operations.spec.ts` — the built-artifact browser
  proof's hostile legacy document carries the new forms and the DOM/console assertions reject
  them

### Implemented

- **One database-atomic terminal commit (B blocker 1).** The previous correction converted the
  arriving terminal commit in Python after a `SELECT cancellation_requested`; B demonstrated
  with two `SQLiteTaskRepository` connections that a Python `SELECT` does not establish writer
  serialization across connections, so a cancellation durably accepted between that `SELECT`
  and the terminal `UPDATE` could still be overwritten. The fix removes the seam entirely: the
  terminal commit is a single `UPDATE` whose `SET` list evaluates
  `CASE WHEN cancellation_requested=1` against the stored row *inside the statement*, folding an
  accepted request into `status='cancelled'`, `cancellation_requested=1` and
  `error=<arriving error or 'workflow cancelled'>`, while a clean commit writes the arriving
  values unchanged. The claim fencing (`status=running AND claim_token=? AND worker_id IS ?`) is
  unchanged, and the definition-occurrence projection now follows the outcome the database
  really committed (read back inside the same transaction), so a folded commit publishes the
  cancelled occurrence, not the submitted one.
- **Fail-closed evidence scrubbing for every host shape (B blocker 2).** The previous regex
  only replaced a POSIX chain ending in a dotted file name, so a private endpoint
  (`https://private.example/api`), bare absolute directories (`/home/alice/private`,
  `/mnt/private-library`) and a Windows adapter root (`C:\Users\alice\media`) survived in a
  decoded envelope. Detection is now a closed set of open-ended shape patterns (scheme
  endpoints, absolute POSIX path segments, drive roots, UNC roots) and, because laundering a
  detected value token by token cannot prove nothing slipped through, any field still carrying
  one of the shapes is replaced wholesale with the bounded operator-safe constant
  (`[redacted: the recorded evidence contained a credential, private endpoint or absolute host
  path]`), which never carries the original value. Credential-shaped values keep the existing
  in-place per-token redaction. `_bounded_identity_path` runs the same detection, so an
  identity column carrying any of the forms is the `[redacted-path]` marker.
- **Extended layered hostile-record proof (both blockers).** Two-connection interleaving test
  for the exact pause point B used, and the endpoint/directory/Windows-root forms asserted
  absent at every layer: the real API reads (list, detail, legacy), the strict frontend models,
  the router-rendered DOM and the built-artifact browser page (DOM, console, fetched URLs).

### Tests and Results

```text
python3 scripts/check_governance.py                                    → PASS
npm --prefix web ci (run as: env -u NODE_ENV npm --prefix web ci)       → PASS
    (this shell exports NODE_ENV=production, which makes npm omit
     devDependencies; with the variable unset the install is complete)
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
    tests.test_operations_workspace                                    → PASS (97 tests)
.venv/bin/python -m unittest discover -s tests                         → 1440 ran, 6 failed,
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
python3 scripts/docker_release_security_smoke_test.py                  → PASS over the committed
                                                                          implementation checkpoint
                                                                          (see Risks for why it
                                                                          runs after the commit)
```

New focused coverage added by this correction round (all passing):

- `tests.test_operator_job_cancellation` — `test_terminal_commit_folds_an_accepted_cancellation_
  across_two_connections`: one connection owns the Worker's terminal commit, a second connection
  over the same database durably accepts the cancellation for the exact state the Worker last
  observed (the pause point B used), and the Worker's own connection then submits the
  in-flight workflow as COMPLETED; the row must become `cancelled` with the request flag kept
  and the linked `task_id` preserved, the terminal commit still reported as accepted, and both
  connections must observe the same durable folded outcome.
- `tests.test_operations_workspace` — the hostile envelope job now carries all four B forms
  (`https://private.example/api`, `/home/alice/private`-style directories,
  `/mnt/private-library`, `C:\Users\alice\media`) across `message`/`durableState`/
  `sideEffects`/`nextAction`; every Operations read rejects all of them, the endpoint/path/root
  fields equal the bounded operator-safe constant, and the credential-only field keeps its
  per-token redaction.
- Frontend: the entity model suites, the router DOM suite and the built-artifact browser suite
  all use the extended hostile record (credential + endpoint + absolute directories + Windows
  adapter root + fingerprint + display root) and must expose none of its values, while the
  provably relative `movie.mkv` identity stays visible.

### Decisions

1. **The fold lives in the SQL statement, not in Python.** Any Python-side read of the flag
   establishes a read-then-write seam that a second connection can exploit, exactly as B
   demonstrated. The single `UPDATE` with `CASE WHEN cancellation_requested=1` against the
   stored row is atomic under SQLite's writer serialization for any connection count, and the
   claim fencing stays byte-for-byte unchanged, so the existing stale-claim/wrong-owner/requeue
   guarantees in `test_automation_job_fencing` remain untouched (all still pass).
2. **The occurrence projection follows the committed outcome.** Because the terminal status is
   now decided inside the statement, the code no longer knows at Python level which branch the
   database took; it re-reads the row inside the same transaction and finalizes the Automation
   definition occurrence from the actually committed status, so a folded commit publishes a
   cancelled occurrence with truthful Task evidence instead of the submitted one.
3. **Detection + whole-field fail closed, not token laundering.** Host path/endpoint shapes are
   open-ended (POSIX directories without a dotted name, drive roots, UNC roots, any scheme), so
   a replacing regex can always be beaten by a new spelling — which is what B demonstrated.
   The implementation now detects with a deliberately broader closed shape set and replaces the
   whole evidence field with a fixed bounded constant when any shape survives; a false positive
   only costs benign detail, while a false negative would leak a host value. Credential values
   keep the proven in-place per-token redaction.
4. **The same shape detection backs the identity projection.** `_bounded_identity_path` already
   failed closed on absolute/scheme/drive/`..`/credential values; it now also runs the shared
   shape scan, so an identity column carrying any forbidden form is `[redacted-path]`.
5. **Unchanged from the previous rounds:** the bounded `/api/v1/operations/*` read alias, the
   legacy compatibility documents' deliberate fields (`source_display`, pinned digest),
   execution-path-scoped controls, digest-free strict frontend models, filter-bound cursors,
   one retry-disabled `mutateLifecycle`, and `resume` still advertised unavailable rather than
   fabricated.

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
  fail in this root working directory with exactly the same failure set and the same private-CWD
  driver documented by the previous rounds (private local runtime configuration that exists only
  in this root working directory; no changed module is exercised by their failing assertions).
  This round's diff touches only `complete_claimed_job`, the Operations evidence/identity
  scrubbing, and test/fake files — none of the four failing modules. The detached Task Base
  worktree proof from the first round remains valid.
  `FAIL / PRE-EXISTING / UNRELATED`; the PASS judgement is B's.
- **Docker release-security smoke PASSED, but only over a committed tree and with one
  environment caveat** (unchanged from the previous round): the harness builds its candidate
  image from `git archive HEAD`, so it was run after the implementation checkpoint `461b11e` was
  committed; it passed end to end (build, image/Compose inspection, four-service stack,
  RBAC/redaction probes, managed activation, Worker restart, durable-evidence scan). The
  environment caveat: the harness's bind-mount sources must be visible to the Docker daemon,
  and this session's sandboxed `/tmp` is not, so the smoke only succeeds when its `TMPDIR`
  points into a daemon-visible path (run here with `TMPDIR=/root/mediaflow/.smoke-tmp`, removed
  afterwards; the direct `/tmp` runs fail with `bind source path does not exist` before any
  product code is exercised — an environment limitation, not a product failure).
- **Residual compatibility surface B may want to rule on** (unchanged from the previous rounds):
  the legacy `GET /api/v1/tasks/{id}` and `GET /api/v1/jobs/{id}` documents still carry
  `configuration_snapshot_digest` (a pre-existing configuration-pin test asserts the exact
  value) and the task-item `source_display` the V1 operator UI renders. The V2 Operations
  workspace never reads those documents, and its own projection carries neither.
- **Evidence over-redaction trade-off.** A structured failure field that legitimately mentioned
  a public provider URL would now be replaced wholesale by the bounded constant; the closed
  failure vocabulary explains provider failures without URLs, and the alternative (laundering
  URLs per token) is exactly the fragility B rejected. No existing test relied on such content.
- **`resume` remains a CLI workflow.** Per Task scope, an unsupported transition is advertised
  unavailable with an actionable reason instead of being fabricated.
- **Backward compatibility** (unchanged from the previous rounds): an empty body on the legacy
  cancel endpoints still succeeds; V1 `/ui` and the pre-existing compatibility documents are
  untouched apart from the redactions B required; cursors minted before this change without a
  filter scope are rejected only when a filter is submitted.

### Checkpoint

The implementation checkpoint `461b11e0957da40cdd3461e0d8bccfc486c462c3` (recorded above as
`Head SHA`) is the coherent correction commit for this Task: it carries the code and the tests
of this correction round, and it is the SHA the release-security smoke ran against. The
follow-up `docs(task)` commit records this report and the SHA itself and changes no product
behavior, so the reviewed range is
`aae640bd7111e9089bb67eb5fef8dbf50c2d85b8..HEAD` with HEAD being that docs commit (a direct
child of the implementation checkpoint).

```text
Status: READY FOR B REVIEW
Head SHA: 461b11e0957da40cdd3461e0d8bccfc486c462c3
```

## B Review Result

```text
Reviewed: aae640bd7111e9089bb67eb5fef8dbf50c2d85b8..0b1a447fb4256d4e3b76b032287a4f4c9dd81f56
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Job cancellation is still not atomic across the real API/Worker connection boundary. Evidence:
  B used two `SQLiteTaskRepository` instances over the same database and paused the Worker's
  `complete_claimed_job()` after its new `SELECT cancellation_requested` but before its terminal
  `UPDATE`; the second connection then durably accepted cancellation as `status=running,
  cancellation_requested=True`. The original terminal update subsequently returned `True` and the
  final row became `status=completed, cancellation_requested=False`. A Python SQLite `SELECT` does
  not establish the claimed writer serialization here, and the UPDATE still does not bind or fold
  the current cancellation flag. Make cancellation-versus-terminal-commit one database-atomic
  transition across separate connections/processes, and add a deterministic two-connection test
  that proves an accepted cancellation cannot be overwritten in this interleaving.
- Structured failure evidence is still not bounded against the full forbidden path/endpoint set.
  Evidence: B stored a valid `mediaflow-failure-v1` Job envelope containing
  `https://private.example/api`, the absolute directories `/home/alice/private` and
  `/mnt/private-library`, and the Windows adapter root `C:\\Users\\alice\\media`; `GET
  /api/v1/operations/jobs/job-paths` returned HTTP 200 with all four values in its `failure`
  document. `_bounded_evidence_text()` only replaces a narrow POSIX path pattern ending in a dotted
  filename, so the new envelope scrubbing does not satisfy the prohibition on private endpoints and
  absolute host/adapter roots. Fail closed to bounded operator-safe evidence for these forms (without
  exposing the original value) and extend the real API/model/DOM hostile-record proof beyond one
  `.mkv` POSIX path.

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
