# Task 42.1 — Unified run inventory and selected-run overview

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 42.1
Parent Slice: 42
Status: READY FOR B REVIEW
Task Base: f1806d3a13c0ab0538c07749ff82621782d91a24
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

An authenticated operator opens `操作与任务`, finds an admitted or historical run using truthful
server-side search, filters, counts and paging, then opens that run's overview without joining Jobs
and Tasks manually. Complete the inventory/selection journey in RO-1 and RO-2 and the read/privacy
portion of RO-7. This Task does not claim the whole Slice or RO-3 through RO-6 complete.

## Why This Task Exists

At Task Base, `OperationsLanding.tsx` is a Worker/manual-action/navigation hub. `TaskListPage.tsx`
and `JobListPage.tsx` read separate bounded collections. `SQLiteTaskRepository.list_tasks` and
`list_jobs` support status/command filters, but not a unified population, business-name/safe-scope
search, creation-time filters or unified totals. `AutomationJob.task_id` and manual execution/task
links already provide durable relationship evidence. Existing lifecycle projections protect reads
and controls, but are not a unified run inventory.

Building only the table would either double-count linked work or require browser merging of
truncated collections. This Task completes a vertical read journey, including durable historical
display evidence and authoritative repository queries. It does not replace the processing engine.
The remaining Slice work can be grouped into coherent detail/evidence, organize-entry,
lifecycle-continuation and task-recovery units; there is no reason now to split into more than eight
Tasks. These are sizing observations, not pre-created Tasks or changes to the Contract.

B planning evidence: committed Slice/Roadmap ACTIVE and governance PASS at Task Base;
`.venv/bin/python -m unittest discover -s tests -p test_operations_workspace.py` passed 20 tests.
That establishes the existing Operations baseline, not acceptance of this planned feature.

## Implementation Scope

```text
Domain read contracts → Persistence/query and admission display evidence
→ shared Application projection → authenticated API → typed Web/query/router → Tests
```

### Operator journey

- **Entry:** `/ui-v2/operations` in the existing AppShell, or an explicit supported run detail link.
- **Visible state:** Chinese business names, operation kind, historical source/target scope,
  trigger, aggregate state, times and bounded queue/Worker evidence; trustworthy result counts.
- **Action:** submit text/status/kind/time filters, click a count card, page, refresh, select/close
  a run and follow existing Task/Job/execution detail for further evidence.
- **Success:** an explicitly linked run remains discoverable before and after Task creation,
  is counted once, and opens with historical identity and list context intact.
- **Failure:** no work, no matches, forbidden access, unavailable/malformed/stale data, missing
  historical evidence and unavailable Worker are distinct; a failed read never means zero runs.
- **Recovery:** correct/reset filters or cursor, retry the bounded read, reconnect, or follow the
  named readiness prerequisite. Refresh/reconnect/navigation never admits or replays work.

### Required behavior and boundaries

1. Add a shared read projection over explicit durable Job/Task/manual-execution relationships.
   Preserve an admission's visible identity and detail links when it acquires a Task. Standalone
   Tasks and pre-Task pending/failed Jobs remain visible. Distinct occurrences, retries and recovery
   continuations remain independent attempts with existing links. Never infer links from filename,
   creation-time proximity, labels or a command prefix alone.
2. Derive status from actual queue/processing evidence. Completed Jobs cannot hide linked Task
   failure/partial success. Waiting, paused, queued and unknown evidence remain distinguishable;
   attention is an overlapping facet. Projection is not a new lifecycle or execution authority.
3. Implement bounded deterministic repository queries for text over safe business name/scope,
   status, operation kind and creation-time range. Support combined filters and directional cursors
   bound to query and principal/authorization context. Obtain page, filtered total, partitioned
   status counts and overlapping attention count from a consistent read basis of the same authorized
   filtered population. Label the population and card-click filter behavior. Do not load all records
   into Python/the browser or resolve an unbounded number of pins per read.
4. Supply bounded historical context from durable admission evidence or the exact pinned snapshot.
   Add only display/link persistence and indexes needed for query correctness and bounded cost.
   Capture necessary evidence for new supported admissions using shared producers; do not change
   selection, authorization, claim or execution behavior. Equal ResourceLibrary/MediaLibrary IDs
   remain distinct. Active rename/delete/root changes cannot rewrite known historical labels.
   Missing legacy evidence is explicitly unavailable; no fallback to current Active or read-time
   backfill of historical records.
5. Expose authenticated bounded list and selected-run overview through shared Python read ports
   (a `/api/v1/operations/runs` family is suitable). Durable history remains readable without usable
   current Active. Reuse existing safe lifecycle/readiness projections and exact linked detail
   routes; do not advertise a newly supported command.
6. Replace the Operations hub body with reference-aligned cards, compact filters, full-width table
   and explicitly selected overview panel. Entry has no selection; selection opens the right panel,
   with complete narrow-screen detail and accessible return. Show actual business identity/scope/
   trigger/state/times/readiness and links to deeper existing evidence. Keep Scan/Preview discoverable
   and existing Task/Job/Automation/Notification navigation and detail/control journeys usable.
7. Use strict frontend models and central API/query/auth boundaries. Preserve submitted filters and
   bounded paging/selection context through history, close/back, deep links, refresh and auth
   continuation. Poll bounded active-work reads, pause hidden polling, back off after failure and
   settle terminal detail polling. Label retained stale data and clear principal-owned cache/
   selection on authentication changes.

Frozen: Slice Contract/Base, Roadmap, canonical requirements/Product Experience, reference images,
rule semantics, physical source/plan authority, execution grants/tickets, Storage adapters,
OrganizerExecutor and Worker ownership/claim/mutation behavior. Existing producers may gain only
necessary display/link evidence. A narrowly necessary architecture factual update may describe the
read boundary and distinguish delivered portions from remaining TARGET; it may not redefine
architecture contracts or claim whole-Slice completion.

## Acceptance Criteria

- [ ] **AC-T1 — One real population:** legal production admissions remain visible before/after Task
      creation without duplication or identity/link loss. Standalone Tasks, pre-Task failures,
      manual executions, scheduled occurrences, continuations and both library kinds' existing
      direct commands/transfers are discoverable. Unknown legacy commands get bounded honest labels.
      Job completion cannot mask Task partial/failure.
- [ ] **AC-T2 — Authoritative query/counts:** text/status/kind/time filters compose; invalid values,
      ranges and limits reject safely; ties page deterministically. Filter/principal cursor mismatch
      refuses with read recovery. Totals and status partitions reconcile beyond one page; attention
      is explicitly overlapping. Page/counts share one read basis under concurrent linkage/state
      changes. The browser never merges truncated lists or manufactures totals/pages.
- [ ] **AC-T3 — Historical identity/privacy:** business name, trigger and source/target scope derive
      from admitted/pinned evidence or explicit unavailability. New admissions retain needed context;
      restart and Active A-to-B rename/delete/root changes cannot rewrite A's identity/search results.
      Equal library IDs retain kinds. Public data/search/errors expose no secrets, private endpoints,
      host roots or raw adapter exceptions.
- [ ] **AC-T4 — Complete find/inspect journey:** shared-shell Chinese inventory follows reference
      composition using real data/type icons. Default entry is full-width with closed detail;
      mouse/keyboard selection and supported deep entry open the correct overview. Close/back/history/
      refresh/reconnect retain safe list context; narrow view is complete. Existing Task/Job/execution
      links remain meaningful after linkage; Scan/Preview and existing journeys remain functional.
- [ ] **AC-T5 — Honest states/failures:** overview distinguishes aggregate status, queue/Worker
      readiness and acknowledged pause from a request. Do not turn `completed_items` into organize
      success or invent percentages/ETA; display known durable facts or explicit unknown/indeterminate
      state. No-work/no-match/loading/stale/read failure/malformed/401/403 offer safe next actions.
      Unavailable is not zero. Active/terminal/hidden/failure polling never replays commands.
- [ ] **AC-T6 — No new authority or side effects:** new reads are authorized/bounded, create no
      processing/admission/configuration work, invoke no Provider or media Storage calls, and do not
      write display backfills. Existing control/mutation rules and C identity under A reuse survive.
- [ ] **AC-T7 — Durable compatible delivery:** additive persistence migrates a real Task-Base schema
      fixture without rewriting pins, links, results, checkpoints or authority. Restart retains truth;
      unsupported schema fails closed; packaged Python static serving loads the built UI. Focused
      integration, real Python-backed browser evidence, full regression and applicable T4 gates pass
      with actual totals/skips/unavailable evidence recorded.
- [ ] **AC-T8 — Reviewable checkpoint:** report actual Base..Head manifest, tests/results, decisions
      and remaining Slice gaps. No private config/credentials, reference changes, unrelated files,
      removed coverage, weakened safety assertions or concealed skips enter the checkpoint. B Review
      stays PENDING until B inspects implementation.

## Required Tests

Use `.venv` or an equivalent declared-dependency environment; run Web commands from `web/`.
Record exact commands, results, totals, skips, failures and unavailable gates. An unavailable
required gate is not PASS. No production media, credentials or external service is required.

### Focused and affected evidence

Add `tests/test_operations_run_inventory.py` covering real SQLite/Application/API integration:
AC-T1–AC-T3 and AC-T6–AC-T7, multiple pages/ties/combined filters/counts, concurrent Job→Task linkage
and state changes, command families, exact pins/missing legacy evidence, both library kinds,
restart, denied permissions/cursors, redaction and zero Provider/Storage/work side effects. If
persistence changes, include a Task-Base schema upgrade fixture, failure/reopen and preserved
execution/Worker state. Use current legal production assemblies; tests cannot remove supported
production capabilities to manufacture a failure or establish completeness.

```sh
.venv/bin/python -m unittest discover -s tests -p test_operations_run_inventory.py
.venv/bin/python -m unittest discover -s tests -p test_operations_workspace.py
.venv/bin/python -m unittest discover -s tests -p test_task_persistence.py
.venv/bin/python -m unittest discover -s tests -p test_processing_worker_readiness.py
.venv/bin/python -m unittest discover -s tests -p test_v2_manual_organize.py
.venv/bin/python -m unittest discover -s tests -p test_direct_file_operations.py
.venv/bin/python -m unittest discover -s tests -p test_direct_file_transfers.py
.venv/bin/python -m unittest discover -s tests -p test_api_security.py
```

Add Web inventory model/query/router/component coverage beside existing Operations tests: malformed
response rejection, server filters/cursors/card actions, selection/history/close/deep links,
authentication clearing, independent read failures and polling lifecycle. Run:

```sh
npm run test -- --run src/entities/operations src/features/operations src/shared/api src/routes
npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/deep-link.spec.ts tests/e2e/manual-operations.spec.ts tests/e2e/manual-organize.spec.ts
```

Adapt existing browser expectations only for intentional inventory presentation/navigation changes;
preserve their safety/compatibility assertions. Add an isolated real Python API/SQLite browser
harness/spec, for example `playwright.python.config.ts` and
`tests/e2e/operations-inventory.python.spec.ts`, and run:

```sh
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
```

Use the built artifact, actual Python services, temporary DB/storage and fake/local dependencies.
Prove admission→Task linkage through a real supported producer/Worker, stable counts, filtered
selection/return, Worker waiting, historical identity after restart/Active change and side-effect-free
reads. Fake HTTP fixtures are additional UI evidence, not a substitute. Equivalent harness naming
is allowed; report its exact reproducible command.

### T4 full regression and quality/safety/package gates

```sh
python3 scripts/check_governance.py
scripts/docker_release_security_smoke_test.py
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests scripts
.venv/bin/python -m pip check
.venv/bin/python -m mediaflow.cli --config config/strategy.example.json config validate
.venv/bin/python -m mediaflow.cli --config config/mediaflow.phase13.2.example.json config validate
git diff --check
git diff --check f1806d3a13c0ab0538c07749ff82621782d91a24
sha256sum docs/pics/操作与任务.png
git check-ignore config/alist.json
git ls-files config/alist.json
rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml
```

Reference checksum: `a8a5dc329891207b0feb487fa60690e97072d11b73da1136324459bf79915f86`.
Private config must be ignored and absent from tracked/staged files; forbidden-dependency `rg`
must have no matches (exit 1). Inspect exact Base..Head and staged manifests/diffs for private or
unrelated files without printing private configuration contents.

From `web/`:

```sh
npm run test -- --run
npm run typecheck
npm run lint
npm run format:check
npm run build
```

Packaging/static-serving and migration gates:

```sh
.venv/bin/python -m unittest discover -s tests -p test_release_security.py
.venv/bin/python -m unittest discover -s tests -p test_release_validation.py
.venv/bin/python -m unittest discover -s tests -p test_migration_rehearsal.py
.venv/bin/python -m unittest discover -s tests -p test_upgrade_preflight.py
```

Build a wheel into an isolated temporary output directory using
`.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w <temporary-output>` and run
`.venv/bin/python scripts/wheel_smoke_test.py <exact-built-wheel>`; record substituted exact paths.
Slice-final resident continuation, destructive recovery and Docker lifecycle evidence remain
required at applicable implementation/final boundaries. This inventory Task does not claim those
not-yet-implemented outcomes.

## Non-goals

- New control/Continue commands, Worker claim/execution changes, authority reissue or unsafe replay.
- Full RO-3 task-kind progress, independently paged item/step/result records, task-scoped logs/audit
  and export presentation; retain existing deeper detail/evidence access in this Task.
- Completing RO-4 live-file `新建整理任务`/return flow or redesigning Files/Preview/execution.
- RO-6 Recognition/Metadata/Classification/conflict forms and failed-analysis recovery.
- Anything Explicitly Deferred/Excluded by Slice 42, including global Review, history deletion,
  queue replacement, MediaLibrary organization, posters, fabricated ETA or reference image changes.
- Canonical documentation closure, Roadmap changes, next-Task creation or Slice PASS/CLOSED.
- Optional copy polish, P2 cleanup or unrelated refactors.

## Developer Completion Report

### Changed Files

Correction checkpoint `5e1a20a` — the correction delta over the reviewed
checkpoint `0586db9` is 29 files, 2480 insertions / 373 deletions
(`git diff --check` clean for the working tree and for the full
`f1806d3..HEAD` range; no private or unrelated files staged; the three
pre-existing untracked `docs/pics/*.png` remain excluded and untouched;
`config/alist.json` stays ignored/untracked/unstaged; reference images
unchanged):

- Python domain/persistence/API: `mediaflow/domain/operations_run.py`
  (public `COMMAND_LABELS`, `target_scope` field),
  `mediaflow/domain/task_persistence.py` (`RunDisplayContext` +
  `admit_manual_execution` display protocol),
  `mediaflow/infrastructure/sqlite_runtime.py` (schema 41,
  `operations_run_display`, `operations_runs_window`, exact-ID
  `operations_run`, attention facet clause, generated
  `command_label_sql`, display writes),
  `mediaflow/interfaces/service_api.py` (attention query/cursor
  scope/echo, window handler, exact-ID overview, `target_scope`),
  `mediaflow/application/manual_scan.py`,
  `mediaflow/application/manual_organize_execution.py`,
  `mediaflow/application/automation.py` (worker default schema 41).
- Python tests: `tests/test_operations_run_inventory.py` (27 → 36 tests:
  cross-connection snapshot, both-direction stable totals, `limit=100`,
  attention facet, exact-ID overview, SQL/Python label parity, two real
  Scan-admission display tests, the real manual-Organize journey display
  test, schema-41 additive-table assertion); runtime-schema pins 40→41 in
  `tests/test_configuration_classification.py`,
  `tests/test_configuration_destination.py`,
  `tests/test_configuration_destination_activation.py`,
  `tests/test_configuration_destination_precheck.py`,
  `tests/test_configuration_organize.py`,
  `tests/test_resident_correction.py`.
- Web source: `web/src/entities/operations/run.ts` (task-kind count
  semantics, attention-facet proof, `targetScope`),
  `web/src/shared/api/api-client.ts` (attention parameter),
  `web/src/features/operations/run-query.ts` (one shared refetch policy),
  `web/src/features/operations/OperationsLanding.tsx` (attention card,
  URL-resident filter/cursor/direction state, push selection, lifted
  overview query + refresh, two-column layout, focus management, target
  scope fact), `web/src/shared/navigation/destination-model.ts`
  (`attention`/`cursor`/`dir` allowlist), `web/src/shared/ui/styles.css`
  (layout/overlay rules).
- Web tests: `web/src/entities/operations/run.test.ts` (+5),
  `web/src/features/operations/OperationsInventory.test.tsx` (8 → 12),
  `web/src/shared/api/operations-api.test.ts`,
  `web/src/features/operations/ManualOperationsRouter.test.tsx`,
  `web/src/shared/navigation/destination-model.test.ts` (+1),
  `web/src/features/operations/run-query.test.ts` (new, 4),
  `web/tests/fake-server.mjs` (attention contract + `target_scope`),
  `web/tests/e2e/operations.spec.ts` (attention toggle, Back, layout),
  `web/tests/e2e/operations-inventory.python.spec.ts` (+1 test).

### Implemented

All eight B blockers of this correction round, same Task, no scope change:

1. **Paging no longer changes the population.** The page window, filtered
   total, status partitions and attention facet come from one
   `operations_runs_window` call: the cursor bounds the page window only,
   counts derive from the business filters only, both directions return
   newest-first rows with correct previous/next cursors (a backward page
   keeps one ordering and honestly proves an older page), and `limit+1`
   is an internal fetch so the published legal `limit=100` is served.
   `operations_runs_page` remains as a thin three-tuple view.
2. **One read snapshot.** Page/total/status/attention run inside an
   explicit `BEGIN … COMMIT` read transaction, so a legitimate admission
   committed by another SQLite connection either lands entirely before or
   entirely after the snapshot — proven by a two-connection regression
   that schedules a real admission at the exact count-statement
   interleaving point.
3. **The attention card filters what it advertises.** `GET
   /api/v1/operations/runs?attention=true` is an explicit composable
   population facet bound into the cursor scope (mismatched replay →
   `invalid_request`), the response echoes `attention`, and the Web card
   toggles it (`aria-pressed`, never disabled) instead of resetting to
   `status=all`; the model rejects a server that echoes the facet without
   applying it. Attention stays an overlapping facet of the status
   partitions.
4. **Historical runs open.** The overview reads one run by exact anchor
   ID from the same linked projection (bounded `WHERE anchor_id = ?`),
   never from a newest-100 window; unknown IDs stay honest 404s.
5. **New work carries its business identity.** Schema 41 adds the
   additive `operations_run_display` table; the manual Scan and manual
   Organize admissions write bounded display evidence (library names,
   reviewed source scope, planned target scope, safe labels) inside their
   own admission transactions from the exact resolved/pinned runtime. The
   projection publishes `source_scope`/`target_scope` and searches the
   labels/scopes (search now matches 扫描/手动整理, the library names and
   the reviewed file scope), with the SQL label CASE generated from the
   same `COMMAND_LABELS` map as `known_command_label` and a parity test.
   Legacy rows stay explicitly unavailable — no current-Active fallback,
   no read-time backfill (the A→B rename regression still passes).
6. **Legal Scan failures stay visible.** The Web model now validates
   task-kind aware: `total` required with any count, non-negative integer
   counts, `completed <= total` for every command, and the
   `completed + failed <= total` sum only for exact-partition families
   (`manual_organize`, the bounded Files commands). A real
   `total=0/completed=0/failed=1` Scan renders as a row with an honesty
   note instead of rejecting the whole inventory; genuinely impossible
   documents still fail closed.
7. **The selected detail follows reality.** The overview query is owned
   by the landing on the shared `runRefetchInterval` lifecycle (5s while
   non-terminal, hidden tabs pause, failure stops polling, terminal
   settles), the header Refresh refetches it, and Job→Task linkage
   updates facts and exact Task links while the admission identity stays.
   All polls are GETs that replay no command.
8. **Complete inspect surface.** The detail is the right column of a
   `.mf-run-layout` grid at desktop widths (sticky under the topbar) and
   a complete full-viewport overlay with visible close control on narrow
   screens, with heading focus on open and focus return on close/Escape.
   Selection now **pushes** history (Back restores the previous list
   entry), closing replaces, and filters + cursor + direction + selection
   live in the URL so refresh, Back/close, deep links and 401 reconnect
   all restore the same list context (allowlist extended accordingly).

### Tests and Results

Focused Python (exact commands from Required Tests):

```text
.venv/bin/python -m unittest discover -s tests -p test_operations_run_inventory.py   → Ran 36, OK (was 27; +9 correction regressions, 0 skips)
.venv/bin/python -m unittest discover -s tests -p test_operations_workspace.py       → Ran 20, OK
.venv/bin/python -m unittest discover -s tests -p test_task_persistence.py           → Ran 13, OK
.venv/bin/python -m unittest discover -s tests -p test_processing_worker_readiness.py → Ran 19, OK
.venv/bin/python -m unittest discover -s tests -p test_v2_manual_organize.py         → Ran 37, OK
.venv/bin/python -m unittest discover -s tests -p test_direct_file_operations.py     → Ran 55, OK
.venv/bin/python -m unittest discover -s tests -p test_direct_file_transfers.py      → Ran 99, OK
.venv/bin/python -m unittest discover -s tests -p test_api_security.py               → Ran 13, OK
```

T4 full regression and quality/safety gates:

```text
python3 scripts/check_governance.py                                  → governance check: PASS
.venv/bin/python -m unittest discover -s tests                       → Ran 2051, OK (skipped=7; run twice — after the
                                                                       implementation and again on the final state)
.venv/bin/ruff format --check .                                      → 332 files already formatted
.venv/bin/ruff check .                                               → All checks passed!
.venv/bin/python -m compileall -q mediaflow tests scripts            → OK
.venv/bin/python -m pip check                                        → No broken requirements found
.venv/bin/python -m mediaflow.cli --config config/strategy.example.json config validate            → Configuration valid
.venv/bin/python -m mediaflow.cli --config config/mediaflow.phase13.2.example.json config validate → Configuration valid
git diff --check                                                     → clean (working tree)
git diff --check f1806d3a13c0ab0538c07749ff82621782d91a24            → clean (full range)
sha256sum docs/pics/操作与任务.png                                    → a8a5dc329891207b0feb487fa60690e97072d11b73da1136324459bf79915f86 (matches reference)
git check-ignore config/alist.json                                   → ignored; git ls-files config/alist.json → empty
rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml                   → UNAVAILABLE (rg not installed, exit 127); equivalent
                                                                       `grep -rniE 'ffprobe|ffmpeg' mediaflow pyproject.toml`
                                                                       → no matches (exit 1, the required result)
```

The 7 skips are the same pre-existing environment-conditional acceptance
tests as at Task Base (real SMB/S3/OpenList/endurance profiles, POSIX
lease, symlink availability, container-deployment Docker gating); this
Task's suites add zero skips.

Packaging/static-serving and migration gates:

```text
.venv/bin/python -m unittest discover -s tests -p test_release_security.py    → Ran 6, OK
.venv/bin/python -m unittest discover -s tests -p test_release_validation.py   → Ran 3, OK
.venv/bin/python -m unittest discover -s tests -p test_migration_rehearsal.py  → Ran 6, OK
.venv/bin/python -m unittest discover -s tests -p test_upgrade_preflight.py    → Ran 4, OK
.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w /tmp/mediaflow-wheel-fix → mediaflow-2.0.0.dev0-py3-none-any.whl
.venv/bin/python scripts/wheel_smoke_test.py /tmp/mediaflow-wheel-fix/mediaflow-2.0.0.dev0-py3-none-any.whl → PASS (runtime schema 41)
scripts/docker_release_security_smoke_test.py                        → UNAVAILABLE (environmental, pre-existing): the Docker
                                                                        daemon in this sandbox cannot see the sandbox's /tmp bind
                                                                        sources (`bind source path does not exist:
                                                                        /tmp/mediaflow-smoke-security-...`), so the compose stack's
                                                                        bind mounts can never resolve here, independent of repository
                                                                        content; same environmental reason recorded at the previous
                                                                        checkpoint
```

Web (from `web/`):

```text
npm run test -- --run src/entities/operations src/features/operations src/shared/api src/routes → 30 files, 453 tests, 0 failed
npm run test -- --run                        → 58 files, 869 tests, 0 failed
npm run typecheck                            → PASS (exit 0)
npm run lint                                 → PASS (exit 0)
npm run format:check                         → PASS (exit 0)
npm run build                                → PASS (exit 0)
npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/deep-link.spec.ts tests/e2e/manual-operations.spec.ts tests/e2e/manual-organize.spec.ts
                                              → 58 passed, 2 failed (see Risks: FAIL / PRE-EXISTING / UNRELATED)
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts → 6 passed
```

The real Python-backed browser harness (built artifact + actual Python
services + temporary SQLite + real producers/Worker) now also proves the
correction round: ≥2 bounded overview GETs within 6.5s on a non-terminal
selection, one more on header Refresh, select → browser Back restoring the
list context, and the detail inside the right-column layout — alongside
the existing admission/linkage, filtered selection/return, Worker-waiting,
restart identity and GET-only side-effect proofs.

### Decisions

1. **One window call, one snapshot.** `operations_runs_window` returns
   page + filter-scoped total + partitions + adjacent-page flags read
   inside one `BEGIN/COMMIT` read transaction; writers on other
   connections block briefly instead of skewing counts, and `limit+1` is
   internal so every published limit works.
2. **Cursor vs population.** Counts are computed from the business
   filters only; the cursor narrows the window only, and previous pages
   are the rows *before* the boundary returned in the same newest-first
   order, so totals (105/105/105/105 rather than 105/85/65/45) and
   partitions are stable across the whole walk.
3. **Attention is a first-class facet.** `attention=true` composes with
   every other filter, joins the cursor scope (a facet/cursor mismatch
   refuses with `invalid_request` + read recovery), and echoes in the
   response; `attention_count` remains the sum of the overlapping
   partitions, which equals `total` while the facet is applied.
4. **Exact-ID overview.** `operations_run(run_id)` reads the same linked
   projection with a bounded ID predicate; existence never depends on a
   newest-window position.
5. **Display evidence is producer-written.** Schema 41 adds only the
   additive `operations_run_display` table, written inside the admitting
   transaction from the exact resolved/pinned runtime (never the current
   Active at read time), joined for scope/labels/search only — no
   selection, authorization, claim or execution behavior changed; legacy
   rows remain explicitly unavailable.
6. **Label parity by construction.** The SQL search label CASE is
   generated from the exported `COMMAND_LABELS` map with a
   `media_`-prefix/`:`-family rule identical to `known_command_label`, and
   a parity test evaluates both against the same command matrix.
7. **Task-kind-aware progress honesty (Web).** Exact-partition commands
   keep the strict sum rule; scan/pipeline/legacy families keep
   `completed <= total` but may carry independent scan errors — one legal
   failing run renders honestly instead of rejecting the page, and no
   persisted count is ever rewritten.
8. **One polling lifecycle (Web).** `runRefetchInterval` is shared by the
   inventory and the lifted overview query; the header Refresh and the
   panel use the same bounded, GET-only, hidden-pause, failure-stopping,
   terminal-settling policy.
9. **URL is the recoverable state (Web).** Filters, cursor + direction,
   and selection all live in search params: selection pushes (Back = the
   prior list entry), closing replaces, filter changes drop the cursor,
   and the reconnect allowlist carries `attention`/`cursor`/`dir` so a
   401 continuation restores the exact context.
10. **Schema 41 lockstep.** Following the documented 39→40 precedent, the
    six literal runtime-schema pins and the `ProcessingWorkerService`
    default moved to 41 with the additive table; migration/rehearsal/
    preflight/backup suites are constant-driven and pass unchanged.

### Remaining In-Slice Work

RO-3 detail/records/export, RO-4 contextual organize entry, RO-5 queued Web
continuation and RO-6 native item/batch recovery remain open. B reevaluates
every RO-1–RO-7 after actual Task PASS; this statement neither closes any
Required Outcome nor authorizes another Task.

### Risks / Deviations

- **FAIL / PRE-EXISTING / UNRELATED:** the required four-spec e2e command
  reports `58 passed, 2 failed`; both failures are the documented
  pre-existing baseline in `deep-link.spec.ts` only — "an explicit route
  choice at the boundary replaces an earlier intention" and "V1 handoff
  does not leak the token into URL or persistent stores". They exercise
  the Review & Recovery / Configuration migration placeholders and the V1
  handoff, code untouched by this Task (the correction changed only the
  `/operations` allowlist branch and operations inventory surfaces), and
  the same two names are recorded in the previous checkpoint's byte-stable
  Task-Base baseline. Evidence kept; not fixed because they lie outside
  this Task's scope — B decides.
- **UNAVAILABLE (environmental, pre-existing):**
  `scripts/docker_release_security_smoke_test.py` fails at
  `docker compose up` because the Docker daemon cannot see this sandbox's
  `/tmp` bind sources (`bind source path does not exist:
  /tmp/mediaflow-smoke-security-…`), so its compose bind mounts can never
  resolve. Not caused by repository content; identical to the previously
  recorded environmental reason.
- **Tool substitution:** `rg` is not installed in this environment; the
  forbidden-dependency gate was executed with the equivalent `grep -rniE`
  scan, which returned the required no-matches result (exit 1).
- Pre-existing, untouched, non-gated staleness left in place (not this
  Task's blockers): `AutomationWorker`'s older default
  `runtime_schema_version: int = 34` (callers pass `SCHEMA_VERSION`),
  `scripts/docker_upgrade_recovery_smoke_test.py`'s schema 38/39
  constants, and the ungated `docs/architecture.md`/`docs/deployment.md`
  schema mentions.
- The frontend models and displays `target_scope` but the detail fact
  renders it exactly as published (relative label or explicit
  unavailability); per-item destination evidence stays on the existing
  detail surfaces per the Task's non-goals.
- B's FIX REQUIRED review text in this file is carried in the follow-up
  report checkpoint, mirroring the documented no-standalone-review-commit
  convention.
- Pre-existing untracked `docs/pics/媒体库.png`,
  `docs/pics/自动化-全局设置.png` and `docs/pics/自动化.png` were preserved
  untouched and excluded from this checkpoint.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 5e1a20ac2f06e67926d73ab7ea6f36a85269a689
```

## B Review Result

```text
Reviewed: f1806d3a13c0ab0538c07749ff82621782d91a24..e89db7cff91febe8dfa220343796b367664082be; completion report at 0586db92835210e14880bd681bb79165e8f537db
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — 分页改变统计总体，反向分页无法连续返回（AC-T2 / RO-2）。**
  `SQLiteTaskRepository.operations_runs_page` 把游标条件同时用于 page、total 和 status counts；
  API 的 previous 分支不恢复降序且固定 `has_previous=False`。
  用真实 `PersistentTaskCoordinator` 创建 105 个独立 Scan 后，
  `.venv/bin/python /tmp/mediaflow-b-42.1-probe.py` 的连续四页（limit=20）总数为
  105、85、65、45；第四页返回上一页得到升序记录且没有 previous cursor，用户无法继续返回。
  同一生产 API 接受的上限 `limit=100` 又因内部请求 101 条而返回 400。
  修正方向：统计只受业务筛选影响；游标只限制页窗口；双向页面维持统一排序、正确相邻游标，
  支持公布的合法 limit，并补充跨多页的真实仓储/API 回归。
- **P1 — 页面和统计没有一致读快照（AC-T2 / RO-2）。**
  当前实现用实例锁串行执行三个独立 SELECT，没有覆盖其他合法 SQLite 连接的读事务。
  `.venv/bin/python /tmp/mediaflow-b-snapshot-probe.py` 使用两个实际仓储连接和生产 coordinator，
  在 page SELECT 与 count SELECT 之间调度一次合法 admission，API 返回
  `items=2, total=3, status_counts={running:3}, next_cursor=None`。
  用户在正常并发入队时看见无法由当前清单解释的统计。
  修正方向：让页、总数、状态分区和 attention 使用同一个数据库读快照，覆盖跨连接入队/
  Job→Task linkage/状态更新，而不是仅锁住当前 Python 对象。
- **P1 — “需要关注”卡片不筛选关注总体（AC-T2 / RO-2）。**
  `OperationsLanding.CountCards` 把该卡片绑定到 `status=all`，无筛选时还禁用按钮；API 没有对应
  attention facet 查询。真实 Python 服务上的 `node /tmp/mediaflow-b-browser-probe.mjs`
  复现默认按钮 disabled；从失败筛选点击卡片后变成全部状态、显示全部 4 条，包括非关注运行。
  修正方向：提供明确的、与既有筛选组合且绑定游标的服务端 attention facet，让卡片应用
  它所标示的筛选；保留 attention 与状态分区重叠的语义。
- **P1 — 超过最新 100 条的真实历史运行无法打开（AC-T1、AC-T4 / RO-1）。**
  `_operations_run_overview` 仅查询最新 100 条再按 ID 查找。
  `.venv/bin/python /tmp/mediaflow-b-42.1-probe.py` 在上述 105 个合法 Scan 中，对仍存在且可分页
  找到的最旧 Task 请求 `/api/v1/operations/runs/<id>` 得到 404。
  这直接阻断历史清单选择和支持的详情深链接。
  修正方向：通过有界精确 ID 查询读取同一个显式链接投影，不以最新列表窗口判断记录是否存在。
- **P1 — 新工作没有保存/投影必要的历史业务名称和源/目标范围，搜索也不覆盖业务标签
  （AC-T3 / RO-2）。** `run_search` 实际只有 anchor ID 和少量原始 scope；scope 为 NULL 时
  整个拼接表达式也为 NULL。`.venv/bin/python /tmp/mediaflow-b-42.1-probe.py` 使用现有完整
  手动整理 fixture（真实 LocalStorage、原样 capabilities、真实 intent→Preview→confirm API、
  已注册 Worker），执行 admission 返回 202，但新运行 `source_scope=null`，没有业务库名/
  目标范围；查询其可见标签“手动整理”、源库名 `Library` 或选中文件 `One.2001.mkv` 都返回
  total=0。另有 105 条 Scan 的可见标签“扫描”搜索也为 0。
  用户无法通过承诺的名称/范围找到刚创建的工作。
  修正方向：在共享合法生产者保存必要的 bounded display context，或有界读取精确 pin 中的
  历史证据；投影并搜索安全业务标签和已知源/目标范围，区分库类型。新工作不能统一按 legacy
  缺失处理，也不能回退当前 Active；run-level 范围属于本 Task，不是被排除的 per-item 明细。
- **P1 — 合法 Scan 失败会使整个 Web 清单被当作 malformed 拒绝（AC-T1、AC-T5 / RO-1）。**
  `normalizeRunSummary` 要求 `completed_items + failed_items <= total_items`，但生产 Scan 的
  failed count 可包含独立扫描错误，Slice Baseline 已明确这种语义。
  `.venv/bin/python /tmp/mediaflow-b-scan-probe.py` 先在真实 LocalStorage 的有效目录上成功
  admission，再模拟源目录消失并运行原始 `ManualScanService`：清单 API 返回 200，合法记录
  `total_items=0, completed_items=0, failed_items=1`。将保存的真实响应
  `/tmp/mediaflow-b-scan-response.json` 交给实际 `normalizeRunInventoryPage`（Vite SSR 加载
  `src/entities/operations/run.ts`）得到 `operations run response did not match the expected contract`。
  一条需要诊断/恢复的真实失败会阻断同页所有运行。
  修正方向：模型尊重既有 task-kind 计数语义，必要时分开主条目计数和 Scan errors；不要修改
  生产失败事实或以跳过该运行掩盖问题。覆盖真实失败响应到 Web 清单的回归。
- **P1 — 已选 active 详情不随轮询、刷新或 Job→Task linkage 更新（AC-T4、AC-T5 / RO-1）。**
  `RunDetailPanel` 未使用已有 overview polling options，也未参与 header refresh。
  `node /tmp/mediaflow-b-browser-probe.mjs` 在真实 Python API 上先选择 pending Preview Job，
  再执行 harness 的真实 `AutomationWorker` claim/linkage，点击 Refresh 并等待 6.5 秒：
  清单已显示“进行中”和 `Movies/Harness/Linked`，详情仍为“待处理”、范围不可用、仅 Job 链接；
  全程 overview GET 只有 1 次。用户观察的状态和可用详情链接停留在 admission 之前。
  修正方向：接入统一 active/terminal/hidden/failure 查询生命周期，显式刷新也刷新所选详情，
  linkage 后保持 admission 身份但更新事实和精确 Task 链接，不重放任何命令。
- **P1 — 选择后的详情布局和浏览器返回不满足承诺的完整 inspect surface（AC-T4 / RO-1）。**
  同一真实 Python 浏览器复现：1400px 桌面上 table 和 detail 均 x=264、宽1080，detail
  y=521 在 table 之后，没有右侧面板；390px 窄屏 detail 为 `position:static`、y=1221，
  留在长清单下方，没有完整全屏详情。截图为 `/tmp/mediaflow-b-desktop.png` 和
  `/tmp/mediaflow-b-narrow.png`，均来自实际构建产物。选择使用 `replace:true`；选择后浏览器
  Back 直接到 `/ui-v2/dashboard`，而不是返回先前的 Operations 列表状态。
  修正方向：完成 Contract 已指定的桌面右侧详情/窄屏完整详情及可访问返回，并把筛选、分页/
  选择上下文纳入可恢复导航状态，覆盖选择→Back/close→刷新/重连，不要求像素一致。
