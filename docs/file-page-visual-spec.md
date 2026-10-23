# Files Page Visual Specification

Status: CURRENT visual baseline — accepted Slice37 with delivered38 route/card editing updates.
Canonical immutable image: [`文件页.png`](pics/文件页.png), `1536 x 1024`.
Current route: `/ui-v2/resourcelib/files`; MediaLibrary has its
[separate specification](media-library-page-visual-spec.md). Old library URLs provide route recovery.

This file owns Files/shared-shell composition and controlled visual acceptance, not live work scope.
[SLICE.md](../SLICE.md) selects current changes; [Progress](progress.md) records accepted Base/Head.
Original revision/delivery notes are retained at
`865ebdce47b0b323064fd8e05fbfaa54546e6269:docs/file-page-visual-spec.md`.
Do not edit/regenerate/compress/recolor/replace the user's reference image.

## Current Presentation Boundary — 2026-09-22

The current table presents selection, exact name, type, size and modification time, with applicable
commands in the controlled accessible context menu. No recognition-result/organize-status feedback,
persistent row action buttons or operation column. Backend evidence is not ordinary page authority.
Preserve boundary whitespace exactly and distinguish it visually/assistively; an absent trimmed
sibling stays not-found, without alternate-path guesses.

Refresh reconciles directory-tree memory/selection against live Storage so externally removed/moved
directories disappear. Keep the selected library/path when valid, or the bounded read-failure and
recovery state when absent. Source organization remains behind exact analysis/separate confirmation.

## Shared Library Selector Presentation — 2026-09-24 A Revision

Both library pages show icon/name/selection/menu only on cards: no Storage/root/count/capacity.
Selected context shows enabled state and exact path (`/` for root), not the name again. Storage is
available in configuration/setup/recovery, not normal browse cards/context. Disabled libraries are
hidden with the existing Web re-enable path. These explicit overrides govern older image labels.

## Selected-card Library Editing — 2026-09-25 A Revision

Selected-card `编辑资源库`/`编辑媒体库` sits beside configuration removal and opens the prefilled
three-step drawer. ID is read-only; name/enabled/Storage/kind-relative root are editable. Save uses
checked atomic Active publication, preserves hidden fields/input/old Active on failure, and never
creates/moves/migrates/deletes media. Ordinary file commands remain separate.

## Scope

The accepted baseline covers the replacement shared light shell, Files body/Add drawer, bounded
live browse/selection/common maintenance and ResourceLibrary organization. No browser Upload/Download.
Other pages' business behavior was frozen only for that historical Slice, not every later Contract.
V1/API authority, exact source/pin, RBAC, capability/confinement and OrganizerExecutor-only mutation
remain protected. Slice45 has accepted complete FileIndex retirement and same-page organizing
analysis/confirmation; former index compatibility/sync obligations are superseded by V2-FILES-005/006.

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
| Library selector/context | Shared card strip showing `source` by name; selected context below shows `已启用` and `路径: /media/incoming` |
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
- selected context:
  - green state `已启用`;
  - `路径: /media/incoming`.

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

The screenshot remains authoritative for the closed, non-hover success-state composition. Single-entry
commands are exposed through a controlled context menu opened by right-click, the Context Menu key or
`Shift+F10`; keyboard and touch users receive an equivalent focusable action entry, so right-click is
not the only discoverability path. Folder names/icons and non-checkbox row areas open folders on left
click, while the context menu retains an explicit `打开` item. No persistent row action buttons or
operation column are rendered.

The table columns are exactly (current presentation boundary — see above):

```text
选择 | 名称 | 类型 | 大小 | 修改时间
```

The reference rows, in order, are:

| Name | Type | Size | Modified |
|---|---|---:|---|---|
| `Avatar.2009.1080p.mkv` | `视频` | `12.4 GB` | `2024-01-15 10:30` |
| `Avatar.2009.nfo` | `其他` | `4 KB` | `2024-01-15 10:30` |
| `sample.jpg` | `图片` | `1.2 MB` | `2024-01-15 10:30` |
| `Subtitles` | `文件夹` | `-` | `2024-01-15 10:30` |
| `Behind.The.Scenes.mkv` | `视频` | `2.1 GB` | `2024-01-14 08:20` |
| `Poster.jpg` | `图片` | `856 KB` | `2024-01-14 08:20` |
| `fanart.jpg` | `图片` | `1.5 MB` | `2024-01-14 08:20` |

The capability reference recognitions and business statuses that produced the earlier `识别结果` and
`整理状态` columns remain backend evidence, but the current Files presentation does not render them.

The first row is checked. Its type icon and selection retain the reference grouping and recognizable
alignment. Exact icon artwork and cell measurements may differ. The closed table has no action
button; command styling appears only inside the controlled context menu.

For an authorized eligible entry, the controlled context menu exposes applicable `打开`,
`重命名`, `复制`, `移动`, `删除` and, for an allowlisted bounded text file, `编辑` actions.
Folder entries include `打开`, `重命名`, `复制`, `移动` and `删除`; ResourceLibrary media entries
may include `整理`, while MediaLibrary entries never include Organize. Unsupported operations are
omitted or disabled with a reason. Opening a folder by left click remains available without an
inline button.
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
| Entry | Select `文件` from the shell or open `/ui-v2/resourcelib/files` |
| Visible state | The replacement shared shell, ResourceLibrary summary, directory tree, file table, common file commands/progress, selection footer and add-library drawer |
| Action | Browse, select, refresh, switch view, Create Folder/Text File, Rename/Copy/Move/Delete/Edit eligible content, organize selected media or complete the local add-library flow |
| Success | Common actions refresh from live Storage with independent outcomes, selected organize action remains clear, a saved ResourceLibrary is Active/browseable, and the page matches the reference |
| Failure | Read, permission, capability, path, limit, stale/conflict, partial transfer, malformed-data or activation failure is shown on the affected item without fabricated success or uncertain replay |
| Recovery | Retry safe reads, return to root, correct input/destination, reload stale text, inspect partial items, reconfirm a current delete/replace, select another library or correct and resubmit a failed ResourceLibrary save |

Viewing, refreshing, browsing and selecting are read-only. Common mutation commands are
explicit and do not start merely by viewing or selecting. Any organize action continues
through same-page analysis/plan summary, explicit intent and backend authority boundaries. The Files page must
never use FileIndex to enumerate physical entries, resolve a selected path, construct source
authority, expose credentials or grant execution authority, and it does not present
recognition/business-status feedback. After a terminal Organize or direct file-operation result,
durable Task/results remain the outcome authority and live Storage refresh supplies directory state.
There is no FileIndex sync/reconciliation consumer; result/display failure never replays Storage mutation.

## Acceptance

Slice 37 was accepted only when all of the following were true. Item 6's historical index-sync
obligation is superseded for CURRENT V2 by Slice45; the original acceptance remains historical:

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

Historical browser evidence, visual differences, Task history and final review remain in Git at
the accepted ranges listed in [Progress](progress.md). Root Slice is the current Contract, not the
old closure packet. This document does not select the next Slice or change its product boundaries.
