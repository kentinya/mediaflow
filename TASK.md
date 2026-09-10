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

This second correction round changes the files listed below relative to the first corrected
checkpoint `16dc2864b1c8fade8c7b8fb7fccb3ca44f54fddb` (Task Base `aae640b` plus both previously
reviewed rounds). It fixes exactly the two B blockers and their direct root causes; everything
from the earlier rounds remains in place.

**Modified files:**
- `mediaflow/infrastructure/sqlite_runtime.py` — `complete_claimed_job` now fences the terminal
  commit of a claimed Job against the durable cancellation flag: a completion or failure that
  arrives after an accepted cancellation is converted into the same cancelled outcome the
  Worker's own boundary publishes (claim fencing unchanged, failure evidence preserved)
- `mediaflow/application/operations_lifecycle.py` — `job_failure_document` scrubs a decoded
  durable failure envelope through the same bounded credential/path redaction as classified
  evidence; failure categories are path-scrubbed; new fail-closed `_bounded_identity_path`
  projects only provably Storage-relative source/destination identities in the TaskItem,
  Result and manual-Scan projections
- `mediaflow/interfaces/service_api.py` — the legacy `/api/v1/*` compatibility item/result
  documents apply the same identity projection, so a hostile persisted identity column cannot
  leak through either read (the V1-rendered `source_display` and the pinned
  `configuration_snapshot_digest` are unchanged)
- `tests/test_operator_job_cancellation.py` — two deterministic cancel-versus-terminal-commit
  tests (COMPLETED and FAILED races) binding the claim-time `job_control_version`
- `tests/test_operations_workspace.py` — the real-API hostile-record proof extended with a
  syntactically valid `mediaflow-failure-v1` envelope carrying a credential and a private path,
  and TaskItem/Result rows carrying absolute host paths in their identity columns; the
  relative-identity and bounded-evidence assertions are preserved and strengthened

Unchanged from the previous rounds: the filter-bound cursor scope, destination-model
allowlists, Dashboard/Library links, list/detail pages, styles and all other entity/API tests.

### Implemented

- **Terminal commits can no longer overwrite an accepted cancellation (B blocker 1).**
  `complete_claimed_job` first reads the durable row inside the same transaction, fenced on
  `job_id + status=running + claim_token + worker_id`. If the cancellation flag is set and the
  submitted commit is not itself the cancelled outcome, the commit is rewritten in memory to
  `status=cancelled, cancellation_requested=true` (error text and any recorded failure evidence
  of the arriving commit are preserved, and a pure completion becomes
  `error="workflow cancelled"` like the Worker's own cancellation boundary) before the UPDATE
  runs. The linked Task keeps its own truthful per-item state. A stale commit with a wrong
  token still returns `False` exactly as before, and the accepted request can never be lost and
  reported as success.
- **Every structured failure branch is scrubbed (B blocker 2, envelopes).** A decoded
  `mediaflow-failure-v1` envelope is no longer trusted as-is: `job_failure_document` publishes
  it only after the same `_bounded_evidence_text` pass used for classified evidence, so a
  credential-shaped value in `message`/`sideEffects` and an absolute host path in
  `durableState`/`nextAction` are replaced while the category and structure survive. The
  `failure_category` branch uses the same bounded pass instead of a bare credential-only
  redaction.
- **Persisted identities fail closed (B blocker 2, identity columns).** New
  `bounded_identity_path` publishes a persisted `source_path`/`destination_path` only when it is
  a provably Storage-relative identity (relative, no drive/scheme/backslash/`..` segment, within
  the bounded length, credential-free); anything else — absolute host/adapter roots, private
  endpoints, credential-shaped values, non-strings — becomes `[redacted-path]`. It is applied in
  the TaskItem and Result Operations projections, the manual-Scan `sourcePath` fields of the
  Operations document, and the legacy compatibility item/result documents, so no Task/Job read
  can echo a hostile identity column.
- **Deterministic regression tests for the exact boundaries B demonstrated.** Two
  cancel-versus-terminal-commit tests on a real claimed SQLite Job, and the extended real-API
  hostile-record proof covering encoded envelopes and hostile identity columns end to end
  (list, detail and legacy reads; relative identities and bounded failure evidence stay
  visible).

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
    tests.test_operations_workspace                                    → PASS (96 tests)
.venv/bin/python -m unittest discover -s tests                         → 1439 ran, 6 failed,
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

- `tests.test_operator_job_cancellation` — two deterministic cancel-versus-terminal-commit
  tests: an accepted running-Job cancellation survives a COMPLETED `complete_claimed_job` (row
  becomes `cancelled`, request flag stays set, claim released, linked `task_id` preserved) and
  also survives a FAILED terminal commit (status fenced, the workflow's own failure evidence
  kept truthful).
- `tests.test_operations_workspace` — the hostile-record sweep now also covers a valid encoded
  failure envelope (credential in `message`/`sideEffects`, private path in
  `durableState`/`nextAction`) and TaskItem/Result identity columns holding absolute host
  paths; every Operations and legacy read must contain neither value, the envelope must still
  publish as bounded evidence (`[redacted]`/`[redacted-path]` in the right fields), and the
  hostile identities must project as `[redacted-path]` while the provably relative
  `movie.mkv` identity stays visible.

### Decisions

1. **The accepted cancellation wins at the Job level; per-item truth stays in the Task.** When
   a terminal commit races an accepted cancellation, the Job becomes `cancelled` — the same
   outcome the Worker's own cancellation boundary publishes — while the linked Task keeps its
   own status, items and Results. A genuinely failed workflow that also raced a cancellation
   keeps its recorded `error` and failure evidence under the cancelled status, so the operator
   sees both truths instead of losing the accepted request. A pure completion becomes
   `error="workflow cancelled"`, matching the existing `AutomationCancelled` convention.
2. **The fence is an in-transaction read plus the unchanged fenced UPDATE, not a new SQL
   predicate.** Reading the flag inside the same lock/transaction is race-free (SQLite serializes
   writers) and keeps the existing claim fencing (`status=running AND claim_token=?
   AND worker_id IS ?`) byte-for-byte, so the stale-claim, wrong-owner and requeue guarantees
   tested in `test_automation_job_fencing` are untouched.
3. **Identity columns fail closed to `[redacted-path]`, not to omission.** The bounded marker
   keeps the document shape the strict frontend models require (they validate `source_path` as a
   string) while never publishing an unverified identity; provably relative identities still
   render as before (`movie.mkv` proof retained).
4. **The same identity rule was applied to the legacy compatibility item/result documents.**
   The B evidence leak existed in the persisted columns, so bounding them only in the Operations
   projection would leave the same hostile row leaking through `/api/v1/tasks/{id}`. A legit
   relative identity is unchanged there; the V1-rendered `source_display` and the pinned
   configuration digest are untouched, so no V1 contract change occurs.
5. **Unchanged from the previous rounds:** atomic execution-path-scoped controls, cooperative
   cancellation observed at item boundaries, digest-free strict frontend models, the
   `/api/v1/operations/*` bounded read alias, command-family filtering with filter-bound
   cursors, one retry-disabled `mutateLifecycle`, and `resume` still advertised unavailable
   rather than fabricated.

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
  fail in this root working directory with the same set of failures and the same private-CWD
  driver documented by the previous round (private local runtime configuration that exists only
  in this root working directory; no changed module is exercised by their failing assertions).
  This correction's diff touches only `sqlite_runtime.complete_claimed_job`, the Operations
  projection in `operations_lifecycle`, the compatibility item/result documents in
  `service_api`, and two focused test files — none of the four failing modules. Direct proof
  from the previous round (a detached Task Base worktree reproducing exactly these 6 failures)
  remains valid; `FAIL / PRE-EXISTING / UNRELATED`; the PASS judgement is B's.
- **Docker release-security smoke PASSED, but only over a committed tree and with one
  environment caveat.** The harness builds its candidate image from `git archive HEAD`, so it
  was run after the implementation checkpoint `4289d14` was committed; it passed end to end
  (build, image/Compose inspection, four-service stack, RBAC/redaction probes, managed
  activation, Worker restart, durable-evidence scan). The environment caveat: the harness's
  bind-mount sources must be visible to the Docker daemon, and this session's sandboxed `/tmp`
  is not, so the smoke only succeeds when its `TMPDIR` points into a daemon-visible path (run
  here with `TMPDIR=/root/mediaflow/.smoke-tmp`, removed afterwards; the direct `/tmp` runs fail
  with `bind source path does not exist` before any product code is exercised — an environment
  limitation, not a product failure).
- **Residual compatibility surface B may want to rule on** (unchanged from the previous round):
  the legacy `GET /api/v1/tasks/{id}` and `GET /api/v1/jobs/{id}` documents still carry
  `configuration_snapshot_digest` (a pre-existing configuration-pin test asserts the exact
  value) and the task-item `source_display` the V1 operator UI renders. The V2 Operations
  workspace never reads those documents, and its own projection carries neither.
- **`resume` remains a CLI workflow.** Per Task scope, an unsupported transition is advertised
  unavailable with an actionable reason instead of being fabricated.
- **Backward compatibility** (unchanged from the previous round): an empty body on the legacy
  cancel endpoints still succeeds; V1 `/ui` and the pre-existing compatibility documents are
  untouched apart from the redactions B required; cursors minted before this change without a
  filter scope are rejected only when a filter is submitted.

### Checkpoint

The implementation checkpoint `4289d1456593dcfac43d51355e8d12647a3a71bc` (recorded above as
`Head SHA`) is the coherent correction commit for this Task: it carries the code and the tests
of this correction round, and it is the SHA the release-security smoke ran against. The
follow-up `docs(task)` commit records this report and the SHA itself and changes no product
behavior, so the reviewed range is
`aae640bd7111e9089bb67eb5fef8dbf50c2d85b8..HEAD` with HEAD being that docs commit (a direct
child of the implementation checkpoint).

```text
Status: READY FOR B REVIEW
Head SHA: 4289d1456593dcfac43d51355e8d12647a3a71bc
```

## B Review Result

```text
Reviewed: aae640bd7111e9089bb67eb5fef8dbf50c2d85b8..10a79850934cf03ca2f991b70dd1e64c3f9e188f
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Running Job cancellation is still vulnerable to a cancel-versus-terminal-commit race, so an
  accepted durable request can be lost and reported as success. Evidence: B claimed a real SQLite
  Job, called `request_job_cancellation(..., expected_version=job_control_version(claimed))`, then
  submitted the already-in-flight claimed Job as `COMPLETED` through `complete_claimed_job()`.
  The cancellation first persisted as `status=running, cancellation_requested=True`, but the stale
  completion returned `True` and the final row became `status=completed,
  cancellation_requested=False`. `complete_claimed_job()` fences status/claim/worker but not the
  cancellation flag, leaving a race after `AutomationWorker`'s final cancellation poll. Make the
  terminal commit unable to overwrite an accepted cancellation (while preserving claim fencing and
  truthful Task/Job outcome), and add a deterministic cancel-versus-completion test for this exact
  boundary.
- The bounded Operations projection still permits hostile persisted data to expose credentials and
  absolute host paths. Evidence: B stored a syntactically valid `mediaflow-failure-v1` Job envelope
  whose message/side-effects contained `Authorization: Bearer topsecret` and whose durable/next
  fields contained `/home/alice/private.mkv`; `GET
  /api/v1/operations/jobs/job-envelope` returned HTTP 200 with both values verbatim because
  `job_failure_document()` returns decoded envelopes without scrubbing. B also stored absolute
  `source_path` values on a TaskItem and Result; `GET
  /api/v1/operations/tasks/task-path` returned `/home/alice/private.mkv` verbatim because the
  allowlisted projection assumes, but does not validate or bound, Storage-relative identities.
  Scrub every structured failure branch and fail closed or safely project persisted source/
  destination identities so credentials, private endpoints and absolute host/adapter roots cannot
  reach the Operations API/model/DOM. Extend the real-API hostile-record proof to cover encoded
  envelopes and hostile identity columns, not only plain errors/display roots.

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
