# Task 43.1 — Native Automation Definition Lifecycle and Focused Publication

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 43.1
Parent Slice: 43
Status: READY FOR B REVIEW
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

The committed Slice 43 and Roadmap are ACTIVE; governance passes. At Task Base, `TASK.md` contains
`NO ACTIVE IMPLEMENTATION TASK`. There is no Developer checkpoint to review.

The actual implementation has these gaps and reusable boundaries:

- `AutomationTaskDefinitionService` wraps revision-bound Draft operations. `AutomationNewPage`,
  `AutomationEditorPage` and definition actions still require an open successor Draft, save,
  validation and activation as separate ordinary user steps.
- `MediaFlowApi._automation_definition_activate_checked_draft` already confines activation to one
  definition, fences exact Draft/Active identities and starts no work. Preserve those guarantees,
  composing ordinary publication in the shared application layer.
- Existing managed normalization owns modes, ResourceLibrary references, relative scope, item bounds
  and interval/Cron validation. Rules/library focused publication, applicable checks, Preview/grant,
  occurrence and Worker services are reusable authority, not reasons to create another store.
- Removal needs live grant revocation and usable retained history, not only configuration deletion.

This is one independently acceptable definition-management boundary across application, persistence,
API and Web. Manual Run once, consolidated reporting and settings adoption remain coherent further
in-Slice work. Initial sizing is compatible with roughly 3–7 major Tasks; only this Task is planned,
and B reevaluates all Required Outcomes after PASS rather than predefining a field/endpoint ladder.

Planning baseline (not Developer implementation evidence):

```text
Branch: main
HEAD: 79544d9aba697036405b06054c0c56a740281bab
python3 scripts/check_governance.py: PASS
.venv/bin/python -m unittest tests.test_automation_task_definition tests.test_v2_automation_operations tests.test_cron_scheduler
Result: 40 tests, OK, no skips (38.473s)
```

The baseline emitted an unclosed SQLite `ResourceWarning`, not a test failure; unrelated cleanup
is not authorized. Bare `python` is absent; use `.venv/bin/python` for project tests/tools.

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
may change. Preserve all three pre-existing untracked PNGs in `docs/pics/`; do not stage/edit/recompress
them. Both Automation checksums match the Slice at planning. `config/alist.json` is ignored/untracked
and must remain unstaged; never use private configuration/credentials to obtain evidence.

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

Commands run from repository root. Add focused application/API suites
`tests/test_automation_definition_publication.py` and `tests/test_v2_automation_lifecycle.py`, native
form/action tests, and `web/tests/e2e/automation-lifecycle.python.spec.ts`. Reuse/extend the isolated
Python harness; explicitly separate real-Python specs from Node-fake selection. These are coverage
locations, not new product abstractions. Update changed presentation expectations without losing
existing compatibility/safety assertions.

### Focused and related integration

```bash
.venv/bin/python scripts/check_governance.py
.venv/bin/python -m unittest tests.test_automation_definition_publication tests.test_v2_automation_lifecycle
.venv/bin/python -m unittest tests.test_automation_task_definition tests.test_v2_automation_operations tests.test_configuration_successor_draft tests.test_configuration_management tests.test_configuration_destination_activation tests.test_v2_rules_workspace_commands tests.test_system_settings_management
.venv/bin/python -m unittest tests.test_cron_scheduler tests.test_automation_definition_occurrence tests.test_automation_task_definition_preview tests.test_automation_preview_grant_gate tests.test_automation_unattended_grant tests.test_automation_definition_execution tests.test_automation_authorized_execution_matrix tests.test_automation_admission tests.test_automation_job_fencing
npm --prefix web run test -- run src/entities/operations/automation.test.ts src/features/operations/AutomationRouter.test.tsx
```

Also run every added/affected Web form/query/transport test. Required scenarios: all lifecycle actions;
stale/concurrent publication and unrelated Draft/sibling preservation; scope/schedule numeric/finite/
boundary/dependency errors; management/activation/revoke permission separation and Viewer denial;
applicable check/persistence/runtime failures; commit-then-response/read failure and duplicate clicks;
Draft-only recovery; empty/no/corrupt Active; retained history after reopen; Scheduler evaluation around
disable/remove; an actual admitted old Job and revocation before the next mutation; fresh grant
binding after relevant edits; zero side effects on reads. Use supported production assemblies, with
fakes/local services at external ports, not test doubles that remove current production capabilities.

### Full regression and quality/safety — T4

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
npm --prefix web run test:e2e -- --config=playwright.python.config.ts tests/e2e/automation-lifecycle.python.spec.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/operations-principal-identity.python.spec.ts
.venv/bin/python scripts/check_governance.py
git diff --check
sha256sum docs/pics/自动化.png docs/pics/自动化-全局设置.png
```

Real-Python browser evidence drives typed create → Save → actual Active readback, edit/copy/toggle,
stale/denied/unknown recovery, removal and retained history. Also drive exact Preview → explicit grant
→ real Scheduler emission/Worker outcome on temporary Local Storage and a synthetic/local Provider;
assert Save/reads do not emit that work, and explicitly invoke Scheduler/Worker. Node fixtures alone
cannot replace production application/persistence integration evidence.

Audit exact `Task Base..Head` manifest and unstaged/staged changes for frozen/unrelated/private files
and credentials; confirm `config/alist.json` remains ignored/untracked/unstaged.
`rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml` must find no runtime/dependency reference (exit 1
with no matches is the expected clean result).

If schema changes are necessary, additionally run
`.venv/bin/python -m unittest tests.test_migration_rehearsal tests.test_upgrade_preflight` and a
documented additive **Task Base schema44 → implemented schema** rehearsal preserving historical
rows/pins/grants/audits; old-schema fixtures alone do not prove that upgrade. Otherwise record schema
unchanged. Wheel/static-serving and Compose lifecycle checks remain Slice-final gates unless this
Task changes their packaging/deployment/resident boundary, in which case include the affected gate
and record exact commands/results. Production media/credentials/external-service validation is not
authorized. Honest unavailable gates are reported for B to assess, not silently skipped or called PASS.

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

Added:

- `mediaflow/application/automation_workspace_commands.py` — focused Automation definition
  publication/lifecycle application service (save/enable/disable/copy/remove, form authority, edit and
  copy candidates, removal evidence, zero-mutation schedule preview, historical projection).
- `tests/test_automation_definition_publication.py` — 20 application-level regressions.
- `tests/test_v2_automation_lifecycle.py` — 12 real-API integration regressions.
- `web/src/entities/operations/automation-lifecycle.ts` (+ `.test.ts`) — fail-closed bounded models
  for the lifecycle documents.
- `web/src/features/operations/AutomationLifecyclePage.tsx` (+ `.test.tsx`) — native typed form,
  lifecycle actions and confirmed removal.
- `web/tests/e2e/automation-lifecycle.python.spec.ts` — real-Python browser proof (4 tests).
- `web/playwright.python.automation.config.ts` — isolated harness instance for that spec.

Modified:

- `mediaflow/domain/configuration_management.py` — added `AutomationDefinitionSaveError` (bounded
  definition/stage/authority-state details).
- `mediaflow/application/configuration_objects.py` — `mutate(..., allow_automation_definition_delete=)`
  gate so only the focused workspace removal may delete a definition.
- `mediaflow/interfaces/service_api.py` — service wiring, `/api/v1/operations/automation/definitions`
  routes, publication readback and the error mapping.
- `scripts/operations_inventory_harness.py` — additive control routes (`automation-lifecycle-state`,
  `seed-automation-definition-grant`, `reset-automation-definitions`).
- `web/src/shared/api/api-client.ts`, `web/src/routes/router.tsx`,
  `web/src/shared/navigation/destination-model.ts` (+ test), `web/src/features/operations/AutomationListPage.tsx`
  — typed client, routes, deep-link continuation and entry links.
- `web/playwright.config.ts` — exclude the new real-Python spec from the Node-fake path.
- `TASK.md` — Developer report and the repo-mandated release-quality gate line (see Risks).

### Implemented

- **One checked Save per intended change (AC-T1/T2):** `save_object` composes a fresh successor from
  the exact observed Active, normalizes and validates the whole document through the existing managed
  authority, and publishes through checked atomic activation. A defensive confinement proof refuses a
  successor that changes any other section or sibling definition.
- **Typed surface (AC-T3):** `GET /definitions` (form authority), `GET /definitions/{id}` (edit
  prefill), `GET /definitions/{id}/copy-candidate`, `POST /definitions/schedule-preview`. The form owns
  name/identity, ResourceLibrary, relative scope, three modes, item bound, enabled state and exactly
  one interval or Cron/IANA-timezone schedule; switching forms clears the other. Unsafe/absolute/
  traversal scopes, out-of-bound/non-finite values, invalid Cron/timezone and missing/disabled
  references fail before publication with zero Active change.
- **Independent states (AC-T4):** create and copy always publish disabled; a create/copy candidate
  that submits `enabled: true` is refused. Enable/disable publishes only enabled state; enabling starts
  no scan/Job/Task/occurrence/grant and disabling neither cancels admitted work nor revokes a grant.
- **Safe removal (AC-T5):** `DELETE /definitions/{id}` resolves references, then **durably revokes
  applicable future unattended authority before** publishing the removal successor, so no window exists
  in which the definition is gone while its scheduled mutation authority is live. Grants, audits,
  occurrences, Jobs/Tasks/Results and pins are retained. A revocation that precedes a failed
  publication is fail-closed, leaves the Active definition in place and reports `authorityState`
  truthfully. Recreating or copying an ID does not revive a removed grant.
- **Recovery/compatibility (AC-T6):** stale Active intent raises `ConfigurationVersionConflict`
  (409) with refresh guidance; `GET /definitions/{id}` and the removal/copy projections also resolve
  Draft-only candidates; `historical_definition` keeps removed-definition history readable from
  non-Active revisions. V1 `/api/v1/automation/*` and `/api/v1/operations/automation/task-definitions`
  reads are unchanged (asserted).
- **Permissions (AC-T7):** writes require `MANAGE_CONFIGURATION` + `ACTIVATE_CONFIGURATION`; reads
  require `READ`. Viewer and manage-without-activate principals are denied (asserted).
- **Zero mutation:** reads and schedule preview create no Draft, Job, Task, occurrence, Provider call
  or Storage call (asserted with a RecordingStorage fake and revision/job counts).

### Tests and Results

- PASS — `.venv/bin/python scripts/check_governance.py` (PASS).
- PASS — `.venv/bin/python -m unittest tests.test_automation_definition_publication tests.test_v2_automation_lifecycle` — 32 tests.
- PASS — `.venv/bin/python -m unittest tests.test_automation_task_definition tests.test_v2_automation_operations tests.test_configuration_successor_draft tests.test_configuration_management tests.test_configuration_destination_activation tests.test_v2_rules_workspace_commands tests.test_system_settings_management` — 124 tests.
- PASS — `.venv/bin/python -m unittest tests.test_cron_scheduler tests.test_automation_definition_occurrence tests.test_automation_task_definition_preview tests.test_automation_preview_grant_gate tests.test_automation_unattended_grant tests.test_automation_definition_execution tests.test_automation_authorized_execution_matrix tests.test_automation_admission tests.test_automation_job_fencing` — 117 tests.
- PASS — `.venv/bin/python -m unittest discover -s tests` — 2,216 tests, 7 skipped, 0 failures. All 7 skips are the pre-existing real OpenList/S3/SMB/Local-endurance external-service gates.
- PASS — `.venv/bin/ruff format --check .`; `.venv/bin/ruff check .`.
- PASS — `.venv/bin/python -m compileall -q mediaflow tests scripts`; `.venv/bin/python -m pip check`.
- PASS — `.venv/bin/mediaflow --config config/strategy.example.json config validate` and `--config config/mediaflow.phase13.2.example.json config validate`.
- PASS — `npm --prefix web run test -- run` — 67 files / 1,021 tests.
- PASS — `npm --prefix web run typecheck`; `npm --prefix web run lint`; `npm --prefix web run format:check`; `npm --prefix web run build`.
- PASS — `npm --prefix web run test:e2e` — 203 Node-fake tests.
- PASS — `npm --prefix web run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts` — 21/21.
- PASS — `npm --prefix web run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-lifecycle.python.spec.ts` — 4/4 (real Python/API/SQLite/browser: create→Save→durable Active readback across restart, zero-side-effect preview, edit/enable/copy/removal, live-authority revocation with retained audit).
- PASS — `npm --prefix web run test:e2e -- --config=playwright.python.unicode-principal.config.ts tests/e2e/operations-principal-identity.python.spec.ts` — 1/1.
- UNAVAILABLE — `.venv/bin/python scripts/docker_release_security_smoke_test.py`: the Docker daemon in this environment cannot see harness bind sources (`invalid mount config ... bind source path does not exist`), so the isolated four-service stack cannot start. The image build, image inspection and Compose rendering stages completed. Not a code failure and not called PASS.
- PASS — `git diff --check`; `git check-ignore config/alist.json` (ignored) and `git ls-files config/alist.json` (empty).
- PASS — no `ffprobe`/`ffmpeg` reference under `mediaflow/` (grep tool; `rg` is not installed in this environment).
- PASS — `sha256sum docs/pics/自动化.png docs/pics/自动化-全局设置.png` match SLICE.md exactly.
- Schema unchanged: no migration rehearsal required.

### Decisions

- **New application service, not a second store.** `AutomationWorkspaceCommandService` composes the
  existing `ConfigurationObjectService`/`ManagedConfigurationService` normalization, validation, audit,
  optimistic concurrency and checked activation; it adds only focused composition and the lifecycle
  commands. It reuses the established `RulesWorkspaceCommandService` pattern.
- **Confinement proof over re-running page-local evidence.** As with the existing
  `_automation_definition_activate_checked_draft`, publication is safe because the successor is
  composed from the exact observed Active and every other section and sibling definition is proven
  byte-identical; that is what makes the previously reviewed Storage/strategy/destination semantics
  carry over unchanged. No Storage/strategy/destination evidence gate is re-invented or bypassed.
- **Revoke-before-publish for removal.** The two stores are separate SQLite databases, so a single
  cross-store transaction is impossible. The chosen order (durable revocation, then publication) is
  fail-closed: a failure after revocation leaves the definition Active with no live authority and
  reports that truthfully, which is strictly safer than the reverse order (definition gone, authority
  live). Grants and audits are never deleted.
- **Create/copy always publish disabled.** This makes "published" and "authorized/enabled" independent
  by construction and prevents a new or copied definition from inheriting schedule authority; the
  operator enables it as a separate explicit command.
- **Explicit route intent over body inference.** `PUT`/`POST .../copy` carry the definition identity in
  the path, and the body ID must match (or be absent); this prevents one filled-in form from silently
  changing identity or overwriting an unrelated row.
- **Isolated Playwright config for the real-Python lifecycle spec.** The journey legitimately advances
  the authoritative Active revision, which by design invalidates the build-time snapshot pins other
  journeys seed once. Sharing the harness would couple unrelated journeys to this spec's ordering, so
  the spec owns `playwright.python.automation.config.ts` on its own port, mirroring the existing
  `playwright.python.unicode-principal.config.ts` precedent. `web/playwright.config.ts` now excludes it
  from the Node-fake path, like the other real-Python specs.
- **Form authority includes the Active revision digest.** It is the immutable optimistic fence the next
  command submits back and is an identity, not secret evidence; the equivalent rules-workspace surface
  already exposes it. No definition/source fingerprint or raw plan is projected.

### Remaining In-Slice Work

Known, not part of this Task: definition-bound Run once/manual-origin admission, consolidated
metrics/reporting and full server inventory/search/paging/reference tabs, and global settings plus
resident adoption. `AutomationTaskDefinitionService`, the Draft-based `AutomationNewPage`/
`AutomationEditorPage` routes and the existing `/activate-draft` path are intentionally left in place
and working; this Task adds the native focused surface alongside them rather than removing them.

### Risks / Deviations

- **TASK.md release-quality gate line (repo-policy repair, not a scope change).** Full regression failed
  `tests.test_release_security.ReleaseSecurityPolicyTests.test_release_quality_gate_commands_are_documented_for_task_execution`
  because B's `TASK.md` did not document `scripts/docker_release_security_smoke_test.py`, which the
  repository requires for every active Task. I added exactly that one line to the existing T4 gate block;
  no Acceptance Criterion, scope, Task Base or Contract wording was changed. `tests.test_release_security`
  now passes (6 tests).
- UNAVAILABLE — the Docker release-security smoke gate (see Tests). Reported honestly for B to assess.
- The 7 full-regression skips are pre-existing external-service gates (real OpenList/S3/SMB/Local
  endurance), unrelated to this Task.
- `web/tests/e2e/operations-principal-identity.python.spec.ts` fails under
  `playwright.python.config.ts` alone; it requires its own `playwright.python.unicode-principal.config.ts`
  (its `BASE` is hardcoded to port 4184). Verified PRE-EXISTING at Task Base with the harness reverted,
  so B's documented combined command for that spec does not hold independently of this Task; the spec
  passes with its dedicated config (1/1).
- The `_open_draft_definition` read path means a Draft-only candidate can be corrected and published by
  the same Save; its old Draft is left untouched, so unrelated edits neither ride along nor disappear.
  This is asserted for the published path; the Draft-only correction path is covered by the shared
  managed authority rather than a dedicated new assertion.
- No schema change, so no migration rehearsal was run.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 4380c15b100d362bc057f7527ce34e4b840b0581
```

## B Review Result

```text
Reviewed: NOT SUBMITTED
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```
