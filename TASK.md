# Task 39.2 — Typed Storage Add/Edit and checked Active Save

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 39.2
Parent Slice: 39
Status: READY FOR B REVIEW
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

- `mediaflow/application/configuration_objects.py`: Storage form authority/projection and checked Add/Edit command; extend shared evidence collection for the enabled Storage being saved.
- `mediaflow/interfaces/service_api.py`: typed Storage routes, management + activation RBAC, runtime binding, bounded Save outcomes and audit route templates.
- `tests/test_storage_page_local_save.py`: isolated application/API provider, concurrency, validation, admission failure, redaction and zero-mutation regressions.
- `web/src/entities/storage/storage-form.ts` and `storage-form.test.ts`: six-provider field model, validation, exact path preservation and typed response normalization.
- `web/src/features/storage/StorageEditDrawer.tsx`, `StorageManagementPage.tsx` and `StorageManagementPage.test.tsx`: four-step Add/Edit, prefill, retained input, explicit state verification, focus and permission states.
- `web/src/shared/api/api-client.ts` and `storage-management-api.test.ts`: authority read and fenced typed Save clients.
- `web/src/shared/ui/styles.css`: drawer/provider choices and Storage-specific six-column widths.
- `web/tests/fake-server.mjs` and `web/tests/e2e/storage-management.spec.ts`: isolated browser fixture, mutation journeys and reproducible screenshots.
- `TASK.md`: factual Developer report only; Task ID/Base/Goal/Scope and B decision remain unchanged.

### Implemented

- Explicit Add/Edit at `/ui-v2/storage` opens step 1; Local, SMB, OpenList, AWS S3, R2 and S3-compatible forms support connection and advanced settings, immutable edit ID, environment-reference names, and secret-free confirmation. Close/Cancel/Escape never Save; values survive navigation and known failures.
- `GET /api/v1/storages` captures exact Active authority; `GET /api/v1/storages/{id}/edit` supplies the selected form; POST/PUT use the same application command. Both Add and Edit reject stale open-time revision/sequence/digest before creating a successor.
- Save composes and validates the complete successor, checks referenced enabled Storages plus the enabled Storage being saved, retains offline strategy/destination evidence, prepares runtime binding and checked-activates atomically. No media work or Storage mutation is started.
- Failed validation, dependencies, credentials/read checks, persistence, runtime preparation or concurrency leave the prior Active intact. Unknown/stale outcomes block resubmission until explicit successful authority verification; no automatic Save replay occurs.
- Same-provider edits preserve omitted supported options; explicit null clears optional settings and provider changes drop the former provider's options. Legacy unnamed Storage projections use their stable ID. OpenList provider-rooted paths remain logical; Local host root and traversal are rejected.
- Shared search, existing detail/read checks and V1 surfaces remain in place. Desktop drawer context now keeps Storage names/IDs readable instead of inheriting Files checkbox-column widths.

### Tests and Results

Final command results (2026-09-26; temporary roots and fake/local services only):

- PASS — `.venv/bin/python -m unittest tests.test_configuration_objects tests.test_storage_configuration_management tests.test_storage_setup_check tests.test_v2_storage_operations tests.test_storage_page_local_save`: 126 tests, zero skips.
- PASS — `.venv/bin/python -m unittest discover -s tests`: 1,834 tests, 7 SKIP (dedicated SMB/S3/OpenList real-service acceptance and Local/SMB/OpenList/S3 endurance profiles are absent).
- PASS — `cd web && npm test -- --run src/entities/storage/storage-form.test.ts src/shared/api/storage-management-api.test.ts src/features/storage/StorageManagementPage.test.tsx`: 69 tests across 3 files, zero skips.
- PASS — `cd web && npm test -- --run`: 694 tests across 47 files, zero skips.
- PASS — `cd web && npm run test:e2e -- --grep 'Storage management'`: 22 Chromium journeys, zero skips; authenticated Add/Edit, provider variation, failed/stale/unknown outcomes, read-only permissions, setup, shared search, read checks, narrow layout and keyboard focus.
- PASS — `cd web && npm run typecheck && npm run lint && npm run format:check && npm run build`: all four gates passed; only the bundle-size advisory remains.
- PASS — `.venv/bin/ruff format --check . && .venv/bin/ruff check .`: 316 files formatted; lint clean.
- PASS — `.venv/bin/python -m compileall -q mediaflow tests scripts`.
- PASS — `python3 scripts/check_governance.py`; `git diff --check`; explicit Task manifest/private-file/reference-image audit; changed-source FFmpeg/FFprobe/private-key exclusion audit.
- UNAVAILABLE — `python3 -u scripts/docker_release_security_smoke_test.py --image mediaflow:task39-2-validation`, run twice in `/tmp/mediaflow-task39-candidate-efomxm1u` with all final Task source/test files verified byte-for-byte against this workspace. Both commands exited 1 before application validation: Docker Hub returned EOF fetching `node:22-bookworm-slim` metadata, then the anonymous token for `python:3.13-slim`. Logs: `/tmp/mediaflow-task39-release-security-exact.log` and `/tmp/mediaflow-task39-release-security-retry.log`. A previous candidate run passed but is not claimed as final-code evidence. The first repository-HEAD attempt was deliberately interrupted because it would not include uncommitted implementation.

Controlled visual evidence (generated/ignored, not committed):

- `web/test-results/storage-closed-1536x1024.png`
- `web/test-results/storage-drawer-step1-1536x1024.png`
- `web/test-results/storage-drawer-long-form-1536x1024.png`

Inspected against unchanged `docs/pics/储存管理.png` (SHA-256
`5e3aa806a081aaa52afdb79e0442e751e793aedcb1e4dd4616049f15e3b3df44`). Browser assertions
also cover narrow width and keyboard/focus; the desktop assertion checks a readable name/ID column
while the drawer is open. No pixel-equality claim or production-provider browser claim is made.

Earlier validation found and corrected missing Add fencing, an insufficient verification gate,
legacy unnamed projection handling and outdated Save assertions. One multi-scenario Web test hit
its 5-second limit under concurrent gates; its five scenarios now run as separate parameterized
cases with the same assertions, without changing timeout limits or skipping coverage.

### Decisions

- Reuse Managed Configuration and checked activation; no second Storage repository or adapter registry. Add authority is captured by a bounded read instead of making the operator handle revisions.
- An enabled unreferenced Storage still needs its own root read check before Save reports success. Disabled unreferenced entries remain configuration facts and receive no misleading passed connection claim.
- Readiness exposes deployment environment-reference names and SET/UNSET only. No real external account or credential was used.
- Explicit state verification can refresh a stale edit's authority only after displaying current Storage context; input stays correctable and a subsequent Save remains an explicit action. If an unknown Add already exists, direct the operator to inspect/edit it instead of replaying creation.
- Docker release-security was treated as material to the new authenticated API/Web composition. No database schema, migration, package dependency or deployment manifest changed; no additional migration gate applies.

### Remaining In-Slice Work

Copy, dedicated enable/disable and reference-protected configuration removal (`RO-4`) remain outside
this Task, as specified by B. No next Task or Slice outcome is defined here.

### Risks / Deviations

- The final-candidate Docker release-security gate is UNAVAILABLE due to the external registry failures above; B must assess this missing evidence.
- Existing workspace Storage implementation was inspected and completed. Pre-existing `docs/pics/媒体库页.png` deletion, `docs/pics/文件页.png` modification and untracked `docs/pics/媒体库.png` were preserved and excluded. `SLICE.md`, Roadmap and the committed Storage reference are untouched.
- `config/alist.json` remains ignored, untracked and unstaged; its contents were not read. Screenshots/test traces and `/tmp` validation logs are local generated evidence only.
- Python emits SQLite ResourceWarnings; jsdom reports unimplemented `window.scrollTo`; the build reports a >500 kB bundle advisory. These messages are recorded separately from actual test results.
- No production SMB/OpenList/S3/TMDB acceptance was attempted. Browser proof uses the local fake API; Python proves the actual application/API behavior independently.

### Checkpoint

The SHA below is the implementation checkpoint. This report is recorded in a following
documentation-only commit so it can name the actual immutable SHA. Neither commit is pushed.

```text
Status: READY FOR B REVIEW
Head SHA: 3a57dc374908aeebc3eaa06e826c27bb50e5db92
```

## B Review Result

```text
Reviewed: NOT SET
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```
