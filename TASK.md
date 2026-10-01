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

Correction checkpoint `ac5a43ed89d5d782809569ce5e58aedb8f2b03cb` — the correction
delta over the reviewed product checkpoint `ae62c00` (previous report head
`2577c58`) is 6 files, 527 insertions / 35 deletions (`git diff --stat
2577c58..ac5a43e`; `git diff --check` clean for the working tree, for
`2577c58..ac5a43e` and for the full `f1806d3a13c0ab0538c07749ff82621782d91a24..HEAD`
range; no private or unrelated files staged; the three pre-existing untracked
`docs/pics/*.png` remain excluded and untouched; `config/alist.json` stays
ignored/untracked/unstaged; reference images unchanged at
`a8a5dc329891207b0feb487fa60690e97072d11b73da1136324459bf79915f86`):

- `mediaflow/domain/task_persistence.py` — the `PersistentTaskRepository.create_task`
  protocol gains a keyword-only `display: RunDisplayContext | None = None`, and the
  two display-composition helpers (`relative_display_scope`,
  `join_display_scope`) move here from the transfer producer so every producer
  composes display evidence from one domain-level definition.
- `mediaflow/infrastructure/sqlite_runtime.py` — `SQLiteTaskRepository.create_task`
  writes the `operations_run_display` row inside the same transaction as the `tasks`
  insert.
- `mediaflow/application/task_runtime.py` — `PersistentTaskCoordinator.create` passes
  its new optional `display` through to the repository.
- `mediaflow/application/direct_file_commands.py` — the complete shared
  direct-command/delete admission boundary (`_run_display_context`, used by
  `_run_single` and `execute_delete`) composes and persists the run display context.
- `mediaflow/application/direct_file_transfers.py` — now imports those two helpers
  from the domain instead of defining them privately; behaviour byte-identical
  (pure move).
- `tests/test_direct_file_operations.py` — 55 → 60 tests: five focused
  display-evidence tests over the real managed activation and production API, plus
  two small static read helpers.
- `TASK.md` (this report; B's round-3 review text carried unchanged).

### Implemented

B's single round-3 P1 — "新 Files direct-command 工作仍被当作无历史范围的记录
(AC-T1、AC-T3 / RO-2)" — fixed at the complete shared production boundary, no scope
change:

1. **Every supported direct-command branch now records its historical business
   scope at admission, for both library kinds.** `DirectFileCommandService` (the one
   boundary serving ResourceLibrary and MediaLibrary work) composes the context from
   the exact pinned Active revision the admission already resolved — never a
   read-time Active lookup: a creation publishes the containing directory as its
   source scope (the library itself at the root, so a root-level `create_directory`
   still names its library) and the created entry as its target; Rename and Text
   Save name the exact entry on each side (Text Save's target is the in-place write
   path); Delete publishes the confirmed top-level scope it removed and invents no
   destination (`target_scope=None` — a side that is `None` has no known scope at
   all, while an empty relative scope means the library root). Values pass the shared
   provably-relative guard, are clamped by the existing `RunDisplayContext` bounds,
   and an unknown library name stays unavailable. The MediaLibrary branch keeps its
   durable `media_files_*` command identity, so `library_kind` stays `media` while
   the display row adds `Movies/...` identity — equal ResourceLibrary/MediaLibrary
   IDs remain distinct.
2. **The display row commits with the Task, restart-safe and immutable.**
   `PersistentTaskCoordinator.create` → `create_task(task, display=...)` writes the
   `operations_run_display` row in the same SQLite transaction as the `tasks` insert,
   so task and identity commit (or fail) together. The row is written once, never
   backfilled or rewritten: a restart over the same database reads the identical
   identity, and a real Active A→B library rename through the same managed service
   the API pins changes nothing in the durable identity or search results. No schema
   change — the runtime schema stays 41, so migration, rehearsal, preflight and
   backup suites pass unchanged.
3. **Search keeps following publication, under the same single guard.** Nothing in
   the read path changed: the registered `mf_run_search_text` scalar still wraps
   every identity input of `run_search`, so a credential-shaped configured library
   name is written as durable evidence, published as `[redacted-path]` and matches
   nothing — including its filtered total, status partitions and attention facet —
   while the visible command label keeps the run discoverable. Moving the two
   composition helpers into the domain removes the last producer-local copy without
   changing any producer's behaviour.
4. **No new authority, capability, confirmation or execution behaviour.** The change
   adds display/persistence work only: no command, no Storage/Provider call, no
   change to selection, authorization, claim, manifest, confirmation/delete rules or
   OrganizerExecutor. `PersistentTaskCoordinator.create`'s new parameter is optional,
   so every other caller (automation admission, CLI, tests) behaves exactly as
   before.

B's reproduction, rerun as `.venv/bin/python /tmp/dev-r3-direct-command-probe.py`
(same `DirectFileOperationsTests` real managed validation/checks/activation, original
LocalStorage with full capabilities, production API in a temporary directory):

```text
before: resource + media runs source_scope=null, target_scope=null; display table 0 rows;
        q=Unified media source / q=movies / q=Movies / q=media-folder all total=0
after:  resource run source="Unified media source", target="Unified media source/movies"
        media run  source="Movies",                 target="Movies/media-folder"
        operations_run_display rows: 2 (search_text carries the library names + scopes)
        q=Unified media source -> 1, q=movies -> 2, q=Movies -> 2, q=media-folder -> 1,
        q=文件维护 -> 2   (LIKE is ASCII case-insensitive: q=Movies also matches the
        resource-created directory "movies"; q=movies likewise matches both)
        overviews: 文件维护 / 媒体库文件维护 with the same source/target identity
```

The same evidence is asserted permanently by the five new tests (root-level and
non-empty relative creation, restart, Active rename, media kind, rename/save entry
scopes, delete-without-destination, credential-shaped name privacy).

### Tests and Results

Focused Python (exact commands from Required Tests, on the committed state
`ac5a43e`):

```text
.venv/bin/python -m unittest discover -s tests -p test_operations_run_inventory.py   → Ran 39, OK
.venv/bin/python -m unittest discover -s tests -p test_operations_workspace.py       → Ran 20, OK
.venv/bin/python -m unittest discover -s tests -p test_task_persistence.py           → Ran 13, OK
.venv/bin/python -m unittest discover -s tests -p test_processing_worker_readiness.py → Ran 19, OK
.venv/bin/python -m unittest discover -s tests -p test_v2_manual_organize.py         → Ran 37, OK
.venv/bin/python -m unittest discover -s tests -p test_direct_file_operations.py     → Ran 60, OK (was 55; +5 correction tests, 0 skips)
.venv/bin/python -m unittest discover -s tests -p test_direct_file_transfers.py      → Ran 100, OK
.venv/bin/python -m unittest discover -s tests -p test_api_security.py               → Ran 13, OK
```

T4 full regression and quality/safety gates:

```text
python3 scripts/check_governance.py                                  → governance check: PASS (start of task and after the checkpoint)
scripts/docker_release_security_smoke_test.py                        → direct execution exits 126 (file mode 644, pre-existing); executed as
                                                                       TMPDIR=/var/mediaflow-smoke-tmp .venv/bin/python scripts/docker_release_security_smoke_test.py
                                                                       → "Release-security smoke acceptance passed." (candidate image build, four-service
                                                                       stack, RBAC, static V2 UI/headers, managed snapshot activation, real V2 manual
                                                                       Organize + resident Worker, log/SQLite canary scan); the TMPDIR directory was
                                                                       created outside the repository and removed afterwards, and no smoke container,
                                                                       network, volume or temp directory was left behind (only the pre-existing
                                                                       /opt/mediaflow, /opt/nginx, jellyfin deployment containers remain untouched)
.venv/bin/python -m unittest discover -s tests                       → attempt 1: Ran 2060, FAILED (failures=1, skipped=7) — see Risks
                                                                       attempt 2 (on the committed state): Ran 2060 in 388s, OK (skipped=7)
.venv/bin/ruff format --check .                                      → 332 files already formatted
.venv/bin/ruff check .                                               → All checks passed!
.venv/bin/python -m compileall -q mediaflow tests scripts            → OK
.venv/bin/python -m pip check                                        → No broken requirements found
.venv/bin/python -m mediaflow.cli --config config/strategy.example.json config validate            → Configuration valid
.venv/bin/python -m mediaflow.cli --config config/mediaflow.phase13.2.example.json config validate → Configuration valid
git diff --check                                                     → clean (working tree)
git diff --check 2577c58..ac5a43e                                    → clean (correction range)
git diff --check f1806d3a13c0ab0538c07749ff82621782d91a24            → clean (full range)
sha256sum docs/pics/操作与任务.png                                    → a8a5dc329891207b0feb487fa60690e97072d11b73da1136324459bf79915f86 (matches reference)
git check-ignore config/alist.json                                   → ignored; git ls-files config/alist.json → empty
rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml                   → UNAVAILABLE (rg not installed, exit 127); equivalent
                                                                       grep -rniE 'ffprobe|ffmpeg' mediaflow pyproject.toml → no matches (exit 1, the required result)
```

The 7 skips are the same pre-existing environment-conditional acceptance tests as at
Task Base (real SMB/S3/OpenList/endurance profiles, POSIX lease, symlink
availability, container-deployment Docker gating); this Task's suites add zero skips.

Packaging/static-serving and migration gates:

```text
.venv/bin/python -m unittest discover -s tests -p test_release_security.py    → Ran 6, OK
.venv/bin/python -m unittest discover -s tests -p test_release_validation.py   → Ran 3, OK
.venv/bin/python -m unittest discover -s tests -p test_migration_rehearsal.py  → Ran 6, OK
.venv/bin/python -m unittest discover -s tests -p test_upgrade_preflight.py    → Ran 4, OK
.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w /tmp/mediaflow-wheel-fix3 → mediaflow-2.0.0.dev0-py3-none-any.whl
.venv/bin/python scripts/wheel_smoke_test.py /tmp/mediaflow-wheel-fix3/mediaflow-2.0.0.dev0-py3-none-any.whl → PASS (runtime schema 41)
```

Web (from `web/`; no Web source changed this round):

```text
npm run test -- --run src/entities/operations src/features/operations src/shared/api src/routes → Tests 453 passed (453), exit 0
npm run test -- --run                        → Test Files 58 passed (58), Tests 869 passed (869), 0 failed
npm run typecheck                            → PASS (exit 0)
npm run lint                                 → PASS (exit 0)
npm run format:check                         → PASS (exit 0)
npm run build                                → PASS (exit 0)
npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/deep-link.spec.ts tests/e2e/manual-operations.spec.ts tests/e2e/manual-organize.spec.ts
                                              → 58 passed, 2 failed (see Risks: FAIL / PRE-EXISTING / UNRELATED, the same two
                                                 deep-link.spec.ts failures B independently reproduced at Task Base)
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts → 6 passed
```

The real Python-backed browser harness (built artifact + actual Python services +
temporary SQLite + real producers/Worker) passes unchanged: truthful labels,
side-effect-free reads, real Worker linkage, stable filtered selection/return,
historical identity after a real restart and polling/history navigation.

### Decisions

1. **One boundary, one composition rule.** All five direct-command branches
   (Create Folder, Create Text File, Rename, Text Save, Delete) on both library
   kinds pass through `DirectFileCommandService`, so the display context is composed
   there — once — instead of per command or per endpoint. Nothing outside this
   boundary was touched (automation admission, CLI admitters and pipeline paths keep
   their existing evidence or legacy-unavailable status).
2. **Honest per-branch scope semantics.** Creation → containing directory (library
   root at the root, where only the library name remains) + created entry; Rename →
   old entry + new entry; Text Save → the one entry written on both sides; Delete →
   confirmed top-level scope, no destination. `None` means "this side has no known
   scope" (never an invented target); an empty relative scope means the library
   root. Only provably relative path shapes ever enter the row.
3. **Persist at admission, read only durable rows.** The row rides the Task's own
   transaction through the existing `create_task` insert path — no schema change
   (runtime schema stays 41), no read-time Active fallback, no write-time backfill
   for legacy rows (they stay explicitly unavailable, as before).
4. **Share the guard, not a copy.** The relative-scope/join helpers moved into
   `mediaflow/domain/task_persistence.py` next to `RunDisplayContext` so the
   transfer, scan, organize and direct-command producers cannot drift; the transfer
   producer's behaviour is unchanged (pure move, verified by its 100-test suite).
5. **No Web change.** The backend now supplies the `sourceScope`/`targetScope` the
   existing strict models and inventory panels already render (same conclusion as
   the round-2 transfer fix), so no model, query, router or fake-server contract
   needed to move.

### Remaining In-Slice Work

RO-3 detail/records/export, RO-4 contextual organize entry, RO-5 queued Web
continuation and RO-6 native item/batch recovery remain open. B reevaluates every
RO-1–RO-7 after actual Task PASS; this statement neither closes any Required
Outcome nor authorizes another Task.

### Risks / Deviations

- **FAIL / PRE-EXISTING / UNRELATED (full-regression attempt 1):**
  `tests/test_resident_correction.py::ResidentCorrectionTests::
  test_live_worker_consumes_later_and_old_published_scan_pins` failed once with
  `AssertionError: -1 != 0 : OperationalError: database is locked` at the CLI
  `jobs submit scan` issued while the spawned worker process was SIGSTOPped — a
  load-dependent live-process write-lock race in a test this Task does not touch
  (its paths never pass `display` to `create_task`; the added statement only runs
  when a producer supplies display evidence). Evidence gathered and kept:
  isolated re-runs on this branch → 13 OK / 6 failures of 19 runs; an interleaved
  comparison against the reviewed base `2577c58` in a temporary `git worktree`
  (created and removed afterwards) → 13 OK / 3 failures of 16 runs with the same
  test and the same `database is locked` class, i.e. the identical flake exists at
  the base B reviewed. Attempt 2 of `unittest discover -s tests` on the committed
  state returned `Ran 2060, OK (skipped=7)` with full output captured. Reported as
  observed — attempt 1 is not claimed as PASS; the flake's disposition is left to
  B's review runs.
- **FAIL / PRE-EXISTING / UNRELATED (required four-spec e2e):** `58 passed, 2
  failed`; both failures are the documented baseline in `deep-link.spec.ts` only —
  "an explicit route choice at the boundary replaces an earlier intention" (line
  209) and "V1 handoff does not leak the token into URL or persistent stores" (line
  479). B independently reproduced the same two names at Task Base from a clean
  `f1806d3` export; the spec, `package.json` and lockfile have no Base..Head
  changes and this correction touched no Web source. Evidence kept; B decides.
- **Docker gate invocation:** direct `scripts/docker_release_security_smoke_test.py`
  exits 126 (file mode 644, pre-existing), so the gate ran as
  `TMPDIR=/var/mediaflow-smoke-tmp .venv/bin/python
  scripts/docker_release_security_smoke_test.py` — the same daemon-visible
  workaround as the previous round, because this session's `/tmp` (and
  `/var/tmp`) are mounts the Docker daemon cannot see. No repository content was
  involved; the temp directory was removed after the run.
- **Tool substitution:** `rg` is not installed in this environment; the
  forbidden-dependency gate was executed with the equivalent `grep -rniE` scan,
  which returned the required no-matches result (exit 1).
- The reproduction probe lives at `/tmp/dev-r3-direct-command-probe.py`, outside
  the repository (same convention as B's `/tmp` probes); it is not part of the
  checkpoint.
- Pre-existing, untouched, non-gated staleness left in place (not this Task's
  blockers, carried from the previous report): `AutomationWorker`'s older default
  `runtime_schema_version: int = 34` (callers pass `SCHEMA_VERSION`),
  `scripts/docker_upgrade_recovery_smoke_test.py`'s schema 38/39 constants, and the
  ungated `docs/architecture.md`/`docs/deployment.md` schema mentions.
- The frontend was not changed this round: the backend now supplies the
  direct-command display evidence the existing strict models already display
  (`sourceScope`/`targetScope`), so no Web source, model or fake-server contract
  needed to move.
- B's FIX REQUIRED review text in this file is carried in this report checkpoint,
  mirroring the documented no-standalone-review-commit convention.
- Pre-existing untracked `docs/pics/媒体库.png`, `docs/pics/自动化-全局设置.png`
  and `docs/pics/自动化.png` were preserved untouched and excluded from this
  checkpoint.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: ac5a43ed89d5d782809569ce5e58aedb8f2b03cb
```

## B Review Result

本轮为第二轮 Developer 修正的 B 复审；实际产品 Head 为 `ae62c00`，报告 Head 为
`2577c58`。独立验证：Python 全回归 Ran 2055、OK (skipped=7)，inventory 聚焦 39 项
通过，真实 Python-backed browser 6 项通过，Docker release-security（以 Python 调用）
PASS；Python/Web format、lint、typecheck、compile、build、pip check、示例配置、治理、
Base..Head whitespace/private/reference 检查通过。

Web 全回归实际为 868 passed / 1 failed (869)：
`NotificationRouter.test.tsx:988` 的 wrong-revision create 测试在 5000ms 超时；该文件
在当前 Head 和独立 Task Base 构建上单独重跑均 25 passed。保留此次 full-run 失败事实，
不把该次全回归标为 PASS；该测试/通知实现未被 Task 改动，共享 API diff 只添加 run 查询，
没有实际生产用户缺陷证据，因此不扩入下面的 P1 列表。修正后仍须按原 Required Tests
完成并记录完整 gate。

必需 fake browser 四组实际为 58 passed / 2 failed。B 从 `f1806d3` 独立导出完整 Web
源码、单独构建，再运行原 `deep-link.spec.ts`，得到 12 passed / 同名 2 failed：
Review & Recovery link 在 221 行找不到、V1 handoff heading 在 494 行找不到。
该 spec、package.json 和 lockfile Base..Head 无改动；两边错误及位置相同，确认这些为
pre-existing/unrelated，未削弱断言或隐藏 skip。基线目录为
`/tmp/mediaflow-b-task42-baseline-r3/web`，证据为 `/tmp/mediaflow-b-r3-base-deeplink.log`
与 `/tmp/mediaflow-b-r3-e2e.log`。

整体方案复核：当前剩余问题是既有生产者的历史上下文覆盖不足；现有 bounded display
context、schema 41 和安全搜索规则足以修正，不需要再加架构层、扩大 Slice 或另开 Task。
下一次为同一 Task 的第三轮修正；若之后仍需超过三轮，须再次从整个 find/inspect 旅程
评估方案复杂度，而不是继续逐入口打补丁。

```text
Reviewed: f1806d3a13c0ab0538c07749ff82621782d91a24..ae62c00da1133afb6d6a7724fd951e870246176b; completion report at 2577c58b2d1bb647c4a3cc584df2b3d1a9acc3c3
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — 新 Files direct-command 工作仍被当作无历史范围的记录
  （AC-T1、AC-T3 / RO-2）。** 在当前支持的资源库和媒体库入口，操作者正常新建目录后，
  Operations 的新运行不能说明是哪个库/范围，也无法按刚使用的库名找到。
  `.venv/bin/python /tmp/mediaflow-b-r3-direct-command-probe.py` 使用现有
  `DirectFileOperationsTests` 的真实 managed validation/checks/activation、原始
  LocalStorage/完整 capabilities 和生产 API，在临时目录中复现：
  `POST /api/v1/resource-libraries/source/files/commands`
  (`create_directory`, `parentPath=""`, `name="movies"`) 返回 200 / SUCCESS，持久 Task
  为 completed，但 runs 清单的 `source_scope=null, target_scope=null`、display table
  为 0 行，`q=Unified media source` 和 `q=movies` 都是 total=0。
  同一配置的 `POST /api/v1/media-libraries/movies/files/commands` 创建 `media-folder`
  也返回 200 / SUCCESS；其 exact overview 正确标为 media，却同样没有源/目标范围，
  `q=Movies`、`q=media-folder` 均为 0。这些是本轮真实新创建的支持工作，不是 legacy、
  非法配置、未来适配器或削弱能力的替身。
  `DirectFileCommandService._run_single` 仅经 coordinator 创建 Task、root-level
  `scope_path` 为空；其共享 direct-command/删除 admission 边界没有提供已有的
  `RunDisplayContext`，当前投影也没有从精确 pin/持久证据补足必要范围。
  修正方向：在这个完整共享生产边界保存或有界投影必要的库类型/历史库名和已知 run-level
  源/目标范围，覆盖两种库及现有 direct-command 分支；沿用同一安全搜索和 immutable pin
  规则，覆盖 root-level、非空相对目录、重启和 Active 变更。不要改操作能力、授权、
  确认/删除规则、执行行为或 OrganizerExecutor，也不要为每个字段/命令另开 Task。
