# Task 41.1 — Rules workspace read model and full-width inventories

This Task follows [the development workflow](../docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](../SLICE.md).

```text
Task ID: 41.1
Parent Slice: 41
Status: PLANNED
Task Base: 5c8aeb40fd7ea43daac100f7b205b082da921336
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
```

## Goal

Deliver the read-only entry journey for the V2 organizing-rules workspace (RO-1 and the read-only
parts of RO-7/RO-8): an authenticated operator can open `/ui-v2/rules`, understand the recognition-
to-policy relationship, and inspect every rule-family inventory from the exact immutable Active
configuration. The initial state is a complete full-width inventory with no selected object, drawer
or editor; search, filtering, tab changes and refresh remain read-only.

## Why This Task Exists

Slice 41 is active, but V2 has no Rules route, navigation destination, typed rules entity or bounded
operator projection. The existing generic configuration revision document is an implementation
surface containing unrelated sections and evidence, and is not a suitable Web contract for the
rules journey. The first independent unit must establish one server-authoritative, secret-free read
model and prove the user can enter and scan the complete rule graph before any mutation workflow is
added. This is the largest useful foundation for the later typed editors, tests/previews and
automatic Save/activation tasks.

## Implementation Scope

Domain/Application/API:

- Add a bounded read-only rules operator projection backed by the exact current Active managed
  revision. It must expose Active identity/readiness, Overview relationship data, and all eight
  sections: Type Bindings, Recognition Types, Recognition Rules, Metadata Policies, Naming Policies,
  Classification Policies and Organize Policies.
- Include stable IDs, names, bounded descriptions/summaries, enabled state and bounded reference /
  impact summaries needed by the inventories. Preserve RecognitionType identity and show binding
  references without resolving or rewriting policy identity.
- Keep the projection secret-free and digest-free for the browser. Do not return credentials,
  authorization material, raw provider options, audit payloads, Draft contents, execution authority,
  internal tokens or unrelated configuration sections. Active is the only source for the displayed
  objects; no Draft is created or read as Active.
- Expose bounded, action-oriented unavailable, empty-active, unauthorized, forbidden and malformed
  read outcomes. Reads must perform no Storage access, Provider call, Task/Job creation, Draft write,
  schedule/notification work or media mutation.

Web/API:

- Add a typed frontend API/entity boundary with strict response normalization and bounded error
  categories. Query/search/filter parameters must be allowlisted and must not make the browser
  infer or substitute policy data.
- Add `/ui-v2/rules` to the typed route/destination model and make `整理规则` the active shared-shell
  destination. Existing routes and Settings/Review recovery destinations remain unchanged.
- Implement one Rules page with an Overview and the eight required rule-family sections. Each family
  opens as a full-width searchable inventory with real Active rows, enabled/reference state and a
  clear empty/no-match state. Narrow and keyboard operation must remain complete.
- Entry, selection, search, filter, tab navigation and refresh never open a drawer or editor and
  never perform a configuration mutation. A row may be highlighted or inspected as read-only, but
  edit/create routes are explicitly deferred.
- Render distinct loading, no Active/onboarding, empty inventory, no-match, unauthorized,
  forbidden, unavailable/malformed and refresh-recovery states with a safe next action. Do not
  expose raw revision IDs/digests or protocol/exception text as ordinary workflow steps.

Tests:

- Add focused Python API/projection tests for exact-Active selection, section completeness, bounded
  redaction, references/impact, empty/unavailable/permission/malformed responses and zero side
  effects.
- Add typed entity/API tests for accepted and rejected payloads, query allowlists and error mapping.
- Add component/router/navigation tests for the route, all eight sections, default closed editor state,
  search/filter/tab/refresh read-only behavior, empty/no-match/error recovery and responsive/keyboard
  reachability.

Files/areas frozen for this Task:

- Existing managed configuration lifecycle, validation, activation, policy resolver, Strategy Test,
  Naming/Classification/Organize Preview and Settings authority remain unchanged except for the
  narrow read projection required above.
- No changes to `config/alist.json`, real credentials, supplied reference images, Storage adapters,
  OrganizerExecutor or the V1 `/ui` journey.

## Acceptance Criteria

- [ ] An authenticated operator can reach `/ui-v2/rules` from the shared shell and via a normal
      deep-link; the page is protected by the existing backend-authoritative read permission.
- [ ] The backend projection is derived from one exact Active revision, contains all eight required
      sections plus bounded Overview/identity/readiness data, and never labels Draft/candidate data
      as Active.
- [ ] Projection and frontend normalization are bounded and secret-free: no credentials, tokens,
      digests, audit contents, unrelated configuration, provider response DTOs or raw exceptions
      cross the Rules Web boundary.
- [ ] The default page is a complete full-width Overview/inventory state with no selected object,
      drawer or editor. All eight sections are discoverable and display actual Active rows or a
      truthful empty state; reference/impact and enabled state remain visible.
- [ ] Search and supported filters operate over the complete returned Active inventory, have
      deterministic no-match behavior, and do not create Drafts, call Providers, inspect Storage,
      create work or mutate configuration. Refresh only re-reads the projection.
- [ ] Loading, no Active/onboarding, empty, no-match, unauthorized, forbidden, unavailable and
      malformed states each explain the durable state and a meaningful safe next action without
      exposing implementation-detail ceremony.
- [ ] The implementation preserves RecognitionType identity, policy-binding semantics and all
      Slice safety invariants; no new mutation path or frontend authority is introduced.
- [ ] Required T3 focused, related integration and normal Web quality checks pass, and the
      checkpoint contains only this Task's coherent changes.

## Required Tests

- `python3 -m pytest -q mediaflow/tests` (or the repository's focused Python test selection covering
  the new projection and service API, plus directly affected configuration tests).
- `python3 -m compileall -q mediaflow`.
- `npm --prefix web test -- --run` with the new Rules entity/API/router/component tests and affected
  navigation/shell tests.
- `npm --prefix web run typecheck` (or the repository's equivalent typecheck script), lint and
  format checks for changed Web files.
- `python3 scripts/check_governance.py` and `git diff --check`.

External TMDB, SMB, OpenList, S3/R2 and user media are not required; use fakes, mocks, bounded local
responses and temporary roots where a read-side dependency must be exercised.

## Non-goals

- Object create/copy/edit/enable-disable/delete forms or any drawer/full-page editor.
- Page-level Save, automatic validation, checked activation, Draft recovery or Active publication.
- Recognition Strategy Test, Metadata test, Naming Preview, Classification Preview, Organize
  authority/whole-chain Preview or live Provider calls.
- Starting Scan/Preview/Organize, scheduled work, notification delivery, Storage browsing or any
  OrganizerExecutor/Storage mutation.
- New recognition fields/operators, Metadata Providers, policy semantics, frontend policy resolver,
  bulk editing, visual graph authoring, V1 retirement or unrelated shell/page redesign.
- Optional visual polish, extra sample data, P2 cleanup or test-only work outside the read journey.

## Developer Completion Report

### Changed Files

### Implemented

### Tests and Results

### Decisions

### Remaining In-Slice Work

### Risks / Deviations

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: [full SHA]
```

## B Review Result

```text
Reviewed: [Head SHA or Task Base..Head]
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
