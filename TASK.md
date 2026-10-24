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
Decision: FIX REQUIRED — A43-01 independently reproduced by B
Next Action: DEVELOPER CORRECTS CURRENT CONSUMER MEMBERSHIP IN THIS SAME TASK
```

## Goal

An operator opens `自动化 → 全局设置`, changes the four engine settings, clicks one Save, and
sees the exact published values separately from the values actually adopted by each relevant
running consumer. Worker/Scheduler adopt eligible polling changes without restart or work arrival.
System Settings reaches the same form, publication authority and consumption readback.

The original Task ID/Base/Goal/Scope remain unchanged. This is the A-return correction inside43.4,
not a new feature Task or a repinned baseline. Original implementation plan, accepted checkpoint
and B packet remain at `b1098329115dd53625ff08c4b616ecc80da89c1d:TASK.md`; A's return is committed
at `00096fb2996776ed386a09904ecb0005a9105c6d:SLICE.md`. Prior PASS/evidence and its disclosed timing
nonconformance remain historical facts; they do not override A43-01 or certify the correction.

Complete Slice **RO-6**, settings contributions to **RO-1/RO-7**, **AC-1/9/10/11** and material
settings/resident/restart contributions to **AC-12**. Traceability: V2-AUTO-001/007/008,
V2-RUNTIME-001/002, UX-001/002/004/007/008/009/010 and REQ-CONFIG-005..012.
Read the complete [Automation journey](docs/product-experience.md#target--complete-native-automation-workspace-active-slice43),
[Automation CURRENT/TARGET contract](docs/architecture.md#automation-and-unattended-execution)
and the committed Slice, particularly RO-6 and A43-01.

## Current checkpoint and actual-code gap

Planning checkpoint: main at `00096fb2996776ed386a09904ecb0005a9105c6d`; submitted executable
candidate remains `20baaeaae52b5b4eee9a162a2679ce51b1d93311`. B inspected the cumulative Task
Base..HEAD manifest and relevant registration → application → domain → API → Web readback chain,
and independently reran A's existing real resident restart reproduction. This is an early blocker
review under workflow §6, not a fresh passing full regression or A Final Review.

| Existing code / entry | Required correction |
|---|---|
| `AutomationSettingsService._resident_state/_consumer_projections` in `mediaflow/application/automation_settings.py` | Reads all historical registrations, then sends all of them to current adoption aggregation. Define current membership from authoritative per-instance liveness, independently of whether that instance reports desirable settings. |
| `evaluate_consumer_adoption` in `mediaflow/domain/automation_settings.py` | Currently requires every historical instance to be adopted. Separate the current service claim from retained stopped/stale history, while requiring all actual current instances to satisfy existing adoption checks. |
| `SQLiteTaskRepository.list_resident_services/stop_resident_service` | Existing lifecycle intentionally retains old identities. Reuse this authority; no deletion, overwrite or schema change is needed merely to repair aggregation. |
| Existing `GET /api/v1/operations/automation/settings`, `automation-settings.ts`, `AutomationSettingsPanel.tsx` | Web normalizer currently independently checks every `instances` row. Keep its conservative validation aligned with the corrected API population, counts, diagnostics and recovery guidance. Fixing only the backend boolean is insufficient. |
| `tests/test_automation_settings_resident.py`, real settings Playwright spec and harness | Existing real processes and managed publication are reusable. Add restart-to-readback assertions through these supported entries, not new process-control products or probe routes. |

## Implementation Scope

The full original four-field publication/adoption behavior remains protected; this round changes
only the A43-01 correction below and directly necessary tests/documentation. No queue, cadence,
publication or mutation redesign is authorized.

1. **Define one current-population rule in the shared read model.** Use the existing registration
   lifecycle and heartbeat freshness at the read timestamp. Every fresh live Worker/Scheduler
   instance is current, including overridden, unreported or schema-incompatible instances; never
   select the latest registration only, one successful report, matching revision/value only, or
   the newest bounded evidence page. A stopped predecessor is not a current consumer. Stale
   registrations remain visible as unverified/stale diagnostics, not proof of a live adopter;
   a later fresh heartbeat must make that same instance subject to current checks again. Preserve
   all registration/report rows and existing freshness thresholds. A healthy replacement may
   complete current adoption despite predecessor history; do not claim all historical processes
   or an unknowable configured replica count are healthy.
2. **Align aggregation, history and fail-closed states.** Current adoption requires a nonempty
   current population per required service and every current instance's own fresh report for the
   exact publication/value, compatible schema and no CLI/deployment override. A fresh heartbeat
   alone is insufficient; an old-value report remains pending. Missing services, stopped-only or
   stale-only populations, unreadable registration/evidence and unavailable Active must not produce
   collective success. Retain bounded diagnostic visibility of historical stopped/stale identities
   through the existing read surfaces without treating old adopted values as current consumption.
   Keep current counts distinct from history counts; avoid adding a new persistence lifecycle,
   history browser, retention policy or deployment supervisor. API-local capacity/stale evidence
   remains separate from the two cadence consumers.
3. **Complete the Web journey over that same contract.** Both Automation and System Settings must
   show published target, each current consumer's actual adoption and the truthful aggregate.
   Historical diagnostics must be labelled separately; do not instruct the operator to start an
   obsolete process when its replacement is healthy. If no current service exists, explain that
   no current adoption is proved and guide restoring/checking that service; stale evidence calls
   for checking process/database/heartbeat, not automatic replay. Preserve a real live override,
   mixed version and pending report's specific next action. Align the typed normalizer, fixtures
   and conservative contradictory-response checks; do not blindly trust `allAdopted=true`, silently
   drop a problematic live instance or weaken existing malformed-response handling.
4. **Add regression coverage from supported entries.** Extend existing process/API/Web fixtures for
   fresh startup → graceful stop → replacement → later checked publication; cover both resident
   roles, simultaneous live instances, override, publication mismatch, absent/stopped/stale-only
   and read failures. Keep history available across SQLite reopen and assert zero new work/media
   effects. Use controlled clocks/fakes for exact freshness/read-failure boundaries, with real CLI
   processes proving the ordinary restart path. Update only affected CURRENT contract details
   about membership/readback if necessary; do not reconcile Slice closure or add process tools.

## Acceptance Criteria

- [ ] Worker and Scheduler started through existing commands adopt the initial publication; normal
  graceful restart of either role leaves its old stopped identity durable, while the fresh
  replacement can restore current service and collective adoption without an operator workaround.
- [ ] A later four-field checked Save targets the new exact publication; current instances must
  actually adopt it before success. Retained predecessor evidence cannot either veto or certify it.
- [ ] Every fresh live instance counts, including simultaneous same-service replicas. One healthy
  instance cannot hide another's pending/old report, override, missing report or incompatible schema.
- [ ] No-live, stopped-only, stale-only, unavailable Active and unreadable evidence remain visibly
  pending/unavailable with actionable recovery. Freshness is not extended, stale evidence is not
  silently promoted, and reappearing fresh instances rejoin current checks.
- [ ] Web/API agree on current membership, counts and adopted status; history is diagnostic and
  preserves its stopped/stale facts without impossible "start the old instance" recovery. Both
  existing settings entrances and refresh/reopen retain the truthful state.
- [ ] Reads/history/reconciliation create no Draft/Job/Task/grant or Provider/Storage/media effect.
  Existing Save/RBAC/concurrency/audit/override/pins/heartbeat/fencing and completed/uncertain
  non-replay behavior remain intact. Accepted45 retirement remains absent.

## Required Tests

Follow [test ownership and levels](docs/development-workflow.md#6-test-levels). Keep testing time
strictly below50% of each role's round; include failed attempts, do not pad elapsed time with waits.
Use isolated temporary state and controlled Providers; never read user databases/media/private config.

### Developer — affected tests

Start by converting the ordinary restart reproduction into a requirement assertion (replacement
restores current adoption), then implement. Reuse `ResidentAdoptionFixture` and real WSGI settings
entry; no fabricated report may stand in for the real restart acceptance. Planned additions belong
in these existing files unless an equivalent cohesive placement is reported:

```bash
python3 scripts/check_governance.py
.venv/bin/python -m unittest tests.test_automation_settings_management tests.test_automation_settings_resident
.venv/bin/python -m unittest tests.test_resident_services tests.test_resident_correction tests.test_system_settings_management
npm --prefix web run test -- run src/features/operations/AutomationSettingsPage.test.tsx src/features/configuration/ConfigurationPage.test.tsx src/features/operations/AutomationRouter.test.tsx
npm --prefix web run typecheck
npm --prefix web run build
# cwd web; production assets, existing isolated real-Python harness
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-settings.python.spec.ts
```

Cover the acceptance matrix in domain/API/normalizer/component tests as appropriate: no-live,
stopped+healthy replacement, stale-only/stale+healthy, two actual live replicas with one override,
live old-publication/unreported/incompatible evidence, read failures and freshness transitions.
Include malformed/contradictory API normalization and bounded history display. Real-process
fixtures must identify the replacement's new registration, not accidentally wait on the predecessor;
ensure independent process/log cleanup. A tiny extension of the existing harness is allowed only
if required for browser proof and invokes actual CLI/application behavior; do not build a generic
restart API. Use API/repository assertions to check no work and retained rows across reopen.

Run Ruff format/lint, compile, ESLint/Prettier on actual changed files plus every new/changed test.
If shared persistence or publication/runtime behavior changes beyond projection, add its directly
affected migration/failure-atomicity/pin tests and report why. No full Python/Web/default E2E,
Docker or release matrix is assigned to Developer; hand off after affected checks.

### B — acceptance and full regression

Review the complete immutable Task Base..corrected candidate, independently repeat normal CLI
restart → existing settings API/Web readback, later publication, real simultaneous live override
and missing service; inspect actual desktop/narrow current/history/recovery presentation. Reassess
**all RO-1..RO-7 and Required Surfaces**, preserving original Slice Base and accepted44/45 boundaries.
A proven remaining blocker permits early FIX REQUIRED before expensive gates.

Before PASS run the [shared T4 gates](docs/development-workflow.md#shared-full-regression-commands).
B retains full regression, real production-asset journeys, wheel/installed consumer and applicable
Docker/restart/security acceptance, as assigned in the original Task packet. In addition to the
settings command above, run existing native integration suites sequentially with isolated outputs:

```bash
# cwd web, after production build; separate harness per invocation
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-workspace.python.spec.ts
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-lifecycle.python.spec.ts
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-run-once.python.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
npm run test:e2e -- --config=playwright.python.unicode-principal.config.ts tests/e2e/operations-principal-identity.python.spec.ts
# repository root, exact corrected candidate image and isolated temporary state
.venv/bin/python scripts/docker_empty_baseline_smoke_test.py --image mediaflow:slice43-candidate
.venv/bin/python scripts/docker_restart_fault_smoke_test.py --image mediaflow:slice43-candidate
.venv/bin/python scripts/docker_release_security_smoke_test.py --image mediaflow:slice43-candidate
```

Record exact source/artifact/image identity, commands, counts/skips/failures, raw logs/screenshots
and test intervals in stable ignored evidence. Prior43.4 executable-input gates do not certify this
changed candidate; reuse only explicitly matching evidence under workflow §6. Required unavailable
acceptance stays pending with B, never transferred to Developer or relabelled PASS. Full runs that
cover focused cases need no duplicate focused runs. Once complete, refresh one compact Closure
Packet and stop planning; A independently reviews original Slice Base..corrected Head.

## Non-goals

New engine fields, schedules/definitions/metrics/records redesign; queue/supervisor/replica management;
auto-restart; registration deletion/retention product; generalized diagnostics tooling; new authority,
Storage/Provider/mutation/recovery behavior; automatic uncertain replay; restoring retired Scan,
standalone Preview or FileIndex; Slice/Roadmap boundaries or closure; next feature Task; push.

## Developer Completion Report

```text
Task: 43.4 / A43-01 correction (no new Task, no scope change)
Checkpoint: 20baaea..HEAD of this commit (source identity below)
Decision: READY FOR B REVIEW — not self-PASSED, not CLOSED
Base reviewed by B: f18d2444f548b81b5892536498a1b4cdd4400be8 (unchanged)
Test Level: T4 (B retains full regression); Developer ran affected checks only
```

### Behaviour delivered (A43-01)

One current-population rule now governs the shared read model, replacing the
historical "every registration must be adopted" aggregate:

- **Current membership is derived at read time** from the existing registration
  lifecycle + heartbeat freshness (`evaluate_resident_service_status`). Every
  fresh live Worker/Scheduler instance is a current consumer and must satisfy the
  existing per-instance checks (own fresh report, exact publication digest/value,
  compatible runtime schema, no CLI/deployment override). One healthy replica
  cannot hide another's pending/old/unreported/override/incompatible state; the
  latest registration, a single success, matching values and the newest evidence
  page are never used as membership.
- **Retained history is diagnostic only.** `stopped` / expired-heartbeat
  registrations stay durable and are projected as bounded `history` with the real
  `historyCount`, so a truncated list can never look complete. History can neither
  veto nor certify adoption, and its recovery text never tells the operator to
  start an obsolete process. No registration/report row is deleted, overwritten,
  or schema-changed; freshness thresholds are unchanged, and a later fresh
  heartbeat makes that same instance subject to the current checks again.
- **Fail-closed reads.** An unreadable registration read or unreadable adoption
  evidence for a service is reported as `consumer_registration_unreadable` /
  `consumer_evidence_unreadable` with a next action, never flattened to an empty
  (apparently healthy) population. Absent, stopped-only and stale-only
  populations report `no_consumer_registered` / `no_current_consumer` and never
  collective success. No-live/stale thresholds are not extended.
- **Web/API agree.** The typed normalizer adds `historyCount`/`history`/
  `durableState`/`nextAction`, keeps the conservative contradictory-response
  guard, and additionally refuses a claim whose `instanceCount` disagrees with its
  rows or that mixes a live row into history. The panel shows current instances
  separately from a folded "历史注册" diagnostic section, distinguishes "no live
  instance" (with heartbeat/database guidance) from "never registered" (start it),
  and surfaces the aggregate's own next action/durable state. Both entrances
  (Automation tab and System Settings) use this same component.
- Verified unchanged: Save/RBAC/concurrency/audit/override/pins/heartbeat/fencing,
  completed/uncertain non-replay, Accepted45 retirements, zero Draft/Job/Task/
  grant/Provider/Storage effect from reads or restarts.

### Files

```text
mediaflow/domain/automation_settings.py             current population + history + read-failure answer
mediaflow/application/automation_settings.py        resident read state, evidence read failures, API shape
scripts/operations_inventory_harness.py             + POST /__harness__/restart-resident-consumer (production
                                                    stop/register path only; harness infra, not a product route)
web/src/entities/operations/automation-settings.ts  history/durableState/nextAction + contradiction guards
web/src/features/operations/AutomationSettingsPanel.tsx  current vs history presentation + recovery copy
docs/architecture.md                                CURRENT contract: membership/readback/history rule
tests/test_automation_settings_resident.py          real restart/replica/override/later-publication proofs
tests/test_automation_settings_management.py        pure decision matrix + real WSGI read matrix
web/src/entities/operations/automation-settings.test.ts       normalizer matrix (new file)
web/src/features/operations/AutomationSettingsPage.test.tsx   current/history/contradiction/no-live UI
web/tests/e2e/automation-settings.python.spec.ts     real-Python restart → readback journey
```

### Actual commands and results (this round)

```bash
python3 scripts/check_governance.py                              # PASS at entry
.venv/bin/python -m unittest tests.test_automation_settings_management \
    tests.test_automation_settings_resident tests.test_resident_services \
    tests.test_resident_correction tests.test_system_settings_management
    # Ran 133 tests, OK (56.5s) — includes the 4 new real-process A43-01 cases
.venv/bin/python -m unittest <new A43-01 cases> # RED on pre-correction domain/application (verified by
    # temporarily restoring only those two files): real restart aggregate stayed 1/2 and
    # the stopped predecessor still vetoed; GREEN after the fix.
npm --prefix web run test -- run src/features/operations/AutomationSettingsPage.test.tsx \
    src/features/configuration/ConfigurationPage.test.tsx \
    src/features/operations/AutomationRouter.test.tsx \
    src/entities/operations/automation-settings.test.ts        # 4 files / 65 tests passed
npm --prefix web run test -- run src/features/operations/  # 21 files / 237 tests passed
npm --prefix web run test -- run src/features/configuration/  # 1 file / 21 tests passed
npm --prefix web run typecheck                                  # clean (app + node configs)
npm --prefix web run build                                      # production assets built
# cwd web, production assets, isolated real-Python harness:
npm run test:e2e -- --config=playwright.python.automation.config.ts \
    tests/e2e/automation-settings.python.spec.ts                # 12 passed (11.6s)
.venv/bin/python -m ruff format --check / check <changed py + harness>   # clean
.venv/bin/python -m compileall <changed py>                     # OK
npx prettier --check / eslint <changed ts/tsx>                   # clean
```

Evidence: `.git/validation-evidence/dev-43.4-a43-01/` (base head, entry status,
python-affected.log, web-unit.log, e2e-settings.log).

### Remaining risks / not done by Developer

- B owns full T4 regression, production-asset journeys, wheel/installed consumer,
  Docker empty-baseline/restart-fault/release-security and independent desktop +
  narrow visual review; none of those are claimed here.
- The harness restart route is test infrastructure around the real
  `ResidentLoop` stop/`register_resident_process` path (as the existing
  start-consumers route already was); it is not a product endpoint and must be
  reviewed as such. Real CLI `worker/scheduler run` restart is covered by the
  Python real-process cases, not by the browser spec.
- History is bounded to `MAX_CONSUMER_HISTORY_ENTRIES` (20) per service with the
  real total in `historyCount`; a deployment with very many historical identities
  sees a truncated diagnostic list by design (no new history browser/retention
  product was added, per non-goals).

## B Review Result

```text
Reviewed: f18d2444f548b81b5892536498a1b4cdd4400be8..00096fb2996776ed386a09904ecb0005a9105c6d
Decision: FIX REQUIRED — A43-01 confirmed by independent existing-entry reproduction
Acceptance runs: real worker run / scheduler run + existing settings GET; reproduced in 1.103s
Task blockers: current membership/aggregate/Web recovery correction above
Slice Required Outcomes / Surfaces all satisfied: NO — RO-6 incomplete
Next: SAME TASK FIX LOOP
```

Reproduction: fresh live Worker+Scheduler adopted2/2; graceful Scheduler replacement left both live
instances adopted but aggregate1/2 because its historical stopped predecessor still vetoes success;
zero Jobs. Local durable evidence:
`.git/validation-evidence/00096fb2996776ed386a09904ecb0005a9105c6d/b-a43-01-planning/`.
This proves the failure, not passing product acceptance. No full gates rerun on this rejected input.
RO-1..5/7 retain A's current no-additional-blocker assessment and historical B evidence, subject to
corrected-candidate reassessment; no new blanket PASS or Slice closure is asserted.

Workspace at entry: main/`00096fb…`, repository and Git writable; only tracked dirty file was the
pre-existing `docs/pics/操作与任务.png` deletion. All existing untracked logs, `.DS_Store` files,
reference images, archive, `15`, browser results and ignored/private config are preserved/unstaged.
Initial exact status is retained in the evidence directory. B changes only this Task document.
Entry governance failed solely because A's committed FIX REQUIRED handoff had no active Task;
this correction plan restores that required state without changing the guard or A-owned Contract.
