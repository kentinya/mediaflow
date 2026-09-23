# Files Page Visual Specification

Status: CURRENT — Slice 37 PASS / CLOSED; Slice 38 route migration is TARGET
Canonical image: [`docs/pics/文件页.png`](pics/文件页.png)
Reference size: `1536 x 1024` pixels
Route: `/ui-v2/library/files` (`/library/files` inside the V2 router)

Slice 38 TARGET moves this same Files journey to `/ui-v2/resourcelib/files`. Its current body,
commands and Organize continuation remain protected. The new MediaLibrary page has a separate
[visual specification](media-library-page-visual-spec.md); that page's explicit removal of card
statistics and file thumbnails does not revise this Files presentation. Slice 37's final Contract
and review are preserved at `9e801ae4485bc95d714a8902bf45bf37896fbc2a:SLICE.md` in Git; root
`SLICE.md` now owns the next capability.

This document is the visual source of truth for the Files page and the shared V2 shell that frames
it. The image is an existing user asset and must not be edited, regenerated, compressed, recolored
or replaced. The 2026-09-14 A rescope makes the reference shell the replacement for the prior dark
horizontal V2 shell rather than a Files-only imitation inside it.

## Current Presentation Boundary — 2026-09-22

A's 2026-09-21 scope clarification removes the business concepts `识别结果` and `整理状态` from the
Files page. The Files table presents physical file facts and explicit actions with exactly six
columns:

```text
选择 | 名称 | 类型 | 大小 | 修改时间 | 操作
```

The information banner describes browsing and organizing ResourceLibrary files without presenting
either removed concept. The explicit `整理` action, the single-item Preview path, the bounded batch
continuation and the OrganizerExecutor authority remain available and unchanged. This is a
presentation-boundary correction: the backend/API projections may still carry recognition and
business-status fields for their existing authorities and result synchronization, but Files must
not display those two concepts as business feedback. Exact Storage entry names, breadcrumb paths
and the current directory path preserve identity characters, including leading or trailing
whitespace, through the frontend projection and navigation. Boundary whitespace is rendered with
visible and assistive disambiguation; a genuinely absent trimmed sibling remains a bounded
not-found state with no alternate-path retry.

The same reactivation makes refresh truthful. When a ResourceLibrary directory is deleted or moved
outside the Web page, `刷新` must reconcile the page-local directory-tree memory and selection with
the refreshed live Storage read: a removed directory may no longer appear as a directory-tree
target or as a stale selection. The selected ResourceLibrary and current directory path are
preserved when the refreshed read remains valid, and the existing bounded read-failure state and
its recovery actions are preserved when the current directory is gone.

The earlier wording in this document that still names the removed columns or the withdrawn Upload/
Download surfaces is historical. Where it conflicts with the closed Slice 37 Contract, that
historical Contract and this section control the Files baseline; the current Slice adds only its
explicit migration requirements.

## Implementation Status — 2026-09-22

The current implementation already establishes the data and authority boundary required by this
page:

- Files discovery is ResourceLibrary-scoped. The page loads enabled ResourceLibraries from the
  Active runtime, then reads `GET /api/v1/resource-libraries/{resourceLibraryId}/files` with only
  a ResourceLibrary-relative `path` and server-issued `cursor`.
- The runtime Files browser reads live Storage through the configured ResourceLibrary root. Its
  optional `file_index` constructor argument is retained only for older composition code and is
  intentionally not consulted by the UI-V2 Files projection.
- The typed Files model excludes FileIndex membership, `fileId`, occurrence and fingerprint
  authority. The backend payload may retain bounded `recognitionResult` / `businessStatus` fields
  for existing authorities and reconciliation, but the current Files page does not render them.
  Raw FileIndex identifiers remain excluded from ordinary page display.
- Files-originated organization Preview is also FileIndex-independent. The page submits
  `scopeKind: "file"`, `resourceLibraryId` and `relativePath` to
  `POST /api/v1/operations/previews`. The server maps the path through the Active
  ResourceLibrary/Storage binding, calls `Storage.stat()`, creates the immutable
  `SourceIdentity`, and enters the existing zero-mutation Preview planner.
- The Files-originated Preview path then calls `create_from_sources`; it does not resolve a
  `fileId`, read a FileIndex row or echo occurrence/fingerprint authority from the browser. The
  resulting Preview remains the source of truth for the existing server-authoritative organize
  continuation and Worker revalidation.
- The page admits bounded multi-item Organize continuation through the existing durable
  Intent -> Preview -> Execute journey and preserves independent item outcomes.
- Slice 37 delivered the complete backend-authoritative common file command set from Files:
  Create Folder/Text File, Rename, Copy, Move, Delete and bounded text Edit. Direct browser Upload
  and Download were subsequently removed from the current product surface by A's 2026-09-20 scope
  revision and are no longer part of the page. The remaining commands stay distinct from media
  organization and retain the same live-Storage authority, explicit intent, bounded scope and
  OrganizerExecutor-only mutation guarantees.

The codebase still contains FileIndex-backed compatibility and legacy operation paths, including
indexed discovery and older file-scoped APIs. Those paths are not the source or authority for the
ResourceLibrary Files page. The page does not present FileIndex recognition/business-status
feedback, and completed Organize or direct file-management mutations may reconcile their known
terminal outcome back to FileIndex. FileIndex is never the source/path/execution authority and a
reconciliation failure never replays Storage mutation.

The Slice 37 implementation contains the replacement shared shell, live Files composition,
ResourceLibrary activation, common file commands and Organize/FileIndex reconciliation. Its
controlled screenshot is reference-aligned but not pixel-identical. Under the 2026-09-14 A
acceptance refinement, pixel-diff counts are diagnostic evidence rather than an independent
pass/fail gate; the final review evidence and non-blocking baseline debts remain in the historical
Slice 37 Contract identified above, with its closure in [Progress](progress.md).

## Scope

Slice 37 owns the shared V2 shell presentation and one primary operator-facing workspace:

- the shared shell chrome rendered across every V2 route;
- the V2 **Files** page;
- the Files page's local "Add ResourceLibrary" drawer shown in the reference image;
- the ResourceLibrary-scoped browse, selection, Create Folder/Text File, Rename, Copy, Move, Delete,
  bounded text Edit and organize continuation journey rendered on that page. Direct browser Upload
  and Download are outside the current product surface.

The following remain behaviorally frozen:

- Dashboard, Operations, Review, Configuration, Notifications, Settings and all other page
  business journeys, although their shared outer shell intentionally changes;
- the V1 `/ui` surface;
- existing route/auth/deep-link semantics and Python business authority;
- FileIndex as a physical file source, source identity authority or execution authority. A bounded
  display projection and post-mutation synchronization/reconciliation are allowed.
- unrelated backend endpoints, schema rewrites, new providers and new Storage capabilities.

The old dark horizontal shell is explicitly not frozen. It must be replaced with the reference
left rail/top bar through the single shared shell component. Non-Files page bodies may adapt to the
new available content rectangle but must not acquire new business behavior or lose existing route,
permission, loading, failure or recovery semantics.

## Reference State

The acceptance screenshot uses a deterministic desktop state at exactly `1536 x 1024`, browser zoom
`100%`, device scale factor `1`, no browser chrome, no page scrollbar and all required fonts/assets
loaded. The drawer is open and shows step 1.

The reference content is:

- brand: `MediaFlow`;
- brand subtitle: `影视媒体资源管理系统`;
- search placeholder: `搜索文件、文件夹或媒体库...`;
- signed-in operator: `admin`;
- active navigation item: `文件`;
- selected ResourceLibrary: `source`;
- Storage label: `source-storage`;
- ResourceLibrary path: `/media/incoming`;
- current directory: `Movies / Avatar (2009)`;
- selected item: `Avatar.2009.1080p.mkv`;
- selected total: `1 个文件（12.4 GB）`;
- total entries: `7 个项目`;
- open drawer: `添加资源库`, step `1 基本信息`.

## Layout Anchors

The image is authoritative for design intent, composition, hierarchy and fixture state. The
following anchors are implementation guidance for the reference viewport; they are approximate and
do not impose pixel-identical CSS geometry:

| Region | Reference placement |
|---|---|
| Left navigation | Fixed full-height rail, approximately `208 px` wide |
| Top bar | Begins after the left rail, approximately `58 px` high |
| Main page content | Starts inside the top bar and uses a wide constrained content area |
| Page title block | Upper-left of the main content: `文件` followed by the subtitle |
| Primary action | Upper-right of the title block: `+ 添加资源库` |
| Information banner | Full content-width light-blue band directly below the title block |
| ResourceLibrary summary | Single compact card below the banner, showing `source` and active state |
| Directory pane | Left pane below the summary card, headed `目录` |
| File pane | Center pane beside the directory pane, containing breadcrumb, toolbar and table |
| Selection footer | Full-width strip below the directory/file work area |
| Add-library drawer | Right-aligned white panel, approximately `425 px` wide, with a visible shadow |

The reference has a light neutral canvas, white surfaces, thin cool-gray borders, dark text and
blue primary actions. The selected navigation item, selected tree row, selected table checkbox and
primary buttons use the same blue family. The green `已启用` state is distinct from the blue action
color. The reference color relationships and visual hierarchy take precedence over named colors,
but exact raster values are not independently pass/fail criteria.

## Visible Elements

### Shell

The Files screenshot must show the replacement shared V2 shell in the following visual order:

1. MediaFlow brand block at the top of the left rail.
2. Navigation items, in order:
   `首页`, `文件`, `媒体库`, `存储管理`, `整理规则`, `自动化`, `操作与任务`, `通知`, `系统设置`.
3. `文件` is the only active navigation item.
4. No fabricated system-capacity or usage block is rendered at the bottom of the left rail.
5. The top bar contains the search field, notification icon and `admin` account control.

The shell must not acquire a second Files-only navigation model. The same shell and ordered
navigation frame every V2 route; Files supplies its search behavior through the shared top-bar slot.
Icons, spacing, selected-state backgrounds and alignment must remain recognizably aligned with the
reference image. Exact glyph artwork, rasterization and CSS measurements may differ. The current
product boundary intentionally removes the reference-only `系统存储` usage block because no
supported authoritative capacity source exists; adding one is outside Slice 37.

### Page Header and ResourceLibrary Summary

The main content shows:

- heading `文件`;
- subtitle `浏览资源库中的文件，选择需要整理的文件。`;
- primary button `+ 添加资源库`;
- information banner:
  `当前显示的是资源库中的文件，可从条目操作直接整理到对应的媒体库（如 Movies、TV Shows）。`;
- summary card:
  - name `source`;
  - green state `已启用`;
  - `存储: source-storage`;
  - `路径: /media/incoming`;
  - `1,248 个文件 · 324 GB`.

### Directory Pane

The directory pane is headed `目录` and contains this expanded tree:

```text
source
└─ Movies
   ├─ Avatar (2009)
   ├─ Inception (2010)
   ├─ Interstellar (2014)
   └─ Dune (2021)
└─ TV
└─ Anime
└─ Others
```

`Avatar (2009)` is the selected directory. `source` and `Movies` are expanded. Folder icons,
disclosure controls, indentation, selected-row background and tree spacing must match the image.

### File Pane

The file pane shows the breadcrumb and controls:

- breadcrumb: home icon, `/`, `Movies`, `Avatar (2009)`;
- button `刷新`;
- list view selected;
- grid view available but not selected.

The screenshot remains authoritative for the closed, non-hover success-state composition. Row overflow and
directory-node hover/focus/context actions provide `新建文件夹`, `新建文本文件`,
`复制`, `移动`, `重命名` and `删除` without adding persistent pixels or shifting the reference controls while
menus/dialogs are closed. Keyboard and touch users receive an equivalent focusable action entry;
right-click alone is not sufficient discoverability.

The table columns are exactly (current presentation boundary — see above):

```text
选择 | 名称 | 类型 | 大小 | 修改时间 | 操作
```

The reference rows, in order, are:

| Name | Type | Size | Modified | Action |
|---|---|---:|---|---|
| `Avatar.2009.1080p.mkv` | `视频` | `12.4 GB` | `2024-01-15 10:30` | `整理` |
| `Avatar.2009.nfo` | `其他` | `4 KB` | `2024-01-15 10:30` | `查看` |
| `sample.jpg` | `图片` | `1.2 MB` | `2024-01-15 10:30` | `查看` |
| `Subtitles` | `文件夹` | `-` | `2024-01-15 10:30` | `打开` |
| `Behind.The.Scenes.mkv` | `视频` | `2.1 GB` | `2024-01-14 08:20` | `整理` |
| `Poster.jpg` | `图片` | `856 KB` | `2024-01-14 08:20` | `查看` |
| `fanart.jpg` | `图片` | `1.5 MB` | `2024-01-14 08:20` | `查看` |

The capability reference recognitions and business statuses that produced the earlier `识别结果` and
`整理状态` columns remain backend evidence, but the current Files presentation does not render them.

The first row is checked. Its thumbnail, file-type icon, action button and overflow menu retain the
reference grouping and recognizable alignment. Exact thumbnail/icon artwork and cell measurements
may differ. Rows with `整理` use the blue action style; `查看` and `打开` use the neutral action
style.

The closed overflow menu is the reference screenshot state. For an authorized eligible entry, the
menu exposes applicable `重命名`, `复制`, `移动`, `删除` and, for an allowlisted bounded
text file, `编辑` actions.
Opening a direct-action dialog must not disturb the reference screenshot state when the menu is
closed. Unsupported operations are omitted or disabled with a reason.

### Common File Actions

- `新建文件夹` creates one valid directory in the selected ResourceLibrary-relative location and
  never replaces an existing entry.
- `新建文本文件` creates one bounded allowlisted text file and enters the same stale-safe text
  editing flow; it cannot create arbitrary binary/media content.
- `重命名` edits one basename within the same ResourceLibrary/Storage. It rejects path separators,
  root rename and existing-target overwrite, then refreshes the live listing on known success.
- `复制` and `移动` accept one item or a bounded selection and open a ResourceLibrary-confined
  destination picker. Same-Storage actions use advertised native capability. Cross-Storage Move is
  explicitly shown as Copy, verify, then source Delete; failed verification preserves the source and
  partial outcomes remain visible per item.
- `删除` accepts one item or a bounded selection. Non-empty directories receive a lightweight
  bounded item/size impact summary and one explicit permanent-effect confirmation; ResourceLibrary
  roots and unbounded recursion are never deletable.
- `编辑` supports only size-bounded, allowlisted text files. Save is the explicit overwrite
  intent for the exact loaded version; binary, oversized, invalid-encoding or stale content fails
  without writing.
- These actions use a direct backend command rather than Recognition/Metadata/Naming/
  Classification/Organize Preview ceremony. They still enforce RBAC, selected Active
  ResourceLibrary confinement, Storage capability, limits, stale/conflict checks and audit. Every
  mutation goes through `OrganizerExecutor`. No uncertain mutation is
  automatically retried and no operation silently falls back.

### Selection Footer

The footer shows, from left to right:

- `已选择 1 个文件（12.4 GB）`;
- primary button `批量整理`;
- secondary button `取消选择`;
- right-aligned `共 7 个项目`;
- previous-page control, page `1`, next-page control.

The footer remains visible in the reference state and must not collapse, wrap or move the
pagination into a second row at the reference viewport.

### Add ResourceLibrary Drawer

The drawer is open on the right and contains:

- title `添加资源库`;
- close control at the upper-right;
- vertical steps:
  - active `1 基本信息`;
  - inactive `2 存储位置`;
  - inactive `3 确认`;
- active panel title `基本信息`;
- helper text `设置资源库的基本信息`;
- required field `名称 *`;
- placeholder `例如：115电影`;
- helper text `请输入易于识别的名称`;
- required field `资源库 ID *`;
- placeholder `例如：source`;
- helper text `仅支持小写字母、数字、连字符，创建后不可修改`;
- step 2 shows the bound `Storage` and a safe Storage-relative resource root path;
- step 3 shows the complete ResourceLibrary candidate and the activation impact;
- field label `状态`;
- enabled toggle and label `启用`;
- helper text `关闭后将在资源库列表中隐藏，但不会删除数据`;
- bottom buttons in the reference step-1 state are `取消` and `下一步`; the final step replaces
  `下一步` with `保存`.

The drawer is a page-local ResourceLibrary creation panel, not a MediaLibrary editor and not a
replacement for the general Configuration page. Its visual stepper, field order, labels, required
markers, button placement and close control follow the reference structure. Exact internal spacing,
typography metrics, borders and shadows may differ when the complete step remains clear and usable.

The final `保存` action submits the complete ResourceLibrary candidate. The backend uses the
current Active configuration as its base, runs the existing configuration validation and checked
activation flow, and makes the new immutable Active runtime available on success. The operator does
not perform a separate Validate or Activate action in this drawer. Any validation, dependency,
Storage check, activation or runtime-load error rejects the save and preserves the previous Active
configuration; the page must not present the ResourceLibrary as saved when activation failed.

## Journey Contract

The page must be documented and later implemented as one vertical journey:

| Stage | Files page contract |
|---|---|
| Goal | Browse and fully manage common file operations in configured ResourceLibraries, create a ResourceLibrary, or choose media to organize |
| Entry | Select `文件` from the shell or open `/ui-v2/library/files` |
| Visible state | The replacement shared shell, ResourceLibrary summary, directory tree, file table, common file commands/progress, selection footer and add-library drawer |
| Action | Browse, select, refresh, switch view, Create Folder/Text File, Rename/Copy/Move/Delete/Edit eligible content, organize selected media or complete the local add-library flow |
| Success | Common actions refresh from live Storage with independent outcomes, selected organize action remains clear, a saved ResourceLibrary is Active/browseable, and the page matches the reference |
| Failure | Read, permission, capability, path, limit, stale/conflict, partial transfer, malformed-data or activation failure is shown on the affected item without fabricated success or uncertain replay |
| Recovery | Retry safe reads, return to root, correct input/destination, reload stale text, inspect partial items, reconfirm a current delete/replace, select another library or correct and resubmit a failed ResourceLibrary save |

Viewing, refreshing, browsing and selecting are read-only. Common mutation commands are
explicit and do not start merely by viewing or selecting. Any organize action continues
through the existing Preview, explicit intent and backend authority boundaries. The Files page must
never use FileIndex to enumerate physical entries, resolve a selected path, construct source
authority, expose credentials or grant execution authority, and it does not present
recognition/business-status feedback. After a terminal Organize result, the backend
automatically synchronizes that item outcome to FileIndex. A known direct file-operation result may
also reconcile display state, but FileIndex never authorizes the operation and reconciliation
failure never replays Storage mutation.

## Acceptance

Slice 37 was accepted only when all of the following were true:

1. A deterministic screenshot at exactly `1536 x 1024` is captured and compared with
   `docs/pics/文件页.png` in the controlled browser/font environment. The report records observed
   differences, but the pixel count is diagnostic rather than a pass/fail threshold. The shared
   shell, Files hierarchy, fixture state, labels and control order must remain complete and
   recognizably aligned. Bounded differences in font/glyph rendering, icon or thumbnail artwork,
   exact dimensions/spacing, borders, shadows and color nuance are accepted.
2. The required visible Chinese labels, row order, values, selected states, drawer state and control
   order above are present. Dense table cells may use bounded ellipsis when the complete underlying
   value remains available to assistive technology and the item/action is unambiguous.
3. The old dark horizontal shell is replaced by the reference light shared shell across V2 without
   creating a Files-only navigation model or breaking existing route/auth/deep-link behavior.
4. The page has bounded loading, empty, unauthorized, forbidden, unavailable and malformed-data
      states with action-oriented recovery; error states do not rewrite the reference success state.
5. `+ 添加资源库` creates a ResourceLibrary, and final `保存` invokes backend validation and
      activation as one user action; any error rejects the save and preserves the previous Active.
6. FileIndex supplies no Files-page recognition/business-status feedback, and every
      terminal Organize item attempts an automatic FileIndex synchronization without replaying media
      mutation when synchronization fails.
7. Create Folder/Text File, Rename, Copy, Move, Delete and bounded text Edit
   complete through direct, low-friction backend-authoritative commands with explicit destructive/
   overwrite intent, bounded selection/recursion, partial-outcome recovery and
   `OrganizerExecutor`-only mutation. Direct browser Upload and Download were delivered by the
   original closure and later removed from the current product surface.
8. Non-Files V2 business journeys and route behavior remain functional inside the intentionally
      replaced shared shell, and V1 `/ui` remains unchanged.
9. The implementation contains no unrelated provider, Storage-adapter or identity-system change;
      focused direct-file, ResourceLibrary activation and post-mutation reconciliation behavior
      stays within the revised Files journey.

The final browser evidence, visual-diff reporting and implementation Task history remain in Git and
the Closure Packet/A Final Review in [`SLICE.md`](../SLICE.md). This document records the accepted
visual and journey contract; it does not select the next Slice.
