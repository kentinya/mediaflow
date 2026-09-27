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
`mediaflow/domain/configuration_management.py`, `mediaflow/application/configuration_snapshot.py`
`tests/test_management_setup.py`
Fourth correction pass changes only these three files; no Web, package-exchange or other product
file is touched, and the previously reviewed projection/edit surfaces are unchanged.

### Implemented

Fourth correction pass, scoped to the single blocker B listed under
`Decision: FIX REQUIRED` / `Next: SAME TASK FIX LOOP`. Task ID, Task Base, Goal and
Implementation Scope are unchanged. No Slice rescope was needed.

**P1 — The shared deployment-authority rebinding boundary is not fail-closed.**
- `mediaflow/domain/configuration_management.py` keeps exactly **one** explicit validation and
  rebinding boundary, `bind_deployment_authority`, and now makes it fail-closed instead of
  presence-only. Two new private helpers sit behind it:
  - `_deployment_principal` validates one supplied principal into a comparison identity: object
    shape, non-empty `id`, environment-name-shaped `tokenEnv`, a non-empty unique `roles` array
    whose entries must resolve through `ApiRole`, boolean `enabled`, and rejection of literal
    secret fields (`token`/`secret`/`password`/`authorization`).
  - `_deployment_authority_identity` validates and normalizes one document's API identity and
    returns `None` **only** when identity is genuinely omitted. Malformed input raises, so
    "omitted" and "malformed" are no longer collapsed into the same accept-and-rewrite path.
- The boundary now distinguishes three outcomes explicitly:
  - **Omitted** authority is bound from this deployment's own bootstrap, preserving the supported
    projected-JSON round trip (Draft/Active JSON, package export/import).
  - **Supplied authority that reproduces this deployment's own identity** is accepted unchanged, so
    a whole-document round trip still works. A legacy single-`tokenEnv` bootstrap is compared by its
    effective runtime projection (one enabled admin principal for that environment reference)
    through `_deployment_authority_matches`, so the two supported spellings are not mistaken for a
    rewrite.
  - **Conflicting or malformed** supplied authority raises `ValueError` and is never persisted:
    a changed role set (the reviewed Viewer-to-admin escalation), an emptied `principals` array, a
    foreign `tokenEnv`, a `tokenEnv`/`principals` combination, unknown roles, duplicate ids or
    environment names, over-limit principal counts, and non-object `api` / non-array `principals`
    values are all rejected rather than normalized into a different, apparently valid document.
  - An unreadable *receiving* bootstrap identity fails closed with its own bounded message instead
    of silently binding or accepting anything.
- The wrong-locator path is deliberately unchanged: a mismatched `persistence.databasePath` is still
  preserved and rejected by the shared managed runtime validator, so it remains a correctable Draft
  validation failure. A deployment that declares no API identity of its own (locator-only bootstrap,
  as used by several existing tests and the recovery loader) has no identity to rewrite, so the
  document's own declaration still flows to the normal validator.
- `mediaflow/application/configuration_snapshot.py`: only the `_bind_deployment_authority` wrapper
  docstring was corrected to describe the new fail-closed semantics; the call sites and behavior
  contract are unchanged. The boundary has exactly two live call sites (`import_draft`, `edit_draft`);
  package import and every guided/System Settings object edit delegate to them, so all
  document-mutating paths cross this one boundary.
- No frontend workaround, no new policy framework, no new Task and no Contract expansion: the fix is
  the single boundary B asked for.

### Tests and Results

- B's reproduction script, re-run against the corrected code:
  - `PUT` of the escalated document (`api.principals=[{id: "viewer", tokenEnv: "MF_VIEWER_TOKEN",
    roles: ["admin"]}]`) now returns **400 `invalid_request`** instead of 200, and the stored Draft
    still carries the bootstrap identity.
  - real `.venv/bin/mediaflow --config ... api serve` restart with the unchanged bootstrap and fake
    credentials: Viewer `configuration/status` returns 200 with `canManageConfiguration=False` and
    `canActivateConfiguration=False` (previously both true). — PASS
- New regressions in `tests/test_management_setup.py` (real `MediaFlowApi` + `ManagedConfigurationService`
  + SQLite, management-only bootstrap, fake credentials, no media or external providers):
  - `test_supplied_deployment_authority_is_validated_and_conflicts_rejected` — omitted authority
    round trip passes and binds this deployment; verbatim matching authority is accepted and versions
    forward; nine conflict/malformed cases (escalated role, emptied principals, foreign `tokenEnv`,
    legacy `tokenEnv`, `api: []`, `api: "..."`, non-array principals, empty roles, literal secret
    field) each return 400 `invalid_request` with the Draft byte-identical (digest, version and
    document compared) and the persisted identity unchanged after every attempt.
  - `test_managed_edits_cannot_change_startup_bootstrap_permissions` — the escalation is rejected on
    both the draft `PUT` and the whole-document `drafts` import (revision count still 1), the
    unescalated Draft still validates with `validationErrors=[]` and activates, and a real
    `final_main(["... ", "api", "serve"])` restart of a *separate* deployment proves the Viewer token
    keeps `canManageConfiguration=False` / `canActivateConfiguration=False` while admin keeps both
    true.
- Test truthfulness: both new tests were confirmed to depend on the fix. Replaying the previous
  presence-only boundary logic accepts the escalation and rewrites `api: []` into bootstrap identity;
  the corrected boundary rejects both. No test was weakened, deleted or newly skipped.
- `.venv/bin/python -m unittest tests.test_management_setup tests.test_configuration_snapshot
  tests.test_system_settings_management tests.test_configuration_objects
  tests.test_runtime_strategy_configuration` — **PASS** (165 tests, no skips)
- Boundary call-site modules (`tests.test_guided_storage_lifecycle`, `tests.test_v2_storage_operations`,
  `tests.test_storage_browser`, `tests.test_storage_page_local_save`,
  `tests.test_automation_unattended_grant`, plus package exchange and API-security modules)
  — **PASS**
- `.venv/bin/python -m unittest discover -s tests` — **PASS** (1,863 tests run, 7 skipped for
  unavailable isolated external/endurance profiles; ResourceWarning output remains visible)
- `cd web && npm test -- --run` — **PASS** (48 files / 738 tests, no skips; jsdom `scrollTo`
  diagnostics remain)
- `cd web && npm run typecheck && npm run lint && npm run format:check && npm run build` — **PASS**
  (bundle-size advisory only)
- `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/python -m compileall -q
  mediaflow tests scripts` — **PASS** (317 files formatted)
- `.venv/bin/python scripts/docker_release_security_smoke_test.py` — **PASS**, exit 0, full
  release-security acceptance on this working tree: clean image/Compose inspection, four-service
  stack, managed activation, Worker restart against the exact Active snapshot and V2 Organize
  completion. See the environment note under Risks / Deviations.
- `python3 scripts/check_governance.py` — **PASS**; `git diff --check` — **PASS**
- Pre-commit audit: `git status`, complete diff, name/status/stat and manifest inspected. Manifest is
  this Task's three files plus the pre-existing `TASK.md`; no dependency, FFmpeg/FFprobe, credential,
  private-path or binary addition. `config/alist.json` remains ignored, untracked and unstaged; the
  pre-existing untracked `docs/pics/*.png` remain untouched.

### Decisions
- Kept one boundary rather than adding validation at each caller, because `import_draft` and
  `edit_draft` are the only live call sites and every other mutating path already delegates to them.
- Rejected conflicting authority instead of rewriting it to the bootstrap identity: rewriting is
  exactly what made the reviewed escalation invisible, and B explicitly required preserving
  malformed-input rejection instead of normalizing bad input into a different valid document.
- Compared a supplied identity against the deployment's *effective* runtime projection rather than
  raw JSON, so the legacy single-`tokenEnv` spelling and the canonical `principals` spelling of the
  same authority still round-trip while any real permission change is rejected.
- Left the wrong-`databasePath` path as a validation failure rather than an import failure, because
  documented recovery behavior and `test_runtime_locator_is_rejected_during_validation_and_activation`
  require the Draft to remain correctable.
- Treated a locator-only deployment as having no API identity to protect, so existing recovery and
  locator-only test assemblies keep working without weakening the guarded case: whenever the
  receiving deployment does have an identity, a differing supplied one is rejected.

### Remaining In-Slice Work
Resident Worker/Scheduler/Notification Worker adoption without restart, deployment/Compose changes and
the remaining Slice 40 Required Outcomes are outside this Task.

### Risks / Deviations
- The Docker smoke gate initially failed in this environment with
  `invalid mount config for type "bind": bind source path does not exist:
  /tmp/mediaflow-smoke-security-*/media/incoming`. This is an environment artifact, not a code
  regression: `/tmp` here is a private systemd tmpfs that the Docker daemon cannot see, and a control
  probe showed a bind from `/tmp` resolves to an empty mount while the same probe from the repository
  root succeeds. Re-running the identical command with a Docker-visible `TMPDIR` passed with exit 0
  (log line `Release-security smoke acceptance passed.`). B's own run also passed on committed HEAD,
  so this gate is reported PASS with that environment note rather than as a code failure.
- The three previously accepted corrections are unchanged by this pass; no previously accepted
  behavior or assertion was weakened.
- Pre-existing untracked `docs/pics/*.png` remain untracked and unmodified; `config/alist.json` stays
  ignored with no credential or private path added anywhere.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 3b739d293e872df2b968aa8c712ad982ffea5f24
```

## B Review Result

B reviewed the full Task Base..HEAD and the third correction at
`6ba2483e047a261560ec66c6f7de8df27e76db36`. Actual HEAD
`7f2060e631aff39a853468d8c512552682c0cb75` adds only the completion report. The report's
READY FOR B REVIEW checkpoint is the review request even though the top-level status was left
FIX REQUIRED. Task ID, Task Base, Goal and Implementation Scope stay unchanged.

The prior three findings were rechecked against the built V2 page served by real MediaFlowApi,
ManagedConfigurationService and SQLite: Draft/Active JSON excludes deployment authority; a
committed activation with a deliberately lost browser response requires explicit verification and
is not replayed; real stale-edit 409 uses its own conflict category; restart-only settings show
the backend boundary. These findings are resolved and are not carried into the blocker list.

Three correction rounds have now completed; the next correction would be round four. B's global
complexity assessment: the Settings lifecycle still fits this Task and the existing revision/API
architecture. The remaining defect is at the shared deployment-authority input boundary introduced
for projected-document round trips. Another frontend workaround, new policy framework, new Task or
Contract expansion is unnecessary. Keep one explicit validation/rebinding boundary, reuse the
receiving bootstrap authority, and preserve malformed-input rejection instead of normalizing bad
input into a different valid document. No Slice rescope is needed.

B verification (2026-09-27):

- Required focused Python modules plus package-exchange and Webhook-redaction regressions:
  PASS, 189 tests, no skips.
- `.venv/bin/python -m unittest discover -s tests`: PASS, 1,861 tests run, 7 skips for unavailable
  isolated external/endurance profiles. ResourceWarnings were visible, not suppressed.
- `cd web && npm test -- --run`: PASS, 48 files / 738 tests, no skips; jsdom scrollTo diagnostics
  remain visible. Web typecheck, lint, format:check and build all PASS; bundle-size advisory only.
- Ruff format/check and Python compileall: PASS (317 formatted files).
- `.venv/bin/python scripts/docker_release_security_smoke_test.py`: PASS on current committed
  HEAD, exit 0, including clean image/Compose checks, managed activation, Worker restart and
  V2 Organize completion. The Developer's reported bind-mount failure did not reproduce in B's
  run; it is not a blocker and is not relabelled as a code regression.
- Real API/SQLite input-boundary probes and a real `.venv/bin/mediaflow ... api serve` restart
  reproduce the blocker below. Temporary bootstrap, database and fake credentials only; no media,
  external providers, direct database edits or disabled production capabilities were used.
- Full manifest inspection: TASK plus the ten coherent product/test files; no dependency changes,
  FFmpeg/FFprobe additions, real credentials or private configuration. The changed old assertions
  require deployment-authority exclusion and preserve persisted-document assertions; they do not
  hide a skip or weaken a safety check. Original untracked images remain untouched.
- Governance preflight, TASK local Markdown links and `git diff --check`: PASS.
  `config/alist.json` remains ignored, untracked and unstaged. B changed only TASK.md.

```text
Reviewed: 95667df757b3682b01dad024cc586d726e8cd89b..7f2060e631aff39a853468d8c512552682c0cb75
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — The shared deployment-authority rebinding boundary is not fail-closed.**
  Current production reachability: an administrator on a valid management-only installation can
  use the supported revision JSON read/edit, validate and checked-activate APIs; the updated
  `ManagedConfigurationService.edit_draft` and `import_draft` both call
  `bind_deployment_authority` (`mediaflow/domain/configuration_management.py:80-123`). This is a
  supported running assembly receiving an edit request, not a hand-corrupted database or a
  deployment started with invalid configuration. Current user impact: a managed edit can replace
  deployment-owned principal/role identity, so after normal API restart the original Viewer token
  has administrative configuration permissions despite an unchanged bootstrap; malformed `api`
  input is also silently rewritten and accepted, rather than leaving a correctable validation
  error. Contract: RO-3 says managed editing/import/recovery cannot import or repoint identity
  authority; Safety Invariant 2 makes bootstrap database/principal authority immutable; Task
  acceptance requires deployment-authority/unsafe fields to be rejected by the backend. RO-2's
  mandatory malformed-object validation must also survive this shared round-trip change.
  Reproducible evidence: create the first empty Draft, GET its projected document, set
  `api.principals=[{id: "viewer", tokenEnv: "MF_VIEWER_TOKEN", roles: ["admin"]}]`, and PUT that
  document with the exact current version. Edit returns 200, validate returns 200 with
  `validationErrors=[]`, and checked activation returns 200. Start the actual CLI API server with
  the original, unchanged bootstrap and fake environment credentials, then GET configuration/status
  using the Viewer token: both `canManageConfiguration` and `canActivateConfiguration` are true,
  while the bootstrap still says `roles=["viewer"]`. The helper leaves any explicitly supplied
  identity untouched; the validator it relies on,
  `load_managed_runtime_configuration` (`mediaflow/infrastructure/runtime_configuration.py:560`),
  checks only the database locator. Separately, PUT the projected document with `api: []`:
  the helper replaces the array with bootstrap identity, persists a dict, and validation again
  returns no errors. Required correction: validate supplied structure and deployment identity at
  the shared boundary, bind only genuinely omitted authority to this deployment, and reject
  conflicting principal/role/token authority instead of persisting it for runtime startup.
  Preserve supported projected JSON round trips and known-failure Draft/Active recovery. Add real
  API/SQLite regressions for omitted authority, matching/conflicting supplied authority and wrong
  `api` types, plus an actual startup/auth projection check proving that managed edits cannot
  change bootstrap permissions. This is an unmet current authority invariant; it does not claim
  that every underlying startup behavior originated in this checkpoint.
