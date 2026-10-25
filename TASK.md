# Task 46.3 — Files-first admitted organizing and native item recovery

Authority: committed [Slice46](SLICE.md) RO-2, AC-2/3/16 and the necessary organizing-entry,
confirmation/readback and safety portions of AC-5/7/8/14/15;
[Development Workflow](docs/development-workflow.md). Read the
[Developer experience](docs/agent-experience/developer-implementation-role.md) before implementation.

```text
Task ID: 46.3
Parent Slice: 46
Status: FIX REQUIRED
Task Base: 83144be20c6c7bc787a0fafad7fabb3e177bde6a
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

An operator selects live ResourceLibrary files/folders and explicitly submits 整理. The system
admits durable organizing work before business readiness, performs bounded discovery/stability and
the full planning pipeline inside that task, exposes actual four-type problems through native task
recovery, then requires exact selected execution confirmation before OrganizerExecutor changes media.
The operator can find the same task, preparation or unknown request after close/reload/reconnect/restart.
New manual file-selection work starts only from ResourceLibrary Files.

Journey: Files selection → explicit organizing admission → visible task progress → Recognition /
Metadata / Classification / Conflict decision when required → non-executing decision Save and safe
analysis → exact in-task summary → explicit ready-subset confirmation → independent durable outcomes.
A normal initial confirmation remains reachable in Running/All without becoming Attention. Technical
failures retain factual stages/effects and are never fabricated business decisions. Separate browsing,
analysis-only and supported old preparation remain non-executing preparation.

Requirements: `V2-OPS-015/017` and necessary `V2-OPS-014/016` integration; `V2-UX-001–003`,
`V2-WEB-001`, `V2-AUTH-001–003`, `V2-SAFE-001`; `UX-001–003/005–007/010`,
`REQ-TASK-002/003/005–010`, applicable `REQ-RECOVERY-001–009`, `REQ-API-002/003`,
`REQ-ATT-001–003`, `REQ-SAFE-001–009`. The Slice46 amendments supersede older pre-task filtering,
readiness and preparation-only semantics for explicit organizing, not for analysis-only work.
Read the complete TARGET manual/task recovery and CURRENT Files, Manual organize, bounded folder
and Tasks/results/recovery journeys in [Product Experience](docs/product-experience.md), the affected
TARGET admission/work-query and CURRENT task/recovery/manual/discovery contracts in
[Architecture](docs/architecture.md), and [Task Center specification](docs/task-center-page-spec.md)
TARGET entry/confirmation plus the retained exact summary and four-type recovery interactions.

### Actual code gap and reuse

- `StorageFilesPage.tsx::organizeMutation` calls `submitFilesDiscovery(autoPrepare: true)` and goes
  to `/operations/organize/new?discoveryId=...`. It admits preparation, not an organizing Task.
  Lost responses search a bounded recent discovery list; the unresolved copy relies on the center
  discovery section. Reuse its caller request identity, exact return context and non-replay behavior.
- `MediaDiscoveryService.admit` already bounds/stats selected entries without recursive traversal,
  pins Active and reconciles equivalent open preparation. `_refuse_unselectable_file`, directory
  admission and the shared walk apply automatic include/exclude/depth/extension rules. The shared
  `scan_filters.classify_entry` conflates an unlisted suffix with explicit exclusion. Preserve
  automatic semantics while separating the deliberate manual selection behavior required here.
- `media_discovery.py` already has bounded traversal, observations, stable-size waiting, attachment
  association, material-bound refusals and fenced atomic plan publication. Reuse these facilities;
  do not create another discovery/plan/queue engine or a global source catalog.
- `ManualOrganizeIntentService._snapshot_from_runtime` requires a compatible type policy;
  `_default_choice` can choose the first available type. This path cannot be the early admitted
  task's mandatory readiness gate or fabricate a RecognitionRule result for an unmatched source.
- `media_organizer.py`, `task_runtime.py`, `task_item_recovery.py` and
  `manual_recovery_continuation.py` already provide pipeline checkpoints, four-type decisions and
  exact summary/confirmation. `PersistentTaskCoordinator` acquires a source lock at item start and
  releases it when waiting for recognition/metadata/confirmation: that execution lock alone is not
  durable unfinished-work ownership across queue, pause, decisions and continuation.
- `sqlite_runtime.py::operations_runs_window` and related item/problem reads project durable linked
  runs. Extend necessary admitted-task membership/linkage, rather than disguising preparation as
  execution or doing browser merges. `OperationsLanding.tsx` and `OrganizeNewPage.tsx` still expose
  center creation, an independent library picker and global discovery/manual-action sections.

### All Slice outcomes reevaluated at planning

| Outcome | Assessment at Task Base |
| --- | --- |
| RO-1 readable actions | Complete: Task46.1 PASS retained at `6072f50d5b2e5268c35d6729290512d1ae986104:TASK.md` |
| RO-2 early Files manual organizing | Incomplete; selected by this Task |
| RO-3 local ordinary operations | Complete: Task46.2 PASS at Task Base; preserve its local modal/readback |
| RO-4 organizing-only eight views / four-type truth | Incomplete; this Task adds only the integration its newly admitted manual work needs |
| RO-5 Automation | Incomplete; changed intent/detail/Enabled/Run once/stability semantics remain outside this Task |

Task46.2 reviewed range: `6072f50d5b2e5268c35d6729290512d1ae986104..bb176f2f36c92d5f5298c19e8d1c9eed45c1a9e5`;
implementation `2541d0c89d70a965cfac4d9f45580fb6147a71cb`. Its acceptance/evidence limits and known
pre-existing row-menu native failure remain in `83144be2:TASK.md`; this plan does not rerun or relabel them.

## Implementation Scope

1. Trace the existing Files command → API discovery → resident Worker → pipeline → summary →
   confirmation → execution/recovery path. Make explicit organizing admission distinct from
   analysis-only preparation using existing durable Task/Job/intent/discovery infrastructure.
   Persist the source selection, actor, exact request identity, pin and real links atomically enough
   to avoid orphan/duplicate admission. Direct files may be stat-verified at admission; folders
   become durable outer work before traversal. No metadata lookup, full folder walk or ready plan
   may be required to create that organizing work. Preserve bounded validation, RBAC, enabled source
   library, root confinement, immutable pins and read-only browse semantics.
2. Separate manual entry rules from automatic scan filtering. A directly selected regular file is
   not rejected merely for an unlisted suffix, include miss or rule miss. Apply explicit extension
   exclusions and truthful unfinished-source checks per item; eligible siblings remain admissible.
   For folder/mixed-folder expansion retain configured primary-media extensions, default video, and
   existing attachment association. Other automatic include/exclude/match conditions cannot veto
   deliberate manual work. Preserve technical safety/traversal budgets and real stability inside
   the admitted task; do not globally weaken Scanner or Automation filtering. Distinguish explicit
   extension rules from a missing allowlist entry, including temporary suffix exclusions. Default
   images/subtitles/NFO are not independent folder primaries or fabricated recognition problems.
   Artwork-off does not promote images; enabled other-same-stem association still works. Custom
   primary extensions retain their deliberate configured meaning; unmatched files remain at source.
3. Add/reuse durable verified source ownership, separate in meaning from a short-lived execution
   lease. Atomically check/reserve each concrete source with its TaskItem admission; no database
   transaction spans Storage I/O. Ownership covers queued/running/paused/unresolved business work
   across manual, existing scheduled/Run once and legal continuation entrances. Use verified
   Storage-relative source identity and admitted context, never filename, UI labels or today's
   Active. Overlapping folder/direct requests and distinct library bindings to the same concrete
   source cannot execute it twice. Return the exact authorized existing-work reference/reason,
   without exposing a foreign principal's private context. A continuation inherits/transfers its
   legitimate lineage without self-conflict. Define release/settlement for success, permitted
   skip/ignore/cancel and terminal failure; neither a lease timeout nor decision Save drops an
   unresolved reservation. Finished history alone is not a perpetual lock; completed/uncertain
   effects remain protected against replay through both old and newly submitted requests.
   Supported pre-change unfinished organizing work must participate in the check; an empty new
   ownership index cannot make an existing queued/paused/recovery source appear available.
   Integrate this safety boundary into existing Automation entrances without changing RO-5 intent.
4. Run the actual shared Parse → Recognition → type-policy → Metadata → Naming → Classification →
   plan pipeline inside admitted work. Persist genuine per-item problems/checkpoints and expose
   existing four-type forms and counts; never force a default type/identity/target or turn transport,
   unreadable sources or invalid configuration into a business decision. Preserve independent
   siblings, explanations, C identity under A naming/classification, provider abstraction and pins.
   Reuse native decision → analysis → exact summary → confirmation → outcome. A new business
   blocker changes the relevant type; Save/analysis is not success. Necessary human recovery steps
   retain lineage; queued/running analysis alone is not Attention. Technical follow-up failure
   removes obsolete four-type problems without claiming success or erasing historical evidence.
5. Keep the exact normal summary/selected confirmation reachable from the admitted run in Running
   and All after refresh/service restart. Normal initial WaitingConfirm without four-type lineage
   is unfinished but outside Attention/pending counts. Preserve full completeness/bounds checks:
   material traversal/primary/depth/time refusal cannot authorize a silently truncated first-N run.
   Show partial read evidence and require the existing explicit known-subset acknowledgement where
   permitted. Summary binds source, pin, plans, attachments, operations/destinations and selected
   subset; overwrite/Delete/cleanup keep separate applicable authority. Revalidate on confirmation
   and at execution with current permissions, capabilities, source evidence and claim/fence checks.
   Repeated/concurrent/unknown confirmation converges on exact durable work; completed or uncertain
   effects and successful siblings never replay. Retain old prepared-work and supported recovery links.
6. Make ResourceLibrary Files the only normal new manual file-selection entry. Remove center
   creation CTAs and independent source-selection/manual-action flow; remove the center discovery
   section once exact task/preparation readback is available from Files, including its exclusive
   reads/polling/refresh dependencies. Give Files bounded durable access to its admitted work,
   separate/pre-existing preparation and exact unresolved request, independent of component memory,
   one overwritable slot or a recent-N-only lookup. Use principal-bound backend readback/paging;
   hints carry no credentials or authority. Generic new-organize URLs guide to Files without work
   or another library picker. Preserve exact valid Files/prepared/recovery context in shared routes;
   foreign/stale/malformed context never guesses a library/request or auto-starts discovery. Update
   necessary Shell/Dashboard/return links. Close/reload/reconnect is read-only and never resubmits.
7. Extend the existing Python/API/SQLite/Worker and browser fixtures through real supported commands.
   Add only necessary additive durable fields/indexes/links; justify any schema change with old-row
   preservation, fresh/upgrade/reopen and failure-atomicity tests. Update affected architecture
   contract facts for the newly delivered path, clearly retaining unimplemented Slice46 TARGET.
   Keep broader center population/eight-view/failure-removal and Automation redesign deferred.

## Acceptance Criteria

- [ ] Single/multiple/direct/folder/mixed Files commands create observable durable organizing work
  before full business readiness. Folder admission precedes recursion. Browsing/refresh/analysis-only
  preparation creates no organizing work or execution authority; MediaLibrary remains destination-only.
- [ ] Direct unlisted suffix and automatic include/rule misses are admitted; explicit excluded
  extensions and unfinished-source duplicates have accurate per-item reasons/existing-work access.
  Eligible siblings survive refusals. Default folder images/subtitles/NFO do not become primaries;
  video/custom extensions and artwork/other-same-stem attachment settings behave as specified.
- [ ] Overlapping concurrent manual/direct/folder/scheduled/Run once/continuation requests across
  separate SQLite connections admit at most one effective owner per verified concrete source.
  Queue, pause, unresolved decisions and restart preserve ownership; legal continuation works.
  Equal names on different sources do not collide; overlapping bindings cannot bypass ownership.
- [ ] Genuine Recognition, Metadata candidate/correction, Classification and Conflict cases are
  admitted, enter their native task lists/counts and complete through decision/analysis/summary/
  explicit execution to real results. No default choice fabricates readiness. New blockers and
  technical failures keep independent state without stale four-type membership or false completion.
- [ ] Normal WaitingConfirm is reachable from Running/All after close/reload/reconnect/real API and
  repository reopening, with its exact summary, and creates no Attention/pending count. Four-type
  recovery retains its human confirmation lineage; decision Save/analysis grants no execution.
- [ ] Real stability, full bounds and completeness gates precede mutation. Over-limit discovery
  cannot execute the first 100 of 101 primaries; empty/no-eligible-primary differs from unavailable
  or incomplete scope. Partial read evidence never silently becomes a complete-scope success.
- [ ] Confirmation executes only the exact selected ready scope through OrganizerExecutor. Stale
  source/plan/permission, duplicate confirmation, uncertain effects, faults after mutation and
  restart retain fences/results; successful and uncertain siblings never replay or gain authority.
  RecognitionType C remains C with NamingPolicy A and ClassificationPolicy A.
- [ ] Center creation/manual/discovery entries and their exclusive reads are gone. Files can reopen
  multiple known tasks/preparations and reconcile a lost admission by exact identity without the
  removed discovery block, recent-N guesses or automatic resubmission. Valid old preparation links
  work; generic/invalid/foreign/stale creation context guides/refuses without new work or scope leaks.
- [ ] New Files/task/recovery states work at 1536×1024 and 390×844 with keyboard, readable actions,
  loading/read error/401/403/not-found recovery, focus and exact return context. Existing ordinary
  local operations, administrative APIs/CLI and Automation records/intents remain intact.

## Required Tests

Follow workflow §6. Developer runs new/changed/directly affected checks; B owns T4 acceptance/full
regression. Exercise success, invalid input, conflict, failure and important edges above through
existing supported entries. Fault injection may delay/fail actual adapters/persistence; do not prove
behavior with unreachable database inventions, guessed routes, fabricated success payloads or DOM state.

### Developer — affected tests

From repository root:

```bash
python3 scripts/check_governance.py
git diff --check
.venv/bin/python -m unittest tests.test_media_discovery tests.test_media_discovery_provider_manifest tests.test_organize_preparation
.venv/bin/python -m unittest tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution
.venv/bin/python -m unittest tests.test_operations_task_center tests.test_task_center_recovery_lineage tests.test_recovery_continuation tests.test_recovery_batch
```

Extend these suites with early admission, direct-vs-folder filtering/attachments, exact request
readback beyond recent pages, source ownership races/settlement, real stability/bounds, four-type
recovery and normal confirmation membership. Any new dedicated source-ownership test module must
also be run explicitly and named in the handoff. Run the directly changed Automation admission/
execution suites when integrating source ownership; do not run all Automation tests by default.
Apply `.venv/bin/ruff check <changed-python-files>` and `.venv/bin/ruff format --check <changed-python-files>`.

From `web/`:

```bash
npm run test -- run src/features/library/StorageFilesPage.test.tsx src/features/operations/OrganizeCreationPage.test.tsx src/features/operations/OrganizeDiscoveryPage.test.tsx src/features/operations/OrganizeRouter.test.tsx src/features/operations/OperationsRouter.test.tsx src/features/operations/OperationsInventory.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/shared/api/operations-api.test.ts src/routes/router.test.tsx
npm run typecheck
npm run lint
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/operations-task-center-visual.python.spec.ts
```

Include any other new/changed component/entity/API tests explicitly. Apply Prettier to changed Web
files. Update the real-Python creation journey to begin from Files, not the removed center link.
Extend the existing harness/specs for real early admission, four business blockers, normal summary
return, exact lost response, backend reopen and actual selected execution. No new orchestration
framework or broad process-tool work. Run directly affected local ordinary-operation checks if
shared Files, task-link or query behavior changes; full direct-files/browser release matrix remains B-owned.

### B — acceptance and full regression

Review the entire immutable Task Base..candidate and reproduce the critical Files → admitted task →
four-type decision → analysis → confirmation → actual mutation path, plus direct/folder filtering,
parallel source reservation and normal WaitingConfirm readback. Verify backend service/repository
reconstruction over the same temporary database, not just page reload. Inspect real desktop/narrow
screenshots, read-error/permission states and no-write reads against built production assets.

Run the real-Python commands above and, from `web/`, the affected ordinary Files regression:

```bash
npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts
```

Run all applicable [shared full T4 gates](docs/development-workflow.md#shared-full-regression-commands):
full Python/Web/static/default E2E, wheel/installed-consumer smoke, C→A identity, RBAC, migration if
changed, source ownership/pins/fences and completed/uncertain non-replay. Since Worker/persistence
admission is affected, assess and run applicable packaged resident restart/deployment/security proof;
record exact candidate/artifact, commands/counts/skips and durable ignored evidence. Unavailable gates
remain pending, not PASS. Task46.2's known pre-existing row-menu native failure is not erased or
assumed fixed; retain its evidence and reassess only if this Task changes the relevant behavior.

Testing/build/probe wall time must be strictly below **50%** of this round's elapsed work time,
counting overlapping runs once, including failed probes. No deliberate waiting, repeated full suites,
weakened assertions/timeouts or transferred B full gates. A proven blocker permits early FIX REQUIRED
in this same Task. Planning requires only governance/document/whitespace checks, not product suites.

## Non-goals

- RO-4's complete organizing-only population across all legacy queries/details, eight-view/failure
  removal, all-history pending union and historical recovered-success projection. Necessary newly
  admitted manual-task membership and four-type lifecycle above are in this Task and cannot be deferred.
- Global Worker/resident block removal remains RO-4. No monitoring product, queue/Worker supervision
  redesign, general idempotency framework, source catalog or governance tooling.
- RO-5 Automation detail/Save/Enabled/grant removal/Run once intent or stability redesign. Only shared
  source-ownership safety integration is included; preserve existing saved filtering and authority.
- New commands/providers, MediaLibrary organizing, cross-kind transfer, global ordinary-operation
  center, cross-Task bulk recovery, arbitrary historical Reprocess, uncertain replay/rollback,
  Upload/Download, retired Scan/Preview/FileIndex restoration, auth redesign or unrelated row-menu fixes.
- Slice/Roadmap boundaries, A final review/closure or a second Task plan.

## Workspace and handoff

Planning starts on `main` at Task Base above. Governance passed; workspace/Git/TASK.md are writable.
Pre-existing deletion `docs/pics/操作与任务.png` and all untracked OS/log/reference/test artifacts,
including `15`, the Automation screenshots and `output/imagegen/slice45-task-center-v1.zip`, are
preserved and excluded. Private runtime configuration/databases/media are not fixtures. This planning
checkpoint changes only TASK.md; no push/publication. A-owned stale first-Task/Implementation Head
pointers in Slice/Roadmap/Progress are not changed by B or used to negate accepted Task46.1/46.2.

Planning validation: `python3 scripts/check_governance.py` PASS; `git diff --check` clean. No product
suite, runtime probe, build or media operation was run for planning; checking time is below 50%.

## Developer Completion Report

Status handed off: **PARTIAL — B46.3-02 and B46.3-03 delivered; B46.3-01 remains
unimplemented. The Task is NOT complete, and no PASS is claimed.**

Checkpoint: `1be609121614e322df8c3abd4c2984c51a00602d` (Task Base
`83144be20c6c7bc787a0fafad7fabb3e177bde6a`, on top of reviewed `d675594f`).

### What this checkpoint changes

**B46.3-02 — independent per-item admission outcomes.** `MediaDiscoveryService.admit`
no longer refuses a whole selection because one selected item is excluded. Each submitted
path resolves to either its real kind or its own `DiscoveryRefusedEntry`; eligible
siblings are admitted as real organizing work and the refused items are persisted with
their bounded `code`/`reason`/`message`/`nextAction`. Structural, RBAC, root-confinement
and budget validation still refuse the entire request, and a selection in which *nothing*
is admissible is refused with the first item's own reason instead of admitting empty work.
A lost-response retry of the same partly-refused selection now reconciles on the union of
admitted scope and refused entries, so it converges instead of claiming a different
selection. The refusal evidence round-trips through SQLite reopen.

**B46.3-03 — no automatic business vetoes on a deliberate folder selection.** The two
manual entrances are now distinct in the single shared predicate module:
`classify_manual_file_selection` keeps its exact-file meaning and the new
`classify_manual_folder_entry` applies only the configured primary-media extension set
(video by default) inside a folder the operator selected by hand, plus the unchanged
temporary/download and extension exclusions. `ManualFolderPolicy` carries the
automatic/deliberate distinction as a value, so the bounded walk asks one question and
`Scanner`/definition-bound filtering is untouched. `_refuse_automatic_directory` /
`_refuse_automatic_file` keep the pre-amendment include/exclude/match gates for
definition-bound Run once and remaining-scope recovery, so this is a per-admission
context and not a global weakening. The mode is stored inside the durable progress
document (`manualSelection`), so no schema column, no migration and no backfill of
existing rows is required: a pre-existing record round-trips as exactly the automatic
admission it was.

Deliberately selected folder and file selections now record only the hard bounds as
refusals: the configured depth (with its `prunedAncestor`) and the explicit
temporary/extension exclusions. Default images, subtitles and NFO never become
independent primaries or fabricated Recognition problems; artwork-off does not promote
them; the existing other-same-stem attachment setting is untouched; a folder of only
non-primary files settles as `empty_excluded` rather than a failure.

Web: refused entries render beside the admitted scope in both the discovery and the
summary workspace views, and the Files page now maps the backend's real bounded reason
(temporary / `excluded_extension_rule` / `configured_depth_exceeded` / `configured_exclude`
/ `not_included`) instead of describing every `source_excluded` as a temporary-file or
extension exclusion. `docs/architecture.md` CURRENT bounded-discovery text states the
deliberate folder rule, the durable admission mode and the per-item refusal contract.

### Files and checkpoints

- `mediaflow/application/scan_filters.py`: `ManualEntryVerdict.EXCLUDED_PRIMARY_EXTENSION`,
  `classify_manual_folder_entry`, `ManualFolderPolicy`.
- `mediaflow/application/media_discovery.py`: per-item `admit` outcomes, the new
  `_directory_refusal`/`_file_refusal` and `_refuse_automatic_*` split (the old
  `_refuse_unselectable_*`/`_refuse_pruned_ancestor` helpers were removed), refusal
  propagation at the definition and recovery entrances, `folder_policy` in `_advance`,
  `_REASON_PRIMARY_EXTENSION`, request-ID reconciliation over refused siblings.
- `mediaflow/domain/media_discovery.py`: `DiscoveryRefusedEntry`, `canonical_refusals`,
  `DiscoveryProgress.refused_entries` / `.manual_selection` (document-level, additive).
- `mediaflow/interfaces/service_api.py`: `selection.refused` / `selection.refusedCount`.
- `web/src/entities/operations/discovery.ts`, `web/src/shared/api/api-client.ts`,
  `web/src/features/library/StorageFilesPage.tsx`,
  `web/src/features/operations/OrganizeCreationPage.tsx`,
  `web/src/features/operations/OrganizeDiscoveryPage.tsx`.
- Tests: `tests/test_media_discovery.py` (`ManualEntrySemanticsTests` rewritten to the
  independent-outcome contract, new `ManualFolderExpansionTests`),
  `tests/test_v2_automation_run_once.py` (unchanged automatic veto),
  `web/src/features/library/StorageFilesPage.test.tsx` (reason-specific copy).

### Actual affected commands and results

From repository root:

- `python3 scripts/check_governance.py` — PASS; `git diff --check` — clean.
- `.venv/bin/python -m unittest tests.test_media_discovery tests.test_media_discovery_provider_manifest tests.test_organize_preparation tests.test_scanner tests.test_attachments tests.test_v2_automation_run_once` — **208 tests OK**.
- `.venv/bin/python -m unittest tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_operations_task_center tests.test_task_center_recovery_lineage tests.test_recovery_continuation tests.test_recovery_batch tests.test_automation_run_once tests.test_automation_definition_execution tests.test_automation_admission` — **298 tests OK**.
- `.venv/bin/python -m unittest tests.test_v2_manual_organize tests.test_operations_workspace tests.test_manual_operations tests.test_operations_run_inventory` — **121 tests OK**.
- `.venv/bin/python -m unittest tests.test_v2_automation_run_once tests.test_v2_automation_operations tests.test_configuration_snapshot` — **83 tests OK**.
- `.venv/bin/python -m unittest tests.test_runtime_files_browser tests.test_direct_file_operations tests.test_media_library_direct_commands tests.test_operations_run_detail` — **129 tests OK**.
- `.venv/bin/ruff check` / `ruff format --check` on all six changed Python files — clean.

From `web/`:

- `npm run test -- run` on the 10 named Files/Operations/entities/API/router suites —
  **176 tests passed**.
- `npm run typecheck` — clean; `npm run lint` — clean; `npm run build` — built;
  Prettier clean on every changed Web file.
- `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts`
  — **41 passed** (real Python API/SQLite/Worker/built assets).
- `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-task-center-visual.python.spec.ts`
  — **2 passed**.

Testing/build/probe wall time was ≈5.5 minutes of an ≈69-minute round (≈8%), counting
overlapping runs once. No full Python discovery, no full Web suite, no packaging/release
matrix and no direct-files release matrix was run; those stay B-owned. No assertion was
weakened and no retry was added.

### Tests that had to change, and why

Five pre-existing expectations encoded the contract B46.3-03 explicitly overrules. Each was
rewritten to assert the *new* contract plus the retained automatic behaviour, never a
weakening:

1. `test_directly_selected_file_ignores_include_and_match_rules` — a deliberate folder now
   keeps its `mkv` files despite an exclude/include rule.
2. `test_a_directly_selected_file_ignores_an_excluded_ancestor` — the deliberately selected
   folder below the excluded ancestor is now admitted.
3. `test_a_directly_selected_nested_folder_cannot_bypass_a_pruned_ancestor` →
   `test_a_directly_selected_nested_folder_below_an_excluded_ancestor_is_admitted`.
4. `test_published_exclude_and_stability_policy_reach_the_worker` — the deliberate
   `Movies/Excluded` selection is admitted; the published stability policy is still proven.
5. `test_a_trailer_of_an_unadmitted_main_file_keeps_ordinary_processing` — swapped the
   non-extension `filename` exclusion for a genuine `extension` exclusion, so the case
   still proves attachment association only against admitted primaries.
6. `test_a_partly_refused_selection_is_never_a_different_scope` (B46.3-02's named
   violation) → `test_a_partly_refused_selection_keeps_eligible_siblings` plus
   `test_a_wholly_refused_selection_creates_no_work`.

`test_a_directly_selected_file_below_a_depth_pruned_ancestor_is_refused` was kept and still
passes: depth is a hard reachability bound, not a business rule, and its `prunedAncestor`
detail is preserved through the new per-item refusal (`DiscoveryRefusedEntry.pruned_ancestor`).

### Remaining work — B46.3-01 (not implemented)

The Task's primary blocker is untouched by this checkpoint: the Files command
(`POST /api/v1/resource-libraries/{id}/files/discoveries`, `autoPrepare: true`) still admits
a *preparation*, and no durable organizing Task exists at submission. Still required:
Scopes 1/3/4/5/6 and the necessary Scope 7 integration — early durable organizing
admission before discovery/business readiness, verified atomic concrete-source ownership
across manual/Automation/continuation entrances with settlement, native four-type recovery
inside the admitted work, exact normal summary/confirmation membership in Running/All after
restart, durable Files task/preparation/unknown-request readback, and removal of the center
creation/manual-action/discovery entries and their exclusive reads. All acceptance bullets
except the direct-file/folder filtering ones remain unmet.

### Known risks / limits

- `selection.refused` is additive. The export/CLI/legacy consumers were not audited for a
  refused-entry projection; only the Web discovery/summary views and the API document
  consume it here.
- The primary-extension refusal inside a deliberate folder reuses the existing
  `unsupported_extension` reason string. That is deliberate (it is the same "not a primary
  media extension" fact an automatic walk reports), but a reader cannot tell from the
  reason alone whether the suffix came from a folder expansion or a direct selection; the
  per-item refused list is the only place a *direct* file refusal carries a distinct code.
- A deliberate folder selection no longer honours a configured `directory`/`glob` exclude
  rule. This is the intended RO-2/B46.3-03 semantics, but it is a real behaviour change for
  a library that used a directory rule as a manual veto; the automatic Scanner/definition
  path is unchanged and asserted.
- The `operations-inventory.python.spec.ts` intra-file ordering dependency reported in the
  previous handoff still exists; the whole file in order passes.
- Task46.2's known pre-existing row-menu native failure is untouched and neither fixed nor
  assumed fixed.

### Remaining Slice outcomes

RO-1 complete (Task46.1). RO-2 partially: direct-file *and* folder eligibility/filtering
plus independent per-item admission now match RO-2; early durable organizing admission,
source ownership, four-type recovery membership and the Files-only center removal are not
delivered. RO-3 complete (Task46.2). RO-4/RO-5 unchanged and still outside this checkpoint.

## B Review Result

```text
Reviewed Task range: 83144be20c6c7bc787a0fafad7fabb3e177bde6a..d675594f5cc5bb504aa47668c14ca700d41f1ed6
Implementation / partial handoff: d675594f5cc5bb504aa47668c14ca700d41f1ed6
Decision: FIX REQUIRED — 2026-10-25
Task blockers: B46.3-01/02/03 (P1)
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP; complete Task46.3, no new Task or Slice closure
```

B independently inspected the complete nine-file Task Base..Head manifest/diff, including the plan,
partial report, production predicates/admission/walk, tests, Web consumers and architecture text.
The checkpoint is a partial increment, not Task acceptance. Task Base/Goal/Scope/High/T4 and all
acceptance criteria remain unchanged. Existing direct-file filtering work can be retained while
completing the same coherent task; do not split remaining scopes into new Tasks or mark Scope 2 PASS.

### Required corrections

1. **B46.3-01 / P1 — deliver the admitted organizing journey, not preparation alone.**
   The actual Files request (`POST /api/v1/resource-libraries/library/files/discoveries`,
   `autoPrepare: true`) returns 202 with one discovery and zero Tasks immediately after submission.
   Implement Scopes 1/3/4/5/6 and necessary Scope 7 integration: durable organizing admission before
   discovery/business readiness, atomic concrete-source ownership across existing entrances and
   continuation, native four-type recovery, exact normal summary/confirmation in Running/All,
   durable Files task/preparation/unknown-request readback and removal of center creation/manual/
   discovery entries and their exclusive reads. Preserve analysis-only preparation, exact pins,
   full bounds/stability, explicit effect confirmation and completed/uncertain non-replay. The
   Developer's remaining-scope report cannot move this Task's RO-2 delivery into later RO-4 work.
2. **B46.3-02 / P1 — preserve eligible siblings on business refusal.**
   Through the same Files command, selecting `Movies/One.2001.mkv` together with
   `Movies/downloading.mkv.part` returns 409 `source_excluded/temporary_file`, with no durable work
   for the eligible file. Change the all-or-nothing business refusal in
   `MediaDiscoveryService.admit` / `_resolve_entry_kind` into independent admitted/refused item
   outcomes. Retain full structural/RBAC/root/bounds validation and truthful original scope; do not
   silently drop exclusions or claim they were organized. Show the refused item's reason and the
   eligible sibling's actual task/progress. Replace
   `ManualEntrySemanticsTests.test_a_partly_refused_selection_is_never_a_different_scope`, which
   currently asserts the contract violation, with coverage for independent outcomes and zero
   mutation before confirmation. Add the equivalent existing-task duplicate plus eligible sibling
   case when source ownership is implemented.
3. **B46.3-03 / P1 — remove automatic manual-entry vetoes for folder selections too.**
   A real published `directory: Movies` automatic exclusion still makes an explicit Files selection
   of `Movies` return 409 `source_excluded/configured_exclude` before any task exists.
   `_refuse_unselectable_directory`, ancestor checks and the folder walk still apply the automatic
   include/exclude gates. Follow RO-2/AC-16 and Task Scope 2: keep configured primary extensions
   (default video), explicit extension exclusions, attachment semantics and hard traversal/source
   safety; do not retain other automatic include/exclude/match conditions as extra manual vetoes.
   Preserve unchanged automatic Scanner/definition-bound filtering through an explicit admission
   context, not a global weakening. Cover folder and mixed-folder paths, including unrelated
   images/subtitles/NFO, custom primary extensions and artwork/other-same-stem settings. Correct
   the new tests and CURRENT architecture text that currently describe retained automatic folder
   vetoes as the complete Slice46 rule. Map the actual bounded reason in Web refusal copy: the
   current generic `source_excluded` copy incorrectly calls this directory-rule refusal a temporary
   or extension exclusion.

### Independent checks and evidence

Evidence is local, ignored and durable in
`.git/validation-evidence/d675594f/b46.3-review/`:

| Check | Actual result |
| --- | --- |
| Governance; full-range `git diff 83144be2..d675594f --check` | PASS / clean |
| `.venv/bin/python -m unittest tests.test_media_discovery.ManualEntrySemanticsTests` | 5 tests OK, 0.362 s test runtime / 0.58 s process wall; `changed-tests.log`; unclosed-SQLite ResourceWarnings remain visible |
| `.venv/bin/python .git/validation-evidence/d675594f/b46.3-review/entry_probe.py` | Three required behaviors above reproduced through existing authenticated Files API, real temporary Local Storage/SQLite; no mutation; `entry-probe.log`, 0.223 s probe body |
| `.venv/bin/ruff check mediaflow/application/media_discovery.py mediaflow/application/scan_filters.py tests/test_media_discovery.py` | All checks passed |

The probe reuses the existing discovery fixture and its validated/published test configuration;
it creates no invented route or impossible database state and uses no production media/secrets.
The five green tests establish only their asserted filtering behavior; they do not establish the
admitted-task journey or validate the contradictory all-or-nothing expectation. Developer-reported
suite results above are not relabelled as independent B runs.

Workflow §6 permits early FIX REQUIRED on proven P1 blockers. Full T4 Python/Web/native/packaging/
resident-restart acceptance remains pending for the corrected candidate; no gate is waived and no
product/visual/full-suite PASS is claimed. Developer runs failing/new/affected tests and hands off
the complete Task; B retains full acceptance ownership. No optional consumer labels, unrelated
row-menu issue or process-tool improvement is promoted to a new Task.

Review started at 12:18:18 UTC. Tests/probes/static/governance commands together consumed less than
5 seconds of subprocess wall time, inside more than two minutes of contract/code/evidence review
before reconciliation; testing is strictly below 50%. No deliberate waiting or repeated full suite.

### All Slice outcomes reevaluated

| Outcome | Assessment at reviewed Head |
| --- | --- |
| RO-1 readable shared actions | Prior Task46.1 acceptance retained; no readability/style change here |
| RO-2 Files-first organizing | Incomplete; partial direct-file predicate change only, B46.3-01/02/03 block this Task |
| RO-3 local ordinary operations | Prior Task46.2 acceptance/evidence limits retained; local status implementation unchanged |
| RO-4 organizing-only center/four-type truth | Incomplete; no complete population/view/recovery delivery in this checkpoint |
| RO-5 Automation detail/Enabled/Run once | Incomplete; unchanged, remains outside Task46.3 except shared source-ownership integration |

Slice remains ACTIVE. Only B-owned TASK.md changes in this review checkpoint; Slice/Roadmap/Progress
and all pre-existing dirty/untracked/private/reference files are preserved. No product implementation,
push, publication, new Task, history rewriting or Slice closure by B.
