# MediaLibrary Page Visual Specification

Status: CURRENT TARGET — Slice 38; shared library-context parity added 2026-09-24
Canonical image: [媒体库页.png](pics/媒体库页.png)
Reference size: `1536 x 1024`
Target route: `/ui-v2/medialib/files`
Contract: [SLICE.md](../SLICE.md)

The supplied image controls the MediaLibrary page's visual hierarchy. The 2026-09-23 user decision
removes library-card statistics and file thumbnails. The 2026-09-24 A presentation correction makes
the MediaLibrary and ResourceLibrary Files library selector/context identical: card facts are not
shown, and the selected context carries only enabled state and path. Reuse the Slice 37 shared
shell and preserve the ResourceLibrary Files body and behavior.

## Required Composition

| Region | Required content and behavior |
|---|---|
| Shared shell | Existing left rail/top bar; `媒体库` active; `文件` selects ResourceLibrary Files; shared navigation/authentication. |
| Header | `媒体库`; subtitle `选择媒体库，浏览其中的文件。媒体库用于存放已整理的媒体文件，支持文件的常规操作。`; `+ 添加媒体库`. |
| Card strip | Enabled libraries with name only; blue selected state and independent action menu; accessible responsive overflow shared with ResourceLibrary Files. |
| Selected-library context | Immediately below the cards, show only `已启用` and exact configured `路径: /...`; do not repeat the name or show Storage. |
| Directory pane | `目录`, selected library root and lazy directories; exact relative identity and selected directory. |
| File toolbar | Relative breadcrumbs, `刷新`, list/grid controls and existing bounded search through the top bar. |
| Selection bar | Above rows: selected count/known size and applicable Copy/Move/Rename/Delete/More; Rename is single-item only. |
| Table | `选择 \| 名称 \| 类型 \| 大小 \| 修改时间 \| 操作`; type icons, directory navigation, selection and per-row actions. |
| Grid | Same entries, selection and commands using type icons, without thumbnails/artwork. |
| Paging | Existing supported bounded previous/next/cursor behavior; accurately labelled loaded/visible count, no fabricated full totals. |
| Add drawer | Right-side white panel, close button, step rail, form and footer; `基本信息 → 存储位置 → 确认`. |

The desktop reference has an approximately `208 px` left rail, `58 px` top bar and a drawer
beginning near `x=1142`. These guide composition, not pixel thresholds. Retain the light canvas,
white panels, cool borders, blue actions/selection and green enabled badges. Cards sit above the
directory/file panes. The drawer must not make controls unusable. Narrow layouts retain actions,
readable content and keyboard/focus behavior.

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

## Drawer and Configuration Actions

Normal entry, reload and reconnect keep the drawer closed. Add opens/focuses the form. Close,
Cancel and Escape restore focus to the invoking control where practical; failed save retains input.

1. **基本信息:** required name and `媒体库 ID`; lowercase letters/digits/hyphens; ID immutable
   after creation; enabled toggle with truthful hidden-from-browse/files-preserved explanation and
   existing Web configuration path for re-enabling.
2. **存储位置:** existing enabled Storage and safe relative MediaLibrary root using existing
   bounded input/browser behavior. Follow backend root validation; no host-path authority or implicit
   directory creation. Missing Storage/setup has an actionable configuration handoff.
3. **确认:** name, ID, enabled state, Storage and root; Back/Cancel/Save. One Save composes validation
   and actual activation. Pending/error/success must not label a draft Active.

The selected card menu can remove configuration after confirmation, explaining that files remain.
Blocking references have an existing configuration recovery route; no forced deletion or automatic
policy rewrite.

## Empty, Error and Operation States

Provide truthful loading, no libraries, empty directory, 401/403, missing/disabled library,
unavailable Storage, stale path/cursor, malformed response, invalid form and failed activation
states. Each supplies a concrete next action. Refresh reconciles directory memory and selection;
it never fabricates removed entries to retain the tree.

Common commands follow existing short dialogs and backend capabilities. Text is allowlisted/bounded;
Delete is explicit; conflicts default to no overwrite. Copy/Move selects a MediaLibrary and confined
directory. Durable progress, independent partial/uncertain outcomes and supported continuation remain
available through Task/Operations after navigation/reconnection.

## Visual Acceptance

Capture drawer-open step 1 and drawer-closed states at `1536 x 1024`, zoom `100%`, scale `1`
with deterministic entries, plus narrow-screen and keyboard/focus evidence. Verify hierarchy,
selection-bar position, six columns, drawer and required functional states. Statistics/artwork
removals are mandatory differences from the image. Font/glyph/spacing variation is acceptable when
the design remains clear; a nonzero pixel diff alone is not a blocker. Slice tests accept behavior
and safety.
