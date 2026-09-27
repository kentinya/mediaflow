# Task 40.2 — V2 Settings lifecycle and bounded configuration editing

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the checkpointed [Slice 40 Contract](SLICE.md).

```text
Task ID: 40.2
Parent Slice: 40
Status: FIX REQUIRED
Task Base: 95667df757b3682b01dad024cc586d726e8cd89b
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the native V2 Settings journey for truthful managed configuration state: an administrator
can create or resume the single first Draft, inspect a clearly labelled Draft or exact Active JSON,
export the supported redacted package, edit allowlisted system settings, and continue through the
existing validate/checked-activate APIs. This advances Slice 40 Required Outcomes RO-1 and RO-3;
it does not implement resident service adoption or new business workspaces.

## Why This Task Exists

Slice 40 Task 40.1 made the empty managed runtime legal and conditional evidence gates correct, but
`/ui-v2/configuration` still renders the generic migration placeholder. The backend already owns
status, first-Draft creation, revision detail, package export and bounded System Settings edit
routes; the missing product-complete unit is their authenticated Web surface with explicit state,
action, success, failure and recovery. Without it, an operator must fall back to the V1 UI or raw
CLI/API calls, violating the Settings Required Surface and RO-3's truthful JSON contract.

## Implementation Scope

Web route and state/query models → existing authenticated configuration/status, first-Draft,
revision, package-export and System Settings API contracts → focused Python/API and Web tests.

- Replace the `/ui-v2/configuration` migration placeholder with a responsive, keyboard-usable
  Settings page that distinguishes setup-required, resumable Draft, empty Active, partially
  configured Active, unavailable/corrupt authority and permission-denied states.
- Expose explicit `创建首个 Draft`/resume and activation actions through the existing backend
  behavior. Reads, refreshes, reconnects and navigation must not create Drafts, validate, activate,
  run checks or start media work; repeated creation must show the durable conflict/recovery state.
- Show exact Active and Draft revision identity/status separately, provide labelled bounded JSON
  inspection and the existing redacted configuration package export. Do not expose literal secrets,
  unsafe webhook credentials, bearer tokens, deployment authority or raw exceptions.
- Provide only the already supported allowlisted System Settings fields through the common settings
  API. Draft edits invalidate prior evidence and remain inactive until explicit validate and checked
  activation; stale/concurrent/validation/runtime failures preserve prior Active and correctable
  Draft state with an actionable next step.
- Keep the existing API permission behavior shared with Web, retain V1 `/ui` as compatibility
  fallback only for unrelated legacy routes, and do not add Storage/library/policy forms or new
  configuration consumers in this Task.

## Acceptance Criteria

- [ ] `/ui-v2/configuration` is a real Settings surface, not a migration placeholder, and its
      authenticated entry/refresh/reload/return states show the backend-authoritative status and a
      bounded next action for setup-required, Draft, empty Active, populated Active and unavailable
      authority.
- [ ] An administrator can create the one first Draft, resume it after reload/reconnect, inspect
      its labelled JSON, and reach explicit validate and checked-activate actions. Repeated creation
      reports the existing durable Draft/conflict; reads and navigation have zero write/work side
      effects. Viewer/read-only and 401/403 behavior remain backend-authoritative.
- [ ] The page can inspect the exact Active JSON after activation and export the supported
      configuration package through the existing API. Draft JSON is visibly Draft; Active JSON is
      the immutable runtime-consumed snapshot. Responses and rendered UI contain no secret values,
      bearer tokens, deployment database/principal authority or raw exception text.
- [ ] Allowlisted System Settings fields can be edited in a Draft through the existing settings
      API, with optimistic version handling and clear inactive/active consumption labels. Unknown,
      deployment-authority or unsafe fields are rejected by the backend and not advertised by Web.
- [ ] Known stale, invalid, permission, unavailable and publication failures preserve prior Active,
      retain correctable Draft state where promised, and expose an action-oriented recovery path;
      uncertain publication outcomes are verified rather than replayed automatically.
- [ ] The Task remains within RO-1/RO-3 and existing RO-4 authority: no business defaults, Storage
      mutation, media Job/Task, scan, metadata request, notification delivery or resident-process
      redesign is introduced by Settings reads/edits/activation.
- [ ] The assigned T4 tests and quality gates pass with honest output, and the checkpoint contains
      only this Task's coherent changes.

## Required Tests

- `.venv/bin/python -m unittest tests.test_management_setup tests.test_configuration_snapshot tests.test_system_settings_management tests.test_configuration_objects tests.test_runtime_strategy_configuration` plus focused API tests for first Draft, status/readiness, package export, permissions, stale edits, validation and checked activation.
- Web tests for the Settings route/component, including setup-required, resumable Draft, empty
  Active, populated Active, Viewer/403, redaction, export, refresh and recovery states.
- `.venv/bin/python -m unittest discover -s tests`.
- `cd web && npm test -- --run && npm run typecheck && npm run lint && npm run format:check && npm run build`.
- `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/python -m compileall -q mediaflow tests scripts`.
- `.venv/bin/python scripts/docker_release_security_smoke_test.py`, `python3 scripts/check_governance.py`,
  `git diff --check`, exact Base..Head manifest review, secret/private-config audit and FFmpeg/FFprobe
  exclusion audit.

## Non-goals

- Work outside Slice 40 or changes to Required Outcomes, Required Surfaces, Safety Invariants,
  Slice Base, Roadmap or canonical product scope.
- Resident Worker/Scheduler/Notification lifecycle, Compose mount/health redesign, process identity,
  restart adoption or deployment migration; those remain later Slice 40 Tasks.
- New business objects, Storage/library/policy workspace redesign, new providers/adapters/commands,
  unrestricted JSON writes, secret resolution, automatic activation or CLI-only completion.
- Changes to the already accepted Task 40.1 runtime empty-envelope/applicability behavior except
  where a directly required Settings regression proves it.
- P2 wording, visual polish unrelated to the Settings journey, or declaring the Slice PASS/CLOSED.

## Developer Completion Report

### Changed Files
`mediaflow/domain/configuration_management.py`, `mediaflow/application/configuration_snapshot.py`, `mediaflow/domain/package_exchange.py`
`tests/test_management_setup.py`, `tests/test_configuration_objects.py`, `tests/test_configuration_package_exchange.py`
`web/src/shared/api/configuration-api.ts`, `web/src/features/configuration/ConfigurationPage.tsx`, `web/src/features/configuration/ConfigurationPage.test.tsx`
Third correction pass changes only these files; `web/src/routes/router.tsx` is unchanged from the first pass.

### Implemented

Third correction pass, scoped to the three blockers B listed under
`Decision: FIX REQUIRED` / `Next: SAME TASK FIX LOOP`. Task ID, Task Base, Goal and
Implementation Scope are unchanged.

**P1 — Publication uncertainty and stale-edit recovery are misreported.**
- `configuration-api.ts` now preserves the bounded backend `code` and structured `details` on every
  failure and classifies writes: a transport abort, an unreadable 2xx, an unparsable error body or an
  unexplained 5xx becomes `ConfigurationUnknownOutcomeError` (no trustworthy answer), while a real
  4xx/409 answer stays a known rejection. A 5xx that carries an explicit `durableState` remains a
  known rejection.
- `ConfigurationPage` dispatches failures by attempted action and conflict code through the exported
  `configurationMutationFailure`: the first-Draft conflict keeps its durable Draft/resume identity; a
  stale settings save recovers from the conflict's own `currentVersion` (input retained, next explicit
  save carries the advertised version); activation conflicts state the durable Draft/Active outcome and
  the backend next action. No failure path claims "原有 Active 保持不变" unless the backend said so.
- An unknown outcome sets an explicit verification gate: every publication action is disabled, the
  authoritative status is re-read, and the operator must press `核实当前状态` (a read-only re-read of
  status plus the selected revision) before another write. The publication is never replayed
  automatically (mutations keep `retry: false`). After verified activation the page re-inspects the
  exact revision, so the committed Active is shown instead of the stale Draft view.

**P1 — The normal configuration JSON exposes deployment authority.**
- One shared bounded projection `portable_managed_configuration_document` (domain) preserves the
  selected immutable revision and every supported managed family while excluding deployment startup
  authority: the `persistence` locator and the `api.principals` / `api.tokenEnv` identity. Managed
  settings inside `api` (for example `remoteExecution`) stay.
- Applied to `ManagedConfigurationService.detail()["document"]` (the Draft and Active JSON the Settings
  page renders) and to the portable package payload in `build_configuration_package`, so neither the
  response nor the export carries deployment database/principal authority. Permitted deployment status
  stays on its separate existing surfaces (`authority`, `health`, `setupRequired`, system-settings
  `bootstrapDatabasePath`).
- `import_draft` and `edit_draft` rebind omitted authority to the receiving deployment
  (`bind_deployment_authority`), so the projected JSON still round-trips through the advanced
  whole-document editor and through package export/import into a validatable, activatable Draft.
  Only omitted authority is filled: a caller-supplied locator/identity still reaches validation
  unchanged, so the existing fail-closed immutable-locator check keeps rejecting it.

**P1 — Settings loses the backend's effective/restart boundary.**
- `settingFields` now keeps each backend `boundary` instead of dropping it after the
  bootstrap-immutable filter, and the selected field states its boundary before publication
  (`激活后即时生效` vs `需重启后生效` plus what that means for the running process).
- The settings panel renders the backend `consumption` evidence: saved vs activated vs actually
  consumed, the consumed Active snapshot, restart-required fields, hot-consumed fields, and the
  backend consumption next action. No new settings consumer and no resident-service change.

### Tests and Results
- `python3 scripts/check_governance.py` — PASS
- Focused Python gate (B's blocker surfaces):
  `.venv/bin/python -m unittest tests.test_management_setup tests.test_configuration_snapshot tests.test_configuration_objects tests.test_configuration_package_exchange tests.test_system_settings_management tests.test_webhook_url_security`
  — PASS (178 tests)
- `.venv/bin/python -m unittest discover -s tests` — PASS (1861 tests run, 7 skipped for unavailable
  isolated external/endurance profiles; ResourceWarning output remains visible)
- `cd web && npm test -- --run` — PASS (48 files / 738 tests, no skips; jsdom `scrollTo` diagnostics remain)
- `cd web && npm test -- --run src/features/configuration/ConfigurationPage.test.tsx` — PASS (11 tests)
- `cd web && npm run typecheck && npm run lint && npm run format:check && npm run build` — PASS
  (bundle-size advisory only)
- `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/python -m compileall -q mediaflow tests scripts`
  — PASS (317 files formatted)
- `.venv/bin/python scripts/docker_release_security_smoke_test.py` — FAIL / PRE-EXISTING / UNRELATED.
  The harness fails when Compose starts the services:
  `invalid mount config for type "bind": bind source path does not exist:
  /tmp/mediaflow-smoke-security-*/media/incoming`. The identical command on a clean detached Task Base
  worktree (`95667df`) fails identically, so it is not caused by this Task's changes and no Task-40.2
  code path is involved. Evidence retained below; not claimed as a pass.
- End-to-end probes against the real `MediaFlowApi` + `ManagedConfigurationService` + SQLite
  (management-only bootstrap, temporary data, no external providers, no media mutations):
  - Draft JSON and Active JSON both exclude `persistence`/`api.principals` while keeping revision
    identity and every managed family — PASS
  - Portable export excludes the same authority — PASS
  - Import rebinds the receiving deployment's locator and principal identity and the imported Draft
    validates — PASS
  - A lost activation answer leaves the server committed while the browser saw nothing (the reviewed
    reproduction) and an independent status read reports `active != null` — PASS
  - A stale Draft save really returns `409 configuration_version_conflict` with
    `durableState=draft_preserved`, `currentVersion`, and `nextAction` — PASS
- `git diff --check` — PASS
- Full suites were run by the Lead on the committed content; working tree equals `HEAD` except this report.

### Decisions
- Keyed 409 presentation on the attempted action plus the backend code, because the same status carries
  three different durable outcomes (first-Draft conflict, version conflict, activation conflict).
- Treated "no trustworthy answer" as a distinct state rather than guessing: only the operator's explicit
  verification read releases the write gate, and no publication is retried automatically.
- Put the projection in the domain layer (`configuration_management.py`) so the revision response and the
  package export share exactly one definition, and kept it separate from secret redaction, which still
  runs on top of it.
- Rebinding only *omitted* authority keeps the existing fail-closed locator validation intact while
  making the projected JSON a lossless round-trip for this deployment.
- The Web page keeps consuming the same existing API contracts; no new consumer, permission path, or
  resident-service behavior was added.

### Remaining In-Slice Work
Resident Worker/Scheduler/Notification Worker adoption without restart, deployment/Compose changes and
the remaining Slice 40 Required Outcomes are outside this Task.

### Risks / Deviations
- Docker release-security acceptance is FAIL / PRE-EXISTING / UNRELATED by the evidence above
  (identical failure at Task Base), so the material Docker gate is not proven for this checkpoint by me.
  Whether that pre-existing failure affects the Task or Slice judgement is B's call.
- Existing tests that encoded the pre-correction behaviour were updated to the newly required
  behaviour, not weakened: the revision-detail assertion now compares against the shared projection and
  additionally asserts the persisted Draft keeps its full authority, and the export assertion now
  asserts principal/token authority is excluded while permitted environment references remain.
- `tests/test_configuration_objects.py` and `tests/test_configuration_package_exchange.py` no longer
  assert `api.principals[0].tokenEnv` inside responses/exports; that assertion is replaced by the
  stricter exclusion assertions B's blocker requires.
- Pre-existing untracked `docs/pics/*.png` remain untracked and unmodified; `config/alist.json` stays
  ignored with no credential or private path added anywhere.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 6ba2483e047a261560ec66c6f7de8df27e76db36
Report commit: the docs commit recording this report is the child of the code checkpoint above;
its own SHA cannot be embedded in itself.
```

## B Review Result

Review scope: the reported checkpoint `3fc526f060614b0d752d656920d4c36084d11844`
and actual HEAD `c187242cc63975e5a6369de1077bac030ee9603b` have identical product code;
the latter only updates the report's Head SHA. B inspected the complete Task Base..HEAD diff.
The probes below use the built V2 page served by real `MediaFlowApi`,
`ManagedConfigurationService` and SQLite repositories, management-only bootstrap with fake
Admin/Viewer credentials, and no media objects or external providers. The lost-response probe
lets the real activation request commit before aborting only its browser response.

Task ID, Task Base, Goal and Implementation Scope remain unchanged. This is review of the second
correction checkpoint;
the corrections remain one Settings lifecycle/projection unit, without a new architecture or Task.

B-run verification (2026-09-27):

- Required focused Python command: PASS, 160 tests, no skips.
- `.venv/bin/python -m unittest discover -s tests`: PASS, 1,858 tests run, 7 skipped
  for unavailable isolated external/endurance profiles; ResourceWarning output remains visible.
- `cd web && npm test -- --run`: PASS, 48 files / 734 tests, no skips. Existing jsdom
  `scrollTo` diagnostics remain visible.
- Web `typecheck`, `lint`, `format:check`, `build`: PASS; build retains the bundle-size advisory.
- `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, and
  `.venv/bin/python -m compileall -q mediaflow tests scripts`: PASS (317 formatted files).
- `.venv/bin/python scripts/docker_release_security_smoke_test.py`: HEAD run failed waiting
  150 seconds for all Compose services to become healthy while full regressions were running.
  The exact command on a clean detached Task Base worktree passed (exit 0; image
  `mediaflow:b40-baseline-review`). A separate HEAD rerun after the suites completed also passed
  (exit 0, release-security acceptance completed). The initial timeout was not reproduced;
  its cause is unproven and it is not a separate Task blocker. Temporary services and the
  baseline worktree were removed.
- `python3 scripts/check_governance.py`, TASK local Markdown links and `git diff --check`: PASS.
  Exact manifest is TASK plus four Settings/router files. No existing tests were removed, weakened
  or newly skipped; no dependency/FFmpeg/FFprobe additions or real credentials were found.
  `config/alist.json` remains ignored/untracked/unstaged; pre-existing images are untouched.

```text
Reviewed: 95667df757b3682b01dad024cc586d726e8cd89b..c187242cc63975e5a6369de1077bac030ee9603b
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — Publication uncertainty and stale-edit recovery are misreported.** At
  `web/src/features/configuration/ConfigurationPage.tsx:81-92`, every 409 is treated as first-Draft
  creation conflict, and every other mutation error asserts that Active is unchanged. Reproduction:
  create/resume/validate the first empty Draft, forward checked activation to the real server with
  Playwright `route.fetch()`, observe HTTP 200, then `route.abort('failed')` before the browser receives
  the result. The page says `原有 Active 保持不变` and still offers activation from its old Draft state;
  an independent authenticated status read reports `active != null`, `emptyActive=true` and
  `setupRequired=false`. Separately, save a Settings successor (201, Draft version 2), edit that same
  Draft through a second authorized client (200), then save from the stale page: the real API returns
  409 `configuration_version_conflict` / `draft_preserved`, but Web says `首个 Draft 已存在`.
  These are supported publication/network-failure and concurrent-edit paths, affecting the admin's
  durable-state diagnosis and next action; they violate Task failure/recovery acceptance and
  RO-1/RO-4 unknown-outcome semantics. Preserve bounded error category and action context, distinguish
  known rejection from unknown publication, and provide state verification before another attempt.
  Recover stale edits from the actual revision/conflict rather than the first-setup message. Add
  regressions using these real API response shapes; never replay publication automatically.
- **P1 — The normal configuration JSON exposes deployment authority.**
  `ConfigurationPage.tsx:120-125` renders `detail.document` from
  `ManagedConfigurationService.detail()` (`mediaflow/application/configuration_snapshot.py:292-322`).
  Reproduction: on the fresh management-only instance, create the first Draft and click
  `恢复 Draft`; parse the displayed JSON. Both `persistence.databasePath` and `api.principals`
  are present, including deployment-owned principal/role configuration. The same fields remain
  visible through `查看 Active JSON` after empty activation. This is the ordinary supported
  Admin Settings journey, not an unsafe imported fixture. It violates the Task's explicit
  requirement that responses/rendered configuration contain no deployment database/principal
  authority and RO-3's separation of managed configuration from deployment authority. Use a shared
  bounded managed-configuration projection that preserves the selected immutable revision and all
  supported managed families while excluding deployment authority; keep any permitted deployment
  status separate. Cover Draft and Active JSON plus portable export against real backend payloads.
- **P1 — Settings loses the backend's effective/restart boundary.**
  `ConfigurationPage.tsx:25-50` drops field `boundary` after filtering bootstrap fields, and the
  editor at lines 325-367 never renders `settings.consumption`. Reproduction on the same real
  instance: resume the successor, set `locale=en-US`, save (200), validate (200), checked-activate
  (200), and inspect Active. `/api/v1/system/settings` reports locale
  `boundary=restart_required`, includes it in `consumption.restartRequiredFields`, and excludes it
  from `hotConsumedFields`; the page has no restart/deployment/effective-state guidance before or
  after publication. An admin therefore cannot tell that this supported setting still needs a
  deployment/restart step, unlike hot-consumed logging settings. This violates Task acceptance's
  clear inactive/active consumption labels and RO-3's explicit truthful restart-only requirement.
  Preserve and display the backend field boundary and consumption evidence, distinguish saved,
  activated and actually consumed settings, and give the required next action without adding new
  settings consumers or resident-service redesign. Test a restart-only field and a hot-consumed
  field using their real production projections.
