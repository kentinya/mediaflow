# Task 37.8 — Files Upload Helper Removal and Directory Replacement Fencing

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md). It is the focused correction Task for the two P1 blockers
recorded by A after the Slice 37 post-reactivation review.

```text
Task ID: 37.8
Parent Slice: 37
Status: PLANNED
Task Base: 062bc0b81021503c5eed76c80517b6ce0bada735
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Close the current Slice 37 P1 blockers by:

1. removing the unreachable Files Upload-specific `_ItemPayloadStream` helper so the
   direct browser Upload/Download vertical is absent end to end; and
2. making confirmed directory Delete fail closed when a same-name directory is deleted and
   recreated, including when the provider reuses an inode or otherwise presents an equivalent
   low-level identity, while preserving legitimate bounded recursive deletion of the originally
   confirmed directory after its confirmed children are removed.

This advances RO-6, RO-7 and RO-11 without adding a new Files surface, Storage capability or
organize path.

## Why This Task Exists

A Final Review found an Upload-specific WSGI payload helper still present at
`mediaflow/interfaces/service_api.py:202-233` after the Files Upload/Download routes, services,
models and UI were removed. The helper is unreachable but contradicts the current A-owned
removal boundary and makes the absence evidence incomplete.

GitHub Actions `quality` run `#114` on 2026-09-20 failed all Python matrix jobs on the direct
directory replacement tests. The current Local directory fence strips `ctime` from
`inode:<ino>:ctime:<ns>` and compares only the inode so confirmed child deletion does not change
the parent identity. On the GitHub runner, deleting and recreating a same-name directory reused
the inode, so the replacement passed the old fence and Delete returned `SUCCESS`. This is a
Storage mutation safety defect, not a test-only flake: a replacement directory must never be
deleted under stale confirmation.

The Task keeps both concerns together because they are the remaining post-reactivation
corrections in the existing direct-Files safety/removal boundary. It does not absorb unrelated
configuration projection, stale Manual Operations fixtures, legacy Playwright routes or the
obsolete Docker smoke probe.

## Implementation Scope

- Remove `_ItemPayloadStream` and any now-unused imports or references from the Files/API
  implementation. Preserve generic Storage `Read`/`Write`, provider transfer primitives,
  Copy/Move, text Edit and OrganizerExecutor behavior.
- Trace the direct Delete evidence from admission through `OrganizerExecutor` and define a
  provider-verifiable directory identity/generation that:
  - distinguishes same-name replacement even when a low-level inode is reused;
  - remains valid while already-confirmed children are removed during the same bounded recursive
    Delete;
  - performs metadata-only validation without reading directory or media content;
  - fails closed when the provider cannot prove the required identity; and
  - never silently falls back to inode-only, size/mtime-only or content-prefix evidence.
- Update the Local Storage/domain/application evidence boundary only as required to carry that
  identity. Keep all mutation behind `OrganizerExecutor`; do not add a direct Storage mutation
  path.
- Add deterministic tests using temporary/fake Storage as appropriate. Tests must explicitly
  cover both inode-reuse/equivalent-identity replacement and valid recursive child removal.
- Keep the existing user-visible failure and recovery semantics: stale/replaced scope reports an
  actionable failed result, leaves replacement content intact and does not automatically replay.
- Update only the directly affected absence/safety tests and evidence. Do not rewrite historical
  Slice packets or change the parent Contract, Roadmap, Progress, product requirements or
  architecture documents.

Frozen areas:

- Files layout, shell, ResourceLibrary activation, Organize destination composition and Save
  Choice behavior;
- Copy/Move transfer semantics, conflict policy, cross-Storage verification and Task fencing
  except for shared identity helpers strictly required by this Delete correction;
- historical Task/Result persistence and schema;
- all unrelated P2 baseline failures and unavailable external probes.

## Acceptance Criteria

- [ ] `mediaflow/interfaces/service_api.py` contains no Upload-specific `_ItemPayloadStream`
      helper or equivalent dead Files Upload request-body adapter.
- [ ] Repository absence inspection finds no direct Files Upload/Download route, binding,
      application service, client projection, UI control or dedicated test beyond explicitly
      retained lower-level Storage/provider transfer primitives and historical governance text.
- [ ] A confirmed Delete of a same-name directory recreated after confirmation fails closed even
      when the provider reuses the old inode or exposes an equivalent low-level identity.
- [ ] The replacement directory and its new content remain intact after the failed Delete.
- [ ] Confirmed bounded recursive Delete still succeeds after removing only the children that were
      part of the same confirmed scope.
- [ ] A provider that cannot provide replacement-resistant directory identity fails before
      mutation; no inode-only, size/mtime-only or content-read fallback is introduced.
- [ ] Delete evidence remains metadata-only, backend-authoritative and confined to the selected
      ResourceLibrary/Storage; `OrganizerExecutor` remains the only Storage mutation boundary.
- [ ] No silent overwrite/delete, implicit fallback or automatic uncertain-effect replay is added.
- [ ] The focused direct-operation tests pass, including the two GitHub-failing regression cases
      and the valid recursive-child-removal case.
- [ ] Python 3.11, 3.12 and 3.13 matrix results are recorded truthfully. Any unavailable local
      interpreter or external gate is explicitly marked `UNAVAILABLE`, not inferred as PASS.
- [ ] The full offline Python regression, relevant Web regression, direct Upload/Download
      absence inspection, governance, lint/format, compile and diff checks pass or are recorded
      with exact remaining failures and classification.
- [ ] The implementation checkpoint contains only this Task; the pre-existing dirty reference
      image and private configuration remain untouched.

## Required Tests

Focused safety and absence checks:

```text
.venv/bin/python -m unittest -v \
  tests.test_direct_file_operations.DirectFileOperationsTests.test_confirmed_delete_refuses_a_replaced_empty_directory \
  tests.test_direct_file_operations.DirectFileOperationsTests.test_confirmed_recursive_delete_refuses_a_replaced_parent_directory \
  tests.test_direct_file_operations.DirectFileOperationsTests.test_confirmed_recursive_delete_tolerates_confirmed_child_removals

.venv/bin/python -m unittest tests.test_direct_file_operations tests.test_organizer
```

The focused suite must include a deterministic fake/provider case that reuses or simulates the
same low-level identity after replacement; relying only on the host filesystem's inode allocator
is insufficient.

Direct-surface absence inspection:

```text
rg -n -i \
  'direct_file_upload|direct_file_download|FilesUploadDialog|files/(upload|download)|_ItemPayloadStream|Files upload|Files download' \
  mediaflow web tests
```

The result may contain only intentionally retained lower-level Storage/provider transfer
primitives and unrelated generic words such as configured download directories; it must not
contain an active Files Upload/Download vertical or the removed helper.

Required quality gates:

```text
python3 scripts/check_governance.py
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests scripts
.venv/bin/python -m pip check
.venv/bin/python -m unittest discover -s tests
cd web && npm run format:check && npm run typecheck && npm run lint && npm run test -- --run && npm run build
git diff --check
test ! -e config/alist.json
```

Before returning `READY FOR B REVIEW`, inspect `git diff --name-status`, the complete diff,
private-file scope, and the exact current `HEAD` SHA. Run the Python quality job on all available
3.11/3.12/3.13 interpreters or record unavailable interpreters explicitly.

## Non-goals

- Fixing the configuration projection test's over-broad `root` assertion.
- Updating stale Manual Operations fixtures or request shapes.
- Repairing legacy Playwright routes/assertions.
- Repairing the Docker release smoke probe or deploying a candidate image.
- Reintroducing browser Upload/Download, adding compatibility routes, or adding a new transfer
  workflow.
- Redesigning Storage providers, schema, ResourceLibrary, Organize, Copy/Move or the shared V2
  shell.
- Changing Slice scope, Roadmap status, Progress history or declaring the Slice closed.

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
