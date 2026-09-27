# Task 40.1 — Empty runtime envelope and applicability-aware activation

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the checkpointed [Slice 40 Contract](SLICE.md).

```text
Task ID: 40.1
Parent Slice: 40
Status: FIX REQUIRED
Task Base: 8ac3292b4baed443de34f7a37989bf105cf0b42d
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Make the server-owned first-setup document a legal, explicit empty runtime that an administrator can
validate and activate through the existing Settings/configuration API, while keeping all populated
object and reference validation strict. This advances Slice 40 Required Outcomes RO-1 and RO-2 and
provides the common applicability contract required by later Settings, library, Worker, Scheduler and
Notification tasks.

## Why This Task Exists

`build_first_setup_starter_document` intentionally emits empty business collections, but the current
complete runtime loader still rejects empty recognition types/rules/type policies (and the resulting
activation path assumes every check is applicable). A fresh installation therefore cannot turn the
existing durable first Draft into a valid Active baseline without invented development strategy data.
The existing API and V2 Settings surface already expose first-Draft, validation and checked activation;
the largest independent next unit is to make that authority truthful at the shared runtime and
activation boundary before adding resident-process or business-page behavior.

## Implementation Scope

Domain/application/runtime configuration → Managed Configuration validation and checked activation →
existing authenticated configuration/readiness API and Settings projection → focused regression tests.

- Accept the supported empty business envelope in the production managed runtime loader and expose
  explicit empty capability state; never merge development/example strategy objects or synthetic
  providers, libraries, policies, destinations, schedules or webhooks.
- Preserve strict schema, value, uniqueness, path and declared-reference checks for every populated
  collection. A declared broken relation remains invalid; an absent capability is unconfigured.
- Centralize applicability decisions used by validation/checked activation and existing successor
  paths: empty Storage/library families need no imaginary probe, an enabled source with applicable
  recognition configuration requires the exact current offline strategy evidence, and an enabled
  destination/policy chain requires the exact current read-only destination precheck. Existing
  exact-revision evidence, secret readiness and concurrency fencing remain authoritative.
- Make the existing configuration/readiness responses distinguish valid empty Active from missing,
  invalid or unavailable Active, with bounded capability/unconfigured wording and no secrets/raw
  exceptions. Viewer/admin permissions and API/Web shared behavior remain unchanged.
- Keep the implementation limited to the managed configuration/runtime/activation boundary and its
  existing Settings/API projection. Do not implement resident service adoption, Compose mounts,
  Scheduler/Notification lifecycle, new policy workspaces or a new setup flow in this Task.

## Acceptance Criteria

- [ ] The actual starter document from `build_first_setup_starter_document` loads through the same
      managed runtime validator used by activation, with zero business objects and no development or
      synthetic defaults; the resulting runtime carries explicit empty capability collections.
- [ ] Through the existing authenticated configuration API, an administrator can create/resume the
      one first Draft, validate it, and checked-activate the untouched empty document. Activation is
      atomic, pins the exact immutable revision/digest, preserves bootstrap database/principal
      authority, and creates no media Job/Task, scan, metadata request, notification or Storage
      mutation.
- [ ] A valid empty Active is reported distinctly from setup-required, missing, corrupt, schema-
      unsupported and runtime-invalid authority. Status/readiness and Settings projections identify
      media business capabilities as unconfigured/not applicable and provide a bounded next action;
      no secret, token, deployment authority or raw exception is exposed.
- [ ] Populated objects still enforce existing type/value/uniqueness/path/reference rules, including
      dangling references and malformed collection types. A broken declared dependency cannot be
      relabelled not-applicable, while an absent optional family does not require fabricated checks.
- [ ] Checked activation and existing successor publication consume one shared applicability decision:
      current exact-revision Storage evidence is required only for enabled referenced Storage;
      Recognition Strategy evidence is required only for an enabled applicable source/configuration;
      destination precheck is required only for an enabled applicable destination/policy chain.
      Stale, failed, missing or changed-secret evidence still fails closed and leaves prior Active and
      correctable Draft state unchanged.
- [ ] RecognitionType identity semantics, OrganizerExecutor-only mutation, Storage confinement,
      redaction, RBAC, optimistic concurrency and existing non-empty configuration behavior remain
      intact, including the RecognitionType C → Naming/Classification A regression.
- [ ] The assigned T4 tests and quality gates pass with honest command output and no skipped or
      weakened assertions; the checkpoint contains only this Task's coherent changes.

## Required Tests

- `.venv/bin/python -m unittest tests.test_management_setup tests.test_configuration_objects tests.test_configuration_snapshot tests.test_runtime_configuration` (or the repository's exact existing runtime/configuration test module names if one differs): empty starter load/validate/activate, status/readiness projections, permissions, concurrency, invalid populated references, stale/failed evidence, zero-mutation and no-work proofs.
- Relevant existing API/Web configuration tests, including `tests.test_operator_ui`, for truthful empty/unconfigured status and redaction without changing the established Settings journey.
- `.venv/bin/python -m unittest discover -s tests`.
- `cd web && npm test -- --run` plus `npm run typecheck`, `npm run lint`, `npm run format:check`, and `npm run build` when the implementation changes the existing Settings/API projection consumed by Web.
- `.venv/bin/ruff format --check . && .venv/bin/ruff check .` and `.venv/bin/python -m compileall -q mediaflow tests scripts`.
- `.venv/bin/python scripts/docker_release_security_smoke_test.py` (the T4 release/security gate).
- `python3 scripts/check_governance.py`, `git diff --check`, exact Base..Head manifest review, secret/private-config audit, and FFmpeg/FFprobe exclusion audit.

## Non-goals

- Work outside Slice 40 or changes to Required Outcomes, Required Surfaces, Safety Invariants,
  Slice Base, Roadmap or the canonical product scope.
- Resident Worker/Scheduler/Notification adoption, process identity/heartbeat changes, Compose mount
  and health redesign, Docker lifecycle proofs or migration/schema redesign.
- Full native policy/Recognition/Review workspace migration, new providers/adapters/commands,
  mandatory media-business onboarding, generated business defaults, or automatic activation.
- Unrestricted JSON writes, deployment database/principal/token editing, secret resolution into
  documents, silent fallback to bootstrap/cache, mutation-based diagnostics, uncertain replay,
  overwrite/delete fallback, or any weakening of existing safety/concurrency gates.
- P2 wording/cleanup, optional proof unrelated to the acceptance criteria, or declaring the Slice
  PASS/CLOSED.

## Developer Completion Report

### Changed Files
`mediaflow/infrastructure/strategy_user_configuration.py`, `mediaflow/application/configuration_snapshot.py`, `mediaflow/infrastructure/configuration_snapshot.py`, `mediaflow/interfaces/service_api.py`, `mediaflow/application/configuration_objects.py`, `tests/test_runtime_strategy_configuration.py`, `tests/test_media_library_activation.py`, `tests/test_configuration_destination_activation.py`

### Implemented
允许 managed runtime 使用显式空业务集合；保留数组、对象、唯一性、路径和声明引用校验，不加载 development/default strategy。配置状态/API readiness 现在区分空 Active，并提供不含秘密的能力状态与下一步。Destination precheck 仅在启用 MediaLibrary 存在且有完整启用的 RecognitionType → Naming → Classification 指向该库 → Organize 链时适用；classification 使用 `library` 时按 runtime 相同 slug fallback 解析。空 Active 可先保存 Storage 和 browse-only MediaLibrary。补充 starter、nested webhook、slug chain 与空 Active → Storage → MediaLibrary API 回归测试。

### Tests and Results
 - `.venv/bin/python -m unittest tests.test_configuration_destination_activation tests.test_media_library_activation tests.test_configuration_objects tests.test_management_setup tests.test_runtime_strategy_configuration` — PASS (126)
 - Slug-routing destination applicability regression — PASS (35 focused destination/media tests)
 - B blocker reproduction command from `config/strategy.example.json` — PASS (`notification` is `CONFIGURED`)
 - Empty setup Active → Storage → browse-only MediaLibrary API regression — PASS
 - `.venv/bin/python -m unittest discover -s tests` — PASS (1858 tests; 7 skips)
 - `cd web && npm test -- --run` — PASS (727 tests, 47 files)
 - `cd web && npm run typecheck && npm run lint && npm run format:check && npm run build` — PASS
 - `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/python -m compileall -q mediaflow tests scripts` — PASS
 - `.venv/bin/python scripts/docker_release_security_smoke_test.py` — PASS
 - `python3 scripts/check_governance.py` — PASS
 - `git diff --check` — PASS; `config/alist.json` absent; no FFmpeg/FFprobe dependency added
 - `tests.test_runtime_configuration` — UNAVAILABLE (module does not exist; corresponding `tests.test_runtime_strategy_configuration` ran)

### Decisions
空策略集合表示合法未配置能力；只有 populated objects 才触发对应 runtime/reference checks。Destination evidence 对 browse-only 库不适用；声明但损坏的依赖仍由完整 runtime validation 拒绝。Classification destination identity 复用 parser 的显式 ID 优先、library slug fallback 语义。状态投影只暴露 bounded capability labels and next actions，不暴露文档内容、路径、凭据或 token。

### Remaining In-Slice Work
Resident Worker/Scheduler/Notification lifecycle and deployment/Compose changes remain outside this Task.

### Risks / Deviations
Correction 初次全量回归发现省略 `mediaLibraries` section 时的新 helper 抛错；按原有“无 destination 不适用”行为修复后重新跑全量并通过。B 本轮 slug blocker 已由显式 ID 优先、library slug fallback 修复。Earlier checkpoint's governance/release-document failures were resolved before this correction. Existing Web checks remain from the prior checkpoint; this correction changes no Web source/projection. Docker smoke passed against isolated stack.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: [pending correction checkpoint]
```

## B Review Result

```text
Reviewed: 8ac3292b4baed443de34f7a37989bf105cf0b42d..79d522fa48247e57e8601169e3fb77d3d0784271
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Destination applicability can be incorrectly treated as false for a valid configured processing
  chain when a classification rule uses the supported `library` field without explicit
  `mediaLibraryId`. Evidence: starting from `config/strategy.example.json`, remove each rule's
  `result.mediaLibraryId` and set its `result.library` to `Movies` or `TV` (the corresponding valid
  slugs `movies` and `tv`). `load_runtime_configuration(document)` succeeds and resolves enabled
  classification rules to both configured MediaLibraries, but
  `ConfigurationObjectService._destination_precheck_applicable(document)` returns `False` because
  it only reads explicit `result.mediaLibraryId` at `mediaflow/application/configuration_objects.py`
  near line 7642. This legal configuration is reachable through managed Settings/JSON import; checked
  activation and successor publication then omit required exact-revision destination evidence,
  violating Slice 40 RO-2's declared-chain applicability and this Task's conditional evidence
  acceptance. Derive routing through the same normalized classification/runtime parser (including
  the supported slug fallback) and add a regression proving this valid chain is applicable and
  cannot activate without current destination-precheck evidence.

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
