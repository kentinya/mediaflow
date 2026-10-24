# Task 43.4 — Automation Engine Settings Publication and Resident Adoption

Authority: committed [SLICE.md](SLICE.md), [Development Workflow](docs/development-workflow.md)
and [B experience](docs/agent-experience/task-planner-reviewer.md). Developer reads the
[implementation experience](docs/agent-experience/developer-implementation-role.md).

```text
Task ID: 43.4
Parent Slice: 43
Status: READY FOR B REVIEW
Task Base: f18d2444f548b81b5892536498a1b4cdd4400be8
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Working Branch: main
Decision: IMPLEMENT THIS TASK ONLY — RO-6 and its settings/navigation/safety integration
Next Action: B INDEPENDENTLY REVIEWS COMPLETE TASK BASE..CANDIDATE AND RUNS T4 ACCEPTANCE
```

## Goal

An operator opens `自动化 → 全局设置`, changes the four engine settings, clicks one Save, and
sees the exact published values separately from the values actually adopted by each relevant
running consumer. Worker/Scheduler adopt eligible polling changes without restart or work arrival.
System Settings reaches the same form, publication authority and consumption readback.

Complete Slice **RO-6**, the settings part of **RO-1/RO-7**, **AC-1/9/10/11** and the material
settings/resident/upgrade contribution to **AC-12**. Traceability: V2-AUTO-001/007/008,
V2-UX-001/002/003, UX-001/002/004/007/008/009/010, REQ-CONFIG-005/006/007/008/009/010/011/012.
Read the complete [Automation journey](docs/product-experience.md#target--complete-native-automation-workspace-active-slice43)
and [CURRENT/TARGET contract](docs/architecture.md#automation-and-unattended-execution).

Task43.3 is PASS on `8ff9b173972c15a46afc9c8f8aaa8c5584c127e2`; its complete review/report is
retained at `f18d2444f548b81b5892536498a1b4cdd4400be8:TASK.md`. This new Task does not repin43.3.
Slice Base remains `853973dbbf8289fa2ad40657033e94e870a690e4`. Preserve accepted45 implementation
`4fcb0028f987f8746f0a8aa7b309e360b07c598e`, closure `13ecfc0e75fc34ff0ae489e655124a178943cba4`
and frozen branch `frozen/slice-43-2026-10-15` at `ed974e0df8b263f631bfe48b524da461013d8780`.

### Actual-code gap

| Existing entry / implementation | Reuse and remaining change |
|---|---|
| `AutomationListPage.tsx`, `openSettings` and settings-tab placeholder | Both currently hand off to generic Configuration; replace the placeholder with the native reference-style settings journey and make header/System Settings links reach it consistently. |
| `ConfigurationPage.tsx`, `configuration-api.ts`; `GET/PUT /api/v1/system/settings` | Existing generic field editor deliberately saves Drafts for separate validation/activation. Preserve that supported contract; the four-field checked Save must be explicit and shared, not silently change old PUT semantics. |
| `domain/system_settings.py`, `SystemSettingsService`; runtime loader `_positive_number` | Reuse field allowlist, units/bounds and managed services. Add finite-number protection for this scope; existing positive comparisons alone do not establish finiteness. |
| `AutomationWorkspaceCommandService`, `ManagedConfigurationService.activate(before_publish=...)` | Reuse focused successor, whole-candidate validation, concurrency/audit and runtime preparation-before-publication patterns. Keep settings publication in an application service, not duplicated Web/API business logic. |
| `SystemSettingsService.consumption_evidence`, API `_runtime_settings_evidence` | Current evidence checks the API's own loaded binding. It cannot certify another process's cadence. Retain/label API-local evidence and compose actual per-consumer evidence for these four fields. |
| `final_cli._run_worker`, `_run_scheduler`; `ResidentLoop.run` | Poll value is chosen at startup and retained in `_poll_seconds`. Scheduler already resolves current Active per tick; use that authority without confusing schedule resolution with cadence adoption. Long idle sleep currently defers both rechecks and loop heartbeat. |
| `resident_services.py`, `ResidentServiceService`, SQLite resident registration/wait rows | Reuse per-instance lifecycle/freshness. Registration-time snapshot and heartbeat alone do not prove settings adoption; persist only the minimal additional adopted-value evidence needed. |
| `AutomationJobService`, `IntervalScheduler`, API runtime binding/stale reads | Reuse atomic Pending+Running admission capacity and stale-update observation. Keep engine controls current at their own boundary while admitted pipeline pins remain immutable. |

These are source findings, not claims that new native probes or future routes already passed.

## Implementation Scope

### Complete journey and four-field contract

- **Entry/state:** Automation settings tab and header shortcut, or the Automation section in System
  Settings; one shared form/read model. Display published target, each relevant consumer's actual
  values/version/freshness, and pending/adopted/override/unavailable status. IDs are diagnostic only.
- **Action/success:** edit the four fields and Save once. Backend validates the full focused
  successor and atomically publishes; then the page observes real adoption independently. Reads,
  refresh, Save and consumption reporting admit no work and grant no media authority.
- **Failure/recovery:** field errors retain input; stale publication requires refresh/review rather
  than overwrite. Failed preparation/validation/activation retains prior Active. Unknown submission
  requires durable reconciliation before explicit resubmission. A stopped/stale/overridden consumer
  never converts published success into a false deployment-wide adoption claim. Give its exact
  next action; routine adoption must not require restart.

| Field | Required meaning / backend validation |
|---|---|
| `automation.maximumActiveJobs` | Integer1–10000; Pending+Running Jobs in the shared admission pool, not worker/thread/file parallelism. Lowering capacity stops new excess admissions, preserves admitted work. |
| `automation.staleJobAgeSeconds` | Integer60–604800; no durable running-Job update for this duration, not total-runtime timeout, cancellation or replay permission. |
| `automation.workerPollSeconds` | Finite positive number in seconds; actual resident processing Worker cadence, independent of heartbeat/lease and Job pipeline pin. |
| `automation.schedulerPollSeconds` | Finite positive number in seconds; actual resident due-check cadence, independent of definition interval/Cron/timezone. |

Backend metadata/defaults are authoritative. Reference recommendations are illustrative, not extra
ranges/defaults. Reject booleans-as-numbers, fractional integers, non-finite/zero/negative polls,
unknown/unsupported keys and edits outside this four-field boundary before publication. Avoid
frontend `parseInt` truncation. Advanced JSON is optional and, if retained here, only this safe subset.

### Ordered implementation steps

1. **Add focused settings publication over managed authority.** Extend `SystemSettingsService`
   or a cohesive application service with exact-Active read/checked four-field Save. Seed a new
   focused successor from the observed immutable Active, never an unrelated open Draft. Preserve
   every other field/object, validate the whole candidate and applicable unchanged evidence,
   prepare its runtime binding, then publish through existing atomic activation/concurrency.
   Record bounded before/after audit and reconciliation evidence; do not weaken shared activation
   checks or require unrelated media probes merely for scalar edits. A no-op Save must not admit
   work or manufacture adoption. First setup and unavailable/corrupt prior Active have distinct
   existing Settings setup/recovery guidance; do not invent a fallback business snapshot.
2. **Expose an explicit shared API contract.** Planned addition: authenticated
   `GET/PUT /api/v1/operations/automation/settings` for this focused projection/command, with
   backend-advertised Save availability/transport, READ/MANAGE_CONFIGURATION enforcement and
   strict typed normalization. This path is a planned implementation, not an existing probe.
   Keep existing generic `/api/v1/system/settings` and revision-settings Draft semantics compatible.
   Add focused-save error mapping and principal-scoped unknown-response reconciliation using
   current Active plus bounded matching publication/audit evidence. Comparing four equal values
   alone must not claim this request committed. Do not auto-retry an unknown mutation after reload,
   reconnect, double-click or principal change; internal concurrency/request details are automatic.
3. **Make resident control adoption real.** At each safe Worker/Scheduler loop boundary resolve
   current valid settings, select configured versus explicit CLI/deployment poll override, install
   the effective cadence and only then acknowledge it. Recheck configuration during idle waits
   on a documented internal bound no greater than5 seconds, independent of the old/new poll value
   and work arrival. Keep idle work/due checks on their selected cadence and preserve existing
   immediate work-drain behavior; rechecks must not busy-spin or cause extra claims/emission.
   Preserve timely heartbeat/lease renewal, cooperative stop,
   recoverable-fault waiting and first-Active startup. During a synchronous busy step adoption may
   remain pending until its next safe boundary; never interrupt/repin/replay admitted media work.
   The same shared loop must retain Notification Worker behavior without expanding its settings.
4. **Persist and project truthful consumer evidence.** Reuse resident instance identity and
   heartbeat/status; add only necessary latest per-instance evidence, using minimal additive
   persistence if required. Report applied fields/effective values, selected published identity,
   adoption time/freshness and explicit override source. A report is written by the consumer after
   adoption, not fabricated by API reads, startup registration or a generic heartbeat. API-local
   capacity/stale evidence stays labelled API-local; Scheduler reports its actual current capacity
   and polling, Worker its actual polling. Non-applicable fields are not asserted consumed.
   Bounded reads must expose every relevant live instance, including mixed versions/overrides;
   stale, stopped, missing, schema-incompatible, unreported or failed-report evidence cannot yield
   collective success. Snapshot identity and value freshness must match the displayed target;
   unrelated later publication cannot be silently treated as a matching adopted version.
5. **Deliver the shared native form/readback.** Embed/reuse one four-field component, query model
   and Save behavior from Automation and System Settings. Preserve tab/filter/return context,
   refresh-safe deep links, authentication continuation and principal-cache isolation. Use the
   supplied light-shell reference composition: form, help panel, schedule/timezone explanation,
   units and clear meanings. Explain configured versus overridden polling and each blocked
   consumer's next action. Keep correctable input during background readback; never show a saved
   candidate as published or a published target as collectively adopted. Provide loading/empty/
   setup/denied/unavailable states, keyboard focus and narrow layout. Do not redesign other settings.
6. **Protect existing authority and hand off.** Verify API/Scheduler use current capacity at new
   admission, stale reads use the selected current threshold, and old supported Job/Task/manual/
   transfer pins/results/grants/claims/fences retain meaning. Missing/corrupt Active prohibits new
   unsafe admission/emission; it does not erase or substitute intact admitted contexts. Reopen/
   upgrade any added evidence schema without altering supported work or requiring an old retired-
   product migration. Update necessary factual settings/deployment/architecture guidance and
   affected fake consumers; keep undelivered targets explicit. Checkpoint implementation and a
   concise affected-test report for B, not a full-suite dossier.

## Acceptance Criteria

- [ ] **S1 — Native settings:** Automation tab/header and System Settings reach the same four-field
  form/authority/readback. Reference-style desktop/narrow/keyboard and refresh/return/auth journeys
  work; no placeholder remains and no general setting store/editor is duplicated.
- [ ] **S2 — Exact checked Save:** valid Save publishes only these fields from the checked Active;
  unrelated open Drafts, definitions and other settings remain unchanged. Invalid/out-of-scope
  input, stale/concurrent writers and preparation/validation/activation faults cannot partially
  publish; prior Active/input and bounded failure-stage/recovery guidance are preserved.
- [ ] **S3 — Submission truth:** double-click does not create duplicate publications; unknown Save is
  retained and reconciled through durable evidence across reload/principal isolation before any
  explicit retry. Publication and per-consumer adoption are separate visible outcomes.
- [ ] **S4 — Actual cadence:** actual Worker/Scheduler processes started before first Active or
  while idle adopt eligible updates without restart/work arrival, including decreasing a previously
  long interval. Configuration recheck is at most5s, plus bounded local scheduling allowance in
  tests; busy adoption waits only for the existing safe boundary. PID/instance identity persists.
  Observe actual loop/wait/work timing, not just an HTTP echo or a self-reported target.
- [ ] **S5 — Honest consumers:** readback reports relevant values/version/freshness per live instance;
  mixed/pending/override/missing/stale/stopped/unavailable states never become collective adoption.
  Explicit poll overrides retain precedence and have actionable deployment guidance. API binding
  alone cannot certify Worker/Scheduler. Old-process reports without new evidence stay unavailable.
- [ ] **S6 — Engine/pin safety:** current capacity/stale semantics, current-Active fail-closed admission,
  timely heartbeats/leases and stop/fault recovery are maintained. Busy/admitted A work keeps its
  legitimate pin after B publication; no unintended cancel/requeue/replay, grant or schedule change.
- [ ] **S7 — Read/security/persistence:** READ/MANAGE_CONFIGURATION, redaction and principal isolation
  hold on every entrance. Passive reads, Save and consumer rechecks cause zero media/Provider/work
  effects. Necessary additive evidence survives reopen/upgrade with existing rows/pins/results intact.
- [ ] **S8 — Acceptance handoff:** changed/affected tests pass without hidden skips/retries or relaxed
  assertions/timeouts; B verifies complete Base..Head and T4 regression/native/process/packaging/
  supported-Compose evidence. Reference/private/unrelated files and preservation refs stay intact.

## Required Tests

Follow [test ownership and levels](docs/development-workflow.md#6-test-levels). New filenames/routes
below are planned additions; equivalent cohesive modules are acceptable when the handoff names the
actual commands. Start from existing Automation/System Settings and real `worker run`/`scheduler run`
entrances. Fixtures use temporary SQLite/local Storage/fake Providers; no user database/media/secrets.
Do not construct nonexistent probe routes or require extra process tooling beyond these outcomes.

### Developer — changed and directly affected tests

Add focused API/publication tests and real resident-process tests, e.g.
`tests/test_automation_settings_management.py` and `tests/test_automation_settings_resident.py`.
Cover S2/S3/S5 with real managed SQLite/API; success, all invalid bounds/finite values, out-of-scope
keys, two independent writers, failed runtime preparation/activation, lost response/reconciliation,
READ/denied and unrelated-Draft preservation. Assert no Job/Task/Provider/Storage/grant effects.

Use real subprocess fixtures from `test_resident_services`/`test_resident_correction` for S4/S6:
start before Active; idle low→high and long→short cadence; publish during a busy pinned step; healthy
heartbeat during long wait/work; DB lock/unavailable/corrupt Active then recovery; process loss,
mixed instances, restart and override. Configured-adoption cases must omit `--poll-seconds` (the
existing correction fixture always supplies an override and cannot prove configured adoption).
Controlled clock/unit tests verify wait deadlines/stop/heartbeat without long sleeps; real processes
independently prove behavior through actual loop/work observables. Report-only assertions are
insufficient. Keep isolated configs/ports/process cleanup and measure test time below50% of the round.

```bash
python3 scripts/check_governance.py
.venv/bin/python -m unittest tests.test_automation_settings_management tests.test_automation_settings_resident
.venv/bin/python -m unittest tests.test_system_settings_management tests.test_resident_services tests.test_resident_correction tests.test_automation_admission tests.test_stale_job_visibility tests.test_configuration_snapshot
# New/changed Web form/normalizer tests plus shared route/settings regressions:
npm --prefix web run test -- run src/features/operations/AutomationSettingsPage.test.tsx src/features/configuration/ConfigurationPage.test.tsx src/features/operations/AutomationRouter.test.tsx src/features/operations/AutomationWorkspaceReadModel.test.tsx
npm --prefix web run typecheck
npm --prefix web run build
# cwd web; planned settings spec, real Python/API/SQLite plus resident processes:
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-settings.python.spec.ts
```

Add the planned Web test file with the actual shared component placement, or substitute its actual
path. Run Ruff format/lint/compile and ESLint/Prettier on actual changed files, and all other new/
modified/directly affected tests. If shared Automation consumers change, rerun the existing lifecycle/
Run-once/workspace specs; if shared persistence changes, include affected reopen/migration cases.
Align fake documents and exclude the new Python-only spec from default fake-backed collection using
the existing convention; retain it in the explicit real command. Developer does not run full Python,
Web/default E2E, Docker or release matrices before handing off.

### B — independent acceptance and full regression

Review immutable **Task Base..candidate**, re-evaluate all Slice RO-1..RO-7 and preserve accepted45.
Independently reproduce a real UI checked Save, long-wait idle adoption without restart or work,
busy A→B pin preservation, override and lost/stale consumer readback. Inspect actual wide/narrow
screenshots against the preserved reference. Use public commands and supported isolated fixtures;
any added harness capability must be implemented before use and invoke actual application services.

Run the [shared T4 gates](docs/development-workflow.md#shared-full-regression-commands), including
full Python/Web/default browser regression, relevant static/security/safety checks, production build,
wheel/installed-consumer and material Docker lifecycle tests. Full runs covering focused cases need
no duplicate module executions. In addition to new subprocess coverage, run native suites sequentially
on isolated temporary configuration/ports:

```bash
# cwd web; after production build
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-settings.python.spec.ts tests/e2e/automation-workspace.python.spec.ts tests/e2e/automation-lifecycle.python.spec.ts tests/e2e/automation-run-once.python.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
npm run test:e2e -- --config=playwright.python.unicode-principal.config.ts tests/e2e/operations-principal-identity.python.spec.ts
# repo root; exact candidate image, isolated temporary stacks
.venv/bin/python scripts/docker_empty_baseline_smoke_test.py --image mediaflow:slice43-candidate
.venv/bin/python scripts/docker_restart_fault_smoke_test.py --image mediaflow:slice43-candidate
.venv/bin/python scripts/docker_release_security_smoke_test.py --image mediaflow:slice43-candidate
```

Existing Docker scripts build from the candidate; record exact source/image/artifact identity and
run serially. Extend only necessary settings-adoption assertions in existing packaging/Compose proofs;
an installed consumer outside the checkout must use the new cadence behavior, not import source.
If evidence persistence changes, include supported current-schema additive upgrade/reopen and
failure-atomicity proof with preserved work/pins/authorities. Do not recreate retired-product schemas.
Full Python covers admission/fencing/Cron-DST/grants/revocation/recovery/C-with-A/A/security; correlate
those results with actual native scheduled execution, Run once and sibling recovery for Slice Final.

Retain exact commands/results, SHA/diffs, matching source/test/harness/dependency/asset identities and
raw logs/screenshots locally or in CI. Reuse only matching B/CI evidence under the workflow;43.3's
T3 PASS does not waive this Task's T4 or certify changed resident code. Record actual timing below50%
per review round; do not sleep to pad elapsed time or label unrun required gates PASS. Unavailable
gates stay with B as pending acceptance, not a request for Developer to run full regression.

Both roles run `git diff --check`, governance and preservation checks. Original reference hashes:
`自动化页.png` = `d2f759ead56a30dce344ccce97e7c119e144ca728a31b3af8e9a355eefa6ba34`;
`自动化页-全局设置.png` = `68d91070e859dd363d3e45dd2d21e38783e0cfbef0867ce28c3f42eac7d6c7b9`.
Keep them untracked/unchanged; preserve the pre-existing `docs/pics/操作与任务.png` deletion, all other
untracked artifacts and ignored/untracked/unstaged `config/alist.json` without reading its contents.

## Non-goals

- Queue/supervisor replacement, more workers/threads, new concurrency controls or auto-restart.
- Changing definitions/schedules/timezones, unattended/manual execution authority, media policy/pins,
  mutation/recovery semantics, or introducing an automatic stale-job cancel/requeue/replay mechanism.
- Notification polling/settings redesign, unrelated general System Settings UI/lifecycle changes,
  bootstrap database/secret/deployment editing or overriding CLI/deployment authority through Web.
- Restoring Scan/standalone Preview/FileIndex, removed-mode compatibility/migration/history engines,
  adding process-tooling projects, pixel-exact fixtures or example values as product constraints.
- A Final Review, Slice closure, Roadmap/Progress boundary changes, next Task planning or push.

## Developer Completion Report

```text
Status: READY FOR B REVIEW (Developer does not self-PASS)
Task Base: f18d2444f548b81b5892536498a1b4cdd4400be8
Candidate: the commit carrying this report (see `git log -1` for the exact SHA)
```

### Implemented behavior

1. **Focused four-field publication (`AutomationSettingsService`).** Added
   `mediaflow/domain/automation_settings.py` (field metadata/bounds/meanings, strict
   normalization, adoption evaluation) and `mediaflow/application/automation_settings.py`
   (checked Save, no-op detection, focused-change proof, reconciliation, consumer
   projection). One Save seeds a successor from the observed immutable Active, applies only
   the four fields, validates the whole candidate, prepares the runtime binding and
   activates atomically. Other settings/definitions/open Drafts stay byte-identical.
2. **Explicit API contract.** `GET/PUT /api/v1/operations/automation/settings` with
   READ / MANAGE_CONFIGURATION enforcement, typed normalization errors (422 with
   `field`/`durableState`/`sideEffects`), `stale` (409, `active_preserved`) and
   prepare/validate/activate stage failures (503). Unknown outcome is reconciled with
   `{"reconcile": true}` against principal-scoped durable audit evidence + current Active.
   Generic `/api/v1/system/settings` Draft semantics are untouched.
3. **Finite-number protection.** `mediaflow.domain.system_settings._validate_number_bounds`
   now rejects non-finite values before any bound, so `inf`/`NaN` can no longer pass a
   `<= 0` comparison.
4. **Real resident cadence adoption.** `ResidentLoop` gained optional
   `cadence_resolver`/`adoption_reporter`; it adopts at entry, before each step and before
   each idle wait, and its idle wait is `min(selected cadence, 5s)`. `worker run` /
   `scheduler run` compose the resolver/reporter through
   `resident_cadence_adoption`; `--poll-seconds` keeps precedence and is reported as an
   override. Notification Worker behavior is unchanged.
5. **Truthful consumer evidence.** Additive runtime schema 50 table
   `resident_settings_adoption`, written only by the owning process after it installed the
   cadence, carrying the publication identity it adopted. Readback reports per-instance
   status/freshness/override with an explicit next action; the collective claim covers only
   the two cadence consumers and the capacity/stale fields carry an `api_local` basis.
6. **Shared native UI.** `AutomationSettingsPanel` renders the same form + adoption readback
   from `自动化 → 全局设置` (replacing the placeholder that handed off) and from
   `/configuration`. Published target, in-progress input and adoption are visually and
   logically separate; an unknown Save blocks further saves until reconciliation.
7. **Docs.** `docs/architecture.md` (delivered CURRENT subsection),
   `docs/deployment.md` (cadence adoption + override guidance), `docs/configuration.md`
   (field meanings + focused settings section).

### Affected commands and actual results

| Command (cwd) | Result |
|---|---|
| `python3 scripts/check_governance.py` | `governance check: PASS` |
| `.venv/bin/ruff format --check .` | `389 files already formatted` |
| `.venv/bin/ruff check .` | `All checks passed!` |
| `.venv/bin/python -m compileall -q mediaflow tests scripts` | exit 0 |
| `.venv/bin/python -m unittest tests.test_automation_settings_management tests.test_automation_settings_resident` | `Ran 32 tests ... OK` |
| `.venv/bin/python -m unittest tests.test_system_settings_management tests.test_resident_services tests.test_resident_correction` | `Ran 86 tests ... OK` |
| `.venv/bin/python -m unittest tests.test_automation_admission tests.test_stale_job_visibility tests.test_configuration_snapshot tests.test_automation_api tests.test_task_persistence tests.test_v2_settings_rule_readiness` | `Ran 117 tests ... OK` |
| `.venv/bin/python -m unittest tests.test_automation_workspace_read_model tests.test_v2_automation_operations tests.test_v2_automation_lifecycle tests.test_automation_definition_publication tests.test_automation_definition_occurrence` | `Ran 146 tests ... OK` |
| `.venv/bin/python -m unittest tests.test_v2_automation_run_once tests.test_v2_settings_rule_readiness tests.test_automation_definition_execution tests.test_media_discovery` | `Ran 171 tests ... OK` |
| `.venv/bin/python -m unittest tests.test_recognition tests.test_api_security tests.test_configuration_objects` | `Ran 100 tests ... OK` |
| `.venv/bin/python -m unittest tests.test_operations_run_detail_plan_evidence` (C-with-A/A) | `Ran 10 tests ... OK` |
| `npm run typecheck` / `lint` / `format:check` (cwd `web`) | all clean |
| `npm run test -- run` (cwd `web`) | `Test Files 82 passed`, `Tests 1183 passed` |
| `npm run build` (cwd `web`) | succeeds (pre-existing chunk-size warning only) |
| `npm run test:e2e` default fake suite (cwd `web`) | `242 passed` |
| `npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-settings.python.spec.ts` | `5 passed` |
| `... automation-workspace.python.spec.ts` | `8 passed` |
| `... automation-lifecycle.python.spec.ts` | `11 passed` |
| `... automation-run-once.python.spec.ts` | `4 passed` |
| `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts` | `41 passed` |

No test was skipped, retried or weakened; no assertion was relaxed and no timeout was raised.
`web/src/features/operations/AutomationWorkspaceReadModel.test.tsx` and
`.../ConfigurationPage.test.tsx` were corrected only where the newly shared panel legitimately
adds one extra GET read (they now scope "one read" assertions to the route they intend to prove).

### Remaining risks / disclosures for B

1. **Adoption evidence is additive (schema 49 → 50).** I verified the additive table creation
   and reopen durability, but **B owns the supported-schema upgrade rehearsal on a real prior
   database with existing work/pins/authorities** (T4). No FileIndex/retired-product schema was
   recreated.
2. **Test cost.** The resident subprocess suites are the slowest part of this round (~30s for
   the two new modules; the previously existing resident modules are unchanged in behavior).
3. **Deliberate limits.** No queue/supervisor replacement, no new concurrency control, no
   auto-restart, no automatic stale/uncertain replay, and no process-tooling project were added.
   `maximumActiveJobs` still counts Pending+Running Jobs in the shared pool.
4. **UI depth.** The form is text-input based with backend-advertised minimum/maximum/unit help;
   there is no per-field slider or Advanced JSON editor, deliberately keeping the surface to the
   safe supported subset.
5. **The harness gained a real in-process resident cadence consumer**
   (`POST /__harness__/start-resident-consumers`) so the browser proof is derived from a real
   adoption; it reuses the production `ResidentLoop` composition and claims no work. B should
   confirm this meets the "actual application services" requirement (I believe it does; the
   subprocess proof is separate in `tests/test_automation_settings_resident.py`).
6. **Not run by Developer (B-owned):** full Python discovery, wheel/installed-consumer, Docker
   lifecycle/security smokes, Unicode-principal and task-center visual native suites, and the
   complete T4 matrix.

## B Review Result

```text
Reviewed: planning only at f18d2444f548b81b5892536498a1b4cdd4400be8
Decision: PENDING — Developer candidate submitted READY FOR B REVIEW; independent T4 acceptance not run
Acceptance runs: none yet on the implementation candidate
Task blockers: not assessed
Slice Required Outcomes / Surfaces all satisfied: NO — B must re-evaluate RO-1..RO-7 after acceptance
Next: B REVIEWS TASK BASE..CANDIDATE AND RUNS T4 ACCEPTANCE
```
