# MediaLibrary Page Visual Specification

Status: CURRENT — accepted50 cards/tree removal/loading, retaining Slice38 business and editing
Historical image only (not a current design or acceptance baseline): preserved in Git at
`f458646d3dac280b118a511c60ec53a5d3075d67:docs/pics/媒体库页.png`.
Desktop validation size: `1536 x 1024`
Route: `/ui-v2/medialib/files`
Work authority: [SLICE.md](../SLICE.md) / [TASK.md](../TASK.md) under the
[workflow](development-workflow.md); large-Slice acceptance: [Progress](progress.md).
The [accepted browse correction](https://github.com/kentinya/mediaflow/blob/53bcc0a3d6e6506bec23dfa92aa35e27cc1864f5/TASK.md#patch-20261113-2--b-pass)
records shared list/grid feedback, current-page sorting and session column widths specified below.

The written composition below defines hierarchy: no card statistics or thumbnails;
both library selectors share cards with name/selection/menu and selected context with enabled state/
path only. Reuse the shared shell; this visual specification adds no unrelated Files business scope.

## CURRENT — Slice50 弹卡、去目录树与加载体验（PASS / CLOSED）

[Slice50](https://github.com/kentinya/mediaflow/blob/214b69b1e64b24fc22068c2e1760cd1b0c6ac787/SLICE.md) / `V2-UX-009–012` 已于 2026-11-07 通过独立 A 终审。
已删除本页与资源库文件页的页内左侧目录树及占位，浏览区利用释放宽度；保留全局侧栏、
面包屑、上一级/根目录、文件夹、搜索、视图、选择、刷新与分页，不新增替代树。

添加/编辑媒体库与资源库四个入口都改为与自动化新建/编辑协调的居中弹卡，保留字段/值、
编辑 ID 不变、隐藏配置、精确 Active/checked Save 和失败/冲突/未知核对。改善两页库配置
编辑/移除菜单与确认，包含用户点名的编辑/删除媒体库，区分普通/危险操作。引用阻塞、
权限/确认及物理文件保留含义不变，配置移除不等于条目 Delete。

库信息未返回与后续目录读取使用和资源库一致的协调占位/加载动画，内容就绪后平顺接入；
占位仅用于未就绪区域，快速响应/有效缓存可直接显示内容，不强制阶段播放或为动画串行
请求。加载不显示“未添加媒体库/空目录”。真实空态、无 Active、权限和读失败各自可辨，
正常同条件刷新保留内容，快速切库/路径不串响应，reduced-motion 保留静态反馈。共享切页
仅覆盖现有 V2 左侧侧栏入口对应的主页面之间，按主页面身份判断；同一主页面内的标签、
详情子路由（含其深链）、切库/目录和开关弹卡不重播整页动画，既有合法局部动效保留。
其他页面业务不重设计。

现行验收以本节替换旧 Directory pane / Add/Edit drawer 及旧图片的对应几何要求；
其他 CURRENT 业务约束保留，原图片及验收历史保留在 Git。桌面 `1536×1024`、`390px` 窄屏、
键盘/焦点、卡片/菜单、慢读取/真实空/错误和快速切换/reduced-motion 须有实际交互及视觉
证据；动态体验不能只靠 DOM/CSS 断言。按用户结果与自动化基准验收，无新增像素/时长指标。

## Required Composition

| Region | Required content and behavior |
|---|---|
| Shared shell | Existing left rail/top bar; `媒体库` active; `文件` selects ResourceLibrary Files; shared navigation/authentication. |
| Header | `媒体库`; subtitle `选择媒体库，浏览其中的文件。媒体库用于存放已整理的媒体文件，支持文件的常规操作。`; `当前页面操作状态` immediately left of `+ 添加媒体库`, with the same button style. |
| Card strip | Enabled libraries with name only; blue selected state and independent action menu; accessible responsive overflow shared with ResourceLibrary Files. |
| Selected-library context | Immediately below the cards, show only `已启用` and exact configured `路径: /...`; do not repeat the name or show Storage. |
| Directory navigation | No page-local tree/placeholder; folders, exact breadcrumbs and parent/root navigation retain browsing. |
| File toolbar | Relative breadcrumbs, `刷新`, list/grid controls and existing bounded search through the top bar. |
| Selection bar | Above rows: selected count/known size and bounded batch Copy/Move/Delete; ResourceLibrary batch Organize remains available. Single-entry commands are not duplicated here. |
| Table | `选择 \| 名称 \| 类型 \| 大小 \| 修改时间`; type icons, directory navigation and selection. Name/size sort only the loaded current page; the toolbar keeps a compact `当前页排序：…` status and a `显示设置` menu whose `恢复默认顺序` resets only the order. Four data columns have discoverable drag/keyboard width handles, and the same menu exposes a session-only `恢复默认列宽` entry in list view only; order and width recovery are disabled at their own default and reset independently. User-set widths are realized by a table exactly as wide as its columns, so the visible boundary follows the announced width; leftover pane space stays outside the table and the default layout still fills it. No persistent operation column. |
| Entry context menu | Right-click, Context Menu key or `Shift+F10` opens the applicable single-entry commands. Folder left click opens directly; no inline Open button. |
| Grid | Same entries, exact path selection, select-all/clear, commands and current-page order using type icons, without thumbnails/artwork. |
| Paging | Existing supported bounded previous/next/cursor behavior; accurately labelled loaded/visible count, no fabricated full totals. |
| Add/Edit card | Centered bounded overlay, close button, step rail, form and footer; `基本信息 → 存储位置 → 确认`. |

The desktop reference has an approximately `208 px` left rail and `58 px` top bar. These guide
composition, not pixel thresholds; its right drawer/tree geometry is superseded by Slice50. Retain
the light canvas, white panels, cool borders, blue actions/selection and green enabled badges.
Library cards sit above the full-width browse area; Add/Edit uses a bounded centered overlay. Narrow
layouts retain actions, readable content and keyboard/focus behavior. Hover, focus, pressed and
selected list/grid states change a light background without row/tile movement; selected stays
distinguishable while hovered, and reduced-motion keeps the feedback immediate without a slide.
Column widths and current-page order are presentation session state, not durable preferences.

## Explicit Image Overrides

- Remove card lines such as `8,432 个文件 · 1.2 TB` entirely. No count, capacity/usage,
  `未统计`, dash placeholder or loading-statistics row, and no collection for these values.
- Replace movie/poster/fanart thumbnails with folder/video/image/text/other type icons. No content
  image requests, artwork lookup, thumbnail generation or FFmpeg/FFprobe.
- Keep per-file size, selected count/known size and bounded direct-command impact/progress.
- No page `整理`/`批量整理`, recognition/status column, organize banner, Scan/Preview action or
  retired Library landing content. Shared `整理规则` navigation remains.
- No browser Upload/Download in the More menu.
- Use actual cursor paging rather than fabricated numbered pages.

## Reference Fixture

Use deterministic fake/local data to reproduce the structural state:

- cards `115网盘`, `115网盘_2`, `夸克网盘`, with the second selected;
- the selected context displays `已启用` and the configured root path `/TV Shows`;
- Storage labels and bindings remain fixture/configuration data but are not rendered in the normal
  browse-page card or selected context;
- relative directory `Breaking Bad` inside the second library; `TV Shows` may label its configured
  root but must not be duplicated in the relative request;
- three season directories, three `Breaking.Bad.S01E0*.mkv` files, `poster.jpg`, `fanart.jpg` and
  `logo.png`; two videos selected with a truthful fixture size summary;
- type icons in every row, no card totals, enabled badges and Add step 1 open.

These are synthetic library labels, not new provider requirements or authorization for production
connections. Do not hardcode fixture data at runtime. Path identity remains exact despite shortened
display labels.

## Card and Configuration Actions

Normal entry, reload and reconnect keep the configuration card closed. Add or selected-card Edit explicitly
opens/focuses the form. Close, Cancel and Escape restore focus to the invoking control where
practical; failed save retains input. Edit pre-fills the exact current Active object and renders ID
read-only.

1. **基本信息:** required name and `媒体库 ID`; lowercase letters/digits/hyphens; ID immutable
   after creation; enabled toggle with truthful hidden-from-browse/files-preserved explanation and
   existing Web configuration path for re-enabling.
2. **存储位置:** existing enabled Storage and safe relative MediaLibrary root using existing
   bounded input/browser behavior. Follow backend root validation; no host-path authority or implicit
   directory creation. Missing Storage/setup has an actionable configuration handoff.
3. **确认:** name, ID, enabled state, Storage and root; Back/Cancel/Save. One Save composes validation
   and actual activation. Pending/error/success must not label a draft Active.

The selected card menu can edit configuration or remove it after confirmation. Edit saves and
activates only after exact-Active concurrency, full validation, applicable read-only checks and
runtime binding; Storage/root changes do not migrate contents. Removal explains that files remain.
Blocking references have an existing configuration recovery route; no forced deletion or automatic
policy rewrite.

## Empty, Error and Operation States

Provide truthful loading, no libraries, empty directory, 401/403, missing/disabled library,
unavailable Storage, stale path/cursor, malformed response, invalid form and failed activation
states. Each supplies a concrete next action. Refresh reconciles live entries and selection;
it never fabricates removed entries or a directory tree.

Common commands follow existing short dialogs and backend capabilities. Text is allowlisted/bounded;
Delete is explicit; conflicts default to no overwrite. Copy/Move selects a MediaLibrary and confined
directory. Durable progress, independent partial/uncertain outcomes and supported continuation remain
available through this library page's centered `当前页面操作状态` modal after close/reload/reconnect/
service restart. Its durable history, independent item evidence and existing permitted controls stay
MediaLibrary-scoped; it never hands normal progress to Task Center or mixes ResourceLibrary work.
Empty/loading/read-error and keyboard dismissal remain usable; closing neither cancels nor replays work.

## Visual Acceptance

Capture Add/Edit card-open step 1 and card-closed states at `1536 x 1024`, zoom `100%`, scale `1`
with deterministic entries, plus narrow-screen and keyboard/focus evidence. Verify hierarchy,
selection-bar position, five columns, context-menu entry, card and required functional states
against the current written composition. No comparison with the retired image is required.
Tree/drawer geometry, statistics and artwork remain absent under the current presentation contract.
Verify readable spacing, actual interaction and the existing business/safety rules.
