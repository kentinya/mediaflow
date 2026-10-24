# Task 43.4 — Automation Engine Settings Publication and Resident Adoption

Authority: committed [SLICE.md](SLICE.md), [Development Workflow](docs/development-workflow.md)
and [B experience](docs/agent-experience/task-planner-reviewer.md). Developer reads the
[implementation experience](docs/agent-experience/developer-implementation-role.md).

```text
Task ID: 43.4
Parent Slice: 43
Status: FIX REQUIRED
Task Base: f18d2444f548b81b5892536498a1b4cdd4400be8
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Working Branch: main
Decision: FIX REQUIRED — R2 INPUT PRESERVATION AND R5 TERMINAL RECOVERY REMAIN INCOMPLETE
Next Action: DEVELOPER CORRECTS THE TWO REMAINING BLOCKERS IN THIS SAME TASK; B RETAINS T4 OWNERSHIP
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
Reviewed candidate: b3dc11f067a9d1a8864d99aa24bdfba0d859fbef (main)
Complete Task range: f18d2444f548b81b5892536498a1b4cdd4400be8..b3dc11f067a9d1a8864d99aa24bdfba0d859fbef
Decision: FIX REQUIRED — R1..R6 below are Task blockers (P1)
Task ID / Base / Goal / Scope / Difficulty / Test Level: unchanged
Slice Required Outcomes / Surfaces all satisfied: NO
Next: correct Task43.4, run failing/new/directly affected checks, checkpoint READY FOR B REVIEW
```

B inspected the complete34-file Task manifest, production/API/CLI/persistence/Web changes and
changed test/harness/doc consumers. The implementation and planning commits were both reviewed;
no partial-diff review or A Final Review is claimed. All six findings originate in implementation
`b3dc11f` (2026-10-24 12:47:04 +08:00), rather than being assumed Base failures. Existing public
settings entrances and `scheduler run` reproduced the failures below. Fault injection was limited
to the existing runtime-construction/validation boundary over isolated fixtures, not nonexistent
routes or production data. The Developer report above remains historical, not B acceptance.

### Required corrections inside this Task

1. **R1 — Prepare runtime before activation (S2/S6/S7).**
   `AutomationSettingsService._activate` calls `activate` without `before_publish`;
   `_automation_engine_settings_projection` constructs the binding only after publication.
   Existing PUT with a runtime-binding construction fault returned500/internal_error while
   Active advanced and capacity changed100→31. Reuse the checked publication lock/preparation
   callback/binding installation pattern already used by focused definition Save. A preparation
   failure must leave both Active and process binding unchanged, with bounded stage/recovery.
   Add an actual runtime-construction failure case; the current test named failed preparation
   injects validation failure and does not exercise this boundary. Reconcile documentation's
   prepare-before-publication claim with the corrected implementation.
2. **R2 — Retain the editing baseline across polling (S2).**
   `AutomationSettingsPanel` preserves edited values but sends `model.target` from the newest
   background read. Real UI: edit capacity; another writer changes scheduler poll5→9;
   wait for the ordinary background GET; Save returns201 and silently restores scheduler5.
   Capture values plus checked identity when editing begins. Refetch may update readback but
   cannot silently attach a fresh identity to old four-field input. A changed target must refuse
   the stale Save or require explicit refresh/review while retaining correctable input. Add a
   real two-writer UI case that includes the normal polling interval; direct stale API tests alone
   do not cover this journey. Do not silently discard edits made during an outstanding Save.
3. **R3 — Separate configuration wakes from business polls (S4/S6).**
   `ResidentLoop.effective_poll_deadline` caps the sleep at5s, after which `run` invokes `_step`
   again. A real `scheduler run` configured60s performed four actual `IntervalScheduler.tick`
   calls at5.01/5.02/5.02s, while reporting60s adopted. Preserve a business-poll deadline across
   bounded config/heartbeat wakes; rechecks must not claim work or emit/tick early. Eligible
   updates must still shorten a long wait within the existing≤5s bound, explicit overrides
   must retain their real cadence, and successful work keeps the existing immediate-drain rule.
   Protect Notification Worker timing too: the changed unconditional cap currently reaches it.
   Test actual idle poll/claim/due-check timing with values above5s and config-only wakes, not
   only `_poll_seconds`, wait caps or self-written adoption rows.
4. **R4 — Make adoption readback stay truthful through normal operation (S5).**
   The owning loop writes a report only on value/digest change, yet readback expires that report.
   Real unchanged60s Scheduler remained live but became adoption `stale` after16s; no report
   refresh occurred. Failed report writes also set `_applied_cadence` before success and are
   never retried for the unchanged publication. Refresh/retry owning-consumer evidence at safe
   bounded points, without fabrication by API/heartbeat or extra business polls. Separately,
   `normalizeAutomationSettings` aggregates the `api_local` row whose adopted flag is always
   false: real backend allAdopted=true with both resident rows adopted still renders pending.
   Aggregate the intended cadence consumers consistently; retain API-local field evidence as
   separate. Cover unchanged healthy processes beyond the freshness window, failed-report
   recovery, genuine collective success, overrides and stopped/stale/mixed instances. Preserve
   exact publication identity and consumer-specific freshness, not value equality alone.
5. **R5 — Reconcile the exact submission, preserve it across reload (S3/S7).**
   `reconcile` accepts any actor-matching `draft_edit` plus currently equal values as committed.
   Existing API reproduction: admin edit fails validation (503); writer publishes the same
   values (201); admin reconciliation returns committed=true and cites the still-Draft failed
   revision, which is not Active. Bind the internal submission identity and baseline to durable
   publication/terminal evidence using existing patterns; a draft edit or older equal submission
   cannot certify publication of this request. An absent audit while a request can still publish
   cannot authorize another Save. Preserve unresolved, non-secret submission context across
   reload/navigation with principal isolation and no stored bearer token. Real UI with committed
   response loss showed the reconcile action before reload and lost it after reconnect; subsequent
   Save is then possible without reconciliation. Test lost-response reload, delayed original
   completion, failed-Draft/equal-other-writer and same-principal historical equality. Keep
   committed/superseded/not-committed/unresolved states truthful rather than one false boolean.
6. **R6 — Complete the required native settings composition (S1).**
   Production desktop/narrow screenshots compared with the original reference show an unstyled
   form and raw adoption tables, without the required help panel or schedule/timezone explanation.
   The new `mf-automation-settings`, `mf-form-field`, `mf-panel`, `mf-detail-grid` and related
   selectors have no stylesheet definitions. Reuse actual shared form/card/table styles and add
   only needed scoped layout. Deliver the specified form/help composition and schedule/timezone
   explanation; fold/label diagnostic IDs rather than making UUIDs the primary page content.
   Keep adoption evidence readable at390px, ordinary keyboard focus and actionable setup/denied/
   error states. Verify real wide/narrow images after production build. This is the missing
   required composition/journey, not a pixel-exact request or new design scope.

### Independent evidence and remaining gates

Local evidence (not remotely accessible):
`.git/validation-evidence/b3dc11f/task43.4-b-review/`.

| Actual B execution | Result |
|---|---|
| `python3 scripts/check_governance.py`; complete Task `git diff --check` | PASS / clean before review-document update; repeated for checkpoint below |
| `PYTHONPATH=. .venv/bin/python <evidence>/api_probe.py` | R1/R5 reproduced through existing real WSGI API and SQLite;0.137s |
| `PYTHONPATH=. .venv/bin/python <evidence>/resident_probe.py` | R3/R4 reproduced with actual `scheduler run`, observer delegates real tick;16.25s; PID alive, liveness live |
| `npm --prefix web run build` | PASS; existing chunk-size warning; freshly served production assets |
| `node <evidence>/browser-probe.cjs` with existing `operations_inventory_harness.py --port4197` | R2/R4/R5 reproduced through actual Web/API;6.042s; desktop/narrow screenshots inspected |
| Both original reference SHA256s; frozen branch | Match Contract; `frozen/slice-43-2026-10-15` remains `ed974e0df8b263f631bfe48b524da461013d8780` |

The initial evidence-script import path and tick-trace path needed correction; their failed runs
are not product defects or passes. Final scripts/logs contain the corrected reproductions; trace
observer does not replace or change the scheduler tick. All isolated processes were stopped.
Conservative cumulative testing/reproduction/check allowance is under60s, including the failed
16s observer attempt, comfortably below50% of this substantive review round; no padding waits.

Per workflow§6, proven blockers permit early FIX REQUIRED: full Python/Web/default/native T4,
wheel/installed-consumer, supported49→50 upgrade and Docker lifecycle/security gates were **not run
by B this round and remain pending**. Developer's reported results are not relabelled B evidence.
The new busy-step test actually checks a pending unclaimed Job, the heartbeat case initially
checks liveness without proving advancement, and the additive-upgrade case starts at schema50.
Strengthen the existing affected tests to exercise the already-required busy boundary, actual
heartbeat progression and supported prior-schema preservation; no process-tooling project or new
Task is needed. Full acceptance/release gates stay B-owned after correction.

### All-Slice outcome reassessment

| Required Outcome / Surface | Disposition on this candidate |
|---|---|
| RO-1 workspace/inventory/statistics |43.3 inventory/records contribution remains prior accepted work; settings/reference/readback portion incomplete (R4/R6). |
| RO-2 checked definition lifecycle |Existing implementation reused; this Task does not change its intended contract. Current whole-Slice T4 still pending; no automatic renewed PASS from historical labels. |
| RO-3 analysis/scoped unattended execution |Existing shared chain and authority retained in scope; current safety/resident/full proof pending. No retired Preview restoration is authorized. |
| RO-4 deliberate Run once |Existing bounded discovery/analysis/confirmation journey retained; final candidate native/Worker regression pending. |
| RO-5 records / Task Center recovery |Prior43.3 accepted read-only records/recovery boundary remains; this Task must not introduce execution recovery in settings/records. |
| RO-6 settings / real resident adoption |INCOMPLETE: R1..R6 block exact publication, concurrent/unknown recovery, cadence and truthful/native adoption. |
| RO-7 shared authority/failure/safety |Settings contribution incomplete; full RBAC/pins/retirement/packaging/current-consumer acceptance remains pending. |

Slice43 stays ACTIVE, **not READY FOR A REVIEW**. Keep the same Task/Base/Goal/Scope and correct
these blockers; no next Task or Closure Packet is warranted. A-owned SLICE/Roadmap/Progress and
accepted45 boundaries are unchanged. Original references, pre-existing dirty/untracked artifacts
and ignored private configuration are preserved; private configuration contents were not read.
This B checkpoint changes only `TASK.md`; no push, history rewrite or implementation self-approval.

## Developer Fix Report — R1..R6 corrections

Historical Task43.4 report and B's FIX REQUIRED review above are retained unchanged. This
section reports the corrections made in the same Task/Base/Goal/Scope.

```text
Status: READY FOR B REVIEW (Developer does not self-PASS)
Task Base: f18d2444f548b81b5892536498a1b4cdd4400be8
Candidate: `24b92ab` (report commit supersedes it with this section only)
Scope: fix R1..R6 inside the same Task/Base/Goal/Scope
```

### Corrections delivered for R1..R6

1. **R1 — runtime preparation now happens before publication.**
   `AutomationSettingsService.save` passes a `before_publish` callback straight into
   `ManagedConfigurationService.activate`, and the API composes it as
   `_prepare_runtime_binding_for_revision` inside `_runtime_binding_lock` (the same
   pattern as the focused definition/resource-library Saves). A preparation fault is
   detected through an internal marker and reported as
   `automation_settings_runtime_failed` (503, `stage: prepare`, `active_preserved`); the
   Active pointer and this process's binding both stay on the predecessor. The runtime
   binding is published with `_publish_runtime_binding` only after a successful activation.
   `docs/architecture.md`/`docs/configuration.md` state the same order.
2. **R2 — the editing baseline survives normal polling.**
   `AutomationSettingsPanel` keeps `{baseline, input}` for an edit; a background refetch
   updates the readback but can no longer attach a fresh publication identity to older
   input. A changed target disables Save, states that another save changed the published
   values, and retains the typed values so they can be reviewed or explicitly discarded.
3. **R3 — configuration wakes are separated from business polls.**
   `ResidentLoop` now keeps a `next_business_poll` deadline; a bounded wake (<= 5s,
   `effective_poll_deadline`) only re-adopts configuration, refreshes the heartbeat and
   refreshes the adoption report. `_step` runs only when the business deadline (the
   *selected* cadence, `business_poll_deadline`) is reached, so a 60s Scheduler no longer
   ticks every 5s; a shorter adoption still shortens a pending long wait, real work keeps
   the immediate-drain rule, and the Notification Worker keeps its own interval. The loop
   gained an injectable `monotonic` clock so the timing is provable without real sleeps.
4. **R4 — adoption readback stays truthful during normal operation.**
   The owning loop re-writes its own report on a bounded refresh even when nothing changed,
   so a live-but-idle consumer no longer decays to `stale`; a failed report write is not
   acknowledged and is retried at the next boundary (never marked applied). The Web
   aggregate now gates `allAdopted` on the resident cadence consumers only, so the
   `api_local` capacity row can no longer render a real deployment-wide adoption as
   pending. `docs/deployment.md`/`docs/configuration.md` record the behaviour.
5. **R5 — reconciliation is bound to the exact submission.**
   Every Save carries a client-generated `submissionId`, persisted in bounded `draft_edit`
   audit evidence and scanned through the ledger's monotonic `sequence` cursor. Reconcile
   returns one of `committed` / `superseded` / `not_committed` / `unresolved` derived from
   *that revision's* own status/validation evidence, so a failed Draft, an older equal
   submission or another writer publishing equal values can no longer certify the request
   (`no submissionId` is always `unresolved`). The panel writes the retained context
   (identity, submitted values, edit baseline, typed input) to a principal-scoped
   session key *before* the mutation and restores it after a reload; only a terminal
   reconcile clears it. No bearer token or secret is stored.
6. **R6 — the required native composition is delivered.**
   `mf-automation-settings`, `mf-panel`, `mf-panel-header`, `mf-form-field`,
   `mf-form-control`, `mf-field-help`, `mf-detail-grid`, `mf-table` and the diagnostics
   disclosure now have real stylesheet definitions with a two-column form+help layout that
   collapses at 900px/480px. The form now ships the reference composition: field help with
   units/bounds/meaning, an "关于自动化引擎" help panel with the publish-vs-adopt warning,
   and a "调度与时区说明" card with interval/Cron/timezone explanation plus a live config
   example. Diagnostic UUIDs moved into a folded "诊断标识" disclosure; the Save button
   reads "保存设置" and is legible at wide and 390px layouts.

### Affected commands and actual results

| Command (cwd) | Result |
|---|---|
| `python3 scripts/check_governance.py` | `governance check: PASS` |
| `.venv/bin/ruff format --check .` | `389 files already formatted` |
| `.venv/bin/ruff check .` | `All checks passed!` |
| `.venv/bin/python -m compileall -q mediaflow tests scripts` | exit 0 |
| `git diff --check` | clean |
| `.venv/bin/python -m unittest tests.test_automation_settings_management tests.test_automation_settings_resident` | `Ran 43 tests ... OK` |
| `.venv/bin/python -m unittest tests.test_system_settings_management tests.test_resident_services tests.test_resident_correction tests.test_automation_admission tests.test_stale_job_visibility tests.test_configuration_snapshot` | `Ran 115 tests ... OK` |
| `.venv/bin/python -m unittest tests.test_automation_api tests.test_task_persistence tests.test_v2_settings_rule_readiness tests.test_automation_workspace_read_model tests.test_v2_automation_operations tests.test_v2_automation_lifecycle tests.test_automation_definition_publication` | `Ran 186 tests ... OK` |
| `.venv/bin/python -m unittest tests.test_v2_automation_run_once tests.test_automation_definition_execution tests.test_recognition tests.test_api_security tests.test_configuration_objects tests.test_operations_run_detail_plan_evidence` | `Ran 155 tests ... OK` |
| `.venv/bin/python -m unittest tests.test_restart_fault_boundary tests.test_notifications tests.test_operator_ui` | `Ran 61 tests ... OK` |
| `.venv/bin/python -m unittest tests.test_configuration_objects tests.test_automation_definition_occurrence tests.test_operations_run_detail_plan_evidence tests.test_api_security` | `Ran 111 tests ... OK` |
| `npm run typecheck` / `lint` / `format:check` (cwd `web`) | all clean |
| `npm run test -- run` (cwd `web`) | `Test Files 82 passed`, `Tests 1191 passed` |
| `npm run build` (cwd `web`) | succeeds (pre-existing chunk-size warning only) |
| `npm run test:e2e` default fake suite (cwd `web`) | `242 passed` |
| `npm run test:e2e -- --config=playwright.python.automation.config.ts <settings+workspace+lifecycle+run-once>` | `31 passed` |
| `npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-settings.python.spec.ts` | `8 passed` |
| `npm run test:e2e` fake suite re-run after the settings fake/reconcile shape update | `242 passed` |

No test was skipped, retried or weakened. Two assertions were *strengthened*: the fake
settings document now states the real reconcile `state`, and the older resident assertions
(`test_loop_survives_a_failing_step_and_keeps_heartbeating`) stop on the step count rather
than counting loop iterations, because bounded configuration wakes are no longer iterations
of the business step.

New/strengthened coverage for the corrections:

- `test_failed_runtime_preparation_preserves_active_and_process_binding` +
  `test_successful_save_installs_the_prepared_runtime_binding` (real runtime-construction
  fault, not a validation failure).
- `test_failed_draft_and_equal_other_writer_never_certify_this_submission`,
  `test_superseded_submission_is_reported_as_published_then_replaced`,
  `test_same_principal_historical_equal_values_do_not_certify_a_new_identity`,
  `test_reconcile_without_submission_identity_never_claims_commit`.
- `test_configuration_wakes_do_not_become_business_polls`,
  `test_shorter_adoption_shortens_a_pending_long_wait`,
  `test_notification_loop_preserves_its_business_cadence`,
  `SchedulerBusinessPollTests.test_long_cadence_is_not_shortened_by_configuration_rechecks`
  (real `scheduler run`, durable wait-state timestamps).
- `test_unchanged_consumer_refreshes_its_own_report`,
  `test_failed_report_is_retried_for_the_unchanged_publication`,
  `SchedulerBusinessPollTests.test_unchanged_live_consumer_keeps_refreshing_its_own_report`.
- `BusyStepAdoptionBoundaryTests` (real publication during a busy step, pin untouched),
  `test_worker_heartbeat_advances_across_a_long_cadence` (durable timestamp advances),
  `test_additive_upgrade_from_the_prior_schema_keeps_rows_and_pins` (starts at schema 49).
- Web: `refuses a stale save after a background readback changed the target` (real 5s
  polling interval), `restores and reconciles an unknown submission after a reload`,
  `states a genuinely adopted deployment as adopted`, and
  `automation-settings-session.test.ts` (principal scoping, no credential, malformed drop,
  clear-on-principal-change).
- Real Python browser: UI `保存设置` publishes exactly once with `submissionId`, a
  concurrent writer's publication refuses the stale Save through the ordinary 5s readback,
  and reconcile answers `unresolved` for a never-submitted identity vs `committed` for the
  real one.

### Remaining risks / disclosures for B

1. **Test cost.** The two focused modules now take ~43 tests / ~50s (resident subprocess
   cases dominate). This round's total wall time was dominated by implementation and
   reading; executed testing/reproduction is a small minority of the round, well under the
   30% budget.
2. **B-owned gates not run here:** full Python discovery, wheel/installed consumer, the
   supported 49→50 upgrade rehearsal on a real prior database with existing work/pins, and
   the Docker lifecycle/security smokes. The in-suite upgrade case simulates the prior
   schema shape; B still owns the real-database rehearsal.
3. **`superseded` semantics.** A submission that published and was later replaced reports
   `committed: true` with `state: superseded`; the page then tells the operator the values
   are no longer the published target. B should confirm this reading of "committed" is
   acceptable rather than expecting a single boolean.
4. **Adoption refresh bound.** The re-report cadence is the same 5s internal bound as the
   configuration recheck; it does not poll business work. Readback staleness remains
   `max(3 × heartbeat interval, 10s)`.
5. **Harness.** The existing in-process resident consumer
   (`POST /__harness__/start-resident-consumers`) is still used for the browser adoption
   proof and reuses the production `ResidentLoop`; the subprocess proof is separate.
6. No queue/supervisor replacement, no new concurrency control, no auto-restart, no
   automatic stale/uncertain replay, and no schema beyond the existing additive schema 50
   table.

## B Re-review — corrected candidate 57b1808

**Decision: FIX REQUIRED.** Same Task43.4 / Base / Goal / Scope; no new Task and no Slice closure.
Independently reviewed cumulative `f18d2444f548b81b5892536498a1b4cdd4400be8..57b180864b1862b07894ab444e1b00fe8b59d287`
(38 changed files), using the previous full original-implementation review plus the complete
`c1f6ea7..57b1808` correction delta (22 files), current source and real-entry reproductions.
This report supersedes the earlier six-open-blocker disposition; it does not reopen resolved items.

### Previous blocker disposition

| Item | Current result |
|---|---|
| R1 preparation before publication | Corrected. Real PUT plus runtime-construction fault returns503/prepare; previous Active and capacity100 remain. Focused binding-install/preservation tests pass. |
| R2 concurrent edits/input | Background-poll baseline overwrite corrected: external scheduler publication disables stale Save and retains capacity51. **Outstanding-Save input loss remains**, below. |
| R3 actual business cadence | Corrected for the reviewed reproduction. Actual `scheduler run` at60s produces only one tick during16.25s; configuration wakes no longer tick every5s. Controlled-clock and process cases pass. |
| R4 fresh/honest adoption | Corrected for prior failures. Same real Scheduler stays live/adopted beyond the report-expiry window and refreshes its own report. Failed-report retry tests pass; real Web/API both show collective adoption. |
| R5 exact submission/reload | Exact identity prevents equal-writer/failed-Draft false success; retained context survives real reload. **Settled rejection/preparation failure cannot resolve**, below. |
| R6 required native composition | Corrected. Fresh production desktop1440px/narrow390px screenshots inspected: actual form/help columns, schedule/timezone card, folded diagnostics and responsive layout exist. |

### Two remaining P1 corrections

1. **R2 — Preserve input accepted while a Save is outstanding (S2 / RO-7).**
   `AutomationSettingsPanel.tsx:359` unconditionally clears `edit` on success, while inputs at
   line555 are still enabled during `submitting`. Real existing settings form: enter capacity41,
   click Save, keep its successful server response in transit, type42, then deliver the response.
   Input is enabled and accepts42, but the form silently returns to41; only41 was published.
   This is the uncorrected portion of the previous R2, introduced by `b3dc11f`
   (2026-10-24 12:47:04 +0800), still present in the correction candidate.
   Either prevent editing for the duration of the outstanding submission, or retain subsequent
   edits separately and reconcile their baseline explicitly after success. Do not unconditionally
   clear a newer edit or silently rebase it. Cover successful and unknown/failed responses with
   input attempts while the actual request is outstanding; if editing is disabled, prove the UI
   never accepts the later value. Keep existing background-refetch protection.
2. **R5 — Supply an actionable terminal recovery for settled non-publications (S3 / RO-6/7).**
   `AutomationSettingsService.save` rejects a stale identity before recording `draft_edit`;
   `_submission_evidence` therefore returns `unresolved` even with a complete healthy audit read.
   `_revision_submission_state` also leaves a completed preparation failure's `validated` revision
   unresolved. The panel correctly refuses an unsafe replay, but has no path out of that state.
   Real existing Web/API race: edit capacity61, another legitimate Save publishes first, the
   original PUT finishes409, then lose only that response. Reconcile twice, including a real page
   reload:200/unresolved, `evidenceComplete:true`, `identityMatched:false`; editing and Save remain
   disabled, capacity remains41. DB/target/audit are readable; another refresh cannot repair this.
   Independent real API construction-fault case: completed503/prepare preserves Active100, but
   repeated reconciliation of its exact submission returns unresolved/validated. The submission
   state mapping/terminal-only UI block was introduced in `fa872df`
   (2026-10-24 14:09:25 +0800); the correction leaves the required failure→recovery journey incomplete.
   Retain sufficient authoritative outcome evidence for this exact actor/submission across the
   whole Save, including pre-Draft refusal, unchanged/no-op and completed persist/validate/prepare/
   activate failures. Reconcile proven non-publication into a terminal, correctable UI state with
   retained input and explicit review of current values. Preserve truthful committed/superseded
   states and principal isolation. A delayed still-running original request must remain fenced;
   absent audit or equal current values alone must never authorize another Save. Add real UI lost
   rejection-response→reconcile→reload→safe deliberate correction coverage, plus preparation-fault
   and delayed-original cases. Use minimal evidence within this Task, not a new process-tooling project.

### Independent validation and limits

Evidence retained locally (not remotely accessible):
`.git/validation-evidence/57b180864b1862b07894ab444e1b00fe8b59d287/task43.4-b-rereview/`.
Contains complete Task/correction diffs, manifest, actual probe scripts/logs/results and wide/narrow/
blocked-recovery screenshots. `resident-probe.log` runs the unchanged previous observer script named
below against this corrected source, delegating to the real production Scheduler tick.

| Actual B command / path | Result |
|---|---|
| `python3 scripts/check_governance.py`; cumulative Task `git diff --check` | PASS / clean before review update; repeated for checkpoint. |
| `npm --prefix web run build` | PASS; pre-existing large-chunk warning. Browser served this fresh production build. |
| `node <current-evidence>/browser-probe.cjs` with existing `operations_inventory_harness.py --port4197` |11.538s; both P1s reproduced, stale-background Save protection and collective adoption pass; reload retains the exact unresolved submission. |
| `PYTHONPATH=. .venv/bin/python <current-evidence>/api-probe.py` | PASS as reproduction:503 preserves Active100, but both reconciles remain unresolved/validated;0.069s script time. |
| `.venv/bin/python -m unittest tests.test_automation_settings_management tests.test_automation_settings_resident` |43 tests,38.696s, OK; ResourceWarning for unclosed SQLite connections retained in raw log. |
| `PYTHONPATH=. .venv/bin/python .git/validation-evidence/b3dc11f/task43.4-b-review/resident_probe.py` |16.25s; actual Scheduler60s: one tick, live/adopted after expiry window, own report advanced. |

Test-collection observation: three existing `test_adoption_*`/resolution/override methods now sit
under helper `_FakeClock` rather than a unittest TestCase (`test_automation_settings_resident.py:790`).
They are not part of the43 discovered tests; do not count them as passed. Move them back into the
applicable existing TestCase during correction. This coverage observation is not a third independent
product blocker; the real process/other unit checks above still provide the stated limited evidence.

Total testing/reproduction/build/check time is conservatively below90s and below50% of this review
round; no padding waits. All probes use existing actual UI/API/CLI entry points and isolated temp
SQLite/fake-local fixtures; no invented product route, production media or private configuration.
The harness and probe processes were stopped after verification.

Workflow§6 permits early FIX REQUIRED for the proven P1s. Full Python/Web/default/native T4,
wheel/installed consumers, real supported49→50 database upgrade rehearsal and Docker lifecycle/
security acceptance remain **pending and B-owned**; they are not Developer implementation defects
and are not waived by the43 focused passes or Developer's reported suite results.

### Reassessment of every Slice outcome

| Outcome / surface | Current disposition |
|---|---|
| RO-1 inventory/statistics/settings composition | Prior43.3 inventory/records review retained; this settings composition now present, with independent wide/narrow evidence. Current whole-Slice regression pending. |
| RO-2 checked definition lifecycle | Existing delivered chain retained; this correction does not expand its contract. Current native/full acceptance pending. |
| RO-3 shared analysis/scoped unattended execution | Existing chain and accepted45 retirement boundary retained; current whole-Slice safety acceptance pending. |
| RO-4 deliberate Run once | Existing bounded analysis/confirmation/admission retained; current native/Worker acceptance pending. |
| RO-5 records/Task Center recovery | Prior43.3 read-only records and Task Center ownership retained; no new settings execution-recovery surface. Final regression pending. |
| RO-6 settings/real adoption | Publication/cadence/adoption/composition corrections evidenced; incomplete terminal unknown-failure recovery (R5). |
| RO-7 shared authority/failure/safety | Incomplete input preservation and terminal recovery (R2/R5); remaining final security/pin/compatibility gates pending. |

Slice43 remains ACTIVE, not READY FOR A REVIEW. Correct these two blockers in the same Task;
no next Task or Closure Packet is justified. Preserve original references/frozen branch, accepted45,
A-owned SLICE/Roadmap/Progress, pre-existing dirty artifacts and ignored private configuration.
This B checkpoint changes only `TASK.md`; no push or history rewrite.

## Developer Fix Report — second correction (R2 input preservation, R5 terminal recovery)

The historical Task43.4 report and both B checkpoints above are retained unchanged. This section
reports the corrections made in the same Task/Base/Goal/Scope.

```text
Status: READY FOR B REVIEW (Developer does not self-PASS)
Task Base: f18d2444f548b81b5892536498a1b4cdd4400be8
Candidate: the commit carrying this report (see `git log -1` for the exact SHA)
Scope: fix the two remaining P1 blockers (R2, R5) inside the same Task/Base/Goal/Scope
```

### Corrections delivered

1. **R2 — input accepted while a Save is outstanding is never silently lost.**
   The four inputs are now `disabled` while `submitting` (already true for an unresolved
   submission), so the field cannot accept a keystroke that no request could carry. For the
   remaining race — a value that still reaches state while the response is in flight — the panel
   keeps a live `editRef` mirror and compares it with the exact `submittedEdit` snapshot when the
   answer arrives: only the fields the operator actually changed after submitting are retained, and
   they are explicitly **re-based onto the just-published identity** (every other field takes the
   newly published value) instead of being cleared or silently attached to the replaced identity.
   The page then states that those values are not yet saved. The existing background-refetch/stale
   protection is unchanged.
2. **R5 — a settled non-publication becomes a terminal, correctable outcome.**
   `AutomationSettingsService` now records a bounded `automation_settings_outcome` durable audit for
   every terminal non-publication of an *identified* submission: a stale/out-of-scope refusal (which
   happens before any Draft exists and therefore had no revision evidence at all), a no-op Save, and
   persist/validate/prepare/activate faults. The record carries only the submission identity, the
   submitted four values, the ending stage/outcome, the published target it was written against and a
   bounded next action; it is mapped by the error's own code (not just its stage) so an out-of-scope
   candidate is not reported as a stale identity. Reconciliation walks the same submission trail but
   now over both `draft_edit` and outcome records, and resolves `not_committed` with a correctable
   `durableState`/`nextAction`. Truthfulness is one-directional: **any** positive publication
   evidence for the identity wins over a later outcome record, so a request that published can never
   be reported as unpublished. Evidence stays actor- and identity-scoped, `evidenceComplete`/
   `identityMatched` are preserved, and an absent record still stays `unresolved` — a
   still-in-flight original request remains fenced and equal current values alone never authorize a
   New Save. After a terminal reconcile the page clears the block, re-bases the retained typed input
   onto the current published identity and states that nothing was published by that request.
3. **Coverage observation (B re-review note).** The three `test_adoption_*`/override assertions that
   sat on the `_FakeClock` helper are now the discovered `ResidentLoopAdoptionUnitTests` TestCase, so
   they actually run.

### Affected commands and actual results

| Command (cwd) | Result |
|---|---|
| `python3 scripts/check_governance.py` | `governance check: PASS` |
| `.venv/bin/ruff format --check mediaflow tests scripts` | `354 files already formatted` |
| `.venv/bin/ruff check mediaflow tests scripts` | `All checks passed!` |
| `.venv/bin/python -m compileall -q mediaflow tests scripts` | exit 0 |
| `git diff --check` | clean |
| `.venv/bin/python -m unittest tests.test_automation_settings_management` | `Ran 34 tests ... OK` |
| `.venv/bin/python -m unittest tests.test_automation_settings_resident` | `Ran 21 tests ... OK` |
| `.venv/bin/python -m unittest tests.test_system_settings_management tests.test_resident_services tests.test_resident_correction tests.test_automation_admission tests.test_stale_job_visibility tests.test_configuration_snapshot tests.test_automation_api tests.test_task_persistence tests.test_v2_settings_rule_readiness` | `Ran 171 tests ... OK` |
| `.venv/bin/python -m unittest tests.test_automation_workspace_read_model tests.test_v2_automation_operations tests.test_v2_automation_lifecycle tests.test_automation_definition_publication tests.test_v2_automation_run_once tests.test_operations_run_detail_plan_evidence` | `Ran 161 tests ... OK` |
| `npm run typecheck` / `npx eslint` / `prettier --check` (cwd `web`) | all clean |
| `npx vitest run` (cwd `web`) | `Test Files 82 passed`, `Tests 1194 passed` |
| `npm run build` (cwd `web`) | succeeds (pre-existing chunk-size warning only) |
| `npx playwright test` default fake suite (cwd `web`) | `242 passed` |
| `npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-settings.python.spec.ts` | `9 passed` |

New/strengthened coverage for this correction:

- Python (`tests/test_automation_settings_management.py`):
  `test_lost_stale_rejection_reconciles_into_a_correctable_state` (the reviewed real race, repeated
  reconciliation including the reload-equivalent), `test_lost_runtime_prepare_failure_reconciles_and_preserves_active`
  (503/`prepare` then a terminal answer with Active 100 preserved),
  `test_lost_validation_rejection_reconciles_as_terminal`, `test_noop_submission_reconciles_as_no_publication_needed`,
  `test_terminal_outcome_is_principal_and_identity_scoped`,
  `test_unresolved_identity_is_not_certified_by_an_equal_concurrent_publish`,
  `test_delayed_original_completion_stays_fenced_until_its_own_evidence`,
  `test_equal_values_delayed_completion_is_recorded_as_no_publication`, and
  `test_publication_evidence_wins_over_a_later_terminal_record`.
- Web (`AutomationSettingsPage.test.tsx`): `refuses to accept input while a Save's response is
  outstanding` (real delayed 201, field read-only during the request, published value shown, no
  phantom input), `never silently clears an edit that raced a finishing Save`,
  `reconciles a lost rejection, survives a reload and allows a deliberate correction` (terminal
  reconcile, retained value, Save re-enabled, storage cleared, and the block still enforced after a
  genuine reload while unresolved).
- Real Python browser (`automation-settings.python.spec.ts`): `a lost rejection response reconciles
  into a correctable form, across a reload` — another writer publishes first, the form's own PUT is
  processed by the real API (409 observed server-side) but its response is aborted, the page and a
  reload keep the unresolved context and the disabled Save, reconciliation proves non-publication,
  the typed value survives and the published Active is untouched.

No test was skipped, retried or weakened and no timeout was raised. The one previously
mis-located helper class now hosts real discovered cases, so this round strictly adds collected
coverage. The settings `python` spec remains excluded from default fake collection by the existing
`testIgnore` convention.

### Remaining risks / disclosures for B

1. **B-owned gates still not run here:** full Python discovery, wheel/installed consumer, the
   supported 49→50 upgrade rehearsal on a real prior database with existing work/pins, Docker
   lifecycle/security smokes and the remaining native/T4 matrix.
2. **Outcome records are additive audit rows**, not a schema change: they use the existing
   `configuration_change_audits` ledger with a new bounded `action`, so no migration is involved and
   existing rows/pins are untouched. B should confirm that accepting a new `action` value in that
   ledger matches the intended contract.
3. **`superseded` semantics** (carried over): a submission that published and was later replaced
   reports `committed: true` with `state: superseded`.
4. **Deliberate limits unchanged:** no queue/supervisor replacement, no new concurrency control, no
   auto-restart, no automatic stale/uncertain replay, no extra settings beyond the four fields.
5. **Test cost:** the two focused modules take roughly 40s together (resident subprocess cases
   dominate). This round's executed testing/reproduction stayed well under the 30% budget; no sleeps
   were added to pad elapsed time.
