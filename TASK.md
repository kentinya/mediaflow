# Task 39.4 — Restore Storage inventory and setup recovery

This Task follows [the development workflow](docs/development-workflow.md) and implements the
bounded correction requested by [A Final Review](SLICE.md#a-final-review).

```text
Task ID: 39.4
Parent Slice: 39
Status: PLANNED
Task Base: 3779d203821930ad898fea49df2cee796c7a1c79
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Restore the Storage workspace's configuration-read and recovery journey: every provider-valid
OpenList root remains usable after Save and reload, and an operator without an initial managed
runtime can enter the existing setup workflow, continue it and return to the actual Active Storage
inventory. Resolve both A P1 blockers within existing RO-2/RO-3/RO-6 and API/Web parity under RO-7.

## Why This Task Exists

A rejected the previously submitted Slice at checkpoint
`3779d203821930ad898fea49df2cee796c7a1c79` after real reproductions established two broken states of
the same workspace: a legal saved OpenList configuration makes inventory decoding fail, and the
setup-required state tells the operator to initialize without providing its recovery handoff.

The real API accepts an unreferenced disabled OpenList object with `rootPath: ""` in a complete
Local-backed managed runtime. Save and inventory return 200, but the production Web normalizer
rejects that empty path. An otherwise identical `/` projection succeeds. Separately, a real
management-only instance exposes no setup action in the Storage page body, while V1 Configuration
already supports first-Draft creation/resume after authentication. These are production-supported
states, not future-adapter or reduced-capability scenarios.

This is one coherent readability/recovery correction, not a Task for one field or link. The three
passed Tasks and their Bases remain historical. Task Base is the actual committed A-review Head;
Slice Base remains `d02539e49d5c99c3e3c0c70de5e994e42824a18e`. No implementation has begun.
High/T4 reflects validation of Active-state truth and recovery across V1/V2 authentication and
checked publication; the correction must reuse those authorities rather than redesign them.

## Implementation Scope

Existing application/API projections → typed Web normalization and display → existing setup
handoff/return → integration and browser proof. No new domain model, repository or setup engine.

- Inspect `normalizeLocation` and the inventory/detail projections it consumes. Accept the empty
  string when it is a valid provider root; keep other required field types, lengths and shapes
  strict. OpenList empty and `/` mean its service root. Preserve root values through prefilled Edit
  and show a clear provider-root label in list/detail/confirmation where needed. Existing valid
  non-empty roots and other providers retain their established semantics; Local confinement stays
  unchanged. Do not replace every missing/invalid value with `/` or drop the offending row.
- Complete the saved-configuration round trip: Add → checked Save → refreshed full inventory →
  detail → Edit → reload. Existing empty-root entries must become readable after deploying the fix
  without re-saving, deleting/recreating configuration, editing SQLite or moving media. A failed
  follow-up read does not prove that Save was rolled back; preserve known results and existing
  explicit unknown-outcome verification without automatically repeating Add/Save/activation.
- Give a genuinely setup-required Storage empty state an explicit `去完成设置` action or equivalent
  that reaches the existing V1 `/ui` Configuration workflow. Reuse existing management readiness,
  first-Draft creation/resume and checked activation. A small existing-V1 entry/return affordance
  and bounded read-projection adjustment are allowed if necessary. The entry must not merely
  create another migration dead end or make the user discover the required page independently.
- Retain/resume unfinished setup. Provide an explicit path back to `/ui-v2/storage` after completing
  the existing workflow; refetch current authority on return/reconnect. Navigation and page reads
  must not create a Draft, run checks, activate or start media work. Draft creation remains explicit;
  duplicate navigation must not produce duplicate initialization. No global post-login onboarding
  or native V2 setup wizard is included.
- Keep no initial setup, existing-but-unavailable Active, malformed inventory and denied authority
  distinct. An administrator gets the applicable existing setup/configuration recovery path; a
  viewer gets truthful administrator guidance without mutation controls. Retain correctable input
  and permission/error information. Never infer that an empty or malformed list means initialization
  should be repeated.
- Preserve memory-only Bearer authentication and backend RBAC. Existing V1 re-authentication is
  acceptable; do not put tokens in URLs, browser persistence or a new handoff mechanism. Return
  targets must be fixed or same-origin allowlisted application routes. Complete the keyboard and
  narrow-screen action/return interaction using existing components.
- Preserve A's Contract, deferrals, Roadmap and reference image. Keep all pre-existing unrelated
  image changes and private configuration outside the implementation checkpoint. Record factual
  resolution of the known defect in configuration guidance as part of the completed behavior;
  Developer does not edit the A-owned Slice or change B's criteria to make the Task pass.

## Acceptance Criteria

- [ ] A legitimate OpenList object with an empty root, including an already-saved disabled entry,
      appears alongside other valid entries in inventory and detail. `/` and a valid subdirectory
      also work. The UI labels the provider root truthfully and prefilled Edit preserves its value;
      reload and subsequent operations do not produce a malformed-inventory error.
- [ ] Actual checked Add/Save followed by API inventory and Web decoding completes the round trip.
      The regression uses real application/API projections, not only hand-authored frontend JSON.
      No configuration/data rewrite is needed for existing empty-root entries. Unrelated malformed
      types/oversized fields and invalid Local roots remain rejected; no row is silently omitted.
- [ ] An authenticated administrator on a fresh instance can use the Storage empty-state action to
      reach existing first setup, explicitly create or resume its configuration and complete the
      existing checked publication. Returning to Storage shows the actual initialized inventory.
      An existing incomplete setup survives navigation/reload/reconnect and can be continued.
- [ ] The journey includes an explicit reachable return from setup to Storage. Keyboard, narrow
      layout and normal authentication continuation work. Tokens never cross URLs/persistent
      browser storage; arbitrary return URLs are not accepted. A viewer cannot create or activate
      setup and receives a meaningful administrator handoff.
- [ ] Missing setup, unavailable Active and malformed read states remain distinguishable. Invalid
      fields, failed checks, stale authority and unknown activation outcomes retain truthful durable
      state and the existing safe correction/verification path. Navigation/read/return never creates
      duplicate Drafts, silently retries Save/activation or starts scans, media Tasks or Storage writes.
- [ ] Existing inventory/search/provider filtering, Add/Edit, row lifecycle actions, diagnostics,
      V1 setup and general Configuration remain compatible. Full graph validation, exact evidence,
      runtime publication, references, audit and confinement are unchanged. The assigned gates pass
      with truthful totals/skips and any externally unavailable validation explicitly reported.

## Required Tests

Use temporary state, actual Local adapters and fake/local OpenList services where reads are needed.
A disabled OpenList root-listing case is valid and needs no external provider. Never use production
credentials, private configuration or user media. Do not weaken tests/assertions or add hidden skips.

- Focused Python/API integration:
  `.venv/bin/python -m unittest tests.test_management_setup tests.test_v2_storage_operations tests.test_storage_page_local_save tests.test_configuration_objects`.
  Cover provider-root Save/inventory/detail consistency and actual fresh/resumable setup authority.
- Focused Web normalization/API/component tests:
  `cd web && npm test -- --run src/entities/storage/storage-management.test.ts src/entities/storage/storage-form.test.ts src/shared/api/storage-management-api.test.ts src/features/storage/StorageManagementPage.test.tsx`.
  Cover empty/slash/non-empty roots, real backend response fixtures, existing saved entries,
  unrelated malformed payload rejection and the distinct setup/unavailable/denied states.
- Browser integration:
  `cd web && npm run test:e2e -- --grep 'Storage management'` plus any affected V1/setup browser
  coverage introduced by the correction. Prove the complete round trip and setup handoff, resume,
  explicit completion, return, authenticated refresh, viewer denial and no side effects on
  navigation. At least one integration proof uses the actual application/API and temporary managed
  state for the return to an initialized inventory; a mocked button destination alone is insufficient.
- `.venv/bin/python -m unittest discover -s tests` for complete Python regression.
- `cd web && npm test -- --run` for complete Web regression.
- `cd web && npm run typecheck && npm run lint && npm run format:check && npm run build`.
- `.venv/bin/ruff format --check . && .venv/bin/ruff check .` and
  `.venv/bin/python -m compileall -q mediaflow tests scripts`.
- `python3 scripts/check_governance.py`, `git diff --check`, exact checkpoint/private-file audit,
  secret-output audit and FFmpeg/FFprobe exclusion audit. No unrelated images or `config/alist.json`.
- `python3 -u scripts/docker_release_security_smoke_test.py --image mediaflow:task39-4-validation`
  against the committed candidate, covering the Python-served V1/V2 composition. Report actual
  failure/unavailability instead of substituting an earlier checkpoint's result. No new migration
  gate is required unless the actual implementation changes persistence, which is outside this
  planned read/handoff correction and must first be raised to B/A.

## Non-goals

- Full native V2 first-setup wizard, global post-login onboarding, general Configuration or System
  Settings redesign, new identity/session/token-transfer mechanisms or secret-value entry.
- New configuration authority, activation shortcuts, schema/data migration, automatic initialization,
  workflow defaults, media jobs, Storage mutation, write probes or provider additions/switching.
- Broad normalizer refactoring, label-only polish, new per-field/per-test Tasks or changing the Slice
  Contract/Base, passed Task history, reference image or unrelated/private files.
- Declaring Slice PASS/CLOSED. This is an A-requested correction: after Task PASS, B returns Slice
  status to READY FOR A REVIEW with the corrected Head and evidence, without issuing A acceptance.

## Developer Completion Report

### Changed Files

Production (6):

- `mediaflow/application/configuration_objects.py` — the bounded `setup` authority block on the
  Storage inventory projection, projected from the one existing
  `ManagedConfigurationService.status_document()` plus the fixed `_V1_SETUP_PATH` constant.
- `mediaflow/interfaces/service_api.py` — backend-authoritative `canStartSetup` on both the
  available and unavailable inventory responses.
- `mediaflow/interfaces/operator_ui.py` — explicit `Return to Storage management` link on the V1
  Configuration view once a managed Active exists.
- `web/src/entities/storage/storage-management.ts` — `PROVIDER_ROOT_LABEL`, `normalizeRootPath`
  accepting the provider-valid empty root byte-exactly, `StorageSetupAuthority` and its strict
  normalizer with the `SETUP_ROUTE` allowlist, and the `canStartSetup`/`setup` model fields.
- `web/src/entities/storage/storage-form.ts` — confirmation summary names an empty remote root as
  the provider root instead of `未填写`.
- `web/src/features/storage/StorageManagementPage.tsx` — truthful `locationLabel`/`rootPathLabel`
  and the new `StorageSetupHandoff` rendering the three distinct unavailable states.

Tests and browser fixtures (9):

- `tests/test_storage_page_local_save.py`, `tests/test_v2_storage_operations.py`,
  `tests/test_management_setup.py`
- `web/src/entities/storage/storage-management.test.ts`, `web/src/entities/storage/storage-form.test.ts`,
  `web/src/shared/api/storage-management-api.test.ts`,
  `web/src/features/storage/StorageManagementPage.test.tsx`
- `web/tests/fake-server.mjs`, `web/tests/e2e/storage-management.spec.ts`

### Implemented

**P1 — provider-valid empty root.** The backend already accepted, stored and projected
`rootPath: ""` (OpenList `_normalize_root` resolves `""` and `/` to the same service root), so no
Python validation changed. The defect was frontend-only: `normalizeLocation` routed the empty
string through the non-empty `normalizeBoundedText`, so one legal saved object made the whole
workspace report `存储管理不可用` and read like a failed Save. A dedicated `normalizeRootPath` now
accepts `""`, `null` and `undefined`, preserves the value byte for byte (trimming would silently
retarget a path that addresses the same resource — `/Media/ ` and `/Media` are different entries),
and still rejects whitespace-only, non-string, NUL and oversized roots as malformed. An empty root
renders as `提供商根目录` in list, detail and confirmation, keeping it distinct from a stored `/`;
a prefilled Edit keeps the stored value unchanged. Local confinement, remote traversal rejection,
oversized-field rejection and every unrelated payload check are untouched, and no row is dropped.

**P1 — setup recovery.** The inventory projection now carries a bounded `setup` block that reuses
the single existing status document rather than creating a second authority, plus the
backend-authoritative `canStartSetup`. The page renders three distinct states — first setup
outstanding, existing-but-unavailable Active, and unreadable snapshot — so initialization is never
suggested for the latter two. An administrator gets `去完成设置` into the existing V1 workflow,
which already auto-selects Configuration on Connect and owns first-Draft creation, guided setup,
checked validation and checked activation. A viewer gets administrator guidance and no unusable
control. The V1 Configuration view gains an explicit return to `/ui-v2/storage`. Both links are
fixed same-origin application routes carrying no token, and the normalizer rejects any other
target. Reading the state is a pure read: no Draft, no check, no activation, no media work.

### Tests and Results

- `.venv/bin/python -m unittest tests.test_management_setup tests.test_v2_storage_operations tests.test_storage_page_local_save tests.test_configuration_objects` — **PASS**, 128 tests, 0 skips, 24.4 s. (Task Base runs the same command at 121 tests, so this Task added 7.)
- `cd web && npm test -- --run src/entities/storage/storage-management.test.ts src/entities/storage/storage-form.test.ts src/shared/api/storage-management-api.test.ts src/features/storage/StorageManagementPage.test.tsx` — **PASS**, 113 tests (was 91).
- `cd web && npm run test:e2e -- --grep 'Storage management'` — **PASS**, 29 Chromium tests, 0 skips, 35.1 s against the rebuilt artifact (was 24; 5 added).
- `.venv/bin/python -m unittest discover -s tests` — **PASS**, 1,843 tests, 7 skips, 334.8 s.
  The +7 delta matches the focused gate exactly (121 → 128). Skips are the pre-existing isolated
  real OpenList/SMB/S3 acceptance and endurance profiles that need external services; no production
  service, credential or user media was used.
- `cd web && npm test -- --run` — **PASS**, 724 tests / 47 files, 0 skips, 282.6 s.
- `cd web && npm run typecheck && npm run lint && npm run format:check && npm run build` — **PASS**.
- `.venv/bin/ruff format --check . && .venv/bin/ruff check .` — **PASS**, 316 files formatted.
  `.venv/bin/python -m compileall -q mediaflow tests scripts` — **PASS**.
- `python3 scripts/check_governance.py` — **PASS** (also re-run against the new Head).
  `git diff --check` — **PASS**. Secret-value audit over the staged diff — **PASS** (only the
  pre-existing throwaway `admin-token` / `viewer-token` test labels). FFmpeg/FFprobe exclusion
  audit over every changed file — **PASS** (no match). `config/alist.json` confirmed still ignored,
  untracked and absent from the manifest.
- `python3 -u scripts/docker_release_security_smoke_test.py --image mediaflow:task39-4-validation`
  — **FAIL / PRE-EXISTING / UNRELATED**. The gate fails identically at the Task Base
  `3779d203821930ad898fea49df2cee796c7a1c79` and at this Head, on a clean `/tmp`, with the same
  error: `docker compose up` reports `bind source path does not exist: …/mediaflow.json` for the
  harness's own temporary deployment root. Verified: the image builds and the compose topology
  renders correctly (the rendered bind points at the file the harness just created, mode 0644);
  only the daemon-side bind resolution of that short-lived path fails. `scripts/docker_smoke_test.py`,
  `scripts/docker_release_security_smoke_test.py`, `compose.yaml` and `Dockerfile` are
  **byte-identical** (md5) between the Task Base and this Head, and this checkpoint modifies **no**
  deployment, packaging or compose file. Per the workflow this is reported, not self-cleared; the
  unavailability of this gate is a judgement for B. I did not substitute an earlier checkpoint's
  result.

### Decisions

- Fixed the defect at the normalization boundary rather than widening the backend. The backend
  already stores and projects the empty root correctly, and A's contract is that the frontend must
  accept provider-valid input; changing domain validation would have altered unrelated providers.
- Wrote a dedicated `normalizeRootPath` instead of relaxing the shared `normalizeBoundedText`.
  The shared helper trims and rejects empty, and it is used by many other entities; changing it
  would weaken unrelated checks. The new helper mirrors the existing `normalizeReferencePath`
  precedent, which already accepts `""` for a library bound to the provider root.
- Added the setup authority to the existing inventory projection rather than a new endpoint or
  wizard. The Task and A's boundary require reusing the current authority; `/api/v1/management/readiness`
  exists but is a second read to reconcile, and keying the affordance on `reason === "no_active"`
  alone cannot separate an existing-but-unavailable Active, which A requires.
- Carried only the *presence* of a setup Draft across the projection, never its revision ID, so the
  Storage page cannot become a second place that addresses a specific Draft.
- Made `canStartSetup` backend-authoritative rather than inferring it from `canManage`, so a viewer
  is never shown a control it cannot use, matching V1's existing read-only branch.
- Used plain `<a href>` for both handoffs, matching the existing `MigrationPage` V1 link, because
  `/ui` and the V2 return are outside the `/ui-v2` router basepath. No token bridge, no return-URL
  round trip: the existing V1 re-authentication prompt remains the continuation step.
- Rendered the three unavailable states from distinct flags rather than the `reason` string, and
  added a cross-check in the normalizer that rejects a readable inventory that still claims setup is
  outstanding, so a mixed or stale response cannot push the operator into a needless initialization.

### Remaining In-Slice Work

None that I know of that belongs to this Task. Both A P1 blockers are addressed in this checkpoint;
whether the Slice's Required Outcomes are now all satisfied is B's call, and I am not asserting
Slice status.

### Risks / Deviations

- The Docker release-security gate is **UNAVAILABLE** in this environment for a pre-existing reason
  documented under Tests and Results. It is the only T4 gate that did not pass, and it is not caused
  by this change.
- V2 `/ui-v2/storage` → `/ui` requires the operator to re-enter the API token in the V1 console, and
  returning re-enters it in V2. This is the existing memory-only Bearer model the Task explicitly
  permits; I did not add a token-transfer mechanism. If B judges that friction too high, it is a
  product decision to escalate to A, not something to fix inside this Task.
- The e2e setup handoff navigates to a deliberately minimal V1 stand-in served by the fake server.
  The real V1 console's create/resume/return behavior is proved by the Python operator-UI and
  management-setup tests against the real backend; the browser proof covers the V2 side of the
  journey and that navigation issues no mutating request.
- Pre-existing `docs/pics/*.png` modifications (one deleted, one modified, one untracked) remain
  outside this checkpoint and untouched; `docs/pics/储存管理.png` is unchanged.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 466337c1337d0b03315d813ba258124538565cc1
```


## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```
