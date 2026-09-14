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
Implementation Head: NOT SET
Contract Revision: 2026-09-14 A ACCEPTANCE REFINEMENT — reference-aligned visual fidelity
```

The Slice Base is immutable. This A-owned rescope supersedes the earlier Files-page-only/frozen-shell
interpretation without changing that Base. Work produced by Task 37.1 before this revision is
implementation evidence only and is not accepted merely because it exists; B must reconcile the
active Task against this checkpointed Contract before further Developer work.

## Scope decision

The approved [`docs/pics/文件页.png`](docs/pics/文件页.png) is the product design to implement, not
an inspiration image and not a page card to place inside the old dark horizontal V2 shell. Slice 37
owns a deliberate replacement of the previous V2 shell presentation with the reference's light
left navigation rail and top bar. The same shared shell must frame all V2 routes so Files does not
create a second navigation system. Existing non-Files business journeys, route authority and page
behavior remain intact, but their outer shell pixels are intentionally allowed to change.

Slice 37 also makes Files a practical common file-management surface. In addition to browsing and
organizing, an authorized operator can create folders or supported text files; rename, copy, move
and delete files/directories; edit bounded supported text files; and upload or download bounded
files/directories.
Single-item actions and bounded multi-selection actions share one Files interaction model. These are
direct file-management commands, not media recognition/metadata/naming/classification/organize
decisions. They do not require the full Organize Preview/policy/execution-token ceremony, but every
mutation remains backend-authoritative, confined to explicitly selected Active ResourceLibrary
roots, capability-checked, auditable and executable only through `OrganizerExecutor`. Delete and
replace are never silent; conflicts, partial transfer and stale content remain explicit.

Arbitrary binary/media-content editing, unbounded recursive operations, arbitrary host paths and
implicit operation fallback remain outside this Slice.

The detailed visual source of truth is
[`docs/file-page-visual-spec.md`](docs/file-page-visual-spec.md). The image is authoritative for
visual detail; this Contract controls product scope, authority and safety.

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
`添加资源库` drawer. The action surfaces expose `新建文件夹`, `新建文本文件`, `上传`, `下载`,
`重命名`, `复制`, `移动`, `删除` and supported `编辑`. Unsupported actions are absent or explain why
they are unavailable. Raw backend authority fields are not displayed.

**Action:** browse or refresh a ResourceLibrary-relative directory, switch presentation, select or
clear entries, create a folder or supported text file, rename/copy/move/delete eligible files or
directories, edit and save bounded text, upload into the current directory, download selected
content, create and activate a ResourceLibrary, or open the existing server-authoritative organize
Preview journey.

**Success:** shell and Files visuals match the reference; direct file actions update the live
listing without leaving hidden stale selection; a saved ResourceLibrary becomes part of the exact
Active runtime; and terminal Organize results synchronize their known outcome to FileIndex.

**Failure:** missing Active configuration, unavailable Storage, invalid path, stale or changed
source, unsupported operation, name/destination conflict, edit conflict/encoding/size failure,
bounded-recursion or transfer-limit failure, partial copy/move/upload/download, denied permission,
malformed response, activation failure, Organize failure or FileIndex synchronization failure is
shown on the affected item with no fabricated success, implicit overwrite/delete or uncertain
replay.

**Recovery:** retry a safe bounded read/download, return to the ResourceLibrary root, correct a name,
destination or edit conflict, reload changed text, inspect independently completed/failed transfer
items, explicitly confirm a still-current bounded deletion, select another ResourceLibrary, correct
and resubmit a failed ResourceLibrary save, inspect the durable Organize result or repair bounded
index synchronization. Failed or uncertain mutations refresh truth and are never automatically
repeated.

## Required Outcomes

| ID | Outcome | Acceptance state |
|---|---|---|
| RO-1 | **Reference-aligned visual fidelity.** | A controlled `1536 x 1024` Files success screenshot preserves the canonical image's shared-shell and Files hierarchy, visible fixture state, labels, control order and design intent. Pixel-diff counts are diagnostic rather than a pass/fail threshold; bounded differences in font/glyph rendering, icon or thumbnail artwork, exact dimensions/spacing, borders, shadows and color nuance are acceptable when the required composition remains complete, recognizable and operable. |
| RO-2 | **Shared V2 shell replacement.** | The old dark horizontal shell is replaced by the reference-aligned light left rail/top bar across V2. Files has no alternate shell; existing route/auth/deep-link behavior remains shared and non-Files business journeys remain functional. |
| RO-3 | **Exact Files composition.** | Header, banner, ResourceLibrary summary, directory tree, breadcrumb, toolbar, table, row values/status/actions, selection footer, pagination and drawer appear in the exact reference order and hierarchy. |
| RO-4 | **ResourceLibrary drawer and activation.** | The three-step drawer matches the reference; final `保存` submits one complete candidate and the backend validates and atomically activates it, preserving the previous Active on every failure. |
| RO-5 | **Storage-authoritative Files data.** | Physical entries and paths come from live ResourceLibrary-scoped Storage. FileIndex supplies only bounded display feedback and post-mutation reconciliation; it never supplies source/path/execution authority. |
| RO-6 | **Complete common file management.** | Files provides Create Folder/Text File, Rename, Copy, Move, Delete, supported bounded text Edit, Upload and Download for eligible files/directories, including bounded multi-selection where meaningful; success refreshes live state and partial/failure outcomes remain independent and recoverable. |
| RO-7 | **Low-friction direct-operation safety.** | Direct file actions do not run the Organize recognition/planning pipeline or require organize execution-token ceremony. Backend RBAC, explicit mutation intent, Storage capability/confinement, stale/conflict checks, audit, no silent overwrite/delete and `OrganizerExecutor`-only mutation remain mandatory. |
| RO-8 | **Organize workflow continuity.** | Files-originated Preview remains ResourceLibrary-scoped and Storage-relative, derives SourceIdentity from live Storage, continues through existing Preview/intent/OrganizerExecutor authority and synchronizes each terminal result independently to FileIndex. |
| RO-9 | **Actionable recovery.** | Read, direct-operation, activation, Organize and index-sync failures preserve Files context, explain durable/known state and provide a safe next action without fabricated rows or automatic uncertain replay. |
| RO-10 | **Non-Files behavior continuity.** | Dashboard, Operations, Review, Configuration, Notifications and Settings retain their existing routes, application behavior, permissions and recovery while adopting the new shared shell chrome; V1 `/ui` remains unchanged. |
| RO-11 | **Test reconciliation.** | Conflicting legacy shell/Files assertions are removed and replaced by Contract-aligned visual, interaction, mutation, failure and frozen-behavior tests; no safety assertion is weakened or skipped. |
| RO-12 | **Security model continuity.** | The Slice reuses existing API-principal authentication, RBAC, audit and backend authority; it introduces no username/password, cookie session, OIDC or frontend Storage authority. |

## Required Surfaces

- the shared V2 shell chrome for every `/ui-v2/*` route, including responsive behavior;
- V2 Files at `/ui-v2/library/files`;
- the Files-local `添加资源库` drawer and its backend Save/activation command;
- bounded ResourceLibrary browsing, status feedback, selection and organize continuation;
- Files toolbar/action menus, destination picker and transfer progress for Create Folder/Text File,
  Rename, Copy, Move, Delete, supported text Edit, Upload and Download;
- backend/application behavior strictly necessary for direct file commands, ResourceLibrary
  Save/activation and post-mutation FileIndex synchronization;
- existing non-Files V2 page bodies only as needed to keep them functional inside the replaced
  shared shell; their business features are not redesigned by this Slice.

## Product Experience / UX Constraints

- The reference is the intended product, so retaining the old V2 chrome is not a compatibility
  objective. Files must feel like the reference workspace rather than a redesign nested in a legacy
  frame.
- The ordinary path is direct: choose entries and a common command, supply only the required name,
  destination, files or supported text, then see progress/result in the same Files context.
- Create, Rename, Copy, Move and Upload do not add redundant confirmation after valid input unless
  the operator explicitly chooses Replace. Text Save is the write intent; Delete uses one clear
  permanent-effect confirmation. No direct command exposes organize Preview, policy selection or
  execution tokens.
- Unsupported actions must be absent or explained. Disabled controls, generic errors and raw
  protocol/exception details are not substitutes for an actionable reason and recovery.
- Selection, expanded directories and current ResourceLibrary context must stay truthful after a
  mutation; deleted or renamed entries cannot remain as hidden stale selection.
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

### Upload and Download

- Upload accepts one or more bounded browser-selected files or a bounded directory tree into the
  current directory. It validates every supplied relative path, streams through the backend,
  enforces request/file/count/depth limits, preserves each item outcome and never exposes Storage
  credentials to the browser.
- Upload destination conflicts use the same explicit no-overwrite/skip/keep-both/replace semantics
  as Copy. Incomplete staging is removed when safely provable or exposed as a recoverable partial
  artifact; success is not reported until the destination is known complete.
- Download resolves one item or a bounded selection through the current ResourceLibrary authority.
  A file streams directly; a directory or multi-selection uses a bounded streamed archive without
  writing an archive back to managed Storage. Download is a read and does not use OrganizerExecutor.
- Interrupted downloads are safe to restart as reads. Upload retry is per failed/known-safe item and
  never automatically repeats an uncertain destination write.

### Shared direct-operation behavior

- The browser submits only ResourceLibrary identity, relative path, requested bounded operation and
  the minimal stale/conflict evidence required by the backend. It never supplies absolute host paths
  or Storage credentials.
- Python application behavior resolves every current Active source/destination ResourceLibrary and
  Storage binding, enforces RBAC, validates capability/path/source state, records a bounded audit and
  invokes every mutation only through `OrganizerExecutor`.
- A direct operation is not reclassified as media organization and does not call Parser,
  Recognition, Metadata, Naming, Classification or the organize Planner.
- Single quick operations may complete synchronously; any long, recursive, upload or batch mutation
  uses the existing Task system with independent per-item outcomes and progress. Download remains a
  bounded read/stream rather than a mutation Task unless archive preparation genuinely requires a
  durable long-running Task.
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
- Delete and overwrite/Replace remain explicit. No create, rename, copy, move, upload, text Save or
  deletion silently replaces/removes user data.
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

- Every common file action covers success, invalid input, permission/capability denial, path escape,
  stale source, target conflict, limits, partial transfer, Storage failure, uncertain effect and safe
  recovery as applicable.
- Tests prove Create Folder/Text File, Rename, Copy, Move, Delete, Edit and Upload cannot bypass
  `OrganizerExecutor`, cannot touch an unselected ResourceLibrary/Storage root and cannot silently
  overwrite/delete. Download tests prove bounded, confined, secret-free zero-mutation streaming.
- Cross-Storage tests prove Copy verification precedes Move source deletion, a failed verification
  preserves the source, partial outcomes are durable and no operation silently falls back.
- Bounded batch/recursive tests prove independent per-item state and that item/depth/size limits stop
  unbounded work before destructive effects.
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

- Arbitrary binary/video/audio/image content editing and media-stream inspection.
- Unbounded recursive/batch operations, arbitrary host-filesystem access, Storage-to-host extraction
  outside authenticated Download, and implicit cross-Storage fallback.
- General Configuration/Settings redesign beyond truthful navigation inside the new shared shell.
- Dashboard, Operations, Review/Recovery, Automation and Notification business-journey redesign;
  their shared shell chrome changes, but their existing page behavior remains.
- V1 `/ui` cutover/retirement and broad parity/accessibility closure beyond the changed shell/Files
  surfaces.
- New providers, Storage adapters/capabilities, identity/security systems, automatic uncertain
  mutation replay, universal rollback and FFmpeg/FFprobe.

## Slice Acceptance Criteria

- [ ] At `1536 x 1024`, the Files screenshot preserves the reference shared-shell and Files
      hierarchy, visible fixture state, labels and control order. The comparison records material
      differences, but nonzero pixel counts and bounded rendering/layout variations do not fail the
      Slice when the composition remains complete, recognizable and operable; the reference asset
      is not rewritten merely to manufacture a passing comparison.
- [ ] The old dark horizontal V2 shell is fully replaced by the reference light rail/top bar, using
      one shared shell across V2 and retaining auth/deep-link/route recovery.
- [ ] Required labels, values, row order, selection states, drawer steps and controls from the visual
      spec are present. Recognizable implementation-owned icons/thumbnails and bounded table
      truncation are acceptable when the complete value remains available to assistive technology
      and the action/state remains unambiguous.
- [ ] Create Folder/Text File, Rename, Copy, Move, Delete, supported text Edit, Upload and Download
      complete from Files with low-friction success/failure/recovery and bounded multi-selection
      where useful.
- [ ] Every mutation completes through backend-authoritative `OrganizerExecutor`; Download remains a
      confined zero-mutation read.
- [ ] Delete and Replace/text overwrite require explicit operator intent, never silently affect
      another path/version and never automatically replay an uncertain result.
- [ ] Same- and cross-Storage Copy/Move expose capability and compound-operation truth; verification
      failure preserves the source and partial results remain independently recoverable.
- [ ] `+ 添加资源库` saves, validates and atomically activates a complete candidate; any failure keeps
      the previous Active.
- [ ] Physical listing remains live Storage-authoritative; FileIndex is display/reconciliation only.
- [ ] Files-originated Organize remains live-Storage/ResourceLibrary-authoritative and each terminal
      result synchronizes independently without mutation replay.
- [ ] Non-Files V2 business routes remain functional inside the new shell; V1 `/ui`, API/RBAC and
      backend mutation authority remain intact.
- [ ] Conflicting old visual tests are replaced and all required T4/full Slice gates pass without
      hidden skips or private configuration.
- [ ] The implementation checkpoint contains only Slice 37 work and necessary evidence.

## Final Validation Expectations

- deterministic `1536 x 1024` screenshot and pixel-diff report against the canonical image after
  fonts/assets load, evaluated under RO-1's structural/reference-aligned acceptance rather than a
  zero-difference threshold;
- shared-shell route/deep-link/auth/401/403/responsive smoke across every V2 product area;
- Files browse/search/navigation/selection/pagination/drawer interaction evidence;
- Create Folder/Text File, Rename/Copy/Move/Delete/Edit/Upload/Download success and failure evidence
  against temporary Storage, including conflict, stale source, transfer limits, partial outcome,
  capability denial, confinement, audit and uncertain-effect non-replay;
- bounded batch/recursive and cross-Storage transfer evidence, including verify-before-delete and
  source preservation on failure;
- ResourceLibrary Save/activation success, validation failure, concurrent/stale failure and prior
  Active preservation;
- exact request/mutation evidence for zero-side-effect reads, live-Storage Preview authority,
  OrganizerExecutor-only direct/organize mutation and non-replaying FileIndex synchronization;
- full Python and Web regression, production frontend build/package validation, governance and
  `git diff --check`;
- scope/private-file inspection confirming the canonical image and `config/alist.json` are untouched.

## Review State

```text
Slice Status: ACTIVE
Implementation Head: NOT SET
Contract Revision: A ACCEPTANCE REFINEMENT — structural/reference-aligned visual fidelity replaces
the pixel-identical gate; shared shell and common file-management scope remain unchanged
Task 37.1 state: pending B re-review under this acceptance refinement; TASK.md intentionally not
modified by A
Next Action: checkpoint this Contract, then B reconciles and reviews Task 37.1 against the refined
visual acceptance before selecting the next coherent Task
```

## Closure Packet

Not prepared — Slice 37 is `ACTIVE` and the revised Required Outcomes are not yet implemented or
validated.

## A Final Review

Not started. A will review the immutable Slice Base through the eventual Implementation Head only
after B supplies a complete Closure Packet.
