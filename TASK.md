# Task 43.1 — Native Automation Definition Lifecycle and Focused Publication

This Task follows [the current development workflow](docs/development-workflow.md) and is subordinate
to [`SLICE.md`](SLICE.md). Planning/review reads [B's experience](docs/agent-experience/task-planner-reviewer.md);
implementation reads [Developer's experience](docs/agent-experience/developer-implementation-role.md).
The current governance and document format adopted during Slice 44 remain authoritative; this file
retains Task 43.1's business obligations and current facts, while detailed prior reports stay in Git.

```text
Task ID: 43.1
Parent Slice: 43
Status: FIX REQUIRED
Task Base: 79544d9aba697036405b06054c0c56a740281bab
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

An operator can create, edit, copy, enable, disable and safely remove one Automation definition in
native V2, publishing only the intended change through one checked Save or lifecycle action, with
truthful published state and an actionable recovery path.

Complete Slice **RO-2**; advance the definition-management entry/state portions of **RO-1** and
shared-authority/compatibility portions of **RO-7**. Preserve and connect the existing exact Preview,
separate grant/revoke and scheduled-execution behavior of **RO-3**. This Task does not claim all of
RO-1, RO-3 or RO-7 complete.

## Why This Task Exists

The original coherent unit is the native definition lifecycle across managed configuration,
application, persistence, API and Web. Its latest Developer implementation checkpoint
`b364a04d1c916ed327e3e8f470dc05e413ad80e6` remains unaccepted. A resumed Slice 43 and integrated
accepted Slice 44 at `28eb41997e1bac1cffef13896bc769ba7ffcfd6d`; no corrected Developer candidate has
been submitted since that recovery. Task identity, original Base and business scope are unchanged.

The current blocker is retained-history resolution: after a definition is removed, recent-window
searches eventually hide its durable occurrence, pin and publication evidence from required API/Web
routes. B reproduced this on the integrated production assembly after 505 ordinary publications and
runtime reopen. The existing exact revision/publication and sequenced ledger readers are sufficient
for correction inside this same Task. Current schema45 and accepted Slice 44 behaviors are inherited
baseline; no new recovery engine, A RESCOPE or next Task is needed for this defect.

Detailed planning, rejected implementation and review history remains reachable at
`a447e3129be89bd20f6a24831b2be122d4fdf955:TASK.md`; the independent resumption assessment is retained at
`39a6a40e4a66de508a331c2d83d17d65578c08cc:TASK.md`. Those snapshots are historical evidence, not a
replacement for current governance or a claim that prior READY/PASS states are current.

## Implementation Scope

```text
Existing definition/domain validation
→ managed revision/reference/audit and live grant persistence
→ focused application publication/lifecycle projections
→ typed authenticated API commands/readback
→ native V2 forms/actions/recovery
→ application/API/Web and real Python browser integration tests
```

### Operator journey

- **Goal:** maintain one bounded ResourceLibrary schedule without orchestrating configuration
  internals or activating unrelated changes.
- **Entry:** shared-shell Automation, explicit New/Edit/Copy/detail actions and compatible old
  definition/editor deep links.
- **Visible state:** published versus unsaved/recoverable candidate, source/mode/bound, readable
  schedule/timezone/next times, enabled state, separate grant and command readiness.
- **Action:** typed configuration and one checked `保存`; enable/disable, copy and reference-safe
  removal. Existing exact Preview and grant/revoke remain separate discoverable actions.
- **Success:** only the intended successor is runtime Active; copy has a new identity, disabled
  scheduling and no grant; removal stops future scheduling/mutation authority and retains history.
- **Failure:** invalid, dependency, stale/concurrent, permission, check or publication faults preserve
  prior authority and correctable input. An ambiguous response is unknown, not proof of rollback.
- **Recovery:** correct named blockers, inspect references, reload current authority, reconcile
  unknown publication before deliberate resubmission, or follow native Settings/Preview/regrant/
  history/Operations with return context. Internal identities are optional diagnostic details.

### Shared publication and lifecycle

1. Compose each command from the exact observed, valid published Active and fence it at publication;
   reject stale intent rather than silently repinning/rebasing. Modify only the selected definition;
   copy adds only the new one. Preserve sibling definitions, other configuration, unrelated open
   Drafts, historical revisions and pins. Reads/form opening create no Draft.
2. Reuse normalization, whole-candidate validation, references, applicable exact-candidate evidence,
   runtime loading and atomic activation. Distinguish absent capabilities from broken declared
   dependencies under existing applicability rules. No fabricated evidence or bypassed checks.
3. Typed forms cover name/stable identity, ResourceLibrary, safe optional relative sub-scope, three
   modes, item bound, enabled state and exactly one interval or Cron/IANA timezone. New/copy starts
   disabled with no authority; ordinary identity allocation need not become user input. Daily/weekly
   controls compile to existing Cron; advanced Cron remains. Upcoming times and invalid/DST guidance
   use the same backend calculation as Scheduler and create no due state/occurrence/work.
4. Save/enabling does not synchronously scan, perform media Preview, emit work or grant authority.
   Disabling stops future scheduled emission at the existing checked boundary; it neither cancels
   admitted work nor revokes a grant. Preserve existing grant/evidence validity rules; relevant
   scope/mode/limit changes cannot reuse insufficient authority. Show fresh Preview/regrant guidance
   where required, without inventing a new invalidation policy.
5. Removal enforces configuration/publication and existing revocation permissions and applicable
   references, publishes the focused successor, and durably revokes applicable future unattended
   authority. Concurrent Scheduler/Worker/grant/publication operations cannot expose an unsafe gap.
   Preserve grants/audits, occurrences, Jobs/Tasks/results and pins; completed/in-flight effects are
   not rolled back or rewritten. Known rejected removal preserves Active and existing authority;
   commit/readback ambiguity exposes actual/unknown durable state and reconciliation. Recreating or
   copying a definition must not revive removed authority. Use existing mutation-boundary gates.
6. Retained occurrence/history links remain readable after removal and restart via a truthful
   historical projection/contextual route. Resolve old context from durable occurrence/pin evidence,
   or label missing legacy evidence; never substitute today's renamed configuration or another
   definition. Removal is not history deletion.
7. Keep existing Draft-only candidates labelled inactive and natively inspectable/correctable. An
   explicit Save publishes only the selected candidate against observed Active; unrelated edits in
   its old Draft neither ride along nor disappear. Draft never becomes runtime authority.

### API, Web and compatibility

- Shared application services own validation/publication/failure behavior; HTTP and Web consume it.
  Enforce current backend management/activation permissions and existing revoke permission as
  applicable. Direct POST cannot bypass an unavailable UI action.
- Return bounded safe publication/readback identity and failures identifying object, stage, durable
  state, effects and next action. Unknown create/copy/save/toggle/remove submissions are read back
  before deliberate resubmission, including commit-then-response/read failure. Prevent accidental
  duplicate lifecycle submissions; never automatically replay POSTs or publish after permission loss.
- Native typed forms replace ordinary Draft orchestration, retain input where safe on failure and
  refetch authority after reconnect. Tokens/secrets/reusable execution authority remain outside
  browser-persisted form state. New/Edit/Copy/detail open only on explicit navigation.
- Reuse the shared light shell/design system and real ResourceLibrary choices, keyboard behavior and
  narrow-screen usability. Publish/enabled/granted/ready are distinct; missing grant/consumer readiness
  is actionable, not represented as a working green switch. Preserve existing exact Preview and
  explicit grant/revoke access and successful unattended execution.
- Preserve V1/API/CLI configuration and existing Automation/Task/Job routes or resolve them through
  truthful context. Empty Active offers dependency guidance; no Active leads to Settings; broken
  prior Active offers recovery without reinitialization or JSON/cache fallback. Keep Settings,
  ResourceLibrary, Rules and history/Operations return context.

The entry list may change to expose these real lifecycle actions/states. Full server inventory
query/pagination, metrics, consolidated records/settings tabs and resident adoption are later
in-Slice work; do not add fake/decorative actions or claim the whole reference workspace complete.

Freeze `SLICE.md`, Roadmap, Progress, permanent product/requirement/safety contracts and Slice Base.
Only necessary Task-owned operational documentation or an explained factual architecture adjustment
may change. Preserve all four pre-existing untracked PNGs in `docs/pics/`; do not stage/edit/recompress
them. Both Automation checksums remain unchanged. `config/alist.json` stays ignored/untracked/unstaged;
never use private configuration/credentials to obtain evidence.

## Acceptance Criteria

- [ ] **AC-T1 — Native lifecycle:** V2 completes create/edit/copy/enable/disable/reference-safe removal
  with one checked Save/lifecycle command per intended change, sharing API/application behavior and
  success/failure/recovery. No ordinary Draft/Validate/Activate orchestration, CLI fallback or raw
  identifier/token ceremony is required.
- [ ] **AC-T2 — Focused immutable authority:** successful commands publish exactly the intended
  successor after whole-candidate validation and applicable evidence/runtime gates. Concurrent/stale
  writers cannot publish mixed changes. Siblings/unrelated Drafts/old pins survive; failures preserve
  prior Active and correctable input.
- [ ] **AC-T3 — Scope/schedule:** supported fields and all three modes round-trip through backend
  rules. Unsafe/absolute/traversal scopes, missing/disabled references, non-finite/out-of-bound values,
  incompatible interval/Cron and invalid timezone/Cron fail safely. Daily/weekly/advanced scheduling
  uses authoritative upcoming times and existing DST semantics with zero work emission.
- [ ] **AC-T4 — Independent states:** new/copy starts disabled without grant; copy has a new stable
  identity. Save/enabling creates no work/authority. Disabling does not cancel/revoke admitted work.
  Published/enabled/granted/ready and current permissions remain distinct; expanded scope cannot
  inherit insufficient authority. Exact Preview/grant/revoke and unattended execution still work.
- [ ] **AC-T5 — Safe removal:** references/publication/revocation permissions and current production
  concurrency gates protect removal. Future scheduling/unattended mutation stop; pins, grants/audits,
  occurrences, Jobs/Tasks/results and usable history survive restart. Failures/ambiguity cannot hide
  authority outcomes; completed effects are unchanged and recreation/copy cannot revive old grants.
- [ ] **AC-T6 — Recovery/compatibility:** failed input survives where safe; unknown lifecycle outcomes
  are reconciled before deliberate resubmission without automatic duplication. Permission loss,
  malformed responses and 401/403 fail closed. Draft-only recovery publishes only the chosen candidate.
  Empty/no/broken Active and compatible old routes offer correct contextual next actions.
- [ ] **AC-T7 — Safety/production evidence:** reads/polling/schedule calculation create no Draft/grant/
  work and call no Provider; publication/checks/Preview perform zero media mutation. Actual Python/
  SQLite/browser and Scheduler/Worker assemblies prove the journey. Current live revocation,
  OrganizerExecutor-only mutation, old/new admitted pins and C-with-A/A identity remain protected.
- [ ] **AC-T8 — T4/checkpoint:** required tests/gates pass with honest totals/skips/unavailable evidence.
  Only Task-owned changes enter the checkpoint; frozen/private files and PNGs survive. No safety-test
  deletion, relaxed assertions, hidden skips or silent fallback achieves PASS.

## Required Tests

Follow [current test levels, stages and evidence rules](docs/development-workflow.md#6-test-levels).
Commands run from repository root. Extend the existing focused application/API, typed Web and native
Python lifecycle coverage; preserve all compatibility/safety assertions. High/T4 remains binding.

### Development and correction feedback

Resolve the known retained-history P1 before expensive gates. Run changed/new tests and directly
affected regressions first, including the existing publication/lifecycle suites and affected Web
model/form/query/transport tests:

```bash
.venv/bin/python scripts/check_governance.py
.venv/bin/python -m unittest tests.test_automation_definition_publication tests.test_v2_automation_lifecycle
npm --prefix web run test -- run src/entities/operations/automation-lifecycle.test.ts src/features/operations/AutomationLifecyclePage.test.tsx
npm --prefix web run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-lifecycle.python.spec.ts
```

Add durable-history cases beyond both former revision/audit windows, runtime reopen, exact historical
name/scope/mode/version, no-occurrence history, unpublished Draft exclusion and missing/corrupt/
unavailable/incomplete evidence. Preserve read-only bounded behavior and true absence versus failure
semantics. The retained B reproducer asserts the existing 404 defect; use its scenario for correction,
then assert readable history rather than treating that reproducer's exit 0 as product acceptance.
Use real API/SQLite/browser feedback for the affected surface, with temporary Local/fake services.

### Final checkpoint gates

These assigned focused/integration cases cover publication, compatibility, Active authority, RBAC,
grant/revocation, schedule/admission and concurrency. Run every added/affected Web test as well:

```bash
.venv/bin/python -m unittest tests.test_automation_definition_publication tests.test_v2_automation_lifecycle
.venv/bin/python -m unittest tests.test_automation_task_definition tests.test_v2_automation_operations tests.test_configuration_successor_draft tests.test_configuration_management tests.test_configuration_destination_activation tests.test_v2_rules_workspace_commands tests.test_system_settings_management
.venv/bin/python -m unittest tests.test_cron_scheduler tests.test_automation_definition_occurrence tests.test_automation_task_definition_preview tests.test_automation_preview_grant_gate tests.test_automation_unattended_grant tests.test_automation_definition_execution tests.test_automation_authorized_execution_matrix tests.test_automation_admission tests.test_automation_job_fencing
npm --prefix web run test -- run src/entities/operations/automation.test.ts src/features/operations/AutomationRouter.test.tsx src/entities/operations/automation-lifecycle.test.ts src/features/operations/AutomationLifecyclePage.test.tsx
```

Required scenarios: all lifecycle actions; stale/concurrent publication and unrelated Draft/sibling
preservation; scope/schedule numeric/finite/boundary/dependency errors; management/activation/revoke
permission separation and Viewer denial; applicable check/persistence/runtime failures;
commit-then-response/read failure and duplicate clicks; Draft-only recovery; empty/no/corrupt Active;
retained history beyond former windows and after reopen; Scheduler evaluation around disable/remove;
an actual admitted old Job and revocation before its next mutation; fresh grant binding after relevant
edits; zero side effects on reads. Use supported production assemblies, with fakes/local services at
external ports, rather than doubles that remove production capabilities.

Full regression and quality/safety gates remain required on the corrected executable candidate.
A final full run that includes the focused cases under their required configuration may record that
coverage instead of mechanically rerunning them; separate native Python, security and other assigned
gates remain due.

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests scripts
.venv/bin/python -m pip check
.venv/bin/python scripts/docker_release_security_smoke_test.py
.venv/bin/mediaflow --config config/strategy.example.json config validate
.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate
npm --prefix web run test -- run
npm --prefix web run typecheck
npm --prefix web run lint
npm --prefix web run format:check
npm --prefix web run build
npm --prefix web run test:e2e
npm --prefix web run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-lifecycle.python.spec.ts
npm --prefix web run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
npm --prefix web run test:e2e -- --config=playwright.python.unicode-principal.config.ts tests/e2e/operations-principal-identity.python.spec.ts
.venv/bin/python scripts/check_governance.py
git diff --check
sha256sum docs/pics/自动化.png docs/pics/自动化-全局设置.png
rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml
```

The FFmpeg/FFprobe check expects exit 1 with no runtime/dependency matches. The three real-Python
browser commands retain separate existing configurations: Automation publications change Active and
invalidate build-time fixture pins, while Unicode-principal verification requires its configured
Unicode identity. This preserves all journeys without the obsolete mixed-harness invocation.

Native real-Python/SQLite/browser evidence must drive typed create → Save → actual Active readback,
edit/copy/toggle, stale/denied/unknown recovery, removal and retained history. Also drive exact Preview
→ explicit grant → real Scheduler emission/Worker outcome on temporary Local Storage and a synthetic/
local Provider; assert Save/reads do not emit that work and explicitly invoke Scheduler/Worker.
Node fixtures alone cannot replace production application/persistence evidence. Preserve current live
revocation, old/new admitted pins, OrganizerExecutor-only mutation and C-with-A/A identity.

Audit the exact `Task Base..Head` manifest and staged/unstaged changes for frozen/unrelated/private
files and credentials. Distinguish accepted Slice 44 baseline from new Task correction. Confirm all
four user PNGs are untouched and `config/alist.json` remains ignored/untracked/unstaged.

Schema45 is inherited accepted baseline; this document reconciliation introduces no migration. If
correction changes schema, additionally run
`.venv/bin/python -m unittest tests.test_migration_rehearsal tests.test_upgrade_preflight` and document
additive **Task Base schema44 → candidate schema** and affected **current schema45 → candidate schema**
rehearsals preserving historical rows/pins/grants/audits. Old-schema fixtures alone do not prove the
actual upgrade. Otherwise record schema unchanged by Task correction. Wheel/static-serving and
Compose lifecycle checks remain Slice-final gates unless the correction changes packaging/deployment/
resident boundaries; then include the affected gates with exact commands/results. Production media,
private credentials and external-service validation remain unauthorized. Report failed, skipped or
unavailable gates honestly; do not omit them or call them PASS.

### B independent verification

B inspects the actual candidate diff and matching original evidence, then independently drives the
removed-definition API/Web detail, occurrences and grant history beyond both former windows and
across runtime reopen. Verify exact published identity, retained Job/Task/authority links, history
without an occurrence, unpublished Draft exclusion, actionable missing/unavailable evidence and
no side effects.
B verifies publication/reconciliation, permissions and current revocation at the affected boundaries.
A proven P1 permits FIX REQUIRED before remaining expensive gates; PASS requires the complete assigned
candidate plan. Repeated full suites need missing, incompatible or contradicted evidence as a reason.

### Evidence and rerun rules

Retain each candidate's index/raw logs/browser artifacts in CI or
`.git/validation-evidence/<full-source-sha>/<run-id>/` through A final review. Record source/reviewed
SHAs, working-tree input changes, commands/cwd/runtime/dependency/config/selection/retry settings,
build digests, exits/counts/durations, first failures/repeats and actual limitations.

The current baseline evidence is
`.git/validation-evidence/28eb41997e1bac1cffef13896bc769ba7ffcfd6d/b-reassess43-20261012/evidence-index.json`.
It independently proves the blocker and verifies matching A integration evidence (442 Python,
Web 80 + 119 and native Automation 10 tests plus recorded quality checks). It is not corrected-candidate
T4 acceptance. Old `/tmp` logs are historical references, not fresh evidence.

Reuse only after verifying identical executable inputs, tests/harnesses, dependencies/configuration
and built artifacts. A report/document-only successor may reuse runtime evidence with an explicit
input diff; rerun document-consuming checks. Any changed executable/test/harness/dependency/config/
artifact needs fresh affected evidence, and the corrected T4 candidate must satisfy its complete final
gates. New authority/Active/mutation/persistence/concurrency risk returns to B for reassessment rather
than a weaker plan. This consolidation changes presentation and current facts only: original meaningful
High/T4 gates and obligations remain intact.

## Non-goals

- Work outside Slice 43, changing its Contract/Base, or declaring Slice PASS/CLOSED.
- Definition-bound Run once/manual-origin admission links, consolidated metrics/history queries,
  full inventory/search/paging/reference tabs and global settings/actual resident polling adoption.
  These remain in-Slice work, not permanent deferrals; the current bounded list is not RO-1 complete.
- A new Preview/discovery/recovery engine or completing the broader long-analysis journey beyond
  preserving existing exact Preview/grant integration here; RO-3 is reevaluated separately after PASS.
- New schedule modes/overlap/backfill, queue/parallelism changes, uncertain replay, universal rollback,
  per-definition Provider/policy/destination/action overrides, MediaLibrary organizing sources,
  unbounded manual organization, history deletion or fabricated reference business data.
- Global Settings/Notifications redesign, identity/Secret Store/deployment editing, new Storage/
  Provider dependencies, FFmpeg/FFprobe, image edits, unrelated refactors or optional P2 cleanup.

## Developer Completion Report

### Changed Files

- `mediaflow/application/automation_workspace_commands.py`
- `tests/test_automation_definition_publication.py`
- `tests/test_v2_automation_lifecycle.py`
- `web/tests/e2e/automation.spec.ts`

### Implemented

Removed the arbitrary recent-revision and recent-audit windows from retained Automation history
resolution. An occurrence now resolves its exact pinned published revision by identity, version and
digest, verifies the historical definition fingerprint and never substitutes a different revision.
Without an occurrence pin, the resolver walks the durable activation ledger newest-first with its
monotonic sequence cursor until it proves the ledger ended. Invalid, contradictory, missing or
incomplete evidence reports the existing actionable unavailable state; it cannot become a false
absence or expose an unpublished Draft. Definition state and its projection are derived from the
same evidence read. Added regressions beyond the old windows, including API/browser history after
runtime reopen. The ordinary Create link is verified to open the native lifecycle journey while the
legacy editor remains testable as an explicit deep link.

No schema, migration, Slice, Roadmap, Progress or architecture change was made.

### Tests and Results

The corrected candidate's full regression passed: `.venv/bin/python -m unittest discover -s tests`
ran 2,501 tests with 7 declared real-service/endurance skips; `npm --prefix web run test -- run`
passed 1,138 tests across 76 files. Browser checks passed 246 default E2E tests, 10 real-Python
Automation lifecycle tests, 21 real-Python Operations inventory tests and 1 Unicode-principal
real-Python test.

Ruff format/check, Python compileall and pip check, Web typecheck/lint/format/build, both example
configuration validations, governance, `git diff --check`, and the expected no-FFmpeg dependency
search all passed. The first default E2E run exposed a stale assertion expecting the old `/new`
destination; that assertion now checks the lifecycle route and the full browser suite passes. Both
the initial failure and corrected run are retained.

The committed-candidate Docker release security smoke built and inspected the image and Compose
topology, then **failed** while waiting for the isolated four-service stack to become healthy. The
scheduler reported `sqlite3.OperationalError: database or disk is full`; `/` had 0 bytes available
and was 100% full. Docker reported 50.85 GB of build cache, 9.098 GB reclaimable. The isolated test
stack was cleaned automatically; shared Docker cache was left intact. This gate is recorded as FAIL,
not PASS or SKIP. Full commands, counts, skips, artifact hashes and raw logs are in
`.git/validation-evidence/70ca531965044ef6414c8ac93cb4d5d204b61cbd/task43.1-fix-20261012/INDEX.md`.

### Decisions

Correction stays in Task 43.1 with its original Base, Goal/scope/acceptance and High/T4. The
candidate makes no schema change and preserves published-history versus Draft-only distinction.

### Remaining In-Slice Work

B must review the corrected candidate and its Docker gate limitation. After any Task PASS, B
reevaluates all Slice Required Outcomes. Run once, consolidated inventory/metrics/history and
runtime settings adoption remain outside this Task.

### Risks / Deviations

The Docker release security smoke remains an environment failure caused by a full root filesystem.
The exact source candidate, image identity, available-space observation and test logs are retained in
the local evidence index. The four pre-existing untracked PNGs have unchanged hashes and remain
unstaged. `config/alist.json` remains ignored, absent, unstaged and uncommitted.

### Checkpoint

```text
Implementation checkpoint SHA: 70ca531965044ef6414c8ac93cb4d5d204b61cbd
Corrected candidate: SUBMITTED
Developer handoff: READY FOR B REVIEW
Developer does not claim Task PASS or Slice completion.
```

## B Review Result

```text
Reviewed: 28eb41997e1bac1cffef13896bc769ba7ffcfd6d
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

**P1 — Removed-definition history becomes unreachable after ordinary subsequent publications
(AC-T5/T6; RO-2).** B independently used the real supported Python API/SQLite/Local/Scheduler harness
and matching built Web: removal initially leaves V2 detail/occurrences and V1 detail/grant routes
readable (200); 505 ordinary authenticated focused publications of another definition all succeed
(200), then those historical routes return 404. Runtime/API/SQLite reopen retains the 404, and the
browser shows `Record not found`. Read-only SQLite proves the occurrence, exact superseded pinned
revision/digest, original historical name and activation publication audit are still present.
The existing resolver incorrectly treats absence from 200 recent revisions, 500 activation audits or
200 ever-published audits as absence from durable history.

Use the existing exact durable revision and publication proof, or complete targeted/cursor reads when
no pin exists. Preserve published-versus-Draft distinction and actionable unavailable/incomplete
states; never substitute current or unrelated identity. Do not enlarge windows or add a recovery
engine. Verify the corrected native journey beyond both former windows and across reopen, preserve
all authority/safety/accepted-baseline behavior and meet complete assigned T4 before PASS.

Latest B reassessment checkpoint: `39a6a40e4a66de508a331c2d83d17d65578c08cc` (documentation only).
Same Task continuation is valid; no new integration blocker was identified in that assessment.
The reproducer's exit 0 means **P1 REPRODUCED**, not product PASS. No new corrected Developer checkpoint,
Task PASS, next Task or Slice completion is claimed; Developer continues the same Task when directed.
