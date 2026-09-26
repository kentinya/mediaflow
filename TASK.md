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

Pending implementation.

### Implemented

Pending implementation.

### Tests and Results

Pending implementation; A's reproduction/baseline results are not completion evidence for this Task.

### Decisions

Use the existing managed authority and V1 setup journey within A's bounded correction scope.

### Remaining In-Slice Work

Both A P1 blockers remain unresolved until implementation and review.

### Risks / Deviations

None approved. Escalate any necessary change to authentication, activation or the Slice boundary.

### Checkpoint

```text
Status: PLANNED
Head SHA: NOT CREATED
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```
