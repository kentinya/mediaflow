# Task 39.2 — Typed Storage Add/Edit and checked Active Save

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 39.2
Parent Slice: 39
Status: PLANNED
Task Base: 2d012c07f049fb2e0831a39b721b1aa465e3888e
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the operator's Storage Add/Edit journey through typed API and V2 Web: enter one of the six
supported provider configurations in the four-step drawer, Save against the exact Active snapshot
used to open it, and see the successfully checked successor become runtime Active. This advances
Slice RO-1, RO-3, RO-6 and RO-7. Copy, enable/disable and removal remain one subsequent coherent
mutation unit under RO-4.

## Why This Task Exists

Task 39.1 delivered truthful Active inventory, references and zero-mutation read diagnostics, but
the current `/ui-v2/storage` page has no working Add/Edit or provider form. Existing generic Draft
object CRUD and checked activation require an operator to manage implementation revisions and do
not deliver the page-local Save promised by the Slice. The ResourceLibrary/MediaLibrary Save paths
show the existing successor, evidence and runtime-binding boundary; Storage needs its own
provider-neutral command and typed Web journey through that boundary. Add and Edit belong together
because they share the same form, validation and checked publication behavior.

## Implementation Scope

- Add a Storage-scoped application command and matching versioned API Add/Edit behavior built on the
  existing Managed Configuration and `ConfigurationObjectService` authority. Capture the exact
  current Active used to open the form; compose one complete successor; run full graph validation,
  applicable exact-successor read-only Storage checks, offline Recognition Strategy Test and
  destination precheck; prepare runtime binding before atomic checked publication. Preserve the
  former Active and its runtime binding on every failed admission. Keep historical admitted work
  pinned to its own snapshot.
- Add an edit-safe, typed projection of the selected Active Storage needed to prefill the form,
  including supported option fields and approved secret-reference *names* without secret values.
  API edits preserve existing options the form does not expose; reject attempted ID changes,
  duplicate IDs, malformed fields, unsupported provider options and stale Active authority.
- Implement Local, SMB, OpenList, AWS S3, Cloudflare R2 and generic S3-compatible form fields and
  provider-specific validation. Include common name, ID, type, root, enabled/read-only and
  supported timeout/retry/concurrency settings. Use only approved deployment-owned secret
  references. Do not add Storage notes or accept notes in the Storage page command.
- Extend the existing Storage workspace with `+ 添加存储`, applicable row `编辑`, and the prescribed
  right-side four-step drawer (`基本信息 → 连接配置 → 高级设置 → 确认`). Keep the drawer closed on normal entry,
  reload and reconnect; explicit Add/Edit opens step 1. Use a left step rail, right form and
  reachable bottom Cancel/Back/Next/Save controls. The inventory remains context at reference
  desktop width. Keep current view/detail/read-check functionality and shared top-bar search.
- Map backend validation, permission, provider/evidence, stale/conflict, persistence and runtime
  failures to field or action-oriented Web states. Retain correctable form input after known
  failure. Treat an unknown Save outcome as a state-verification problem: refresh exact Active
  before any new explicit submission; never automatically replay Save.
- Add focused application/API/entity/component/browser coverage for success, invalid fields,
  provider variation, secret redaction, stale writers, graph/evidence/runtime failures, no Storage
  mutation, drawer focus/keyboard/narrow layout and existing route compatibility. Keep the
  committed reference image and pre-existing unrelated `docs/pics/` changes outside the checkpoint.

## Acceptance Criteria

- [ ] Authenticated authorized operators can open Add or Edit from `/ui-v2/storage`. The drawer is
      closed on ordinary entry and opens at step 1 only on explicit intent. It follows the Slice
      composition and field order: `名称`, `存储 ID`, `存储类型`, then provider connection, advanced
      settings and secret-free confirmation. Edit is prefilled from one exact Active object, shows
      immutable ID, and preserves supported existing options. Back/Next preserve entered values;
      Cancel, close and Escape never Save and restore focus where practical. Long forms, narrow
      width and keyboard operation keep controls reachable.
- [ ] All six supported provider types can be added and edited through typed fields and API
      validation without JSON-only editing. Local roots use backend confinement; remote roots stay
      logical provider-relative paths. ID follows `[a-z0-9][a-z0-9_-]` up to 64 characters and
      cannot change on Edit. Only fields valid for the selected provider are shown and accepted;
      supported timeout/retry/concurrency values follow existing domain limits. Storage notes are
      absent from input, output and search.
- [ ] API/Web never return or log secret values, raw credentials, tokens, authorization headers or
      cookies. Form prefill and confirmation use only approved secret-reference names/readiness.
      Missing or unavailable references fail safely with an actionable recovery path; no secret
      value is copied into a test fixture, response, audit or error.
- [ ] Each Save binds to the exact Active authority seen when Add/Edit opened and uses backend
      permissions for management and activation. It composes a complete successor from that Active,
      validates every dependency, obtains applicable exact-successor read-only Storage evidence,
      offline strategy-test evidence and destination precheck, prepares runtime binding, then
      atomically checked-activates. No Draft edit alone reports success. The refreshed list/detail
      and subsequent configuration work consume the new immutable Active snapshot.
- [ ] Duplicate ID, invalid name/provider/root/endpoint/options, stale Active, denied permission,
      unavailable/missing mount or credential, failed check/strategy/destination evidence,
      persistence failure and runtime-binding failure preserve prior Active and Storage contents.
      The UI identifies the affected object or field, durable state and explicit correction or
      refresh action. Correctable input remains; unknown outcomes are verified from Active before
      another manual attempt. No page Save starts a media Task or performs Storage mutation.
- [ ] API and Web use one application command and the same RBAC, validation, concurrency, audit,
      redaction, error and recovery semantics. Existing V1 `/ui`, general Configuration,
      Storage Browser, Files/MediaLibrary, read diagnostics, adapters and OrganizerExecutor remain
      compatible. The checkpoint changes only this Task and leaves the A-owned Slice Contract and
      unrelated/private files untouched.

## Required Tests

Run and record exact commands, counts, skips and unavailable gates. Use temporary roots, fake/local
provider services and synthetic secret references; never require production SMB/OpenList/S3/TMDB.

- `.venv/bin/python -m unittest tests.test_configuration_objects tests.test_storage_configuration_management tests.test_storage_setup_check tests.test_v2_storage_operations` plus focused new Add/Edit application/API tests for all six provider types, exact Active fencing, full validation/evidence, runtime binding, audit, redaction and zero Storage mutation.
- `.venv/bin/python -m unittest discover -s tests` for the T4 full Python regression.
- `cd web && npm test -- --run` plus focused Storage entity/API/component tests for provider forms,
  steps, prefill, option preservation, field errors, unknown outcome and permission states.
- `cd web && npm run test:e2e -- --grep 'Storage management'` for authenticated Add/Edit success,
  provider variation, failed/stale Save recovery, drawer closed/open states, desktop/narrow layout,
  keyboard/focus and continued inventory/read-check behavior. Capture controlled `1536 x 1024`
  drawer-open and closed visual evidence against the committed reference; report browser or
  fixture limitations honestly.
- `cd web && npm run typecheck && npm run lint && npm run format:check && npm run build`.
- `.venv/bin/ruff format --check . && .venv/bin/ruff check .` and
  `.venv/bin/python -m compileall -q mediaflow tests scripts`.
- `python3 scripts/check_governance.py`, `git diff --check`, manifest/private-file and secret-output
  audit, and FFmpeg/FFprobe exclusion audit. Record whether
  `scripts/docker_release_security_smoke_test.py` or another packaging/migration gate is material
  to the actual diff; run any material gate and report an unavailable external gate explicitly.

## Non-goals

- Copy, enable/disable, configuration removal and their `更多` actions; these form the remaining
  RO-4 mutation unit. Do not display dead controls that appear usable.
- Full general Configuration redesign, first-time setup replacement, physical Storage file
  mutation, write probes, media Scan/Preview/Organize or new adapters/providers.
- Storage notes, arbitrary host browsing, secret values, reference rewrites, Storage ID migration
  or physical root migration.
- Editing the committed `docs/pics/储存管理.png`, unrelated image work, or any change to the Slice
  Contract/Roadmap boundary.

## Developer Completion Report

### Changed Files

Pending Developer implementation.

### Implemented

Pending Developer implementation.

### Tests and Results

Pending Developer implementation.

### Decisions

Pending Developer implementation.

### Remaining In-Slice Work

Pending Developer implementation.

### Risks / Deviations

Pending Developer implementation.

### Checkpoint

```text
Status: PLANNED
Head SHA: NOT SET
```

## B Review Result

```text
Reviewed: NOT SET
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```
