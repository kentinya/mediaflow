# Files Page Visual Specification

Status: ACTIVE Slice 37 reference
Canonical image: [`docs/pics/文件页.png`](pics/文件页.png)
Reference size: `1536 x 1024` pixels
Route: `/ui-v2/library/files` (`/library/files` inside the V2 router)

This document is the visual source of truth for the Files page. The image is an existing user
asset and must not be edited, regenerated, compressed, recolored or replaced. This documentation
round changes documentation only; it does not change the frontend, backend, tests or the behavior
of any other page.

## Scope

Slice 37 owns one operator-facing page:

- the V2 **Files** page;
- the Files page's local "Add media library" drawer shown in the reference image;
- the existing ResourceLibrary-scoped file browsing and selection journey as rendered on that page.

The following are frozen for this Slice:

- Dashboard, Operations, Review, Configuration, Notifications, Settings and all other page
  journeys;
- the V1 `/ui` surface;
- shared API, domain, persistence, Storage, OrganizerExecutor and metadata authority;
- global navigation semantics and shared shell behavior outside the Files route;
- FileIndex as an ordinary Files-page concept;
- new backend endpoints, schema changes, new providers and new Storage capabilities.

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
- open drawer: `添加媒体库`, step `1 基本信息`.

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

### Add Media Library Drawer

The drawer is open on the right and contains:

- title `添加媒体库`;
- close control at the upper-right;
- vertical steps:
  - active `1 基本信息`;
  - inactive `2 存储位置`;
  - inactive `3 确认`;
- active panel title `基本信息`;
- helper text `设置媒体库的基本信息`;
- required field `名称 *`;
- placeholder `例如：115电影`;
- helper text `请输入易于识别的名称`;
- required field `媒体库 ID *`;
- placeholder `例如：115-movies`;
- helper text `仅支持小写字母、数字、连字符，创建后不可修改`;
- field label `状态`;
- enabled toggle and label `启用`;
- helper text `关闭后将在媒体库列表中隐藏，但不会删除数据`;
- bottom buttons `取消` and `下一步`.

The drawer is a page-local panel, not a replacement for the general Configuration page. Its
visual stepper, field order, labels, required markers, button placement, close control and
internal spacing must match the reference. The form's authoritative validation and persistence
remain outside this documentation-only activation.

## Journey Contract

The page must be documented and later implemented as one vertical journey:

| Stage | Files page contract |
|---|---|
| Goal | Browse a configured ResourceLibrary and choose files to organize |
| Entry | Select `文件` from the shell or open `/ui-v2/library/files` |
| Visible state | The reference shell, ResourceLibrary summary, directory tree, file table, selection footer and add-library drawer |
| Action | Browse the ResourceLibrary, change directory, select files, refresh, switch view, open a folder or continue with the local add-library flow |
| Success | The selected file and its bounded organize action are clear, while the page matches the reference image |
| Failure | Missing Active configuration, unavailable Storage, invalid path, unauthorized access or malformed data is shown in the Files page without fabricated rows or unsafe mutation |
| Recovery | Retry the bounded read, return to the ResourceLibrary root, select another enabled ResourceLibrary or leave the page; no automatic mutation, Provider call or unrelated-page navigation is created |

Viewing, refreshing, browsing and selecting are read-only. Any later organize action must continue
through the existing Preview, explicit intent and backend authority boundaries. The page must never
accept arbitrary host paths, expose credentials or use FileIndex-only identity as mutation authority.

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
5. Other page screenshots and route behavior remain unchanged. No shared-shell change is accepted
   without proof of this condition.
6. The implementation adds no backend or persistence change unless a later A-owned scope decision
   explicitly expands this Slice.

Required browser evidence, visual diff tooling and any implementation Task belong to a later B
Task. This document does not claim that the image has already been implemented.
