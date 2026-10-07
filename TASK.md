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

## Correction Report — Fix Loop 1 (B Decision: FIX REQUIRED, 79544d9..4380c15)

This correction addresses exactly the five P1 blockers listed in `## B Review Result` and their
direct root causes. Task ID, Task Base, Goal and Scope are unchanged; no acceptance criterion,
Contract wording or Task Base was altered.

### Changed Files (correction)

Modified:

- `mediaflow/features/operations/AutomationLifecyclePage.tsx` (web) — route-context-bound form
  state and command targets; explicit scope submission; fractional-interval validation; daily/weekly
  schedule conveniences; actionable failed-edit-read recovery; unknown-Copy intent tracking with
  durable reconciliation before resubmission.
- `web/src/features/operations/AutomationLifecyclePage.test.tsx` — 5 new journey regressions
  (copy-route Save targeting, scope clear, fractional interval, daily convenience, unknown-Copy
  reconciliation).
- `web/src/entities/operations/automation-lifecycle.ts` (+ test) — `AutomationCopyIntentModel`
  fail-closed normalizer; historical edit-projection state; exclusive-minimum interval limits.
- `web/src/entities/operations/automation.ts` (+ existing test) — fractional-interval document
  support; `historical` definition state; (no test changes needed there).
- `web/src/entities/shared/normalize.ts` — `normalizeFiniteNumber`/`normalizeOptionalFiniteNumber`
  strict finite-number primitives.
- `web/src/shared/api/api-client.ts` — `fetchAutomationCopyIntent`.
- `web/src/features/operations/AutomationDetailPage.tsx` — retained-history labelling.
- `mediaflow/application/automation_workspace_commands.py` — removal authority restore/residual
  proof (no `TypeError`), live authority readback, copy-intent projection, copy audit source
  evidence, exclusive-minimum interval limits.
- `mediaflow/interfaces/service_api.py` — historical resolution in `_automation_definition_resolution`
  and a new `_automation_definition_context_historical`; V1 detail/grant/audit/revoke/occurrences and
  V2 detail/draft/occurrences resolve removed history; `GET /definitions/{id}/copy-intent`; grant and
  revoke routes serialized on `_runtime_binding_lock`.
- `mediaflow/infrastructure/sqlite_configuration_management.py` —
  `list_recent_command_audits` bounded durable-evidence reader.
- `scripts/operations_inventory_harness.py` — additive `run-automation-scheduler-tick` control route.
- `tests/test_automation_definition_publication.py` — 6 new regressions (26 total).
- `tests/test_v2_automation_lifecycle.py` — 5 new regressions (17 total).
- `web/tests/e2e/automation-lifecycle.python.spec.ts` — 2 new real-Python journeys (6 total).
- `TASK.md` — Status and this correction report.

### Implemented (correction)

- **P1-1 — Copy navigation (AC-T1/T2/T6):** form state now carries its route-context key; a
  retained form from another definition route is never used as the Save candidate. Edit Saves
  always target the route's definition ID (`targetId`), not the retained form's ID, and the
  submitted candidate is recomposed under that identity. Proven by a real-browser journey
  (create → publish copy → open origin → change Name unsaved → open copy route → Save → the
  copy is published with its own loaded values and the origin's durable name is unchanged) and a
  component regression that navigates through the real router.
- **P1-2 — Removal authority (AC-T2/T5/T6):** the pre-publication revocation now captures the
  exact prior live grant first. When publication is rejected because a legitimate concurrent Save
  won, the exact prior grant is durably restored (new grant row with identical bounds, prior row
  retained as audit) and the bounded error reports the *live* authority state read at that moment —
  no `TypeError` (the unsupported `current_revision_id` kwarg is gone). When publication succeeds,
  a residual re-revoke proves no live authority survived; a residual failure is reported as
  `automation_definition_removal_authority_live` on the already-published removal instead of being
  hidden. Concurrent grant/revoke API journeys are serialized with publication on
  `_runtime_binding_lock`, so an interleaved confirmed regrant cannot slip live authority between
  the revocation and publication. Proven by three application regressions (interleaved Save wins
  with authority restored; interleaved regrant fenced; residual-failure truthfully reported) plus
  the real grant/revoke routes.
- **P1-3 — Retained history (AC-T5/T6):** `_automation_definition_resolution` now resolves a
  removed definition from its newest non-Active revision as a last step and labels it
  `definitionState: "historical"` / `historicalState: "removed"` in the V2 operator document; the
  V1 detail, grant/grant-state, grant-audit, revoke and occurrences routes resolve the same
  evidence through `_automation_definition_context_historical`, and the V2 occurrences response
  reports `historicalState`. Granting/previewing a removed definition stays impossible (404 on
  POST grant). Proven by a real Scheduler emission (harness tick through the production
  `IntervalScheduler` assembly) whose occurrence remains readable through the V1 and V2 detail and
  occurrence routes after removal, and by API regressions.
- **P1-4 — Scope/schedule (AC-T3):** the typed form always submits `sourceScope` (empty string
  publishes the cleared scope); the Web definition normalizer and form validation accept any
  finite positive number (fractional `1.5` round-trips through create/edit/read with the exact
  value); the form limits now carry the domain's exclusive-minimum interval bound;
  daily (`0 8 * * *`) and weekly (`0 8 * * 1`) convenience controls compile to the existing Cron
  semantics with the same timezone field; a failed edit read now renders an actionable recovery
  state instead of a stuck loader.
- **P1-5 — Unknown Copy (AC-T6):** a Copy whose response is lost (`transport_unavailable`) is an
  unknown outcome, not a rejection: the page retains the submitted intent, blocks further Copy
  commands, and offers one explicit reconciliation read (`GET /definitions/{id}/copy-intent`)
  which resolves the exact committed identity from durable managed-configuration audit evidence
  (`routeObjectId`/`sourceObjectId`/candidate recorded at command time). A committed copy is
  opened directly; a genuinely unpublished outcome is labelled as such before deliberate
  resubmission. Nothing is replayed automatically and no second copy is allocated.

### Tests and Results (correction)

- PASS — `.venv/bin/python scripts/check_governance.py` (PASS).
- PASS — `.venv/bin/python -m unittest tests.test_automation_definition_publication tests.test_v2_automation_lifecycle` — 43 tests (26 + 17).
- PASS — `.venv/bin/python -m unittest tests.test_automation_task_definition tests.test_v2_automation_operations tests.test_configuration_successor_draft tests.test_configuration_management tests.test_configuration_destination_activation tests.test_v2_rules_workspace_commands tests.test_system_settings_management` — 124 tests.
- PASS — `.venv/bin/python -m unittest tests.test_cron_scheduler tests.test_automation_definition_occurrence tests.test_automation_task_definition_preview tests.test_automation_preview_grant_gate tests.test_automation_unattended_grant tests.test_automation_definition_execution tests.test_automation_authorized_execution_matrix tests.test_automation_admission tests.test_automation_job_fencing` — 117 tests.
- PASS — `.venv/bin/python -m unittest discover -s tests` — 2,227 tests, 7 skipped (the same
  pre-existing real OpenList/S3/SMB/Local-endurance external-service gates), 0 failures.
- PASS — `.venv/bin/python -m unittest tests.test_release_security` — 6 tests.
- PASS — `.venv/bin/ruff format --check .`; `.venv/bin/ruff check .`.
- PASS — `.venv/bin/python -m compileall -q mediaflow tests scripts`; `.venv/bin/python -m pip check`.
- PASS — `.venv/bin/mediaflow --config config/strategy.example.json config validate` and
  `--config config/mediaflow.phase13.2.example.json config validate`.
- PASS — `npm --prefix web run typecheck`; `npm --prefix web run lint`; `npm --prefix web run format:check`; `npm --prefix web run build`.
- PASS — `npm --prefix web run test -- run` — 67 files / 1,030 tests.
- PASS — `npm --prefix web run test -- run src/entities/operations/automation.test.ts src/features/operations/AutomationRouter.test.tsx` — 24 tests.
- PASS — `npm --prefix web run test:e2e` — 203 Node-fake tests.
- PASS — `npm --prefix web run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-lifecycle.python.spec.ts` — 6/6, including the new copy-navigation,
  retained-history (with a real Scheduler-emitted occurrence) and removal-authority journeys on
  the real Python/API/SQLite/browser harness.
- PASS — `npm --prefix web run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts` — 21/21.
- PASS — `npm --prefix web run test:e2e -- --config=playwright.python.unicode-principal.config.ts tests/e2e/operations-principal-identity.python.spec.ts` — 1/1.
- UNAVAILABLE — `.venv/bin/python scripts/docker_release_security_smoke_test.py`: this run failed
  earlier than the checkpointed one — the image build's `npm ci` step timed out reaching
  `registry.npmjs.org` (`EIDLETIMEOUT`), so no image/stack stages ran this time. The checkpointed
  run's environment limitation (bind-source mount visibility for the four-service stack) also
  remains. Not a code failure and not called PASS; both failures are environment/network
  conditions outside the repository.
- PASS — `git diff --check`; `git check-ignore config/alist.json` (ignored) and
  `git ls-files config/alist.json` (empty).
- PASS — no `ffprobe`/`ffmpeg` reference under `mediaflow/` and `pyproject.toml`
  (`grep -rni`, exit 1 with no matches; `rg` is not installed in this environment).
- PASS — `sha256sum docs/pics/自动化.png docs/pics/自动化-全局设置.png` match SLICE.md exactly.
- Schema unchanged: no migration rehearsal required.

### Decisions (correction)

- **Route-context-bound form state over per-route components.** The lifecycle page keys its form
  state to the exact route context (`definitionId` or create) and derives every definition-bound
  command target from the route rather than the form. This preserves the single-page architecture
  and makes Copy navigation safe by construction; the e2e journey covers the real navigation.
- **Restore-on-rejected-removal.** The revocation-before-publication order is retained (no window
  with the definition gone while authority is live), but a *known rejected* publication now
  restores the exact prior live grant durably — a new grant row with the prior row retained as
  audit, since the revoked PK row is durable evidence that may not be rewritten. Restoration is
  best-effort: the raised error always reports live truth read after the fact.
- **Residual post-publication re-revoke.** A successful removal re-checks applicable authority at
  publication time and revokes any residual grant; failure is reported as
  `automation_definition_removal_authority_live` (HTTP 200 with `durableState:
  successor_published`) instead of silently claiming full revocation. Grant and revoke routes now
  share `_runtime_binding_lock` with publication, closing the review's interleave.
- **Copy-intent reconciliation from managed audit evidence.** The copy command's audit context now
  records `routeObjectId` (route target), `sourceObjectId` (copy source) and the exact candidate;
  `list_recent_command_audits` (bounded, newest-first, redaction-preserving) reads them back. This
  avoids guessing from today's Active document and works across removal of either definition.
- **Exclusive-minimum interval bound.** The form authority now advertises `minimum: 0,
  exclusiveMinimum: true` for `intervalSeconds` (matching the domain's `0 < x <= MAX` rule) and
  the Web model/normalizer accept finite positive numbers, so a supported `1.5` no longer breaks
  the edit read.
- **Historical resolution as a bounded read-only fallback.** The Active → open-Draft → newest
  non-Active revision resolution order keeps every existing route truthful; historical documents
  are labelled (`historicalState: "removed"`) and never presented as Active/Draft authority.
  Granting and Preview stay Active-only.

### Risks / Deviations (correction)

- UNAVAILABLE — the Docker release-security smoke gate (see Tests; both the checkpointed bind-source
  limitation and this run's npm registry timeout). Reported honestly for B to assess.
- The 7 full-regression skips are pre-existing external-service gates, unrelated to this Task.
- The copy-intent reconciliation's evidence window covers audited copy/create commands (200 most
  recent); it resolves the latest observed command for the definition, which is the exact intent a
  lost-response operator reconciles.
- No schema change; no migration rehearsal required.
- `web/tests/e2e/operations-principal-identity.python.spec.ts` still requires its dedicated
  `playwright.python.unicode-principal.config.ts` (pre-existing, unchanged from the checkpoint).

### Checkpoint (correction)

```text
Status: READY FOR B REVIEW
Head SHA: PENDING_COMMIT
```

## B Review Result

```text
Reviewed: 79544d9aba697036405b06054c0c56a740281bab..4380c15b100d362bc057f7527ce34e4b840b0581
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — Copy navigation can make Save modify the original definition (AC-T1/T2/T6;
  RO-2 focused publication).** In the real Python harness and built native Web, open
  `proof-origin`, change its Name without saving, then use Copy. The browser navigates to
  `/ui-v2/operations/automation/lifecycle/proof-origin-copy` but retains the original form.
  Save sends `PUT /api/v1/operations/automation/definitions/proof-origin`: the original's
  durable name changes to the unsaved value while the copy remains unchanged. Reproduction
  uses `npm --prefix web run build` and the actual temporary-data harness
  `.venv/bin/python scripts/operations_inventory_harness.py --port 4190`. Evidence:
  `node /tmp/mediaflow-b-review-43-1-browser.mjs`, case
  `copy-navigation-keeps-original-form`, logged in
  `/tmp/mediaflow-b-review-43-1-browser.log`. `AutomationLifecyclePage.tsx` retains an
  unkeyed form across definition routes and uses that form's ID for commands. Bind loaded
  state, retained input, command target and its observed authority to the current definition
  context; navigation must never silently apply another definition's input or fence. Cover
  the actual copy-navigation-and-Save journey through Python/Web.

- **P1 — Removal does not preserve authority on rejection or fence concurrent regrant
  (AC-T2/T5/T6; Implementation Scope, Shared publication and lifecycle 5; RO-2 removal).**
  `.venv/bin/python /tmp/mediaflow-b-review-43-1-python.py` uses real services, exact
  Preview/confirmed API grant and the same SQLite file for configuration and runtime, as
  production does. A legitimate concurrent focused Save interleaved at the existing
  `before_publish` seam makes removal lose publication: the target remains Active, but
  its grant is already `revoked`, and `AutomationDefinitionSaveError` construction raises
  `TypeError` for unsupported `current_revision_id` instead of returning bounded recovery.
  A legitimate confirmed API regrant between revocation and publication returns 201;
  removal then succeeds with the definition absent and its latest grant still `active`.
  Both results are in `/tmp/mediaflow-b-review-43-1-python.log`. This interrupts the
  operator's live automation after a rejected removal and leaves a successful removal's
  authority outcome contrary to the promised revocation. No media mutation is claimed by
  this reproduction. `automation_workspace_commands.py:542` commits revocation before
  activation without fencing the intervening grant/publication operations. Use the actual
  production persistence/concurrency boundary to preserve existing authority on known
  rejection and serialize removal against grant/Scheduler/Worker/publication boundaries;
  report conflict/unknown durable state without an unhandled exception. Do not weaken the
  existing grants or mutation guards. Two repository connections to the same production
  SQLite file are not evidence that the stores are necessarily separate databases.

- **P1 — Retained history becomes inaccessible after successful removal (AC-T5/T6;
  Implementation Scope, Shared publication and lifecycle 6; RO-2 retained history).**
  The same Python reproduction emits an occurrence with the real Scheduler, reads
  `/api/v1/operations/automation/task-definitions/auto-task/occurrences` successfully (200),
  removes the definition successfully (200), then reads that identical history entry and
  receives 404 `automationTaskDefinitions 'auto-task' was not found`; one occurrence
  remains durable. Evidence: `removed-history` in
  `/tmp/mediaflow-b-review-43-1-python.log`. The operator's existing history route resolves
  only Active/open-Draft definitions through `_automation_definition_resolution`.
  `historical_definition` is not connected to the production API history path. Make retained
  API/Web history and linked outcomes readable through durable occurrence/pin context after
  removal and restart, with truthful historical labeling and no substitution of current
  configuration or revived authority. Verify the existing operator entry end to end.

- **P1 — Typed scope/schedule management does not complete the promised round trip
  (AC-T3; RO-2 scope and daily/weekly scheduling).** The real browser reproduction clears
  `Relative source scope` from `incoming` to empty and receives a successful Save, but the
  durable scope is still `incoming` (`clear-source-scope` in the browser log):
  `buildCandidate` omits empty scope, and backend merge preserves the old value. Separately,
  the current production API accepts and reads `intervalSeconds: 1.5` with HTTP 200, within
  its declared bounds; opening that definition in native Web remains on `Loading the
  definition`. The frontend integer-only definition normalization rejects this supported
  value and the page hides the failed edit read; its form validation is also integer-only.
  The real schedule selector exposes only interval and advanced Cron, with no required
  daily/weekly convenience controls. Evidence:
  `node /tmp/mediaflow-b-review-43-1-form.mjs`, recorded in
  `/tmp/mediaflow-b-review-43-1-form-confirmed.log`, plus the scope case above. Represent an
  explicit scope clear, align Web normalization/validation with supported backend numeric
  rules, show actionable failed-read recovery, and implement daily/weekly controls compiled
  to the existing Cron/timezone calculation. Cover persisted round trips and backend
  upcoming-times/DST behavior without emitting work.

- **P1 — Unknown Copy is called rejected and can duplicate a committed copy after Refresh
  (AC-T6; RO-2 unknown-submission readback).** In the actual browser/Python journey, the
  first Copy request is executed by the real backend and returns 200; Playwright then drops
  only its response to simulate transport loss. Web displays `Copying the definition was
  rejected (transport_unavailable).` Refresh followed by the available Copy action publishes
  both `proof-unknown-copy` and `proof-unknown-copy-2`. Evidence: `unknown-copy-submission`
  in `/tmp/mediaflow-b-review-43-1-browser.log`; the reproduction does not fabricate the
  backend result or remove any capability. The operator cannot determine which copy was
  committed, and refreshing authority alone is not reconciliation of that submitted intent.
  Retain the submitted intent/context, label transport loss as unknown, and reconcile its
  exact publication outcome before allowing deliberate resubmission. Do not silently repin
  and allocate another copy or automatically replay the command. Prove committed-response
  loss and genuinely unpublished/unknown outcomes through the real Python/Web surface.
