# Task 40.2 — V2 Settings lifecycle and bounded configuration editing

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the checkpointed [Slice 40 Contract](SLICE.md).

```text
Task ID: 40.2
Parent Slice: 40
Status: READY FOR B REVIEW
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
`web/src/features/configuration/ConfigurationPage.tsx`, `web/src/features/configuration/ConfigurationPage.test.tsx`, `web/src/shared/api/configuration-api.ts`, `web/src/routes/router.tsx`
`web/src/features/configuration/ConfigurationPage.tsx`, `web/src/features/configuration/ConfigurationPage.test.tsx`, `web/src/shared/api/configuration-api.ts`, `web/src/routes/router.tsx`
Correction pass updates these same Settings files for B's three blockers.
Second correction pass also updates `web/src/shared/api/configuration-api.ts` for bounded 409 conflict details.

### Implemented
将 `/ui-v2/configuration` 替换为认证的 React Settings 页面：读取后端权威状态，区分 setup-required、Draft、empty/populated Active 与不可用 authority；提供显式首 Draft/恢复、Revision JSON 检查、脱敏包导出、Draft 验证与 checked-activate。System Settings 编辑仅从后端 `sections` allowlist 生成字段选择器并携带精确版本/Active fencing，所有写操作都由显式按钮触发；复用统一授权边界保留 401/403 行为，失败提示保持有界且不暴露原始异常或秘密。
将 `/ui-v2/configuration` 替换为认证的 React Settings 页面：读取后端权威状态，区分 setup-required、Draft、empty/populated Active 与不可用 authority；提供显式首 Draft/恢复、Revision JSON 检查、脱敏包导出、Draft 验证与 checked-activate。System Settings 编辑仅从后端 `sections` allowlist 生成字段选择器并携带精确版本/Active fencing，所有写操作都由显式按钮触发；复用统一授权边界保留 401/403 行为，失败提示保持有界且不暴露原始异常或秘密。

### Tests and Results
- `python3 scripts/check_governance.py` — PASS
- `.venv/bin/python -m unittest tests.test_management_setup tests.test_configuration_snapshot tests.test_system_settings_management tests.test_configuration_objects tests.test_runtime_strategy_configuration` — PASS (160)
- `.venv/bin/python -m unittest discover -s tests` — PASS
- `cd web && npm test -- --run` — PASS
- `cd web && npm run typecheck && npm run lint && npm run format:check && npm run build` — PASS
- `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/python -m compileall -q mediaflow tests scripts` — PASS
- `.venv/bin/python scripts/docker_release_security_smoke_test.py` — PASS
- `git diff --check` — PASS
 - `cd web && npm run typecheck` — PASS
 - `cd web && npm test -- --run src/features/configuration/ConfigurationPage.test.tsx` — PASS (3 tests)
 - `cd web && npm test -- --run src/routes/router.test.tsx` — PASS (3 tests)
 - `cd web && npm run lint` — PASS
 - `cd web && npm run format:check` — PASS
 - `cd web && npm run build` — PASS (Vite bundle-size advisory only)
 - `python3 scripts/check_governance.py` — PASS
 - `git diff --check` — PASS
- Correction focused test: `cd web && npm test -- --run src/features/configuration/ConfigurationPage.test.tsx` — PASS (5 tests)
- Second correction focused test: `cd web && npm test -- --run src/features/configuration/ConfigurationPage.test.tsx` — PASS (7 tests)

### Decisions
前端只消费既有 configuration/status、revision、system settings、validate/activate 与 package export 契约，不新增配置消费者或绕过后端权限。Revision JSON 使用后端 detail 的已脱敏 `document`；Active 与 Draft 用独立标签呈现。页面刷新只重新读取状态，不自动创建、验证或激活。
前端只消费既有 configuration/status、revision、system settings、validate/activate 与 package export 契约，不新增配置消费者或绕过后端权限。Revision JSON 使用后端 detail 的已脱敏 `document`；Active 与 Draft 用独立标签呈现。页面刷新只重新读取状态，不自动创建、验证或激活。

### Remaining In-Slice Work
Resident Worker/Scheduler/Notification 生命周期、部署/Compose 变化及其他 Slice 40 Required Outcomes 仍不属于本 Task。
Resident Worker/Scheduler/Notification 生命周期、部署/Compose 变化及其他 Slice 40 Required Outcomes 仍不属于本 Task。

### Risks / Deviations
本次只完成 Web Settings 垂直面；工作树中原有的文档图片未纳入提交。
本次只完成 Web Settings 垂直面；Correction pass reran the full Python/Web T4 gates. Only pre-existing ResourceWarning output remains, with no test failures. 工作树中原有的文档图片未纳入提交。
Second correction fixes Active `revisionVersion` fencing and preserves bounded first-Draft 409 recovery identity; no new external dependency or authority is introduced.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: [correction commit SHA]
```

## B Review Result

```text
Reviewed: 95667df757b3682b01dad024cc586d726e8cd89b..d2849c9006bdd365f1d1b05cab21ec2cb4c86dde
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.

- Active-to-successor System Settings edits send the wrong optimistic identity. The page constructs
  `expectedActiveVersion: active.version` at `ConfigurationPage.tsx:143-150`, while the production
  successor path compares against `active.revision_sequence` (`mediaflow/application/configuration_snapshot.py:513-536`).
  The repository contract explicitly keeps the immutable `revisionVersion` distinct from the
  mutable Draft edit token (`mediaflow/domain/system_settings.py:396-403`), and the existing API
  test requires Active edits to send `expectedActiveVersion: active_view["revisionVersion"]`
  (`tests/test_system_settings_management.py:631-642`). In a legal published configuration whose
  mutable `version` differs from its revision sequence, an administrator cannot create a successor
  Draft from the Settings page and the required Active → edit journey is broken. Use the exact
  Active revision identity (`revisionVersion`/revision sequence) and add a focused Web/API regression
  that first advances the Active edit/version independently, then saves Settings from Active.
- Repeated first-Draft creation does not expose the durable conflict/recovery state. The backend
  returns a bounded 409 with `durableState: setup_draft_preserved`, the existing Draft identity and
  a resume action (`tests/test_management_setup.py:327-336`), but `createFirstDraft`/`request` maps
  every non-2xx response to the generic `ConfigurationApiError` and the mutation handler only shows
  `操作未完成...` (`web/src/shared/api/configuration-api.ts:35-43`,
  `web/src/features/configuration/ConfigurationPage.tsx:75-84`). In the current legal production
  journey, a concurrent/repeated click therefore hides the exact durable Draft and tells the admin
  only to refresh, violating RO-1's explicit repeated-creation recovery and the Task's conflict
  acceptance. Preserve a bounded conflict category/details (without raw exceptions/secrets), render
  the existing Draft/resume action, and add a focused Web regression for a 409 first-Draft response.
