# Task 37.8 — Files Safety and Quality Gate Reconciliation

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md). It is the focused correction Task for the remaining Upload
P1 blocker and the bounded quality-gate reconciliation recorded by A after the Slice 37
post-reactivation review.

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

Close the remaining Slice 37 P1 blocker and reconcile the bounded, already-known quality-gate
debts by:

1. removing the unreachable Files Upload-specific `_ItemPayloadStream` helper so the
   direct browser Upload/Download vertical is absent end to end; and
2. aligning the configuration-status redaction assertion and the two Manual Operations
   contract/fixture tests with the current supported API semantics without weakening secret or
   authority checks; and
3. making the executable governance guard implement the documented
   `FIX REQUIRED -> active correction Task` lifecycle and keeping release-quality Task
   documentation complete.

This advances RO-6, RO-7 and RO-11 without adding a new Files surface, Storage capability or
organize path.

## Why This Task Exists

A Final Review found an Upload-specific WSGI payload helper still present at
`mediaflow/interfaces/service_api.py:202-233` after the Files Upload/Download routes, services,
models and UI were removed. The helper is unreachable but contradicts the current A-owned
removal boundary and makes the absence evidence incomplete.

GitHub Actions `quality` run `#114` on 2026-09-20 exposed two host-filesystem directory-replacement
tests whose stronger inode-reuse guarantee is now an A-accepted residual risk. The current
implementation retains bounded impact confirmation and final metadata revalidation; this Task
must not grow a directory-generation, birth-time/statx or persistent-handle architecture to close
that rare race. The two tests must be reconciled to the accepted contract without adding skips or
claiming the race is fixed. Valid bounded recursive deletion of already-confirmed children remains
covered.

The same full Python quality gate also contains three bounded P2 debts with known causes:

- the configuration-status redaction test rejects the legitimate projected field name
  `root_path` because it searches for the broad substring `root`, even though the hostile root
  value is not exposed;
- two Manual Operations contract tests still submit or compare a superseded Preview
  request/fixture and receive HTTP 400 before their actual fixture/redaction assertions; and
- the release-security policy test requires an active Task to name the release-security smoke
  command explicitly.

These are included because the user explicitly requested that the known P2 quality-gate debts be
reconciled in this correction Task. The Task also owns the ten recorded legacy Playwright
failures, the obsolete Docker manual-Organize probe and replacement of the old `/opt/mediaflow`
`source2` reproduction with isolated current-candidate evidence. This remains test and acceptance
reconciliation for already-owned Slice 37 journeys; it does not restore retired product routes or
authorize production-media mutation.

At Task Base, the executable governance guard contradicted the authoritative workflow by rejecting
every active Task unless the Slice was `ACTIVE`, while the documented correction loop requires the
Slice to remain `FIX REQUIRED` until B's correction Task passes. The current Task range already
contains the focused guard correction and regression coverage; Developer must preserve and include
that accepted behavior in the final Task checkpoint.

## Implementation Scope

- Remove `_ItemPayloadStream` and any now-unused imports or references from the Files/API
  implementation. Preserve generic Storage `Read`/`Write`, provider transfer primitives,
  Copy/Move, text Edit and OrganizerExecutor behavior.
- Retain existing Delete impact, scope digest, explicit confirmation, final metadata revalidation,
  per-item outcomes and non-replay behavior. Reconcile the two host-filesystem replacement tests
  with the accepted residual-risk contract; do not add a new directory identity/generation
  abstraction or claim that inode reuse is fixed.
- Update only the directly affected absence/safety tests and evidence. Do not rewrite historical
  Slice packets or change the parent Contract, Roadmap, Progress, product requirements or
  architecture documents.
- Update `scripts/check_governance.py` so a committed `FIX REQUIRED` Slice may have one matching
  active correction Task while the corresponding Roadmap row remains `ACTIVE`. Preserve rejection
  of `FIX REQUIRED` with no active Task, mismatched parent Slice, non-Active Roadmap state,
  uncheckpointed Contracts and invalid Base ancestry.
- Replace the configuration redaction test's broad field-name substring assertion with checks that
  the injected hostile values and forbidden raw configuration fields are absent while the
  intentional bounded `root_path` projection remains allowed.
- Reconcile the two Manual Operations contract tests and their frontend fixture with the current
  supported Preview request/response contract. The journey must reach the intended successful
  capture; changing the expected status to 400 or weakening forbidden-evidence assertions is not
  acceptable.
- Keep the active Task's release-quality command list complete, including
  `python3 scripts/docker_release_security_smoke_test.py`; the external smoke may be reported
  `UNAVAILABLE` when Docker is unavailable, but the command and actual result must be recorded.
- Reconcile the recorded full Playwright failures:
  - rewrite assertions that still navigate to retired FileIndex or old Scan/Preview routes to the
    current supported Files/Operations entry when the same user outcome remains required;
  - remove an obsolete route test only when the product route is explicitly retired and equivalent
    current-journey coverage proves the applicable auth, failure and recovery semantics;
  - scope duplicate read-only copy assertions by role, section or route-owned container instead of
    changing product copy to satisfy a fragile unique-text locator; and
  - add no skip, retry-only masking or weakened safety assertion.
- Update `scripts/docker_release_security_smoke_test.py` so its manual-Organize probe submits the
  current supported Choice/Preview request contract rather than the obsolete `metadataIdentity`
  field. Reuse a current application/API fixture or shared request builder where practical so the
  harness does not maintain a second drifting protocol. HTTP 400 is not a passing outcome.
- Replace the old environment-specific `source2` reproduction with an isolated Docker acceptance
  harness for the current candidate, implemented as
  `scripts/docker_files_transfer_impact_smoke_test.py` or an equivalently isolated command recorded
  in the completion report. It must use a temporary Compose project, temporary managed
  configuration and synthetic sparse media larger than 20 GiB, call the real transfer-impact API,
  prove aggregate bytes are informational, prove control-plane limit failures remain structured,
  and perform zero Copy/Move/Delete mutation.

Frozen areas:

- Files layout, shell, ResourceLibrary activation, Organize destination composition and Save
  Choice behavior;
- Copy/Move transfer semantics, conflict policy, cross-Storage verification and Task fencing;
- historical Task/Result persistence and schema;
- unrelated product redesign and external production deployment state.

## Acceptance Criteria

- [ ] `mediaflow/interfaces/service_api.py` contains no Upload-specific `_ItemPayloadStream`
      helper or equivalent dead Files Upload request-body adapter.
- [ ] Repository absence inspection finds no direct Files Upload/Download route, binding,
      application service, client projection, UI control or dedicated test beyond explicitly
      retained lower-level Storage/provider transfer primitives and historical governance text.
- [ ] Delete evidence remains metadata-only, backend-authoritative and confined to the selected
      ResourceLibrary/Storage; `OrganizerExecutor` remains the only Storage mutation boundary.
- [ ] No silent overwrite/delete, implicit fallback or automatic uncertain-effect replay is added.
- [ ] Existing bounded recursive Delete coverage remains passing, and the two GitHub-failing
      host-filesystem tests are reconciled to the accepted residual-risk contract without skips,
      weakened safety assertions or a false claim that inode reuse is fixed.
- [ ] README documents the accepted Local concurrent-directory replacement risk and the operator
      prevention/recovery path.
- [ ] Governance accepts the committed Slice 37 `FIX REQUIRED` state with this matching active
      Task and `ACTIVE` Roadmap row, while its existing rejection cases remain covered.
- [ ] Configuration-status redaction tests prove hostile values and forbidden raw configuration
      fields are absent without rejecting the legitimate bounded `root_path` projection.
- [ ] Both Manual Operations contract tests complete the current supported Preview/Organize
      capture successfully, match the reconciled frontend fixture and retain all secret/internal
      evidence prohibitions.
- [ ] The active Task documents and runs, or truthfully marks unavailable, the required
      release-security smoke command.
- [ ] Full Playwright passes with zero failures and no new skips. Retired routes are not restored;
      affected tests either follow the current supported Files/Operations journey or are removed
      only with explicit replacement coverage.
- [ ] Duplicate read-only explanation coverage uses a route/section/role-scoped locator and retains
      the intended content assertion.
- [ ] The Docker release-security manual-Organize probe uses the current API contract and completes
      the supported success path; an obsolete HTTP 400 is not accepted.
- [ ] Isolated current-candidate Docker evidence proves a bounded synthetic `source2`-equivalent
      directory with aggregate media bytes above 20 GiB is admitted for Impact without reading
      media content or mutating Storage.
- [ ] The isolated large-byte smoke also proves entry/depth/path/control-plane violations return
      structured actionable errors, including truthful HTTP 413 where applicable.
- [ ] Docker gates use only temporary/synthetic data and record `UNAVAILABLE` when Docker is absent;
      no result from the old `/opt/mediaflow` checkout is presented as current-candidate evidence.
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
  tests.test_direct_file_operations.DirectFileOperationsTests.test_confirmed_recursive_delete_tolerates_confirmed_child_removals

.venv/bin/python -m unittest tests.test_direct_file_operations tests.test_organizer
.venv/bin/python -m unittest -v \
  tests.test_governance \
  tests.test_configuration_status.ConfigurationSnapshotTests.test_hostile_configuration_content_is_never_exposed \
  tests.test_manual_operations_contract.ManualOperationsContractTests.test_real_api_documents_carry_no_forbidden_evidence \
  tests.test_manual_operations_contract.ManualOperationsContractTests.test_real_api_documents_match_the_frontend_fixture \
  tests.test_release_security.ReleaseSecurityPolicyTests.test_release_quality_gate_commands_are_documented_for_task_execution
```

The two host-filesystem replacement tests must be updated or replaced to assert only the accepted
contract: ordinary scope/stale revalidation remains covered, while the narrow inode-reuse race is
documented residual risk. Do not skip them silently or replace them with a test that pretends the
race is solved.

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
cd web && npx playwright test
python3 scripts/docker_release_security_smoke_test.py
python3 scripts/docker_files_transfer_impact_smoke_test.py
git diff --check
test ! -e config/alist.json
```

Before returning `READY FOR B REVIEW`, inspect `git diff --name-status`, the complete diff,
private-file scope, and the exact current `HEAD` SHA. Run the Python quality job on all available
3.11/3.12/3.13 interpreters or record unavailable interpreters explicitly. If the Developer
implements the isolated transfer-impact scenario inside an existing Docker harness rather than
the named dedicated script, the completion report must record the exact equivalent command and
evidence.

## Non-goals

- Restoring retired FileIndex, Scan or Preview routes solely to make legacy tests pass.
- Reading or mutating the real `/opt/mediaflow` `source2` library or any production/user media.
- Treating the old `/opt/mediaflow` checkout as current-candidate validation.
- Implementing directory-generation, birth-time/statx or persistent-handle fencing for the accepted
  Local inode-reuse race.
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
