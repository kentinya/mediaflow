# Slice 37 — Files Workspace, Common File Management and V2 Shell

This is the A-owned Slice Contract for the Files workspace, its ResourceLibrary journey, bounded
common file management and the shared V2 shell replacement required by the canonical visual
reference. Slice 33 remains `PASS / CLOSED` in Git and Progress history. The previously planned
Slice 34, Slice 35 and Slice 36 boundaries remain retired.

```text
Slice ID: 37
Name: Files Workspace, Common File Management and V2 Shell
Owner: A — Slice Owner / Architect / Final Reviewer
Status: ACTIVE
Base SHA: b507edba167f5af3af8c53bfcf1417ba4fefddf4
Implementation Head: 3e15ab35f3ebb7e76cb278fb5004726ad5b7aebb
Contract Revision: 2026-09-22 A POST-CLOSURE REACTIVATION — Files exact path identity and whitespace presentation
```

The Slice Base is immutable. This A-owned rescope superseded the earlier
Files-page-only/frozen-shell interpretation without changing that Base. Work produced by Task 37.1
before this revision was implementation evidence only and was reviewed against this checkpointed
Contract as part of the completed Slice.

## Post-closure Reactivation

On 2026-09-20, A reactivated Slice 37 under the post-closure P0/P1 correction loop. The
newly discovered P1 defect is a user-visible target-path semantic mismatch: the local CLI
previews `ClassificationRule.result.library` as the first target-path prefix, while the
formal Organize flow omits it and starts with `result.path`. The same configured rule can
therefore preview and organize to different destinations.

This correction remains inside RO-8 Organize workflow continuity and the existing final-target
composition invariant. It does not add a new provider, classification condition, Storage
capability, mutation path, Files surface or non-Files business journey. The prior Closure Packet
and A Final Review remain historical facts; this reactivation adds one focused correction Task
and requires a fresh A review over the original Base through the corrected head.

## Current Post-closure Reactivation — Files Refresh Truthfulness

On 2026-09-21, A reactivated Slice 37 again under the post-closure P0/P1 correction loop after
production-like use showed that an externally deleted ResourceLibrary directory such as
`source/电影/SSH` can remain visible in the Files directory tree after the operator clicks
`刷新`.

The defect is a P1 user-visible state/recovery break inside RO-3 exact Files composition,
RO-5 Storage-authoritative Files data, RO-9 actionable recovery and RO-11 test reconciliation.
The backend Files read already re-reads live Storage and does not use FileIndex as its V2 Files
authority. The Web page retains `knownDirectoryPaths` and `visitedDirectories` across a refresh,
so the directory tree can re-render a path that the refreshed Storage listing no longer contains.

This correction is intentionally narrow: refresh must reconcile the local directory-tree and
selection presentation with the newly fetched live listing. It does not add a FileIndex sync,
background scan, mutation, cache layer, provider capability, route, or new Files command. The
prior Closure Packets and A Final Reviews remain immutable historical facts; this reactivation
adds Task 37.9 and requires a fresh A review over the original Slice Base through the corrected
head.

## Current Post-closure Reactivation — Files Exact Path Identity

On 2026-09-22, A reactivated Slice 37 again under the post-closure P0/P1 correction loop after
production-like Docker use found that a ResourceLibrary directory whose real Storage name is
`SSH ` (one trailing ASCII space) is shown as `SSH` and opens as `电影/SSH`, producing a
Storage `not_found` error even though the live directory is present.

The deployed stack is running from `/opt/mediaflow` and mounts the host Storage
`/mnt/HDD_2` at `/media`. The live Files API correctly returns the exact entry identity
`name = "SSH "` and `path = "电影/SSH "`. The Web shared normalizer applies `trimEnd()` to
the Files entry name/path projection, so the UI loses the identity character before rendering and
navigation. This is a P1 user-visible path-authority and recovery break inside RO-3 exact Files
composition, RO-5 Storage-authoritative Files data, RO-9 actionable recovery and RO-11 test
reconciliation.

This correction is intentionally limited to the Web Files projection and its tests: exact
Storage-relative names and paths must survive normalization, navigation must request the exact
encoded path, and invisible leading/trailing whitespace must be made unambiguous in the visible
Files presentation. It does not change Storage providers, backend/API contracts, FileIndex,
Docker/Compose deployment, or any media directory. The user-owned test residual directory is
explicitly outside this Task and will not be deleted, renamed or otherwise mutated by Developer.
This reactivation adds Task 37.10 and requires a fresh A review over the original Slice Base
through the corrected head.

The same reactivation also records a RO-11 quality-gate correction discovered in GitHub Actions
quality run `#115` on 2026-09-21. The accepted Local directory replacement risk uses the provider's
stable directory identity (the inode segment), while the two host-filesystem tests were branching
on the full `inode:...:ctime:...` token and could demand a refusal in the already-accepted
inode-reuse/ctime-change case. Task 37.9 must align those tests with the accepted contract without
changing production fencing, adding skips, or claiming the race is fixed. The release-quality Task
command inventory must also remain present in the active `TASK.md`.

GitHub quality run `#117` then showed that the corrected tests completed successfully on Python
3.11 and 3.13, while the Python 3.12 matrix job was cancelled by the existing 15-minute test-job
timeout before its full 1718-test run completed. Task 37.9 raised only the quality test job timeout
to 30 minutes; it did not remove a Python version, weaken a test, or change the wheel job timeout.
The resulting GitHub quality run `#118` on commit `320d8437a8872f7a08ee84295a0f900a39f84a7d`
passed all Python 3.11/3.12/3.13 jobs and the dependent wheel build/smoke job. CI is now a green
baseline for the remaining Files Web implementation.

## Current A-owned Scope Clarification — Remove Files Recognition/Status Feedback

On 2026-09-21, A authorized a focused Files presentation correction: the Files page must no
longer present the business concepts `识别结果` or `整理状态`. This removes those concepts from
the Files information banner, table headers/cells and row status presentation. The Files table
continues to expose physical file facts and explicit actions, with the resulting columns:
`选择 | 名称 | 类型 | 大小 | 修改时间 | 操作`.

This is a presentation-boundary correction, not removal of the underlying recognition, metadata,
FileIndex or organize data model. The backend/API projections may remain available for their
existing authorities and result synchronization, but Files must not display those two concepts as
business feedback. The explicit `整理` operation, single-item Preview path, bounded batch path and
OrganizerExecutor authority remain in scope and must continue to work.

The current visual source of truth must be reconciled to this clarification before final review.
The existing visual-spec wording that names the removed columns remains historical/pending
synchronization until that follow-up is completed; it does not authorize reintroducing the
removed page presentation.

## Current A-owned Scope Revision — Remove Direct Files Upload/Download

On 2026-09-20, A explicitly revised the current Slice boundary after confirming that the operator
does not need direct browser Upload or Download from the Files workspace. The current product
surface therefore retains Files browsing, ResourceLibrary activation, Create Folder/Text File,
Rename, Copy, Move, Delete, bounded text Edit and Organize continuation, but no longer offers
direct browser Upload or Download.

This is a vertical product-scope removal, not a UI-only hide. The implementation must remove the
Files Upload/Download controls, dialogs, client calls, HTTP routes, application services, direct
Upload/Download domain projections and their dedicated tests. It must not remove Storage
`Read`/`Write`, OpenList/S3 provider transfer primitives, Copy/Move transfer behavior or other
OrganizerExecutor capabilities used by the remaining journeys.

The previous Slice 37 Closure Packet recorded the then-delivered Upload/Download surfaces and
remains historical evidence. This current A-owned revision supersedes those surfaces for the
reactivated implementation boundary; it does not delete or rewrite the historical record.

## Current A-owned Scope Clarification — Copy/Move Bounds

On 2026-09-20, A clarified the existing bounded Copy/Move contract after production evidence showed
that the implementation treated `20 GiB` of source media content as an admission limit. Media
content byte size does not materially determine the in-memory manifest size and must not by itself
reject a Copy or Move.

For Copy/Move, bounded scope means:

- bounded top-level selection count;
- bounded recursively enumerated entry count and directory depth;
- bounded safe relative paths and bounded manifest/checkpoint/operator projections;
- metadata-only Impact/admission that does not read media bytes;
- the existing one-Task, per-item execution, fencing, conflict and recovery behavior.

The aggregate media byte count remains useful impact/progress information, but it is not a
Copy/Move admission ceiling. This clarification does not authorize multi-batch orchestration,
parallel child Tasks, a native-directory-Move bypass, a new Storage capability, an implicit
fallback or automatic replay. Delete and bounded text Edit retain their own existing content/scope
limits.

## Current A-owned Residual Risk Disposition — Concurrent Local Directory Replacement

On 2026-09-21, A accepted the narrow residual race in which another process deletes and recreates
the same Local directory between the final confirmed-scope revalidation and the actual Delete, and
the filesystem reuses the previous inode. The existing implementation already requires explicit
Delete confirmation, re-enumerates and digests the bounded scope before mutation, performs a final
metadata revalidation and mutates only through `OrganizerExecutor`. Those controls remain mandatory.

Slice 37 does not add a cross-provider directory-generation architecture, birth-time/statx
dependency, persistent directory handle model or new Storage capability solely to close this
extremely narrow race. The limitation is documented in README with an operator recovery/prevention
path: quiesce download, sync and other file-management processes for the selected directory,
refresh Files, review the current impact and confirm again immediately.

This disposition does not authorize removing the existing scope digest, stale checks, explicit
confirmation, bounded enumeration, per-item outcomes or non-replay rules. It changes the current
acceptance meaning by treating inode-reuse inside that final race window as a known non-blocking
residual risk rather than a Slice P0/P1 blocker. B must reevaluate Task 37.8 against this revision;
Developer must not implement the superseded directory-generation/fencing expansion.

## Scope decision

The approved [`docs/pics/文件页.png`](docs/pics/文件页.png) is the product design to implement, not
an inspiration image and not a page card to place inside the old dark horizontal V2 shell. Slice 37
owns a deliberate replacement of the previous V2 shell presentation with the reference's light
left navigation rail and top bar. The same shared shell must frame all V2 routes so Files does not
create a second navigation system. Existing non-Files business journeys, route authority and page
behavior remain intact, but their outer shell pixels are intentionally allowed to change.

Slice 37 also makes Files a practical common file-management surface. In addition to browsing and
organizing, an authorized operator can create folders or supported text files; rename, copy, move
and delete files/directories; and edit bounded supported text files. Direct browser Upload and
Download are removed from the current product boundary.
Single-item actions and bounded multi-selection actions share one Files interaction model. These are
direct file-management commands, not media recognition/metadata/naming/classification/organize
decisions. They do not require the full Organize Preview/policy/execution-token ceremony, but every
mutation remains backend-authoritative, confined to explicitly selected Active ResourceLibrary
roots, capability-checked, auditable and executable only through `OrganizerExecutor`. Delete and
replace are never silent; conflicts, partial transfer and stale content remain explicit.

Arbitrary binary/media-content editing, unbounded recursive operations, arbitrary host paths and
implicit operation fallback remain outside this Slice.

During this reactivation, Slice 37 also owns the formal destination-composition correction:
`ClassificationRule.result.library` must be validated as a safe relative path prefix and
composed before the classification rule's relative `path`, matching the CLI's `Movies/其他电影/...`
behavior. `mediaLibraryId` continues to select the configured MediaLibrary, Storage and root;
`library` does not replace that authority.

The detailed visual source of truth is
[`docs/file-page-visual-spec.md`](docs/file-page-visual-spec.md). The image is authoritative for
visual detail; this Contract controls product scope, authority and safety.

For the current reactivation, this Contract additionally controls the Files presentation boundary:
the page does not display `识别结果` or `整理状态`, while the explicit `整理` action and its
server-authoritative continuation remain available. The visual specification must be synchronized
before final Slice review.

## User goal and vertical journey

**Goal:** an authorized operator can enter the redesigned V2 shell, open Files, understand the
active ResourceLibrary, browse live Storage entries, perform ordinary bounded file management,
create a ResourceLibrary and continue selected media through safe organization without interpreting
backend implementation details.

**Entry:** select `文件` in the shared reference-aligned V2 shell or open
`/ui-v2/library/files` (router path `/library/files`) through the existing memory-only API-principal
authentication boundary.

**Visible state:** at `1536 x 1024` the route presents the canonical reference composition: shared
light left rail, top bar, active Files navigation, search, ResourceLibrary summary, information
banner, directory tree, breadcrumb, file table, selected row, selection footer, pagination and open
`添加资源库` drawer. The action surfaces expose `新建文件夹`, `新建文本文件`, `重命名`,
`复制`, `移动`, `删除` and supported `编辑`. Direct `上传` and `下载` surfaces are absent.
The Files page does not display `识别结果` or `整理状态` feedback; the explicit `整理` action
remains available. Unsupported actions are absent or explain why they are unavailable. Raw backend
authority fields are not displayed.

**Action:** browse or refresh a ResourceLibrary-relative directory, switch presentation, select or
clear entries, create a folder or supported text file, rename/copy/move/delete eligible files or
directories, edit and save bounded text, create and activate a ResourceLibrary, or open the
existing server-authoritative organize Preview journey.

**Success:** shell and Files visuals match the reference; direct file actions update the live
listing without leaving hidden stale selection; a saved ResourceLibrary becomes part of the exact
Active runtime; and terminal Organize results synchronize their known outcome to FileIndex.

**Failure:** missing Active configuration, unavailable Storage, invalid path, stale or changed
source, unsupported operation, name/destination conflict, edit conflict/encoding/size failure,
bounded-recursion or transfer-limit failure, partial copy/move, denied permission, malformed
response, activation failure, Organize failure or FileIndex synchronization failure is shown on
the affected item with no fabricated success, implicit overwrite/delete or uncertain replay.

**Recovery:** return to the ResourceLibrary root, correct a name, destination or edit conflict,
reload changed text, inspect independently completed/failed Copy/Move items, explicitly confirm a
still-current bounded deletion, select another ResourceLibrary, correct and resubmit a failed
ResourceLibrary save, inspect the durable Organize result or repair bounded index synchronization.
Failed or uncertain mutations refresh truth and are never automatically repeated.

## Required Outcomes

| ID | Outcome | Acceptance state |
|---|---|---|
| RO-1 | **Reference-aligned visual fidelity.** | A controlled `1536 x 1024` Files success screenshot preserves the canonical image's shared-shell and Files hierarchy, visible fixture state, labels, control order and design intent. Pixel-diff counts are diagnostic rather than a pass/fail threshold; bounded differences in font/glyph rendering, icon or thumbnail artwork, exact dimensions/spacing, borders, shadows and color nuance are acceptable when the required composition remains complete, recognizable and operable. |
| RO-2 | **Shared V2 shell replacement.** | The old dark horizontal shell is replaced by the reference-aligned light left rail/top bar across V2. Files has no alternate shell; existing route/auth/deep-link behavior remains shared and non-Files business journeys remain functional. |
| RO-3 | **Exact Files composition.** | Header, banner, ResourceLibrary summary, directory tree, breadcrumb, toolbar, table, row values/actions, selection footer, pagination and drawer appear in the exact reference order and hierarchy; the Files page does not expose `识别结果` or `整理状态` feedback, while the explicit `整理` action remains available. |
| RO-4 | **ResourceLibrary drawer and activation.** | The three-step drawer matches the reference; final `保存` submits one complete candidate and the backend validates and atomically activates it, preserving the previous Active on every failure. |
| RO-5 | **Storage-authoritative Files data.** | Physical entries and paths come from live ResourceLibrary-scoped Storage. FileIndex remains available for bounded backend reconciliation and existing result synchronization, but it does not supply Files-page recognition/status presentation, source/path authority or execution authority. |
| RO-6 | **Bounded common file management.** | Files provides Create Folder/Text File, Rename, Copy, Move, Delete and supported bounded text Edit for eligible files/directories, including bounded multi-selection where meaningful; success refreshes live state and partial/failure outcomes remain independent and recoverable. Copy/Move are bounded by selection, entry/depth/path and control-plane evidence, not by aggregate source media bytes. Direct browser Upload and Download are outside the current product surface. |
| RO-7 | **Low-friction direct-operation safety.** | Direct file actions do not run the Organize recognition/planning pipeline or require organize execution-token ceremony. Backend RBAC, explicit mutation intent, Storage capability/confinement, stale/conflict checks, audit, no silent overwrite/delete and `OrganizerExecutor`-only mutation remain mandatory. |
| RO-8 | **Organize workflow continuity.** | Files-originated Preview remains ResourceLibrary-scoped and Storage-relative, derives SourceIdentity from live Storage, continues through existing Preview/intent/OrganizerExecutor authority and synchronizes each terminal result independently to FileIndex. Formal destination composition uses the same `library/path` prefix semantics as the CLI. |
| RO-8C | **Formal classification path parity correction.** | For a classified rule with `library = "Movies"` and `path = ["其他电影"]`, every formal Plan, Preview, precheck, execution and result projection composes `Movies/其他电影/...`; the configured `mediaLibraryId` still resolves the actual destination MediaLibrary and Storage root. |
| RO-9 | **Actionable recovery.** | Read, direct-operation, activation, Organize and index-sync failures preserve Files context, explain durable/known state and provide a safe next action without fabricated rows or automatic uncertain replay. |
| RO-10 | **Non-Files behavior continuity.** | Dashboard, Operations, Review, Configuration, Notifications and Settings retain their existing routes, application behavior, permissions and recovery while adopting the new shared shell chrome; V1 `/ui` remains unchanged. |
| RO-11 | **Test reconciliation.** | Conflicting legacy shell/Files assertions are removed and replaced by Contract-aligned visual, interaction, mutation, failure and frozen-behavior tests; no safety assertion is weakened or skipped. |
| RO-12 | **Security model continuity.** | The Slice reuses existing API-principal authentication, RBAC, audit and backend authority; it introduces no username/password, cookie session, OIDC or frontend Storage authority. |

## Required Surfaces

- the shared V2 shell chrome for every `/ui-v2/*` route, including responsive behavior;
- V2 Files at `/ui-v2/library/files`;
- the Files-local `添加资源库` drawer and its backend Save/activation command;
- bounded ResourceLibrary browsing, selection and organize continuation; the Files page does not
  present recognition/status feedback;
- Files toolbar/action menus, destination picker and transfer progress for Create Folder/Text File,
  Rename, Copy, Move, Delete and supported text Edit;
- backend/application behavior strictly necessary for direct file commands, ResourceLibrary
  Save/activation and post-mutation FileIndex synchronization;
- the shared formal destination composition used by Organize Plan, destination Preview/precheck,
  manual/automation projections and execution result evidence;
- existing non-Files V2 page bodies only as needed to keep them functional inside the replaced
  shared shell; their business features are not redesigned by this Slice.

## Product Experience / UX Constraints

- The reference is the intended product, so retaining the old V2 chrome is not a compatibility
  objective. Files must feel like the reference workspace rather than a redesign nested in a legacy
  frame.
- The ordinary path is direct: choose entries and a common command, supply only the required name,
  destination or supported text, then see progress/result in the same Files context.
- Create, Rename, Copy and Move do not add redundant confirmation after valid input unless
  the operator explicitly chooses Replace. Text Save is the write intent; Delete uses one clear
  permanent-effect confirmation. No direct command exposes organize Preview, policy selection or
  execution tokens.
- Unsupported actions must be absent or explained. Disabled controls, generic errors and raw
  protocol/exception details are not substitutes for an actionable reason and recovery.
- Selection, expanded directories and current ResourceLibrary context must stay truthful after a
  mutation; deleted or renamed entries cannot remain as hidden stale selection.
- Files presentation must remain focused on live Storage facts and explicit actions: it must not
  show `识别结果` or `整理状态` business feedback, but it must retain the explicit `整理` action
  and its existing safe continuation.
- Existing non-Files routes keep their information and recovery semantics inside the new shell.
  Shell replacement must not fabricate product areas that have not been migrated.
- Desktop reference fidelity is structural and reference-aligned rather than pixel-identical.
  Exact raster output, typography metrics, icon/thumbnail artwork and CSS measurements may differ
  without blocking acceptance when the complete reference hierarchy, fixture state, labels and
  controls remain recognizable and operable. Narrower layouts remain bounded, operable and free of
  horizontal action loss.

## Shared shell contract

- The reference left rail and top bar replace the old dark horizontal `Operator workspace` shell.
- The left rail uses the reference brand, subtitle, recognizable icon/spacing treatment, active
  state and ordered labels: `首页`, `文件`, `媒体库`, `存储管理`, `整理规则`, `自动化`, `操作与任务`,
  `通知`, `系统设置`.
- Navigation labels route to the existing supported V2 destination or an existing truthful migration
  landing; visual replacement does not fabricate a completed business surface.
- The bottom `系统存储` block is bounded system-status presentation and performs no Storage access
  merely by rendering.
- The top bar contains the route-relevant search affordance, notification entry and bounded current
  principal/account control. The controlled reference fixture displays `admin`; production does not
  infer a new identity system or expose the bearer token.
- All V2 routes use this one shell component and one navigation model. Files-specific search behavior
  may be injected into the shared top-bar slot without creating a second shell.
- V1 `/ui`, backend routing and authentication semantics do not change.

## Common file-management contract

### Create Folder and Text File

- Create one directory in the currently selected ResourceLibrary-relative destination using a valid
  basename. Existing-target conflict fails without replacing anything.
- Create Text File creates one empty or initial bounded allowlisted text file and then uses the same
  stale-safe Edit/Save behavior. It cannot create arbitrary binary/media content.
- Creating multiple nested path segments, a ResourceLibrary root or an absolute host path through a
  name field is rejected.

### Rename

- Rename applies to one exact ResourceLibrary-relative file or directory at a time and keeps it
  within the same ResourceLibrary and Storage.
- The operator edits only the basename. Separators, dot segments, absolute paths, reserved/invalid
  names and root rename are rejected locally and by the backend.
- Existing-target conflict never overwrites silently. The operator corrects the name or uses a
  separately supported explicit conflict action; this Slice does not add rename-overwrite.

### Copy and Move

- Copy and Move accept one item or a bounded selection of files/directories plus an explicitly
  selected destination inside an enabled Active ResourceLibrary root. Source and destination paths
  are resolved by the backend; the browser never supplies host paths or credentials.
- Copy/Move Impact may enumerate bounded metadata and calculate aggregate media bytes for display,
  but aggregate source content size is not an admission limit. Manifest/checkpoint/projection memory
  remains bounded through top-level selection, entry count, directory depth, safe path length and
  bounded output rules.
- Same-Storage operations use the provider's advertised native capability. The system never silently
  substitutes Copy for Move, Move for Copy, or another organize policy.
- Cross-Storage Copy is allowed only through an explicitly advertised backend transfer path.
  Cross-Storage Move is an explicit compound `Copy -> verify -> Delete source` operation, shown as
  such before submission and recorded per item. A failed verification never deletes the source; a
  failure after verified copy leaves a visible partial result and safe cleanup/continuation action.
- Destination conflicts default to no overwrite. `跳过`, `保留两者/重命名` and `替换` may be
  offered only as explicit supported choices; Replace requires a separate permanent-effect
  confirmation and exact destination revalidation.

### Delete

- Delete applies to one item or a bounded selection of files/directories. ResourceLibrary roots are
  never deletable. A non-empty directory is enumerated within configured item/depth/size limits;
  unbounded or changed scope fails before deletion.
- The UI identifies the exact selection and, for directories, a lightweight item/size impact
  summary, then requires one explicit permanent-effect confirmation. This is not an Organize
  Preview and requires no raw execution token.
- Capability/permission denial, changed source and uncertain effect remain visible and are not
  automatically retried.

### Edit

- Edit is limited to allowlisted bounded text sidecars such as NFO and subtitle/text files. It is
  not a video/audio/image editor and does not inspect media streams or add FFmpeg/FFprobe.
- Read and Save are size bounded. Invalid encoding, binary content and oversized content fail with
  an explanation and no write.
- Save is the operator's explicit overwrite intent for the exact loaded Storage version. A changed
  source fails stale rather than silently replacing newer content.

### Direct browser Upload and Download

- Direct browser Upload and Download are intentionally removed from the current Files product
  surface.
- This removal does not change Storage `Read`/`Write` contracts or provider primitives needed by
  OrganizerExecutor, Copy/Move, text Edit or other supported backend workflows.

### Shared direct-operation behavior

- The browser submits only ResourceLibrary identity, relative path, requested bounded operation and
  the minimal stale/conflict evidence required by the backend. It never supplies absolute host paths
  or Storage credentials.
- Python application behavior resolves every current Active source/destination ResourceLibrary and
  Storage binding, enforces RBAC, validates capability/path/source state, records a bounded audit and
  invokes every mutation only through `OrganizerExecutor`.
- A direct operation is not reclassified as media organization and does not call Parser,
  Recognition, Metadata, Naming, Classification or the organize Planner.
- Single quick operations may complete synchronously; any long, recursive or batch mutation uses the
  existing Task system with independent per-item outcomes and progress.
- After known success, Files refreshes from live Storage. Any bounded FileIndex reconciliation is
  display bookkeeping only; failure is recorded without replaying the Storage effect.

## Safety and Authority Invariants

- Scanner, Parser, Recognition, Metadata, Naming, Classification and Planner remain zero-mutation.
- Files reads, refreshes, navigation, search, selection and view switching remain zero-mutation.
- All reads and direct actions are confined to explicitly selected enabled ResourceLibraries and
  their Active configured Storage roots; arbitrary host paths and unselected destinations are
  rejected. Cross-Storage transfer is admitted only as the explicit bounded Copy/Move contract
  above, never as an implicit fallback.
- Only `OrganizerExecutor` may call mutating Storage operations, including CreateDirectory, Copy,
  Move, Delete and Write initiated by Files. Download/read streaming remains zero-mutation.
- Direct file management uses a smaller admission path than Organize but never bypasses RBAC,
  capability checks, explicit mutation intent, conflict/stale checks, audit or path confinement.
- Delete and overwrite/Replace remain explicit. No create, rename, copy, move, text Save or deletion
  silently replaces/removes user data.
- Local directory Delete retains bounded impact, explicit confirmation and final stale revalidation.
  The accepted concurrent delete/recreate plus inode-reuse residual race is documented in README;
  operators must quiesce other writers and refresh/reconfirm when the selected path may be changing.
- No automatic retry follows an uncertain mutation. Recovery begins by refreshing live Storage and
  showing the known effect state.
- Files-originated Organize Preview/continuation still derives authority from live Storage and never
  from FileIndex. The browser submits only ResourceLibrary identity and relative path.
- FileIndex remains display/reconciliation state, never physical listing, path validation, Preview
  source identity or execution authority.
- The final ResourceLibrary `保存` remains backend-atomic and preserves the prior Active on failure.
- No new authentication/identity/session system, FFprobe/FFmpeg dependency, provider switch, schema
  rewrite or silent operation fallback is introduced.

## Test and Compatibility Policy

- Every supported common file action covers success, invalid input, permission/capability denial,
  path escape, stale source, target conflict, limits, partial transfer, Storage failure, uncertain
  effect and safe recovery as applicable.
- Tests prove Create Folder/Text File, Rename, Copy, Move, Delete and Edit cannot bypass
  `OrganizerExecutor`, cannot touch an unselected ResourceLibrary/Storage root and cannot silently
  overwrite/delete. Removal tests prove direct Files Upload/Download controls, routes, services and
  client projections are absent while required Storage/provider primitives remain available.
- Cross-Storage tests prove Copy verification precedes Move source deletion, a failed verification
  preserves the source, partial outcomes are durable and no operation silently falls back.
- Bounded Copy/Move tests prove independent per-item state and that selection count, entry count,
  directory depth, path and control-plane evidence limits stop unbounded work before destructive
  effects; aggregate source media bytes are display evidence, not admission authority. Delete and
  text Edit retain their applicable content/scope size limits.
- Tests prove read-only Files interactions remain zero-side-effect and do not create Tasks, call
  Providers or invoke any mutation path.
- Tests prove ResourceLibrary Save rejects invalid/conflicting candidates and preserves prior Active.
- Tests prove Files listing remains Storage-authoritative and FileIndex reconciliation failure does
  not replay completed/uncertain mutation.
- Controlled screenshots prove the reference composition, fixture state and new shared shell across
  Files. Pixel-diff metrics remain useful diagnostic evidence but are not a zero-difference gate;
  responsive and route smoke evidence proves non-Files journeys still work.
- Existing tests that freeze the old dark shell or contradict this Contract must be replaced, not
  retained to force obsolete behavior. Security/authority tests must not be deleted or weakened.
- Fakes, mocks, temporary roots and local services only; no production credentials or media.

## Explicitly Deferred

- Direct browser Upload and Download are removed from the current product scope, not deferred for a
  later Files implementation.
- Arbitrary binary/video/audio/image content editing and media-stream inspection.
- Unbounded recursive/batch operations, arbitrary host-filesystem access, Storage-to-host extraction
  and implicit cross-Storage fallback.
- General Configuration/Settings redesign beyond truthful navigation inside the new shared shell.
- Dashboard, Operations, Review/Recovery, Automation and Notification business-journey redesign;
  their shared shell chrome changes, but their existing page behavior remains.
- V1 `/ui` cutover/retirement and broad parity/accessibility closure beyond the changed shell/Files
  surfaces.
- New providers, Storage adapters/capabilities, identity/security systems, automatic uncertain
  mutation replay, universal rollback and FFmpeg/FFprobe.

## Slice Acceptance Criteria

- [x] At `1536 x 1024`, the Files screenshot preserves the reference shared-shell and Files
      hierarchy, visible fixture state, labels and control order. The comparison records material
      differences, but nonzero pixel counts and bounded rendering/layout variations do not fail the
      Slice when the composition remains complete, recognizable and operable; the reference asset
      is not rewritten merely to manufacture a passing comparison.
- [x] The old dark horizontal V2 shell is fully replaced by the reference light rail/top bar, using
      one shared shell across V2 and retaining auth/deep-link/route recovery.
- [x] Required labels, values, row order, selection states, drawer steps and controls from the visual
      spec are present. Recognizable implementation-owned icons/thumbnails and bounded table
      truncation are acceptable when the complete value remains available to assistive technology
      and the action/state remains unambiguous.
- [x] Create Folder/Text File, Rename, Copy, Move, Delete and supported text Edit complete from
      Files with low-friction success/failure/recovery and bounded multi-selection where useful.
- [x] Direct Files Upload and Download controls, routes, services, models and dedicated tests are
      removed; Storage/provider primitives needed by remaining workflows remain intact.
- [x] Delete and Replace/text overwrite require explicit operator intent, never silently affect
      another path/version and never automatically replay an uncertain result.
- [x] Same- and cross-Storage Copy/Move expose capability and compound-operation truth; verification
      failure preserves the source and partial results remain independently recoverable.
- [x] Copy/Move no longer rejects a file or bounded directory solely because aggregate source media
      bytes exceed 20 GiB; Impact remains metadata-only and manifest/checkpoint/projection state
      remains bounded by selection, entry/depth/path and output limits.
- [x] `+ 添加资源库` saves, validates and atomically activates a complete candidate; any failure keeps
      the previous Active.
- [x] Physical listing remains live Storage-authoritative; FileIndex is display/reconciliation only.
- [x] Files-originated Organize remains live-Storage/ResourceLibrary-authoritative and each terminal
      result synchronizes independently without mutation replay.
- [x] Formal Organize destination composition includes the classification `library` prefix before
      the classification relative path, matching the local CLI, across Plan, Preview, precheck,
      execution and result evidence.
- [x] The `library` prefix is validated with the same bounded safe-relative-path rules as other
      destination contributions; unsafe values fail closed without Storage mutation.
- [x] Files `刷新` re-reads the live ResourceLibrary directory and reconciles local directory-tree
      and selection state so an externally removed path is no longer shown after refresh; the
      regression path remains read-only and does not consult FileIndex or mutate Storage.
- [x] Files no longer renders `识别结果` or `整理状态` in the information banner, table headers,
      row cells or status pills; the table retains `选择 | 名称 | 类型 | 大小 | 修改时间 | 操作`,
      the explicit `整理` action remains functional, and the synchronized visual specification
      records the same presentation boundary.
- [x] Non-Files V2 business routes remain functional inside the new shell; V1 `/ui`, API/RBAC and
      backend mutation authority remain intact.
- [x] Conflicting old visual tests are replaced and all required T4/full Slice gates pass without
      hidden skips or private configuration.
- [x] The implementation checkpoint contains only Slice 37 work and necessary evidence.

## Final Validation Expectations

- deterministic `1536 x 1024` screenshot and pixel-diff report against the canonical image after
  fonts/assets load, evaluated under RO-1's structural/reference-aligned acceptance rather than a
  zero-difference threshold;
- shared-shell route/deep-link/auth/401/403/responsive smoke across every V2 product area;
- Files browse/search/navigation/selection/pagination/drawer interaction evidence;
- Create Folder/Text File, Rename/Copy/Move/Delete/Edit success and failure evidence against
  temporary Storage, including conflict, stale source, control-plane transfer limits, large media
  byte totals, partial outcome, capability denial, confinement, audit and uncertain-effect
  non-replay;
- Direct Upload/Download removal evidence: no Files controls, client calls, HTTP routes, application
  services or dedicated projections/tests remain, while Storage `Read`/`Write`, provider transfer
  primitives and Copy/Move behavior remain available;
- bounded batch/recursive and cross-Storage transfer evidence, including verify-before-delete and
  source preservation on failure;
- ResourceLibrary Save/activation success, validation failure, concurrent/stale failure and prior
  Active preservation;
- exact request/mutation evidence for zero-side-effect reads, live-Storage Preview authority,
  OrganizerExecutor-only direct/organize mutation and non-replaying FileIndex synchronization;
- Files refresh truthfulness evidence showing an externally removed directory disappears from the
  directory tree and stale selection state without adding a mutation or FileIndex request;
- formal destination parity evidence for `library/path` composition, CLI/formal target agreement,
  safe-prefix rejection, MediaLibrary resolution and zero-mutation failure behavior;
- full Python and Web regression, production frontend build/package validation, governance and
  `git diff --check`;
- scope/private-file inspection confirming the canonical image and `config/alist.json` are untouched.

## Review State

```text
Slice Status: ACTIVE
Implementation Head: 3e15ab35f3ebb7e76cb278fb5004726ad5b7aebb
Contract Revision: 2026-09-22 A POST-CLOSURE REACTIVATION — Files exact path identity and whitespace presentation
Task 37.8 state: PASS
Task 37.9 state: PASS
Task 37.10 state: PLANNED
Current Quality Baseline: GitHub quality run #118 PASS on 320d8437a8872f7a08ee84295a0f900a39f84a7d
Next Action: Developer implements Task 37.10 Files exact path identity and whitespace presentation
```

## Closure Packet

```text
Slice: 37 — Files Workspace, Common File Management and V2 Shell
Base SHA: b507edba167f5af3af8c53bfcf1417ba4fefddf4
Head SHA: 9e105d88c624e2ec8cfcc6fc71bef50cb929e99f

Required Outcomes:
- RO-1 Reference-aligned visual fidelity — COMPLETE
- RO-2 Shared V2 shell replacement — COMPLETE
- RO-3 Exact Files composition — COMPLETE
- RO-4 ResourceLibrary drawer and activation — COMPLETE
- RO-5 Storage-authoritative Files data — COMPLETE
- RO-6 Complete common file management — COMPLETE
- RO-7 Low-friction direct-operation safety — COMPLETE
- RO-8 Organize workflow continuity — COMPLETE
- RO-9 Actionable recovery — COMPLETE
- RO-10 Non-Files behavior continuity — COMPLETE
- RO-11 Test reconciliation — COMPLETE for current supported surfaces; stale baseline gates are
  recorded below as non-blocking
- RO-12 Security model continuity — COMPLETE

Required Surfaces:
- Shared responsive V2 shell for supported /ui-v2 routes — COMPLETE
- V2 Files at /ui-v2/library/files — COMPLETE
- Files-local Add ResourceLibrary drawer and atomic activation — COMPLETE
- ResourceLibrary browsing, status, selection and Organize continuation — COMPLETE
- Create Folder/Text, Rename, Copy, Move, Delete, Edit, Upload and Download surfaces — COMPLETE
- Backend direct-command, activation and exact FileIndex reconciliation behavior — COMPLETE
- Supported non-Files V2 bodies inside the shared shell — COMPLETE

Implemented:
- Replaced the old V2 chrome with the reference-aligned shared light rail/top bar and delivered the
  live-Storage Files workspace, bounded ResourceLibrary activation and reference composition.
- Delivered backend-authoritative Create Folder/Text, Rename, Copy, Move, Delete, bounded text
  Edit, Upload and Download with independent outcomes and explicit recovery.
- Connected one or many eligible Files entries to the existing durable Organize
  Intent -> Preview -> Execute journey and reconciled terminal Results only to their exact current
  FileIndex occurrence without replaying Storage mutation.

Tasks completed:
- 37.1 — Files reference browse, shared shell and selection authority
- 37.2 — ResourceLibrary atomic activation
- 37.3 — Bounded Files maintenance and ResourceLibrary removal
- 37.4 — Bounded Files Copy and Move transfers
- 37.5 — Bounded Files Upload and Download
- 37.6 — Files multi-item Organize continuation and FileIndex reconciliation

Final Tests:
- Governance, Ruff format/lint, compileall, pip check, FFmpeg/FFprobe exclusion and git diff check:
  PASS.
- Task 37.6 focused Python integration/security: 128 passed.
- Full Python regression: 1761 run; 1751 passed, 7 skipped, 3 failed. All 3 failures reproduce
  unchanged at Task Base and concern the pre-existing configuration-status assertion and old
  manual-operations fixture capture.
- Web format, TypeScript and ESLint: PASS; Vitest: 460 passed.
- Files/manual-Organize focused Playwright: 44 passed.
- Full Playwright: 122 run; 112 passed, 10 failed. The failures exercise already-unsupported legacy
  FileIndex/Scan/Preview routes or a duplicate read-only explanation assertion; the affected
  routes/tests predate Slice 37 and no supported Files or Organize test failed.
- Production Web build: PASS (non-blocking existing chunk-size warning).
- Controlled Files screenshot: PASS at 1536x1024; diagnostic diff 296787/1572864 pixels
  (18.8692%, mean absolute RGB 7.452/5.621/2.984), with the required shared-shell and Files
  hierarchy complete and operable.
- Wheel build and installed-wheel smoke, schema 38 backup/restore/verify/migration rehearsal:
  PASS.
- Docker release security smoke: unavailable as a final passing gate. The candidate image, Compose
  topology, non-root runtime, V1/V2 assets, auth/RBAC and Active activation passed before the
  pre-existing smoke harness submitted obsolete `metadataIdentity` choice input to the current
  `metadata` API and received the expected HTTP 400.

Safety Evidence:
- Files listing and Organize admission resolve the enabled Active ResourceLibrary and live Storage
  server-side; browser/FileIndex identifiers never supply physical authority.
- Reads, selection, Intent and Preview are zero-mutation; every direct or Organize Storage mutation
  remains behind OrganizerExecutor, RBAC, capability/confinement, stale/conflict and explicit
  destructive-intent checks.
- Batch transfer/upload and Organize outcomes remain independent; uncertain effects are not
  automatically replayed.
- TaskItems and Results retain exact verified occurrence/fingerprint identity; reconciliation is
  atomic with Result publication where supported and the explicit retry performs no Storage call.
- No test was deleted to hide a safety failure, no skip was added, no assertion was weakened, and
  no config/alist.json, credential, ignored artifact or dirty reference image entered the reviewed
  implementation checkpoint.

Known Non-blocking Issues:
- P2: three pre-existing Python assertions remain red at Task Base: one configuration projection
  test matches the legitimate `root_path` field name, and two old manual-operations fixture tests
  expect a superseded request shape.
- P2: ten legacy Playwright assertions still target routes removed before the Slice Base
  (`/library/file-index`, old Scan/Preview entry) or assert a unique copy of a duplicated read-only
  explanation. These are not reachable through the current supported V2 navigation and do not
  block current Files/non-Files journeys, but the suite command remains nonzero.
- P2: the Docker release smoke manual-Organize probe still sends the superseded
  `metadataIdentity` field instead of `metadata`; focused real WSGI and browser Organize journeys
  pass with the current contract.

Explicitly Deferred:
- Arbitrary binary/video/audio/image editing and media-stream inspection.
- Unbounded recursive/batch operations, arbitrary host-filesystem access, host extraction outside
  authenticated Download and implicit cross-Storage fallback.
- General Configuration/Settings redesign and non-Files business-journey redesign beyond shared
  shell integration.
- V1 /ui retirement, broad parity/accessibility closure, new providers/adapters/identity systems,
  universal rollback, automatic uncertain replay and FFmpeg/FFprobe.

Documentation Reconciliation Needed:
- Completed by the A Final Review closure checkpoint below. The three baseline test/harness debts
  remain non-blocking follow-up facts and do not reopen this closed Slice.

Decision: PASS / CLOSED
```

## A Final Review

```text
Reviewed Range: b507edba167f5af3af8c53bfcf1417ba4fefddf4..9e105d88c624e2ec8cfcc6fc71bef50cb929e99f
Decision: PASS / CLOSED
P0/P1 Blockers:
- None.
```

Closure Reconciliation:

- All twelve Required Outcomes and all Required Surfaces are complete across the shared V2 shell,
  Files browse/selection, ResourceLibrary activation, direct file management, Upload/Download,
  Organize continuation and FileIndex reconciliation.
- The vertical journey is complete: the operator can enter Files, see live ResourceLibrary-scoped
  state, act on bounded selections, receive independent success/failure/partial outcomes, and
  recover through refresh, corrected input, explicit re-confirmation or durable task state.
- The reviewed implementation preserves the architecture and safety invariants: read/analysis
  stages remain zero-mutation, all Storage mutation crosses OrganizerExecutor, authority is
  backend-resolved from Active ResourceLibrary/Storage bindings, overwrite/delete are explicit,
  and uncertain effects are never automatically replayed. RecognitionType identity remains
  independent of downstream policy reuse.
- Validation is truthful: focused direct-Files/activation/Organize Python coverage passed
  (`256 passed`, `13 subtests passed`); the full Python suite passed `1751`, skipped `7` and
  failed `3` pre-existing P2 assertions; Web format, typecheck, lint, Vitest (`460 passed`) and
  production build passed; focused Files/Organize Playwright passed `56`; full Playwright passed
  `112` and retained `10` pre-existing legacy/duplicate P2 failures. Ruff, compileall, pip check,
  governance, FFmpeg/FFprobe runtime exclusion and diff checks passed. The Docker release smoke
  remains unavailable only because its pre-existing probe submits the superseded `metadataIdentity`
  field; current focused WSGI/browser Organize coverage passes.
- The canonical reference image in the reviewed Base..Head is unchanged. The separate dirty
  worktree image observed during review is pre-existing user work and is excluded from the reviewed
  checkpoint. Explicitly Deferred scope remains deferred and was not silently expanded.

The Slice is therefore `PASS / CLOSED` as of 2026-09-20. The next legal action is for A to select
the next large Slice in a subsequent A turn.

## Post-reactivation Closure Packet

```text
Slice: 37 — Files Workspace, Common File Management and V2 Shell
Base SHA: b507edba167f5af3af8c53bfcf1417ba4fefddf4
Head SHA: 6322d5364ad0fe8ab4e4bc01d6a523454b6b94d8

Required Outcomes:
- RO-1 Reference-aligned visual fidelity — COMPLETE
- RO-2 Shared V2 shell replacement — COMPLETE
- RO-3 Exact Files composition — COMPLETE
- RO-4 ResourceLibrary drawer and activation — COMPLETE
- RO-5 Storage-authoritative Files data — COMPLETE
- RO-6 Bounded common file management — COMPLETE; Copy/Move is bounded by control-plane scope,
  not aggregate media bytes, and direct browser Upload/Download is outside the current surface
- RO-7 Low-friction direct-operation safety — COMPLETE
- RO-8 Organize workflow continuity — COMPLETE
- RO-8C Formal classification path parity correction — COMPLETE
- RO-9 Actionable recovery — COMPLETE
- RO-10 Non-Files behavior continuity — COMPLETE
- RO-11 Test reconciliation — COMPLETE for current supported surfaces; baseline P2 debts remain
  recorded below
- RO-12 Security model continuity — COMPLETE

Required Surfaces:
- Shared responsive V2 shell for supported `/ui-v2` routes — COMPLETE
- V2 Files at `/ui-v2/library/files` — COMPLETE
- Files-local Add ResourceLibrary drawer and atomic activation — COMPLETE
- ResourceLibrary browsing, status, selection and Organize continuation — COMPLETE
- Files toolbar/action menus and bounded Create Folder/Text File, Rename, Copy, Move, Delete and
  supported text Edit — COMPLETE
- Shared formal `library/path` destination composition across Plan, Preview/precheck, projections,
  execution and result evidence — COMPLETE
- Direct browser Upload/Download controls, routes, services, models and dedicated tests — REMOVED
  per the current A-owned scope revision; absence verified
- Existing non-Files V2 page bodies inside the shared shell — COMPLETE

Implemented:
- Corrected formal destination composition to include `ClassificationRule.result.library` as the
  first safe relative prefix while preserving `mediaLibraryId` authority and CLI parity.
- Removed the direct Files Upload/Download vertical while preserving generic Storage Read/Write,
  provider transfer primitives, Copy/Move, text Edit and OrganizerExecutor behavior.
- Repaired Files-originated Save Choice validation against live Storage without requiring a
  FileIndex row, retained FileIndex-originated validation, and preserved zero-mutation rejection
  and stale-source recovery semantics.
- Removed the aggregate media-byte Copy/Move admission ceiling and added truthful bounded JSON 413
  serialization for control-plane limit failures.
- Made the Files drawer regression deterministic under the full Web suite without changing the
  production component or weakening assertions.

Tasks completed:
- 37.1 — Files reference browse, shared shell and selection authority
- 37.2 — ResourceLibrary atomic activation
- 37.3 — Bounded Files maintenance and ResourceLibrary removal
- 37.4 — Bounded Files Copy and Move transfers
- 37.5 — Bounded Files Upload and Download
- 37.6 — Files multi-item Organize continuation and FileIndex reconciliation
- 37.7 — Formal destination parity, current-scope Upload/Download removal, Save Choice source
  validation, Copy/Move control-plane correction and Web regression determinism

Final Tests:
- `python3 scripts/check_governance.py` — PASS.
- Focused Python groups — `297 passed`, `91 subtests passed` across the required Task groups.
- Full Python regression — `1703 passed`, `7 skipped`, `4 failed`, `1392 subtests passed`; all
  four failures reproduce at Task Base and are recorded as non-blocking P2 baseline debts.
- Ruff format/check, compileall, pip check and `git diff --check` — PASS.
- Web format, TypeScript, ESLint and production build — PASS; build retained the existing non-blocking
  chunk-size warning.
- Web Vitest — `33 files`, `455 passed`, `0 failed`.
- Focused Files Playwright — `31 passed`.
- Direct Upload/Download absence search — zero matches for the dedicated Files vertical identifiers.
- `config/alist.json` absent and the canonical dirty reference image unchanged from Task Base.
- Prior Slice-level full Playwright evidence remains `112 passed`, `10` legacy/duplicate P2 failures;
  current correction-specific Files coverage passes as above.
- Docker release security smoke and the Docker `source2` reproduction remain unavailable because the
  existing harness/stack uses the superseded `metadataIdentity` request shape and is not the current
  candidate checkout.

Safety Evidence:
- Destination validation is fail-closed for unsafe `library` contributions; `mediaLibraryId`
  remains the sole MediaLibrary/Storage root authority.
- Preview, DryRun, Save Choice and other analysis stages remain zero-mutation; OrganizerExecutor
  remains the only Storage mutation boundary.
- Files-originated source validation uses pinned Active Storage authority without requiring a
  FileIndex row; missing/stale sources preserve durable Choice and intent state.
- Copy/Move keeps bounded selection, entry, depth, path, manifest and checkpoint controls; large
  aggregate media bytes remain impact/progress information only.
- No silent overwrite/delete, implicit transfer fallback or uncertain mutation replay was added;
  generic Storage Read/Write and provider primitives remain available.
- The reviewed diff contains no credentials, `config/alist.json`, ignored artifacts or modified
  canonical reference image, and no tests were skipped, deleted to hide a failure, or weakened.

Known Non-blocking Issues:
- P2: four pre-existing Python failures reproduce at Task Base: one configuration projection
  assertion rejects the legitimate `root_path` field name; two manual-operations contract tests
  expect a superseded request/fixture shape; and one release-security test expects a different
  task quality-gate documentation shape. None is in the Task implementation diff or current
  Files/destination journey.
- P2: ten legacy Playwright assertions from the prior closure target unsupported routes or a
  duplicate read-only explanation; they are outside current supported navigation.
- P2: Docker release smoke remains unavailable due to the obsolete `metadataIdentity` probe and
  the unavailable `source2` Docker reproduction.

Explicitly Deferred:
- Preserve the current Contract list unchanged: arbitrary binary/video/audio/image editing and
  stream inspection; unbounded recursive/batch operations; arbitrary host filesystem access;
  host extraction outside authenticated Download; implicit cross-Storage fallback; general
  Configuration/Settings redesign; V1 `/ui` retirement; new providers/adapters/identity systems;
  universal rollback; automatic uncertain replay; and FFmpeg/FFprobe.

Documentation Reconciliation Needed:
- A should reconcile the historical pre-reactivation closure record with this post-reactivation
  correction packet while preserving both as dated history, and record the final review over the
  original Slice Base through this corrected Head.

Decision: SLICE READY FOR A REVIEW
```

## A Final Review — Post-reactivation 2026-09-21

```text
Reviewed Range: b507edba167f5af3af8c53bfcf1417ba4fefddf4..6322d5364ad0fe8ab4e4bc01d6a523454b6b94d8
Decision: FIX REQUIRED
P0/P1 Blockers:
- The current Upload/Download-removal acceptance is not fully satisfied. The reviewed
  implementation still contains the Upload-specific `_ItemPayloadStream` helper in
  `mediaflow/interfaces/service_api.py:202-233`. Its docstring and WSGI payload logic describe
  an admitted Files Upload item, although the helper is now unreachable after the route/service
  removal. This contradicts the A-authorized boundary requiring the direct Files Upload/Download
  vertical, including its helpers, to be removed, and makes the Closure Packet's absence claim
  materially incomplete. Remove this dead Upload helper, then rerun the direct-surface absence
  inspection and the affected Python/Web regression gates.

Required correction evidence:
- rerun `python -m unittest discover -s tests` and record every matrix result, skip and remaining
  failure truthfully;
- rerun the direct Upload/Download absence inspection after removing `_ItemPayloadStream`.
```

Accepted Residual Risk:

- GitHub Actions `quality` run `#114` on 2026-09-20 exposed two Local directory replacement tests
  that can observe `SUCCESS` when delete/recreate reuses the inode inside the final revalidation to
  mutation window.
- A accepts this as a non-blocking residual risk for Slice 37 because it requires a narrow concurrent
  replacement race and does not represent the ordinary single-operator path. Existing scope
  confirmation and stale revalidation remain required and must not be weakened.
- README contains the operator-facing prevention and recovery guidance. B must remove the
  replacement-resistant generation architecture from Task 37.8 and reconcile the two host-filesystem
  tests with this accepted contract without adding skips or representing the race as fixed.

## A Final Review — Post-reactivation Closure 2026-09-21

```text
Reviewed Range: b507edba167f5af3af8c53bfcf1417ba4fefddf4..2115d1839eb0611f097913eae8a43492d00346a2
Decision: PASS / CLOSED
P0/P1 Blockers:
- None.
```

Closure Reconciliation:

- All current Slice 37 Required Outcomes and Required Surfaces are complete. The final supported
  Files surface is the shared V2 shell, live ResourceLibrary browsing, ResourceLibrary activation,
  Create Folder/Text File, Rename, Copy, Move, Delete, bounded text Edit and Organize continuation.
  Direct browser Upload/Download was removed vertically from the current scope; generic Storage
  Read/Write, provider transfer primitives and Copy/Move behavior remain available.
- The user journey is complete: the operator enters Files, sees live Storage-authoritative state,
  performs bounded actions with explicit destructive intent where required, receives independent
  success/failure/partial outcomes, and recovers through corrected input, refresh, revalidation or
  durable Organize state. Non-Files V2 journeys remain functional inside the shared shell.
- The formal destination correction is complete: `ClassificationRule.result.library` is validated
  as a safe relative prefix and composed before `result.path` consistently across Plan, Preview,
  precheck, execution and result evidence, with CLI parity and zero-mutation rejection.
- Safety invariants hold: analysis/read stages remain zero-mutation, only `OrganizerExecutor` mutates
  Storage, authority is resolved from backend Active ResourceLibrary/Storage bindings, overwrite and
  delete are explicit, cross-Storage Move verifies before deleting the source, and uncertain effects
  are never automatically replayed. RecognitionType identity remains independent of downstream policy
  reuse.
- A reran the final gates on the reviewed implementation checkpoint: Python `1718` tests passed with
  `7` skips; Web format/typecheck/lint/Vitest `455` tests and production build passed; Playwright
  `119` tests passed with no failures or skips; governance, Ruff, compile, dependency, diff and
  private-file checks passed; Docker release-security and transfer-impact smoke tests passed.
  Python 3.11/3.12 were unavailable locally and are not inferred. The accepted narrow Local
  directory replacement/inode-reuse race remains documented residual risk, not a claimed fix.
- The dirty working-tree copy of `docs/pics/文件页.png` was pre-existing user work and is excluded
  from the reviewed checkpoint. `config/alist.json` is absent and no secret/private configuration
  entered the reviewed range. The next legal action is A selecting the next large Slice in a later
  turn.

## Post-reactivation Closure Packet — Task 37.9

```text
Slice: 37 — Files Workspace, Common File Management and V2 Shell
Base SHA: b507edba167f5af3af8c53bfcf1417ba4fefddf4
Head SHA: 52383fa67c007ec814156503856fe8b7aa0219af

Required Outcomes:
- RO-1 Reference-aligned visual fidelity — COMPLETE
- RO-2 Shared V2 shell replacement — COMPLETE
- RO-3 Exact Files composition — COMPLETE; refresh truthfully reconciles local tree/selection
  state and the Files page no longer presents recognition/status feedback
- RO-4 ResourceLibrary drawer and activation — COMPLETE
- RO-5 Storage-authoritative Files data — COMPLETE; refresh remains live Storage-authoritative and
  does not consult FileIndex
- RO-6 Bounded common file management — COMPLETE
- RO-7 Low-friction direct-operation safety — COMPLETE
- RO-8 Organize workflow continuity — COMPLETE
- RO-8C Formal classification path parity correction — COMPLETE
- RO-9 Actionable recovery — COMPLETE; failed refresh preserves the existing bounded retry/root
  recovery without fabricated rows or automatic replay
- RO-10 Non-Files behavior continuity — COMPLETE
- RO-11 Test reconciliation — COMPLETE for current supported surfaces; accepted baseline P2 debts
  remain recorded below
- RO-12 Security model continuity — COMPLETE

Required Surfaces:
- Shared responsive V2 shell for supported `/ui-v2` routes — COMPLETE
- V2 Files at `/ui-v2/library/files` — COMPLETE
- Files-local Add ResourceLibrary drawer and atomic activation — COMPLETE
- ResourceLibrary browsing, selection, truthful refresh and Organize continuation — COMPLETE
- Files toolbar/action menus and bounded Create Folder/Text File, Rename, Copy, Move, Delete and
  supported text Edit — COMPLETE
- Shared formal `library/path` destination composition across Plan, Preview/precheck, projections,
  execution and result evidence — COMPLETE
- Direct browser Upload/Download controls, routes, services, models and dedicated tests — REMOVED
- Existing non-Files V2 page bodies inside the shared shell — COMPLETE

Implemented:
- Task 37.9 refresh boundary clears page-local directory memory and selection before the same
  bounded authenticated GET; stable directory discovery prevents stale paths from being
  reintroduced after refresh.
- Files presentation now contains exactly `选择 | 名称 | 类型 | 大小 | 修改时间 | 操作`;
  `识别结果` and `整理状态` are absent while the explicit `整理` action and existing
  zero-mutation continuation remain.
- Focused unit and browser coverage proves external-directory removal, stale-selection clearing,
  valid-context preservation, bounded failure recovery, six-column presentation, GET-only refresh
  and no `/file-index` request.
- The visual specification records the current presentation boundary and refresh truthfulness.

Tasks completed:
- 37.1 — Files reference browse, shared shell and selection authority
- 37.2 — ResourceLibrary atomic activation
- 37.3 — Bounded Files maintenance and ResourceLibrary removal
- 37.4 — Bounded Files Copy and Move transfers
- 37.5 — Bounded Files Upload and Download
- 37.6 — Files multi-item Organize continuation and FileIndex reconciliation
- 37.7 — Formal destination parity, current-scope Upload/Download removal, Save Choice source
  validation, Copy/Move control-plane bounds
- 37.8 — Files safety and quality gate reconciliation
- 37.9 — Files refresh truthful state and focused presentation

Final Tests:
- `python3 scripts/check_governance.py` — PASS.
- `.venv/bin/python -m unittest discover -s tests` — `1718` passed, `7` skipped, OK on the
  local Python 3.13 run.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m pip check` — PASS; no broken requirements.
- `.venv/bin/ruff format --check .` and `.venv/bin/ruff check .` — PASS.
- `cd web && npm run test -- --run` — first full concurrent run `459/460`, with one unrelated
  `OrganizeRouter.test.tsx` timing failure; isolated rerun `13/13` passed. Task-focused Web
  suite passed `38/38`.
- `cd web && npm run test:e2e` — `120/120` passed with no failures or skips; Task-focused Files
  subset passed `38/38`.
- `cd web && npm run typecheck`, `npm run lint`, `npm run format:check` — PASS.
- `cd web && npm run build` — PASS; production artifact generated.
- `git diff --check` and reviewed-scope/private-file inspection — PASS; `config/alist.json` is
  absent and the canonical image change remains pre-existing and uncommitted.
- `TMPDIR=/root/mediaflow .venv/bin/python scripts/docker_release_security_smoke_test.py` —
  PASS.
- `TMPDIR=/root/mediaflow .venv/bin/python scripts/docker_files_transfer_impact_smoke_test.py` —
  PASS; synthetic aggregate `22548578304` bytes was admitted as impact evidence while bounded
  depth/entry/selection limits failed closed without mutation.
- GitHub quality run `#118` remains the green Python 3.11/3.12/3.13 baseline recorded by the
  active Task.

Safety Evidence:
- Files refresh performs only the existing bounded authenticated GET; focused tests and full
  browser coverage found no mutation request and no `/file-index` request.
- Removed directory paths and selections are not fabricated after a successful refresh; failed
  reads retain bounded retry/root recovery.
- OrganizerExecutor, backend authority, explicit delete/replace intent, stale checks and
  non-replay behavior remain unchanged.
- No credentials, production Storage, external provider or private configuration entered the
  reviewed checkpoint.

Known Non-blocking Issues:
- Full Web Vitest has an intermittent unrelated scheduling failure in
  `OrganizeRouter.test.tsx`; the exact file passes in isolation (`13/13`), and the affected
  Organize browser journeys pass. No Task 37.9 file or behavior is implicated.
- The accepted narrow Local directory replacement/inode-reuse race remains documented residual
  risk and is not claimed fixed.
- Existing build-size warning for the generated JavaScript chunk is non-blocking and outside
  this Task.

Explicitly Deferred:
- Direct browser Upload/Download is removed from the current scope.
- Arbitrary binary/media editing, unbounded recursive/batch operations, new providers/storage
  capabilities, identity/security-system redesign, automatic uncertain-mutation replay,
  universal rollback, V1 `/ui` retirement and FFmpeg/FFprobe remain deferred or out of scope as
  stated in the Contract.

Documentation Reconciliation Needed:
- A should perform the final review over `b507edba167f5af3af8c53bfcf1417ba4fefddf4..52383fa67c007ec814156503856fe8b7aa0219af`
  and reconcile any factual closure references across authoritative documents. No Contract,
  Slice Base or Required Outcome change is requested.

Decision: SLICE READY FOR A REVIEW
```
