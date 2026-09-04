# Task 27.1 — Runtime Files Browser and FileIndex Surface Split

This Task follows [the development workflow](../docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](../SLICE.md).

```text
Task ID: 27.1
Parent Slice: 27 — Manual Operations and File Lifecycle
Status: IN PROGRESS
Task Base: 306b77d0aad44ab0a2e233866f8972247b437a7d
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
```

## Goal

Deliver the first vertical part of Slice 27 RO-1 and its required RO-8 surface parity: an
authenticated operator can open a distinct read-only `Files` surface backed by the currently
consumed configured Storage and a distinct `FileIndex` surface backed by indexed discovery records.
The Files surface reuses the bounded Storage Browser contract, shows Storage-relative entries and
bounded FileIndex membership, and uses the same application behavior through Web and versioned API.

## Why This Task Exists

Slice 26 already provides a safe, paginated Storage Browser, but only as a setup/revision surface.
The current Operator Web `Files` view and `/api/v1/files` behavior are FileIndex catalog behavior;
they do not let an operator browse the real configured Storage or distinguish the two concepts. This
blocks every later manual Scan/Preview/Organize entry path and makes a file's visible source context
ambiguous.

This is the largest reasonable first unit because it establishes the user-facing daily entry point
across Application, API, Web and tests while remaining read-only. It does not need to invent the
processing-disposition or execution model that later Tasks will build on.

## Implementation Scope

- **Domain/Application:** introduce or adapt a runtime-bound, provider-neutral Files browsing use
  case that resolves only the exact current Active runtime Storage configuration, preserves the
  existing Storage-relative path, cursor, breadcrumb and bounded error semantics, and exposes a
  bounded index-membership projection for listed file entries where a ResourceLibrary scope is
  available.
- **Persistence:** add only the read path needed to answer whether a returned Storage file is
  indexed, using the existing FileIndex authority and Storage/path identity. Do not add processing
  disposition, source-occurrence history or fingerprint lifecycle in this Task.
- **API:** expose unambiguous versioned read contracts for real Storage `Files` browsing and indexed
  `FileIndex` listing/detail. Preserve compatibility aliases where practical, but do not leave one
  ambiguous endpoint or UI label serving both meanings. Enforce existing RBAC, Active snapshot
  binding, bounded pagination and secret-free structured failures.
- **Operator Web:** make `Files` the real configured-Storage browser and present the existing catalog
  as `FileIndex`. Provide root/breadcrumb navigation, directory traversal, file metadata, index
  membership, bounded pagination, retry/reload feedback and clear distinction between the two
  surfaces. Read-only viewing must not start a Task, call a Metadata Provider or invoke Storage
  mutation.
- **Tests:** cover the complete read-only journey through Application/API/Web, including supported
  Storage adapters through fakes or local test services, authentication/RBAC, active-configuration
  binding, path confinement, cursor boundaries, empty/error states and index-membership projection.
- **Frozen areas:** `Scanner`, Parser, Recognition, Metadata, Naming, Classification,
  `OrganizePlan`, `OrganizerExecutor`, Task execution, manual authority, review/recovery semantics,
  Worker readiness, scheduled automation and the existing FileIndex identity schema are frozen except
  for the minimum compatible read integration required above. `config/alist.json` must remain ignored,
  untracked and unstaged.

## Acceptance Criteria

- [ ] An authenticated operator can browse the configured Storage root and descendant directories in
      `Files` through the existing Storage abstraction, with deterministic bounded entries containing
      safe relative paths, type, size and modification information.
- [ ] Files browsing is bound to the exact current Active runtime configuration, never a Draft,
      setup-only revision, stale process configuration or arbitrary host path; missing/invalid Active
      runtime fails closed with the existing structured recovery semantics.
- [ ] Root handling, breadcrumb navigation, cursor continuation, empty directories, hostile names,
      symlink restrictions where applicable, absolute/backslash/scheme/traversal paths and provider
      read/auth/permission/timeout/not-found failures are bounded and actionable. A browser request
      performs no Storage write, delete, move, copy, link, directory creation or other mutation.
- [ ] The operator can reach a separate `FileIndex` view for indexed discovery records and a separate
      `Files` view for real Storage entries. The API exposes the same distinction without requiring
      callers to infer it from an overloaded response.
- [ ] A real Storage file entry can show bounded FileIndex membership for the requested authorized
      library context, while the response does not claim processing disposition, current occurrence
      identity or organization outcome before those contracts are implemented in later Tasks.
- [ ] Web and API use the same application behavior, authorization, validation, pagination, error
      category, redaction and Active-runtime binding. Viewer/read access works only within existing
      RBAC; unauthorized access is rejected and does not reveal Storage contents.
- [ ] Files/FileIndex reads do not create Jobs, Tasks, reviews, Provider requests or execution
      authority, and viewing or retrying a read does not mutate the configured Storage.
- [ ] Focused and affected tests pass, the checkpoint contains only this Task's coherent changes,
      and no real credentials, private endpoints, user media or `config/alist.json` are introduced.

## Required Tests

Run from the repository root with the project environment:

```bash
python -m unittest \
  tests.test_storage_browser \
  tests.test_file_catalog \
  tests.test_file_catalog_api \
  tests.test_api_security \
  tests.test_operator_ui \
  tests.test_dashboard
ruff format --check mediaflow tests
ruff check mediaflow tests
python -m compileall -q mediaflow tests
git diff --check
```

Add Task-specific tests as needed and include them in the focused command. Use temporary Local roots,
fakes or isolated local services only. Record actual test totals, failures, skips and unavailable
external services in the Developer Completion Report; do not count fake behavior as production
Storage compatibility.

## Non-goals

- Current-source occurrence/fingerprint correlation, processing-disposition states, duplicate-work
  admission or explicit Reprocess (Slice 27 RO-2).
- File- or ResourceLibrary-scoped Scan, durable manual operation submission, Preview findings,
  manual Organize execution, conflict/review/recovery continuation or Worker readiness (Slice 27
  RO-3 through RO-7).
- Changes to Storage mutation semantics, capabilities, fallback policy, OrganizerExecutor,
  attachments, cleanup, overwrite/delete authority or scheduled unattended organization.
- Slice 28 configuration/operations administration, settings/import-export/Webhook management, or
  Slice 29 Docker packaging and production runtime release.
- New Storage providers, mutation-based Storage probes, recursive/unbounded browser behavior,
  arbitrary host filesystem access, Metadata Provider switching, built-in identity, Secret Store
  integration, media streaming, asset generation or quality-upgrade behavior.
- Optional proof, broad UI redesign, unrelated refactors, test-only cleanup or P2/P3 polish.

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
