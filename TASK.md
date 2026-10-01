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

Correction checkpoint `ae62c00` — the correction delta over the reviewed
checkpoint `5e1a20a` (completion report `aacd3de`) is 7 files, 480 insertions /
56 deletions (`git diff --check` clean for the working tree and for the full
`f1806d3..HEAD` range; no private or unrelated files staged; the three
pre-existing untracked `docs/pics/*.png` remain excluded and untouched;
`config/alist.json` stays ignored/untracked/unstaged; reference images
unchanged):

- Python domain: `mediaflow/domain/manual_safety.py` (the single fail-closed
  `bounded_identity_path` rule with `_EVIDENCE_PATH_SHAPES` moved here from the
  application layer, plus the new `searchable_identity_text` search guard),
  `mediaflow/domain/task_persistence.py` (`admit_files_transfer` protocol gains
  an optional `display`).
- Python application/infrastructure: `mediaflow/application/operations_lifecycle.py`
  (publication now delegates to the shared domain rule — identical behavior),
  `mediaflow/infrastructure/sqlite_runtime.py` (deterministic
  `mf_run_search_text` scalar registered on every runtime connection; `run_search`
  built only from guarded public forms; `effective_scope` prefers
  admission-written display evidence; `admit_files_transfer(..., display=...)`
  writes `operations_run_display` inside the admission transaction),
  `mediaflow/application/direct_file_transfers.py` (transfer admission composes
  and persists the bounded display context from the pinned runtime).
- Python tests: `tests/test_operations_run_inventory.py` (36 → 39 tests:
  credential-shaped library-name search privacy through a real Scan admission
  with a READ principal, hostile legacy `scope_path`/Job `source_scope`
  fallback privacy, and a published-vs-searchable parity matrix),
  `tests/test_direct_file_transfers.py` (99 → 100 tests: a real Copy
  impact/confirm admission writes the display row, is searchable by source
  library name and destination directory, publishes the target in the overview,
  and survives a repository restart).
- `TASK.md` (this report; B's round-2 review text carried unchanged).

### Implemented

Both P1 blockers of this correction round, same Task, no scope change:

1. **A new Files transfer admission carries its historical business scope
   (AC-T3 / RO-2).** After the manifest digest is re-verified against the exact
   pinned runtime, `submit_transfer` resolves the source and destination
   library display names from that same revision-pinned runtime and composes
   them with the reviewed relative source scope and the chosen destination
   directory into a bounded `RunDisplayContext`. The new optional `display`
   parameter of `admit_files_transfer` persists it as the
   `operations_run_display` row inside the very same `BEGIN IMMEDIATE`
   transaction that creates the Task, its bounded items and the claimable
   transfer row. Proved against the real production Copy impact/confirm API
   with the original `TransferApiTests` LocalStorage fixture: the display row
   holds `source_scope="Unified media source/a.mkv"`,
   `target_scope="Unified media source/Movies"`; a READ viewer finds the run
   with `q=Unified media source`, `q=Movies` and `q=a.mkv` (total=1 each); the
   overview identifies the target while keeping `command_label=文件传输`; a
   fresh repository over the same database reads the identical identity. The
   persisted `scope_path` (`a.mkv`), items and transfer authority rows are
   untouched, and no manifest, confirmation, Worker/execution-authority or
   Storage-mutation behavior changed — no command was added.
2. **Search matches only evidence the public projection publishes (AC-T3 /
   RO-2, RO-7, Safety Invariant 8).** The fail-closed identity rule moved into
   the domain (`manual_safety.bounded_identity_path` with the
   `_EVIDENCE_PATH_SHAPES` tuple) so publication and persistence share
   literally one definition, and a new deterministic `mf_run_search_text`
   scalar, registered on every runtime SQLite connection, wraps every identity
   input of `run_search` — anchor ID, effective source scope, effective target
   scope and the display search text — returning exactly the published form of
   a value and nothing at all when the projection would replace it with
   `[redacted-path]`. Page rows, the filtered total, the status partitions and
   the attention facet all derive from that guarded document, so neither a
   READ-principal substring search nor the counts can probe hidden text — for
   admission display rows, raw `tasks.scope_path`, raw
   `automation_jobs.source_scope` or any legacy column. The sentinel
   reproduction now answers `q=INVENTORYPROBE-SECRET`, `q=INVENTORYPROBE` and
   `q=api_key=INVENTORYPROBE` with `total=0, status_counts={},
   attention_count=0`, while `q=扫描` still returns the run and neither the
   list, the search result nor the overview contains the sentinel; hostile
   legacy scopes (`/srv/...`, credential-shaped, `https://` endpoints) behave
   the same. To keep searchable text inside the published identity,
   `effective_scope` now prefers the admission-written display evidence
   (library name + reviewed scope) before the raw task scope; rows without a
   display row keep the previous order, so legacy reads are unchanged.

No schema change: the runtime schema stays 41 (the additive
`operations_run_display` table already exists), so migration, rehearsal,
preflight and backup suites pass unchanged.

### Tests and Results

Focused Python (exact commands from Required Tests, on the final committed
state):

```text
.venv/bin/python -m unittest discover -s tests -p test_operations_run_inventory.py   → Ran 39, OK (was 36; +3 correction regressions, 0 skips)
.venv/bin/python -m unittest discover -s tests -p test_operations_workspace.py       → Ran 20, OK
.venv/bin/python -m unittest discover -s tests -p test_task_persistence.py           → Ran 13, OK
.venv/bin/python -m unittest discover -s tests -p test_processing_worker_readiness.py → Ran 19, OK
.venv/bin/python -m unittest discover -s tests -p test_v2_manual_organize.py         → Ran 37, OK
.venv/bin/python -m unittest discover -s tests -p test_direct_file_operations.py     → Ran 55, OK
.venv/bin/python -m unittest discover -s tests -p test_direct_file_transfers.py      → Ran 100, OK (was 99; +1)
.venv/bin/python -m unittest discover -s tests -p test_api_security.py               → Ran 13, OK
```

T4 full regression and quality/safety gates:

```text
python3 scripts/check_governance.py                                  → governance check: PASS
scripts/docker_release_security_smoke_test.py                        → direct execution exits 126 (file mode 644, pre-existing); executed as
                                                                       `.venv/bin/python scripts/docker_release_security_smoke_test.py` with
                                                                       `TMPDIR=/var/mediaflow-smoke-tmp` → "Release-security smoke acceptance passed."
                                                                       (candidate image build, four-service stack, RBAC, static V2 UI/headers,
                                                                       managed snapshot activation, real V2 manual Organize + resident Worker,
                                                                       log/SQLite canary scan — see Risks for the TMPDIR workaround)
.venv/bin/python -m unittest discover -s tests                       → Ran 2055, OK (skipped=7); four runs this round — three clean (one before,
                                                                       two after formatting with captured output) and one attempt that recorded
                                                                       failures=1 without a captured test name (see Risks)
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
                                                                       `grep -rniE 'ffprobe|ffmpeg' mediaflow pyproject.toml` → no matches (exit 1, the required result)
```

The 7 skips are the same pre-existing environment-conditional acceptance tests
as at Task Base (real SMB/S3/OpenList/endurance profiles, POSIX lease, symlink
availability, container-deployment Docker gating); this Task's suites add zero
skips.

Packaging/static-serving and migration gates:

```text
.venv/bin/python -m unittest discover -s tests -p test_release_security.py    → Ran 6, OK
.venv/bin/python -m unittest discover -s tests -p test_release_validation.py   → Ran 3, OK
.venv/bin/python -m unittest discover -s tests -p test_migration_rehearsal.py  → Ran 6, OK
.venv/bin/python -m unittest discover -s tests -p test_upgrade_preflight.py    → Ran 4, OK
.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w /tmp/mediaflow-wheel-fix2 → mediaflow-2.0.0.dev0-py3-none-any.whl
.venv/bin/python scripts/wheel_smoke_test.py /tmp/mediaflow-wheel-fix2/mediaflow-2.0.0.dev0-py3-none-any.whl → PASS (runtime schema 41)
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
services + temporary SQLite + real producers/Worker) passes unchanged:
admission→Task linkage, stable counts, filtered selection/return, Worker
waiting, historical identity after restart/Active change and side-effect-free
reads.

### Decisions

1. **One redaction rule, one home.** `bounded_identity_path` (with the
   `_EVIDENCE_PATH_SHAPES` tuple) moved from the application layer into
   `mediaflow/domain/manual_safety.py` — the module whose stated purpose is
   that "application, persistence and transport projections use the same
   definition" — and `operations_lifecycle` now delegates to it. Behavior is
   byte-identical; the move exists so the persistence search boundary and the
   API publication cannot drift.
2. **Search ⊆ publication is enforced inside SQL, not by a replica.** The run
   document feeds every identity input of `run_search` through the registered
   deterministic `mf_run_search_text` scalar, which is exactly
   `published-form-or-nothing`. There is no second, hand-written SQL copy of
   the redaction rules to fall out of parity, and the guard applies to every
   row (admission-written or legacy) at read time — no write-time backfill and
   no return-row-only masking.
3. **Redacted values contribute nothing, not the marker.** A hidden scope/label
   is excluded from the searchable text entirely rather than matching as
   `[redacted-path]`, so counts and search expose neither the content nor its
   shape; rows stay discoverable through their safe identity (run ID, business
   label, visible scope).
4. **Admission-written display evidence is the preferred historical scope.**
   `effective_scope` now reads display → task `scope_path` → Job
   `source_scope`. The display row commits inside the admitting transaction
   (durable, restart-safe, never a read-time Active lookup), it carries the
   business name plus the reviewed scope, and preferring it keeps the
   searchable business name inside the published identity. Only rows that have
   a display row are affected — today that is new transfers (Scan/manual
   Organize rows keep their previous result because their `scope_path` was
   already NULL); legacy rows read exactly as before.
5. **Transfer display evidence is producer-written, additive and bounded.**
   The context is composed from the revision-pinned runtime `_build_manifest`
   just resolved plus the already-reviewed relative scopes, clamped by the
   existing `RunDisplayContext` bounds; only provably relative path segments
   are used, and an unknown value stays unavailable. No schema change (41
   stays), no new command, no change to selection, authorization, claim,
   manifest, confirmation or execution behavior.

### Remaining In-Slice Work

RO-3 detail/records/export, RO-4 contextual organize entry, RO-5 queued Web
continuation and RO-6 native item/batch recovery remain open. B reevaluates
every RO-1–RO-7 after actual Task PASS; this statement neither closes any
Required Outcome nor authorizes another Task.

### Risks / Deviations

- **FAIL / PRE-EXISTING / UNRELATED:** the required four-spec e2e command
  reports `58 passed, 2 failed`; both failures are the documented baseline in
  `deep-link.spec.ts` only — "an explicit route choice at the boundary replaces
  an earlier intention" and "V1 handoff does not leak the token into URL or
  persistent stores". They exercise the Review & Recovery / Configuration
  migration placeholders and the V1 handoff, code untouched by this Task (the
  correction changed only domain redaction plumbing, the run-inventory SQL
  document, transfer admission display persistence and their tests), and the
  same two names are recorded in the previous checkpoint's byte-stable
  Task-Base baseline. Evidence kept; not fixed because they lie outside this
  Task's scope — B decides.
- **Unreproduced full-regression attempt:** one of the four
  `unittest discover -s tests` runs this round recorded
  `FAILED (failures=1, skipped=7)`; the command printed only the tail, so the
  failing test's name was not captured. The eight focused suites in that same
  attempt all passed (their results are recorded above), and the immediate
  re-run plus a third run on the identical final state both returned
  `Ran 2055, OK (skipped=7)` with full output captured and no failure block.
  Reported as observed — not claimed as PASS for that one attempt; the
  reproduction/identity of the flake is left to B's review runs.
- **Docker gate invocation:** direct `scripts/docker_release_security_smoke_test.py`
  exits 126 (file mode 644, pre-existing), so the gate ran as
  `.venv/bin/python scripts/docker_release_security_smoke_test.py`. This
  session's `/tmp` (and `/var/tmp`) are mounts the Docker daemon cannot see
  (`bind source path does not exist`), so the run used
  `TMPDIR=/var/mediaflow-smoke-tmp` — a daemon-visible directory outside the
  repository — and then completed the full acceptance, matching B's finding
  that this gate is runnable in the current environment. No repository content
  was involved in the workaround and no smoke containers, networks, volumes or
  temp directories were left behind.
- **Tool substitution:** `rg` is not installed in this environment; the
  forbidden-dependency gate was executed with the equivalent `grep -rniE`
  scan, which returned the required no-matches result (exit 1).
- Pre-existing, untouched, non-gated staleness left in place (not this Task's
  blockers): `AutomationWorker`'s older default `runtime_schema_version: int = 34`
  (callers pass `SCHEMA_VERSION`), `scripts/docker_upgrade_recovery_smoke_test.py`'s
  schema 38/39 constants, and the ungated `docs/architecture.md`/`docs/deployment.md`
  schema mentions.
- The frontend was not changed this round: the backend now supplies the
  transfer display evidence the existing strict models already display
  (`sourceScope`/`targetScope`), so no Web source, model or fake-server
  contract needed to move.
- B's FIX REQUIRED review text in this file is carried in this report
  checkpoint, mirroring the documented no-standalone-review-commit convention.
- Pre-existing untracked `docs/pics/媒体库.png`,
  `docs/pics/自动化-全局设置.png` and `docs/pics/自动化.png` were preserved
  untouched and excluded from this checkpoint.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: ae62c00da1133afb6d6a7724fd951e870246176b
```

## B Review Result

本轮复审真实 correction checkpoint `5e1a20a`（第一轮 Developer 修正），同时覆盖原 Task
Base..Head 和 `aacd3de` 的完成报告。B 独立复核：Python 完整回归 Ran 2051、OK
(skipped=7)，聚焦 inventory 36 项通过；Web 58 files / 869 tests 通过；真实 Python-backed
浏览器 6 项通过。Python format/lint/compile/pip check、Web typecheck/lint/format/build、
示例配置校验、治理和 diff/private/reference 检查通过。本轮未将 Developer 对两个 fake
browser 失败的 pre-existing 归因当作已独立验证的 PASS 证据。
`scripts/docker_release_security_smoke_test.py` 直接执行因权限返回 126；等价调用
`.venv/bin/python scripts/docker_release_security_smoke_test.py` 实际完成四服务、RBAC、静态 UI、
真实 manual Organize/Worker 和日志/SQLite 安全验收并 PASS。当前环境已可运行该 gate，
完成报告的旧环境 UNAVAILABLE 不代表本轮验证结果。

```text
Reviewed: f1806d3a13c0ab0538c07749ff82621782d91a24..5e1a20ac2f06e67926d73ab7ea6f36a85269a689; completion report at aacd3de064aae47dad3156398f4f70e12dc5cc29
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — 新 Files transfer admission 仍缺少承诺的历史业务范围（AC-T3 / RO-2）。**
  当前合法 Local 配置经真实 managed validation、Storage checks、strategy test、destination
  precheck 和 activation 后，通过生产 Copy impact/confirm API 创建的任务，未写入
  `operations_run_display`；投影只有 `source_scope=a.mkv, target_scope=null`。
  操作者在 Operations 无法按刚选择的源库名称或目标目录找到该工作，也不能从概览识别目标。
  `.venv/bin/python /tmp/mediaflow-b-r2-direct-probe.py` 使用现有 `TransferApiTests` 的完整
  配置 fixture、原始 LocalStorage/能力和原始服务，在 admission 返回 202 后复现：
  新 Task 存在、清单返回 200，但搜索源库名 `Unified media source` 和已选目标 `Movies`
  都是 total=0（文件名 `a.mkv` 则匹配 1），display table 为 0 行。
  这是本轮 schema 41 下新产生的支持工作，不能按 legacy 缺失处理。修正方向：在当前生产
  transfer admission 的共享边界持久化必要的安全业务标签及源/目标范围，或有界读取其精确
  pin/已持久化 admission 证据；与已有投影、搜索、重启和 Active 变更语义一致。不得更改
  manifest、确认、Worker/执行权限或 Storage mutation 行为，也不需要新增命令。
- **P1 — 搜索仍匹配公开投影已隐藏的原文，泄露受保护文本的匹配信息
  （AC-T3 / RO-2、RO-7，Safety Invariant 8）。** `RunDisplayContext` 和
  `_insert_run_display_locked` 保存未脱敏 labels/scopes/search_text，SQL `run_search` 直接
  使用这些原文；`bounded_identity_path` 只在序列化响应时隐藏范围，无法保护搜索。
  `.venv/bin/python /tmp/mediaflow-b-r2-privacy-probe.py` 通过真实合法 managed activation、
  原始 LocalStorage、实际 SQLite runtime + SQLite FileIndex 和生产 Scan API，以测试
  sentinel 库名 `Archive api_key=INVENTORYPROBE-SECRET` 创建 Scan（202）。公开清单范围
  为 `[redacted-path]`，但只有 READ 权限的 viewer 查询 `q=INVENTORYPROBE-SECRET` 或其
  子串 `q=INVENTORYPROBE` 均返回 total=1，不存在的 sentinel 返回 0。操作者可利用
  Operations 文本搜索和统计探测本应隐藏的内容；配置合法，未删除/隐藏生产能力，未使用
  真实凭据。修正方向：让查询只匹配与公开投影一致的安全证据，在进入可搜索上下文之前
  完成必要的脱敏/不可公开文本排除；不要仅在返回行中替换原文。对现有 scope fallback
  保持同一安全规则，并用真实 admission + READ principal 验证子串搜索不能命中隐藏内容。
