# Files Page Visual Specification

Status: ACTIVE Slice 37 reference
Canonical image: [`docs/pics/文件页.png`](pics/文件页.png)
Reference size: `1536 x 1024` pixels
Route: `/ui-v2/library/files` (`/library/files` inside the V2 router)

This document is the visual source of truth for the Files page. The image is an existing user
asset and must not be edited, regenerated, compressed, recolored or replaced. This documentation
round records the confirmed functional semantics for the page; it does not change the frontend,
backend, tests or the behavior of any other page.

## Current Code Status — 2026-09-14

The current implementation already establishes the data and authority boundary required by this
page:

- Files discovery is ResourceLibrary-scoped. The page loads enabled ResourceLibraries from the
  Active runtime, then reads `GET /api/v1/resource-libraries/{resourceLibraryId}/files` with only
  a ResourceLibrary-relative `path` and server-issued `cursor`.
- The runtime Files browser reads live Storage through the configured ResourceLibrary root. Its
  optional `file_index` constructor argument is retained only for older composition code and is
  intentionally not consulted by the UI-V2 Files projection.
- The typed Files model excludes FileIndex membership, `fileId`, occurrence and fingerprint
  authority. A bounded `recognitionResult` / `businessStatus` projection may be added for display
  feedback sourced from FileIndex, but it is not source identity, path authority or execution
  authority. Raw FileIndex identifiers remain excluded from ordinary page display.
- Files-originated organization Preview is also FileIndex-independent. The page submits
  `scopeKind: "file"`, `resourceLibraryId` and `relativePath` to
  `POST /api/v1/operations/previews`. The server maps the path through the Active
  ResourceLibrary/Storage binding, calls `Storage.stat()`, creates the immutable
  `SourceIdentity`, and enters the existing zero-mutation Preview planner.
- The Files-originated Preview path then calls `create_from_sources`; it does not resolve a
  `fileId`, read a FileIndex row or echo occurrence/fingerprint authority from the browser. The
  resulting Preview remains the source of truth for the existing server-authoritative organize
  continuation and Worker revalidation.
- The current page permits local selection of multiple entries, but its Preview mutation currently
  rejects more than one path with `Batch Preview is planned`; only one selected file can proceed
  through the implemented Preview path.

The codebase still contains FileIndex-backed compatibility and legacy operation paths, including
indexed discovery and older file-scoped APIs. Those paths are not the source or authority for the
ResourceLibrary Files page. The page may consume bounded FileIndex business-state feedback for
display, and completed Organize items synchronize their terminal outcome back to FileIndex. No
other Files-page action may introduce a FileIndex dependency.

The reference image remains a visual target rather than a claim of completed visual parity. The
current implementation does not yet provide every screenshot element, including the exact Chinese
copy, table columns/status presentation or the open `添加资源库` drawer.

## Scope

Slice 37 owns one operator-facing page:

- the V2 **Files** page;
- the Files page's local "Add ResourceLibrary" drawer shown in the reference image;
- the existing ResourceLibrary-scoped file browsing and selection journey as rendered on that page.

The following are frozen for this Slice:

- Dashboard, Operations, Review, Configuration, Notifications, Settings and all other page
  journeys;
- the V1 `/ui` surface;
- shared API, domain, persistence, Storage, OrganizerExecutor and metadata authority;
- global navigation semantics and shared shell behavior outside the Files route;
- FileIndex as a physical file source, source identity authority or execution authority. A bounded
  display-only business-status projection and terminal Organize-result synchronization are allowed.
- unrelated backend endpoints, schema changes, new providers and new Storage capabilities. The
  focused ResourceLibrary save/activation command and the required result-to-FileIndex
  synchronization may reuse or extend the existing application authority without moving decisions
  into the browser.

If a later implementation needs a shared style or shell change, the change must be rejected unless
it is strictly page-local or it proves that every frozen page remains visually and behaviorally
unchanged.

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

The image is authoritative. The following anchors are implementation guidance for the reference
viewport and must not be used to replace screenshot comparison:

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
color. Exact rendered pixels in the reference image take precedence over any named color.

## Visible Elements

### Shell

The Files screenshot must show the existing operator shell in the following visual order:

1. MediaFlow brand block at the top of the left rail.
2. Navigation items, in order:
   `首页`, `文件`, `媒体库`, `存储管理`, `整理规则`, `自动化`, `操作与任务`, `通知`, `系统设置`.
3. `文件` is the only active navigation item.
4. A `系统存储` usage block is visible at the bottom of the left rail.
5. The top bar contains the search field, notification icon and `admin` account control.

The shell must not acquire a second Files-only navigation model. Icons, spacing, selected-state
backgrounds and alignment must follow the reference image.

### Page Header and ResourceLibrary Summary

The main content shows:

- heading `文件`;
- subtitle `浏览资源库中的文件，选择需要整理的文件。`;
- primary button `+ 添加资源库`;
- information banner:
  `当前显示的是资源库中的文件，这些文件将根据识别结果整理到对应的媒体库（如 Movies、TV Shows）。`;
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

The table columns are exactly:

```text
名称 | 类型 | 大小 | 修改时间 | 识别结果 | 整理状态 | 操作
```

The reference rows, in order, are:

| Name | Type | Size | Modified | Recognition | Organize status | Action |
|---|---|---:|---|---|---|---|
| `Avatar.2009.1080p.mkv` | `视频` | `12.4 GB` | `2024-01-15 10:30` | `Avatar (2009)` | `待整理` | `整理` |
| `Avatar.2009.nfo` | `其他` | `4 KB` | `2024-01-15 10:30` | `-` | `跳过` | `查看` |
| `sample.jpg` | `图片` | `1.2 MB` | `2024-01-15 10:30` | `-` | `跳过` | `查看` |
| `Subtitles` | `文件夹` | `-` | `2024-01-15 10:30` | `-` | `跳过` | `打开` |
| `Behind.The.Scenes.mkv` | `视频` | `2.1 GB` | `2024-01-14 08:20` | `-` | `待整理` | `整理` |
| `Poster.jpg` | `图片` | `856 KB` | `2024-01-14 08:20` | `-` | `跳过` | `查看` |
| `fanart.jpg` | `图片` | `1.5 MB` | `2024-01-14 08:20` | `-` | `跳过` | `查看` |

The first row is checked. Its thumbnail, file-type icon, status pill, action button and overflow
menu must retain the same alignment as the reference. Rows with `整理` use the blue action style;
`查看` and `打开` use the neutral action style; `跳过` uses the muted status style.

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
- bottom buttons are `取消` and, on the final step, `保存`.

The drawer is a page-local ResourceLibrary creation panel, not a MediaLibrary editor and not a
replacement for the general Configuration page. Its visual stepper, field order, labels, required
markers, button placement, close control and internal spacing must match the reference.

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
| Goal | Browse a configured ResourceLibrary and choose files to organize |
| Entry | Select `文件` from the shell or open `/ui-v2/library/files` |
| Visible state | The reference shell, ResourceLibrary summary, directory tree, file table, selection footer and add-library drawer |
| Action | Browse the ResourceLibrary, change directory, select files, refresh, switch view, open a folder or continue with the local add-library flow |
| Success | The selected file and its bounded organize action are clear, a saved ResourceLibrary is Active and browseable, and the page matches the reference image |
| Failure | Missing Active configuration, unavailable Storage, invalid path, unauthorized access, malformed data or ResourceLibrary activation failure is shown without fabricated rows or unsafe mutation |
| Recovery | Retry the bounded read, return to the ResourceLibrary root, select another enabled ResourceLibrary, correct the add form and save again, or leave the page; a failed save preserves the previous Active configuration |

Viewing, refreshing, browsing and selecting are read-only. Any later organize action must continue
through the existing Preview, explicit intent and backend authority boundaries. The Files page may
show bounded FileIndex-derived recognition and business-status feedback, but must never use
FileIndex to enumerate physical entries, resolve a selected path, construct source authority,
expose credentials or grant execution authority. After a terminal Organize result, the backend
automatically synchronizes that item outcome to FileIndex; no other Files-page action may introduce
FileIndex.

## Acceptance

The future implementation is accepted only when all of the following are true:

1. A deterministic screenshot at exactly `1536 x 1024` matches `docs/pics/文件页.png` pixel for
   pixel in the controlled browser/font environment. Any nonzero visual diff must be investigated;
   it is not waived as a design preference.
2. The exact visible Chinese labels, row order, values, selected states, drawer state and control
   order above are present.
3. The Files page preserves existing read-only, ResourceLibrary, authorization and Storage
   boundaries.
4. The page has bounded loading, empty, unauthorized, forbidden, unavailable and malformed-data
      states with action-oriented recovery; error states do not rewrite the reference success state.
5. `+ 添加资源库` creates a ResourceLibrary, and final `保存` invokes backend validation and
      activation as one user action; any error rejects the save and preserves the previous Active.
6. FileIndex may supply only bounded recognition/business-status feedback for display, and every
      terminal Organize item attempts an automatic FileIndex synchronization without replaying media
      mutation when synchronization fails.
7. Other page screenshots and route behavior remain unchanged. No shared-shell change is accepted
      without proof of this condition.
8. The implementation contains no unrelated backend, persistence, provider or Storage capability
      change; focused authority changes required by ResourceLibrary save/activation and
      post-Organize FileIndex synchronization remain within this page journey.

Required browser evidence, visual diff tooling and any implementation Task belong to a later B
Task. This document does not claim that the image has already been implemented.
