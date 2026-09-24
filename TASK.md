# Task 38.6 — Files/MediaLibrary 统一资源库选择上下文展示

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [Slice Contract](SLICE.md).

```text
Task ID: 38.6
Parent Slice: 38
Status: READY FOR B REVIEW
Task Base: 3e0c8643d63489c4fbca17ea194e437faf933535
Difficulty: Medium
Test Level: T2
Planner / Reviewer: A acting for B
```

## Goal

Unify the ResourceLibrary Files and MediaLibrary browse-page library selector presentation: cards
show only library identity/selection, while the selected-library context shows only enabled state
and exact configured path. This advances Slice 38 RO-1/RO-2 and preserves both pages' complete
existing user journeys.

## Why This Task Exists

The two delivered pages currently expose library facts differently. MediaLibrary cards repeat
Storage and root facts per card, while Files uses a different single/multi-library summary and may
show storage/count information. The A-approved presentation correction establishes one predictable
selection-and-context pattern for both routes. This is a focused Web presentation unit, not a new
configuration, Storage or file-operation capability.

## Implementation Scope

```text
Shared Web presentation
  → common library card geometry and selection/menu behavior
  → selected-library context with enabled state and exact root path only
  → ResourceLibrary Files and MediaLibrary integration
  → focused component/API-model/browser regression coverage
```

- Update the shared selector/context presentation used by `StorageFilesPage` and
  `MediaLibraryFilesPage`.
- Cards retain name, icon, selected state and independent removal/configuration action only.
- The selected context renders `已启用` and `路径: /...`; root is `/` and paths retain exact
  configured identity. Do not render Storage name/ID, media-library name duplication, file counts,
  capacity or statistics in this context.
- Keep Storage selection and binding details in Add/configuration drawers and actionable failure or
  setup recovery states.
- Preserve disabled-library filtering, route-specific directory/file behavior, ResourceLibrary
  Organize continuation, MediaLibrary command restrictions, accessibility, keyboard focus and
  narrow-screen behavior.
- Keep API payloads, Active configuration authority, route parameters and backend behavior unchanged.

## Acceptance Criteria

- [ ] `/ui-v2/resourcelib/files` and `/ui-v2/medialib/files` use the same card geometry, selected
      state, action-menu boundary and selected-context placement for one or many libraries.
- [ ] Every browse-page card shows only the library name/icon/selection/action affordance; no card
      renders Storage, Storage ID, root path, file count, capacity or statistics.
- [ ] The selected context shows only the truthful `已启用` state and exact `路径: /...`; switching
      libraries updates it without stale facts, and the root renders exactly as `/`.
- [ ] Storage remains available in Add/configuration steps and actionable recovery messages, while
      normal browse-page cards/context contain no Storage display.
- [ ] Disabled libraries remain hidden from browse selection; existing configuration re-enable and
      removal behavior remains intact.
- [ ] Files keeps its complete browse, direct-command, Organize and return-context journey, and
      MediaLibrary keeps its bounded command/configuration journey and no-Organize boundary.
- [ ] Focused Web/component/browser tests and the assigned T2 quality checks pass without weakened
      assertions, hidden skips or API behavior changes.

## Required Tests

- `npm --prefix web run test -- --run` (affected Web component/entity/API tests, including Files and
  MediaLibrary selector/context coverage).
- `npm --prefix web run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/medialib-files.spec.ts`
- `npm --prefix web run typecheck`
- `npm --prefix web run lint`
- `npm --prefix web run format:check`
- `git diff --check`
- `python3 scripts/check_governance.py`

## Non-goals

- New MediaLibrary or ResourceLibrary API behavior, Storage providers, configuration schema or
  Active-snapshot semantics.
- Changes to route/auth/deep-link behavior, file commands, transfer/recovery, Organize, permissions,
  Storage confinement or disabled-library lifecycle.
- Changes to the supplied reference images, thumbnails/statistics scope, page tables or file-row
  facts.
- Showing Storage in the normal browse-page card/context; configuration and recovery display remains
  explicitly allowed.
- Declaring Slice 38 PASS/CLOSED; B review remains required after Developer checkpoint.

## Developer Completion Report

### Changed Files

- `web/src/features/library/LibraryCardStrip.tsx`
- `web/src/features/library/StorageFilesPage.tsx`
- `web/src/features/library/MediaLibraryFilesPage.tsx`
- `web/src/features/library/MediaLibraryFilesPage.test.tsx`
- `web/src/shared/ui/styles.css`
- `web/tests/e2e/medialib-files.spec.ts`

### Implemented

- Unified ResourceLibrary and MediaLibrary browse selectors on the shared card strip.
- Browse cards now expose only icon, name, selection and the independent action menu.
- The selected-library context now shows `已启用` and the exact configured root path; `/` remains `/`.
- Preserved Storage facts in configuration/recovery surfaces, disabled-library filtering, route state,
  direct commands and the ResourceLibrary Organize continuation.
- Reused the shared card menu with MediaLibrary-specific icon, labels and removal action.

### Tests and Results

- `npm --prefix web run test -- --run` — PASS (43 files, 601 tests).
- `npm --prefix web run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/medialib-files.spec.ts` — PASS (46/46; rerun after `npm --prefix web run build` refreshed the served artifact).
- `npm --prefix web run typecheck` — PASS.
- `npm --prefix web run lint` — PASS.
- `npm --prefix web run format:check` — PASS.
- `npm --prefix web run build` — PASS (Vite emitted the existing chunk-size warning).
- `git diff --check` — PASS.
- `python3 scripts/check_governance.py` — PASS.

### Decisions

- The existing ResourceLibrary card strip is the shared presentation boundary; its item type and
  icon/menu labels are parameterized so both library kinds retain their own identity and actions.
- The root-path context is intentionally derived from the selected library only, so switching cards
  cannot leave stale facts from another library visible.

### Remaining In-Slice Work

- Other Slice 38 MediaLibrary configuration, browsing, direct-command and recovery outcomes remain
  outside this Task.

### Risks / Deviations

- The worktree contained a pre-existing modified `docs/pics/文件页.png`; it was preserved and excluded
  from this checkpoint.
- Playwright's first invocation used a stale static build and had one presentation failure; after the
  required build refresh, the exact command passed 46/46.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 5e2255442531a2892c7b2b76c5df071c08abb21f
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
