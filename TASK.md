# NO ACTIVE IMPLEMENTATION TASK

Task52.2 已由独立B复核PASS；当前没有新的实施Task。剩余Slice52 RO-4待后续规划。

# Task52.2 — 九个主页面切换、读取接入与两库刷新体验

用户于 2026-11-08 明确要求“激活TASK”,Task52.2 成为正式活动实施 Task,实施已授权。
Task52.2 已由独立 B 在 `35fec54c` 上复核 **PASS**：B52.2-01／02均已修正，
本Task的九页切换／读取接入与两库刷新结果完成。下方保留计划及验收，不授权新实施、
推送、发布或部署；原Task Base保持。Slice52仍ACTIVE，下一项剩余结果为RO-4自动化
旧打开链路退出，本轮未规划下一Task。

Task52.1 已由独立 B 复核 **PASS**，原始 Base
`c7913f6a751ee980db2b82ffaefec40d3d43528c` → 已审实现
`62a158f684996372b08b7a570368ffcf1b4cb194`；完整计划、返工、实际结果与限制见
[固定复核报告](https://github.com/kentinya/mediaflow/blob/4cf0efdf23981351ee3c7ef19d599726a070a4bb/TASK.md#b-review-result)。
报告后继只有 TASK.md 变化，不改变执行输入。本次规划不重新签署该实现的验收。
其导航 E2E 中 403 文案定位失败、在原 Base 的同样复现及补充原生行为通过事实保留，
不宣称所有旧 E2E 全绿。

全 Slice 重评：RO-1 探索布局／完整详情和 RO-2 有界浏览／准确返回已由 Task52.1 完成；
RO-3 九页切换／实际读取接入及两库刷新由Task52.2复核完成；RO-4 自动化旧打开链路
尚未交付，留待后续授权规划。Slice52 仍 ACTIVE，未达到交 A 终审的条件。
Slice/Roadmap/Progress 中旧“首次规划”措辞的事实协调留给其所有者，本轮不改变合同。

## Authority and task metadata

Authority: committed [Slice52 Contract](SLICE.md) at
`c7913f6a751ee980db2b82ffaefec40d3d43528c`；生命周期及测试分工遵循
[Development Workflow](docs/development-workflow.md)。实施者阅读
[Developer experience](docs/agent-experience/developer-implementation-role.md)，审查者阅读
[B experience](docs/agent-experience/task-planner-reviewer.md)。

```text
Task ID: 52.2
Task Type: SLICE
Parent Slice: 52
Status: PASS
Task Base: 4cf0efdf23981351ee3c7ef19d599726a070a4bb
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B / independent B review of Developer checkpoint
Implementation Authorization: AUTHORIZED BY USER 2026-11-08 — 激活TASK
```

## Planning checkpoint and workspace

本轮规划起点：`/Users/songzhidong/mediaflow`，分支 `main`，HEAD即上述Task Base；
治理检查PASS，TASK.md与Git可写，暂存区为空。预存跟踪变更 `mediaflow/.DS_Store`；
未跟踪 `.DS_Store`、`.explore_adapter_block.py`、`.mgmt.log`、`.t*.log`、`15`、
`docs/`／`docs/pics/`／`output/`／`testdata/`／`web/`元数据及 `output/` 下既有调查／
预览材料均保留。本轮只维护并checkpoint根TASK.md，不读取运行数据库、私有配置或用户媒体。

激活起点：`main` / `419f0539e85e0d016ca9f302cc389f0a70bde129`；治理检查PASS，
暂存区为空，预存跟踪／未跟踪文件与上述记录一致并保留。本次仅提交TASK.md激活信息；
原Task Base保持，不以规划／激活提交重新定基线。

## Goal

完成 Slice52 **RO-3、AC-5/6**，保留 AC-8 的读取／执行安全。适用稳定要求
`V2-UX-014/015` 及保留的 `V2-UX-012`、`REQ-WEB-001/003/005/006`、
`REQ-SAFE-005/007`。完整旅程及边界见
[Product Experience TARGET](docs/product-experience.md#target--slice52-experience-refinement-active)、
其 CURRENT Slice50 侧栏切换／加载旅程，以及
[Architecture TARGET](docs/architecture.md#target--slice52-experience-refinement-active) 和 CURRENT Files navigation/loading。

目标／入口：用户通过现有侧栏进入探索、文件、媒体库、存储、整理规则、自动化、任务中心、
通知、设置。可见状态／动作：切页、目标页实际等待到内容接入的完整过程舒缓；快响应和
缓存没有突兀闪现的加载提示，慢读取有稳定、可辨的局部反馈，用户可继续导航和操作。
成功：两库选择目录、手动刷新或一次普通操作完成后，真实内容平顺更新，列表不被瞬时
刷新提示推挤。失败／恢复：未返回、真实空、无 Active、权限或读取失败仍清楚区分；用户
使用该页原有的安全重读、返回根目录、选择合法库／路径或重新连接入口继续。

## Actual gaps at Task Base

- `AppShell.tsx::ShellPageSurface` 已以主页面身份控制一次入场，并保留同一个路由容器；
  `styles.css` 从 opacity 0.2 用 200ms 恢复，存储及两库另有
  `mf-content-settle` 从 0.55 用 170ms 淡入。叠加及较低起始透明度是需调校的真实路径，
  数字本身不是缺陷判据，必须比较实际切换过程。
- `LoadingPanel.tsx` 目前仅供存储／两库使用；其他页有各自的即时等待分支。不能只调一个
  共享组件就认为九页全部覆盖，也不要求把九页改成同一种骨架。
- 两库的 BrowseView 都直接按 `refreshing` 插入／移除 `mf-files-refresh-state` 段落；
  父级直接传 `isFetching`。缓存重读、手动刷新和操作后失效均会经过该路径，提示占正文行。
- 现有 `page-transition.spec.ts` 已驱动真实侧栏、快切、前后退、认证续转、卡片／未保存
  退出与 reduced-motion；主要采样 Shell 属性，等待固定280ms，慢读接入只覆盖存储。
  不能将这些断言或停稳截图作为本 Task 的完整可见验收。

### Existing entry and read map

以下路径均为已注册的现有入口（浏览器前缀 `/ui-v2`）。从真实侧栏／页面控件进入，
慢读／失败只能作用于这些操作实际发出的读取，不构造不存在的产品入口。

| 主页面／路径 | 已有读取与呈现定位 |
|---|---|
| 探索 `/explore` | `ExplorePage` 的 browse/search/options query；`ExplorePosterGrid` 骨架及已有成功页；保留52.1分页／返回／输入焦点 |
| 文件 `/resourcelib/files` | `StorageFilesPage` 的 system-status → statusReady 后 storage-files、OrganizeWorkPanel；库信息与目录为不同等待区域 |
| 媒体库 `/medialib/files` | `MediaLibraryFilesPage` 的 media-libraries、system-status 及 media-library-files；原数据依赖保持 |
| 存储 `/storage` | `StorageManagementPage` / storageInventoryQueryOptions、LoadingPanel、mf-content-settle |
| 整理规则 `/rules` | `RulesWorkspacePage` / fetchRulesInventory；保留 header，读取 Active 规则状态后接入正文 |
| 自动化 `/operations/automation` | `AutomationListPage` / listQuery、recordsQuery；主列表及现有统计／记录按实际查询状态处理 |
| 任务中心 `/operations` | `OperationsLanding` / runInventoryQueryOptions；摘要、视图、筛选与运行清单接入；保留选中任务卡 |
| 通知 `/operations/notifications` | `NotificationListPage` / notificationListQueryOptions；当前等待分支整块替换为页面内容 |
| 设置 `/configuration` | `ConfigurationPage` / fetchConfigurationStatus → 实际挂载的 `AutomationSettingsPanel` / fetchAutomationSettings（另有principal读取）；检查整个接入过程 |

## Implementation Scope and Developer guidance

代码范围为上述九页**必要的读取呈现**（含设置页实际挂载的 `AutomationSettingsPanel.tsx`
引擎设置读取区域）、`AppShell.tsx`、`LoadingPanel.tsx`、
`RefreshControl.tsx` 和 `styles.css` 的相关规则，以及直接受影响测试。按真实需要复用简单
共享反馈逻辑；保持 Router/AuthBoundary/Query 的职责，不建设新的页面状态框架。

1. **先看完整切换，再动实现。** 在现有 Node fake-server 和 Python 隔离夹具中，使用侧栏
   保存桌面1536×1024、390×844的代表性改前过程；核对每个主页面快读／慢读时，标题、
   工具区、等待区和内容何时出现。复用现有采样／trace，仅补实际缺的读取与内容接入观察。
2. **协调主页面过渡和内容接入。** 可调校起始透明度、缓动与节奏，或减少重复淡入；
   具体方案以完整切换过程舒缓、无突兀明暗变化为准，不指定动画层数。保留 persistent
   ShellPageSurface，不给业务子树按页面 key 重挂载。按最终实际
   主页面身份触发一次，同页标签／分页／目录／弹卡／轮询不重播。已有弹卡覆盖规则、
   未保存阻止退出及 reduced-motion 保持；正常目标页几何差异允许。
3. **逐页接上真实等待。** 对照上表检查九页，不止检查 Shell。快读／缓存可直接呈现，
   通过稳定布局、协调占位或必要时延后显示短暂忙碌提示等方式改善接入，具体方案按各页
   实际状态选择，不强制增加定时器。若延后反馈，只延后呈现，不延后请求、错误、授权
   判断或已就绪内容。确有等待时反馈应稳定可辨，真实内容接入协调；不新增
   强制播放时间，不为动画串行原本独立的读取。保留已有请求启用条件、查询身份／缓存
   隔离、自动刷新节奏及真实错误分支。无需重做业务表单／布局。
4. **完整处理两库刷新。** 区分首次库信息、首次目录和同条件后台重读；没有成功数据时
   不显示假空目录，有同条件内容时保持可读。将忙碌反馈与现有工具区／内容区域协调，
   消除瞬时提示插入／移除造成的突兀推挤与闪灭，正常稳定反馈及平顺替换可用；仅搬位置
   仍突兀闪现不算完成。快速刷新不闪，慢刷新仍可辨，
   手动刷新／普通操作后更新走同一呈现规则。换库／路径使用自身等待与结果；错误仍走
   原有安全恢复，不延长旧权限或让旧目录冒充目标目录。
5. **沿真实操作补覆盖并交接。** 调整并扩展既有 page-transition、两库及各改动页测试。
   原导航测试的固定280ms采样结束、必须降低透明度及必须使用 `mf-content-settle` 动画
   等实现断言，随本次合法呈现方案改为读取状态、目标内容可用、过渡完成及中间过程的
   行为检查；不要求保留指定淡入或动画名称，也不靠统一延长等待掩盖闪烁。保留主页面
   归属、容器生命周期、同页不重播、弹卡覆盖与真实等待／失败等原有行为保障。
   验证快读／缓存／慢读／失败／快切及真实内容接入。保留52.1分页、详情滚动／返回与输入
   不被迟到读取抢焦的结果。普通操作后的验证通过已有临时库控件执行一次已支持的命令，
   确认刷新不重发该命令。仅调整本 Task 必需文档事实；交出精确 checkpoint 及实际结果。

后端 API／权限／Active 发布、Storage 操作、schema、任务引擎、query命令语义与公共 Modal
生命周期保持。若实现确实需要改变这些边界，先由 B 复核范围和测试等级，不夹入呈现修正。

## Acceptance Criteria

- [x] **TAC-1 九页完整过程：** 上表九页在桌面和390px实际侧栏切换时，从离开原页、等待
  到目标内容就绪均舒缓；没有明显闪白、干扰阅读的明暗突变、突兀推挤／非预期来回位移。
  共享页头／导航稳定，正常页面布局／高度差异和协调占位替换允许。比较改前／改后过程，
  不以固定时长、CSS值、任意几何变化或单张停稳截图判断。
- [x] **TAC-2 读取接入：** 每页首次快读、有效缓存返回、实际慢读均可用；快读不突兀闪现
  等待提示／骨架，慢读有稳定可辨反馈，内容平顺接入。数据一旦就绪可交互；读取照原有
  依赖及时开始，不为动画添加网络延时或串行请求。
- [x] **TAC-3 两库刷新：** 分别完成冷读、缓存返回、手动快／慢刷新、普通操作后的更新；
  不再瞬时插入“正在刷新当前目录”推挤列表，也不将闪现搬到固定位置。慢刷仍有可访问
  的忙碌反馈，同条件成功内容保留；空、无 Active、失败与权限状态及原恢复入口清楚。
- [x] **TAC-4 归属与恢复：** A→B→C快切、浏览器前后退、认证续转到原目标，URL／选中
  导航／内容一致；两库快换库／路径的迟到读取不串结果。真实失败可以通过现有入口恢复，
  不将等待当空态、不无限占位、不隐藏失败。共享鉴权语义保持。
- [x] **TAC-5 同页与弹卡：** 同页分页／筛选／标签、切库／路径、刷新及弹卡开关不重播
  整页入场；任务／存储／库／自动化卡的遮罩覆盖完整视口，卡片内容与操作完整可用，
  长内容可在卡内滚动，背景及焦点正确恢复。简短卡片不要求铺满视口或出现滚动条。
  未保存选择保留原输入和URL；reduced-motion静态清楚可操作。
- [x] **TAC-6 已交付及安全：** Task52.1 的浏览位置、分页、详情及慢读时继续搜索输入
  保持；纯探索／导航零任务准入／配置发布／媒体 mutation。普通文件命令只由用户原入口
  明确提交一次，进度、独立结果及未知请求核对不因呈现更新丢失或重放。

## Required Tests

按[工作流测试分工](docs/development-workflow.md#6-test-levels)。下列命令是未来候选的
实施／验收计划，本轮Task激活没有执行产品测试。

**用户时间约束：** 每轮实施或 B 复核的测试耗时须小于该轮总耗时的50%。记录轮次总耗时
及测试占用时间，并行测试按占用时间区间并集计。先做代码／旅程核对，合并重复覆盖，
修复先跑已知失败与受影响用例；不以等待凑比例，不删必要门禁。若剩余必需门禁无法在
该约束内完成，交接时标记待验收项及原因，不能记为 PASS。

### Developer — affected tests

仓库根目录：`python3 scripts/check_governance.py`、`git diff --check`。

`web/` 内执行新改和直接受影响测试：

```sh
npm run typecheck
npm run test -- run src/shared/ui/AppShell.test.tsx src/shared/ui/modal-card.test.tsx src/shared/auth/AuthorizedReadBoundary.test.tsx src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx
npm run test:e2e -- tests/e2e/page-transition.spec.ts
npm run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/medialib-files.spec.ts --grep 'Task52[.]2|directory navigation, breadcrumb return, refresh and selection reset|library selection, lazy navigation, breadcrumbs, search and refresh|empty and recoverable failure states preserve the Files context|missing directory, stale cursor and unavailable Storage offer scoped recovery'
```

page-transition 的六个既有用例直接覆盖共享过渡、读取接入、弹卡、未保存退出及认证续转，
由 Developer 运行。两库只运行新增／修改用例及上列已有目录刷新／空态／失败恢复用例；
新增／修改的两库E2E标题含 `Task52.2`，其余实际受影响用例按完整标题追加到命令并记录
原因。不因本次呈现变化默认要求 Developer 整跑配置发布、整理准入或文件命令业务矩阵；
B 的对应回归范围仍按下文执行。

追加实际改动页对应的 `ExplorePage.test.tsx`、`StorageManagementPage.test.tsx`、
`RulesWorkspacePage.test.tsx`、`OperationsInventory.test.tsx`、`AutomationRouter.test.tsx`、
`NotificationRouter.test.tsx`、`ConfigurationPage.test.tsx`、`AutomationSettingsPage.test.tsx`
（均位于对应 feature），以及新增
反馈逻辑测试；不机械运行未受影响功能。覆盖成功／慢读、真实空、失败恢复、缓存快返、
迟到响应及未保存退出冲突；反馈逻辑测试验证可见行为，不照抄实现定时器数值。
对实际新改路径执行 `npx eslint <changed-TS/TSX-paths>` 和
`npx prettier --check <changed-web-paths>`，随后 `npm run build`。

复用现有 `operations-inventory.python.spec.ts` 增补其真实 Python API 支持页面的导航／
读取接入，`explore.python.spec.ts` 补探索切页读取，`direct-files.python.spec.ts` 补两库
刷新及一次普通操作后更新；新用例标题含 `Task52.2`，便于只跑新覆盖：

```sh
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep Task52.2
npm run test:e2e -- --config=playwright.python.explore.config.ts tests/e2e/explore.python.spec.ts --grep Task52.2
npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts --grep Task52.2
```

复用已有生产构建／Python API／临时SQLite与本地Provider、临时Storage夹具；各 harness
能力不同（Explore harness 无业务Active且 Storage spy 拒绝调用），不要在错误夹具上猜造
成功页。真实页面请求可用 Playwright route.fetch 后延迟响应，或返回对应现有失败；只对
用户操作确实发出的读取注入。九页成功内容／中间过程由 Node现有fixture全部覆盖，
Python组合覆盖真实读取接入；原生证据标明夹具身份，不把假API称真实Python。

若确需改已有 Python harness，补该文件的 ruff check／format --check 及其直接受影响测试，
不新增通用验收服务。Developer 交接受影响验证，不承担全量 Web／Python／发布矩阵。

### B — acceptance and regression

独立审完整 **Task Base..candidate**，先核对TAC用户旅程及关键问题，再跑门禁。
在同视口比较改前／改后，九页逐一观察快读／缓存／慢读到真实内容接入的中间过程；
使用既有trace／截图序列和实际交互，不把 opacity采样通过当体验通过。两库补慢刷新、
读取失败后恢复、快换目录迟到响应及普通操作后更新。身份错误／未保存退出、同页卡片
和52.1返回／输入竞态按实际入口复核。

`web/`：

```sh
npm run typecheck
npm run lint
npm run format:check
npm run test -- run
npm run build
npm run test:e2e -- tests/e2e/page-transition.spec.ts tests/e2e/deep-link.spec.ts tests/e2e/library-files.spec.ts tests/e2e/medialib-files.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep Task52.2
npm run test:e2e -- --config=playwright.python.explore.config.ts tests/e2e/explore.python.spec.ts
npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-settings.python.spec.ts
```

B52.2-02 修正会直接影响设置页的引擎读取区域，追加上述既有真实Python设置旅程；
Developer仍只跑新改／直接受影响用例，不接手B的完整验收。

全 Web 单元由 B 负责：共享 Shell、CSS 与读取反馈被九页及弹卡消费，是本 Task 的具体
共享影响依据。原生范围限共享导航／两库／探索／设置和新增Python接入用例，不扩成全部E2E。
根目录治理及 `git diff --check`；若改 Python harness，再跑其受影响检查。T3不要求
全Python、wheel、Docker或生产矩阵。记录精确候选、实际命令／结果／失败与证据；已有
403定位失败事实保留，不自动删除断言或当新阻塞，按该候选实际行为核对。

## Non-goals

不实施 RO-4 自动化旧打开／definition／editor退出；保留其现有入口及命令。
不重做九页业务、主题／设置或设计系统；不扩展API／Provider／Storage／schema／权限／
队列／恢复引擎，不修改公共Modal生命周期，不更改已接受Slice结果／延期，不修无关
基线定位问题或创造流程工具Task。Slice终审前的现行文档协调由对应所有者处理。

## Developer Completion Report

**READY FOR B REVIEW** — Task Base `4cf0efdf23981351ee3c7ef19d599726a070a4bb`
→ 实现候选 `e8a65644`(web 代码与测试);本报告随随后的 docs checkpoint 落盘。
工作区:分支 main,治理检查 PASS,预存脏文件 `mediaflow/.DS_Store` 及全部未跟踪
文件保留未动,暂存区仅含本 Task 文件。未推送、未发布。

### 变化(实现候选内 26 个文件)

- 新增 `web/src/shared/ui/read-reveal.ts`:共享延时呈现门 `useReadReveal`(默认
  400ms 只延后呈现,不延后请求/错误/授权/已就绪内容)+ `read-reveal.test.tsx`
  三个可见行为用例(快读不显示、慢读稳定显示并保持、结束即隐并重新武装)。
- 九页接入真实等待:Explore(首读骨架、已应用条件行、筛选选项状态行)、
  文件(库信息/目录两个首读面板)、媒体库(库列表首读面板、目录首读面板、系统状态
  未返回时不再假称“无 Active 配置”)、存储(LoadingPanel)、整理规则(保留 header、
  正文状态行)、自动化(两个 tab 各自的读取横幅)、任务中心(运行清单横幅)、
  通知、设置(整块替换横幅)——均只在各自读取真实变慢后才挂出等待态,错误分支
  不经过延时门(排除 isError)。另修整理记录面板:快读/缓存重读不再用瞬时行
  替换已示内容,慢速后台重读在内容尾部追加一条稳定状态行。
- 两库刷新:`new web/src/features/library/FilesRefreshState.tsx` — 固定高度预留行
  (`mf-files-refresh-slot`, min-height 20px)替代原来 `refreshing` 时直接插入的
  `正在刷新当前目录...` 段落;快刷不出现文字、不推挤列表,慢刷在预留位淡入一条
  `role="status"` 稳定反馈,结束时原位移除。两页的 `mf-content-settle` 保留。
- 主页面过渡:`AppShell.tsx` 新增 `mf-page-surface-entry-active` 窗口(entry 开始后
  320ms),窗口内抑制 `mf-content-settle` 叠加淡入(同页/晚到内容的 settle 不受影响);
  `styles.css` 入场起始透明度 0.2→0.5、200ms→260ms,settle 起始 0.55→0.7,新增
  等待态淡入 `mf-wait-reveal`。persistent ShellPageSurface、同页不重播、遮罩层
  `:has(...)` 立即满透明规则、reduced-motion 分支均保持。
- `LoadingPanel.tsx` 加 `mf-wait-reveal` 类;`RefreshControl.tsx` 快刷保持原文案、
  慢刷才切换到 refreshingLabel(disabled 不变)。
- 测试:`page-transition.spec.ts` 按 Task 要求移除固定 280ms 采样、“必须降低透明度”、
  “必须使用 mf-content-settle/动画名”类实现断言,改为:settle 轮询、九页各自
  等待文案归零(快读不闪)、采样窗口内 sidebar/topbar 几何不变、溢出≤1、
  叠加层不被过渡约束、缓存再进入无等待文案;慢读用例把
  `**/api/v1/storages*` 改为真实命中的 `**/api/v1/operations/storage-management/inventory*`
  (旧 glob 从未匹配,原“慢读”并未真正限流——本次已用 route 拦截计时验证)并延至
  1600ms。新增两库 `Task52.2` 刷新用例(Node 与 direct-files Python 各自验证
  快刷无闪烁、慢刷稳定反馈、列表 y 坐标零位移、逐 GET);direct-files 另含一次真实
  新建文件夹命令后刷新不重发 POST;explore.python 新增 `Task52.2` 快换页无等待态+
  慢目标页单一稳定状态;operations-inventory.python 新增 `Task52.2` 真实慢读交接
  (拦截计数断言证明限流生效)。

### 受影响测试实际结果(全部在 `web/`,仓库根治理 PASS、`git diff --check` 干净)

```text
python3 scripts/check_governance.py                         → PASS
npm run typecheck                                           → PASS(多次,含最终)
npx eslint <22 个改动 ts/tsx>                                → PASS(0 问题)
npx prettier --check <改动 web 路径>                          → PASS(先 --write 修 2 处后复核)
npm run test -- run <13 个受影响/新增单测文件>                 → 13 files / 341 tests passed(35s)
npm run build                                                → PASS
npm run test:e2e -- tests/e2e/page-transition.spec.ts         → 6 passed(14.7s,终版)
npm run test:e2e -- library-files+medialib-files --grep
  'Task52[.]2|directory navigation…|library selection…|empty…|missing…' → 6 passed(7.1s)
npm run test:e2e -- --config=playwright.python.config.ts
  operations-inventory.python.spec.ts --grep Task52.2         → 1 passed(3.8s)
npm run test:e2e -- --config=playwright.python.explore.config.ts
  explore.python.spec.ts --grep Task52.2                      → 1 passed(2.8s)
npm run test:e2e -- --config=playwright.direct-files.python.config.ts
  direct-files.python.spec.ts --grep Task52.2                 → 1 passed(5.2s)
```

调试期失败均定位到真实原因并已修复:初次 page-transition 慢读用例失败=路由 glob
从未命中真实库存路径;两库新用例首轮失败=根目录无查询串致正则不命中(已改为
`files(?:\?|$)`);explore 新用例首轮失败=断言串用三 ASCII 点而组件渲染 U+2026
(已按真实字符修正,并保留调试期证明行在 DOM 的证据);operations 用例首轮“通过
但 1.3s”=过早 unroute 提前释放了被拦截请求(已改为响应回来后再 unroute,并加
拦截计数断言)。修复仅调整本 Task 自己的新用例,未删除既有断言。

**时间约束:** 本轮总耗时约 50 分钟;全部测试执行累计约 8 分钟(各命令实测时间戳
相加,含 2 次 typecheck、单测、build、5 组 E2E,并行区间按并集)≈ 16%,低于 30% 上限。

### 剩余风险与待 B

- B 的全量 Web 单测/lint/format/完整 E2E/Python 回归及 TAC 逐页人工对比未执行
  (按分工归 B);改前/改后同视口过程比较需 B 在真实夹具中进行。
- 403 文案定位失败的既有事实保留(未触碰相关断言);本 Task 未宣称旧 E2E 全绿。
- 延时门为呈现参数(400ms)/过渡参数(0.5、260ms、0.7、320ms),TAC 要求按过程
  而非数值判定;若 B 在真实视口发现过慢/过快,应在同一 Task 内给 FIX 单点调节。
- 未跑:全量 `npm run test -- run`、全仓 eslint/format、未列出的 Python/发布矩阵
  (均属 B 范围);未改后端/权限/schema/任务引擎/公共 Modal。
- 会话内未读取运行数据库、私密配置或用户媒体;临时 fixture 均为既有 harness。

## B Review Result

```text
Reviewed Task Base: 4cf0efdf23981351ee3c7ef19d599726a070a4bb
Implementation candidate: 35fec54ccd412d061f75ff22075fbe3472829ea8
Report successor inspected: b717a11592b2fe9f22f4a1b51945d1e25cfc0b94 (TASK.md only)
Decision: PASS
B52.2-01 / B52.2-02: VERIFIED FIXED
Task blockers: NONE
Slice Required Outcomes / Surfaces all satisfied: NO
Next: NEXT TASK — RO-4 remains; not planned in this review
```

2026-11-08 独立 B 核对完整原始Base..candidate的26个文件，包括初始实现及全部修正；
本轮逐项审查新增高度交接、测试和重排后的分支，确认Save／权限／Active／采用读回／
未知提交核对逻辑未变，T3保持。起点main / b717a115；候选后继只改TASK报告，预存
mediaflow/.DS_Store及全部未跟踪材料保留，本轮只提交Task文档。
原始FIX REQUIRED、部分修正及全部实际失败仍在
[f622f615固定报告](https://github.com/kentinya/mediaflow/blob/f622f615/TASK.md#b-review-result)
及此前报告中；本次未改写为旧候选已通过。

### 可见结果与TAC

- **TAC-1/2：** 桌面1536×1024和390×844，九个真实侧栏入口分别观察实际慢读取到就绪，
  并与原Task Base同视口材料对照；快读／缓存返回由导航原生回归及局部逐帧探针覆盖。
  页头／导航稳定，内容归属正确，读取未冒充空态，必要等待可辨。快响应无需强制播放
  占位，真实内容接入较原基线协调；正常目标布局／高度变化、稳定占位替换可接受。
- **B52.2-01：** 原样复跑三页entry-probe，存储／文件／媒体库均无正文二次变淡，
  contentOpacityDrops=[]、Shell结束后正文最低透明度1；不以透明度数字代替画面验收。
- **B52.2-02：** 原样位置探针在桌面／390px的正常、180ms、900ms读取共6条旅程中，
  快读均无等待提示闪现，慢读提示持续到就绪；下方阅读块的位移分摊到连续帧，原来
  单帧整跳的接入已变为平顺滑动。人审同一段中间画面及最终画面，无突然挤走／内容
  叠盖／再变淡。允许阅读块随实际表单高度自然移动，不要求坐标不变或固定像素高度。
  reduced-motion另测390px快／慢读取：静态就绪、反馈清楚，未残留隐藏／裁切。
- **TAC-3：** 两库冷读／缓存返回、快／慢手动刷新与真实普通命令后更新通过本候选
  原生回归。刷新提示不再瞬时插行挤列表，慢刷新反馈仍可访问，同条件成功内容保留；
  真实空态、路径／权限／失败恢复、跨库／路径独立响应保持。
- **TAC-4/5：** 九页正常／快切、前后退、认证续转，同页筛选／标签／目录／刷新及
  弹卡开关不重播整页入场；未保存选择、任务／存储卡层级、背景与焦点返回通过。
  新高度交接仅作用设置读取区域，普通重渲染不重播，卸载取消，未重挂载业务子树。
- **TAC-6：** 当前真实Python探索回归保持52.1分页／搜索退出／缓存淘汰恢复、慢读
  不抢输入、详情滚动与焦点。纯导航／探索无命令提交；两库命令后刷新不重发POST，
  独立结果、未知提交核对与精确Save／冲突／采用读回保持。后端、schema、权限及媒体
  引擎未改，不将本Task接受扩成生产发布或核心容量引擎的重新验收。

### 本轮B门禁及可复核材料

材料在本机 `.git/validation-evidence/35fec54c/b52-2-review/`；不承诺随Git同步。
全部为候选生产构建、本地假API／Provider、临时SQLite／Storage，没有用户运行数据或
真实外部服务。每组Playwright使用独立--output，端口相同的设置／Base对照／两库顺序运行。
命令、起止时间和退出码见各*-run.json；以下为本轮B自己执行，非复用Developer标签。

- web/ `npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run build`：
  PASS；static-runs.json及各日志，原大chunk提示保留。
- web/ `npm run test -- run`：**96 files / 1451 tests passed (133.93s)**；unit.log，
  保留jsdom scrollTo提示。
- web/ `npm run test:e2e -- tests/e2e/page-transition.spec.ts tests/e2e/deep-link.spec.ts tests/e2e/library-files.spec.ts tests/e2e/medialib-files.spec.ts --output <独立目录>`：
  **87 passed / 1 failed (1.4m)**；navigation-files.log。
- web/ `npm run test:e2e -- --config=playwright.python.explore.config.ts tests/e2e/explore.python.spec.ts --output <独立目录>`：
  **18 passed (21.9s)**；python-explore.log。
- web/ `npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts --output <独立目录>`：
  **28 passed (55.3s)**；python-files.log。
- web/ `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep Task52.2 --output <独立目录>`：
  **1 passed**（命令4.81s）；python-operations.log。
- web/ `npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-settings.python.spec.ts --output <独立目录>`：
  **12 passed / 3 failed (45.2s)**；python-settings.log。12条完整设置读取、Save、并发
  冲突、非法输入、真实采用、重启历史及未知提交核对旅程通过；3条失败归属见下文。
- 根目录entry-probe、settings-position-probe、settings-reduced-probe、403-probe
  原生脚本／JSON／日志与截图；nine-page/和base-nine-page/各18条完整旅程，保存
  原始逐帧数据及同视口等待／就绪图，contact-*.png仅供并排核对，不代替过程证据。
- `git archive`导出原Task Base到base-source/，复用相同依赖独立构建；Base源码、
  生产资产、Python/Node夹具均由该归档读取。Base..candidate的Python、原设置Python
  spec、包依赖均未变化，未访问或修改用户配置／媒体。
- 根目录治理检查及完整Base..candidate、报告文档的 `git diff --check`通过。
  本Task仍为T3，未运行全Python／wheel／Docker／发布矩阵，不宣称这些门禁完成。

### 已独立确认的非阻塞基线测试问题

1. **403单句定位：** 在原Task Base独立运行deep-link的同一403用例，仍因一句提示
   匹配2个元素而strict失败（base-403.log）。B又在候选与Base走完整入口：连接无READ
   身份→看到403且无401／身份仍保留→通过现有链接返回→明确断开／换有READ身份→
   回到探索，全部通过且零命令，见403-probe.json/log。保留原测试失败，没有删断言。
2. **3条旧容量集成脚本：** B在原Task Base独立运行同三条设置用例（base-settings.log），
   与候选同样停在Files的 `getByLabel("目录")`：脚本期望的旧入口在Base就不存在，
   尚未走到后续整理容量断言。该失败不是本Task的设置读取呈现引入；现有Files的库／
   文件夹／面包屑旅程由两库当前原生回归覆盖。作为既有测试维护及证据限制保留，未
   删除／跳过／修改断言，不要求Developer在本Task顺手修复；本次不声称那三条旧容量
   整理集成链已获得新证明。设置侧实际受影响行为由上述12条完整原生及1451单测覆盖。

这4项失败均保留真实退出状态，未称全套E2E绿色；当前Task的可见结果与受影响权限／
命令生命周期已独立验证，无本Task P0/P1。此结论只接受Task52.2范围。

### 全Slice重评与停止边界

RO-1／RO-2：Task52.1既有PASS保持，本轮探索回归无回归。RO-3：Task52.2完成。
RO-4：自动化列表旧“打开”及definition／editor链路仍在，退出尚未交付。
因此Task52.2 PASS，Slice52仍ACTIVE；选择NEXT TASK但本轮不规划新Task，不交Closure
Packet、不宣告Slice关闭。Slice／Roadmap／Progress及CURRENT/TARGET协调留给对应所有者。
验证时间按并行区间并集计，约3.4分钟，低于本轮总时长50%；review-timing.json记录实际
起止和基线／原生／静态／重跑区间，没有以等待凑比例。

## Developer fix completion report — B52.2-01

**READY FOR B REVIEW(修正轮)** — Task Base `4cf0efdf23981351ee3c7ef19d599726a070a4bb`
(保持不变)→ 实现 checkpoint `3178f1bfdf32b4fd29f0a1f492a75b8dfc9d03d3`(web 代码与
测试,2 个文件),本报告为其后的 docs checkpoint。工作区:分支 main,治理检查 PASS,
预存跟踪变更 `mediaflow/.DS_Store` 与全部未跟踪文件保留未动,暂存区只含本 Task 文件;
未推送、未发布、未读取运行数据库/私密配置/用户媒体。

### 根因与修正(真实源码身份)

- **根因确认(B 命中)**:`styles.css` 中 `mf-content-settle` 是 CSS animation
  (`animation: ... both`),entry 窗口用 `.mf-page-surface-entry-active
  .mf-content-settle { animation: none }` 抑制;窗口 320ms 结束移除类时,已显示正文的
  animation-name 由 none 重新应用,浏览器对仍在 DOM 的元素从 0.7 起补播一次
  ——“跳过叠加淡入”变成“稍后补播淡入”。
- **修正(commit `3178f1bf`,`web/src/shared/ui/styles.css`)**:正文揭示改为
  `transition: opacity`(170ms)+ `@starting-style { opacity: 0.7 }`,即只在元素
  **首次渲染**时从 0.7 平顺接入一次;transition 只有元素自身 opacity 实际变化才启动,
  因此 entry 窗口结束、卡片层出现/关闭、reduced-motion 等祖先类变化仅启停 transition
  属性而不改变 computed opacity——已显示内容永不补播,晚到读取仍按自身时序平顺接入。
  抑制规则、`:has(卡)` 同帧规则与 reduced-motion 分支同步改为 `transition: none`,
  删除 `@keyframes mf-content-settle` 并更新注释。B 指导的「区分已呈现/晚到读取」
  由首次渲染语义天然实现,未延长窗口、未推迟任何请求/错误/授权/已就绪内容。
- **未改动**:entry 窗口时序(320ms)、`AppShell.tsx`、`LoadingPanel`、
  `RefreshControl`、两库刷新预留行、九页读取接入代码、Router/AuthBoundary/Query/
  Modal 生命周期、后端与权限;弹卡覆盖、同页不重播、未保存退出与 reduced-motion
  既有规则保持。

### 覆盖(新增/修改测试,均在真实现有入口上)

- `web/tests/e2e/page-transition.spec.ts`:采样器增记正文透明度 `content` 与
  `entryActive`,采样窗口参数化并新增 `waitForSamplerWindowEnd`(必须采样到 entry
  窗口结束之后,不以首次满透明或等待文案消失为终点);新增用例
  “sidebar handoff keeps the storage and both library bodies steady through fast,
  cached and slow reads”:沿真实侧栏完成 存储/文件/媒体库 三页的
  **首次快读 → 经探索返回的缓存读(3 段)→ reload 断会话缓存后的慢读(3 段)**,
  慢读仅对这三页实际发出的 inventory / resource-libraries files / media-libraries
  files 读取经现有 `page.route` 延迟 1500ms。判据全部为可见行为:正文一旦满透明任何
  后续帧不得回落、慢读正文首帧 >700ms(证明限速真实生效)、快读/缓存后该页等待文案
  为 0、窗口内确有 entry 窗口帧参与。
- 既有 6 个用例(共享过渡/慢读占位/弹卡/未保存退出/认证续转与 reduced-motion)
  未删除、未弱化断言。

### 测试有效性与实际结果(全部实测)

- **可达性核验(防把验收结论建立在不可达断言上)**:临时将 `styles.css` 恢复到候选
  `e8a65644` 版本重建后,新用例在首段快读即失败:
  `expect(received).toBeGreaterThanOrEqual(expected)  Expected: >= 0.999  Received: 0.7`
  (正是 B52.2-01 的正文再次变淡),随后恢复修复版重建;证明该断言能捕获此缺陷。
- **B 复现脚本复跑**:将 `.git/validation-evidence/e8a65644/b52-2-review/entry-probe.mjs`
  原样复制到 `.git/validation-evidence/b52.2-01-fix/`(仅随脚本目录改变输出位置),
  自建 `FAKE_PORT=4192` Node fake-server + 修复后构建:存储/文件/媒体库三页
  `contentOpacityDrops: []`、`settledShellMinimumContent: 1`(证据在本机 .git 目录,
  不承诺远程可访问)。
- 仓库根:`python3 scripts/check_governance.py` → PASS;`git diff --check` → 干净。
- `web/` 改动文件门禁:`npm run typecheck` → PASS;
  `npx eslint tests/e2e/page-transition.spec.ts` → PASS;
  `npx prettier --check tests/e2e/page-transition.spec.ts src/shared/ui/styles.css` → PASS。
- `npm run build` → PASS(保留原大 chunk 警告;全部 E2E 跑在最终构建产物上)。
- 单测:`npx vitest run`(AppShell、read-reveal、modal-card、AuthorizedReadBoundary、
  StorageFilesPage、MediaLibraryFilesPage 6 文件)→ **6 files / 115 tests passed
  (11.4s)**。
- `npm run test:e2e -- tests/e2e/page-transition.spec.ts` → **7 passed**(修复后首跑
  35.1s,最终构建复跑 35.5s,含新增回归用例 20.5s/20.6s)。
- `npm run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/medialib-files.spec.ts --grep 'Task52[.]2|directory navigation, breadcrumb return, refresh and selection reset|library selection, lazy navigation, breadcrumbs, search and refresh|empty and recoverable failure states preserve the Files context|missing directory, stale cursor and unavailable Storage offer scoped recovery'` → **6 passed (6.6s)**。
- 调试期失败:无(新用例首轮即绿;唯一失败为上述旧 CSS 可达性核验的预期失败)。
- **时间约束**:本轮 14:16:21 开始、14:33 完成交接,总耗时约 17 分钟;上述全部
  测试/构建/静态检查命令累计执行约 2.4 分钟 ≈ 14%,低于 30% 上限(未以等待凑时间)。

### 剩余风险与待 B

- B 分工的全量门禁本轮未执行:全 Web 单测 `run`、全仓 lint/format、其余 E2E、
  Python harness 用例(`operations-inventory/explore/direct-files .python.spec`)、
  TAC 九页同视口改前/改后人工比较;本修正未触及 Python 相关入口,Python 用例由 B 按
  原验收计划执行。既有 403 文案定位失败事实保留,本轮未触碰相关断言。
- `@starting-style` 需较新浏览器(Chromium≥117、Safari≥17.5、Firefox≥129);更旧
  浏览器上慢读内容直接以满透明出现(无一次性揭示),无功能影响。Playwright Chromium
  与 B 探针均已验证;若 B 判定需兼容旧浏览器,可在同 Task 改为挂载期 JS 状态判定方案,
  请给单点 FIX 指示。
- 呈现参数(settle 170ms/0.7、entry 窗口 320ms、读后延时 400ms)与 B 复核时一致;
  TAC 按完整过程而非数值判定,若 B 在真实视口发现节奏问题,请在同 Task 给单点调节。
  卡同帧抑制语义由 animation 迁移为 transition(同样只在首次渲染揭示),弹卡遮罩/
  滚动/焦点恢复旧行为未改,请在弹卡用例中复核。

## Developer fix completion report — B52.2-02

**READY FOR B REVIEW(修正轮 2)** — Task Base
`4cf0efdf23981351ee3c7ef19d599726a070a4bb`(保持不变)→ 实现 checkpoint
`36ac50a5`(web 源码与测试,3 个文件),本报告为其后的 docs checkpoint。
工作区:分支 main,治理检查 PASS,预存跟踪变更 `mediaflow/.DS_Store` 与全部
未跟踪文件保留未动,暂存区只含本 Task 文件;未推送、未发布,未读取运行数据库、
私密配置或用户媒体,夹具均为既有 Node fake-server 与本地 stub。

### 根因与修正(真实源码身份)

- **根因确认(B 命中)**:`web/src/features/operations/AutomationSettingsPanel.tsx`
  的引擎读取(`GET /api/v1/operations/automation/settings`)在
  `AuthorizedReadBoundary` 内直接按 `query.isPending` 输出
  StatusBanner「正在读取引擎设置」,未接入本 Task 的延时呈现门;父级
  `ConfigurationPage.tsx` 只门控了自己的配置状态等待,子读取在其返回后立即
  开始——快读时提示块闪出又随时被表单替换(桌面/390px 均可见),下方
  「整理规则就绪状态」随之两次位移。
- **修正(commit `36ac50a5`)**:
  - `AutomationSettingsPanel.tsx` 新增
    `useReadReveal(query.data === undefined && !query.isError)` 门:快读/缓存
    返回期间该分支渲染 `null`,读取确有等待(越过共享揭示窗口)才挂出原有
    StatusBanner 文案;错误与共享鉴权边界不经门。请求、启用条件、查询键、
    5s 采用情况回读、Save/权限/Active 发布、采用读回与未知提交核对语义一律未改。
  - 就绪表单 `div.mf-automation-settings` 与无 Active 的 `section.mf-panel` 加入
    既有 `mf-content-settle`(首次渲染 0.7→1、170ms 一次性揭示),内容接管
    等待区时平顺接入一次;entry 窗口抑制、弹卡 `:has(...)` 同帧规则与
    reduced-motion 分支原样作用于它,B52.2-01「已显示内容永不补播」语义不变。
- **未改动**:`ConfigurationPage.tsx`、`LoadingPanel.tsx`、`RefreshControl.tsx`、
  `read-reveal.ts`、`styles.css`、九页其余读取接入、两库刷新预留行、Router/
  AuthBoundary/Query/公共 Modal、后端/权限/schema/任务引擎。

### 覆盖(新增测试,均在真实现有入口上,未构造产品外入口)

- `src/features/operations/AutomationSettingsPage.test.tsx`(新增
  `heldSettingsRead` 夹具:只持有该页真实发出的引擎 GET,其余 URL 按既有
  `recordingFetch` 固定应答)+ describe「engine settings read handoff on System
  Settings (Slice52 RO-3)」三用例,全部从真实 `/ui-v2/configuration` 进入:
  ① 快读——配置状态已返回、引擎读取仍进行时提示行从未上屏,放行后表单直接
  接管、全程零写入;② 慢读——越过窗口后出现且持续一条稳定提示,就绪后表单
  接管、提示不再出现;③ 失败——既有「引擎设置暂不可用/请刷新」原样及时出现,
  不经过等待行,零写入。
- `tests/e2e/page-transition.spec.ts`:新增 `SettingsFrame` 帧探针(逐 rAF 记录
  提示行/表单/配置状态/失败文案四个可见量)与三用例——
  快读+经探索返回的缓存重进全程 0 帧提示且状态先于表单;
  慢读仅对该页真实 GET 经现有 `page.route` 延迟(1500ms)后,呈现「状态先到 →
  一段首尾相连无缺口的提示帧 → 表单接管(无同帧叠加、无二次闪现)」;
  500 失败走既有恢复文案且零命令。`WAITING_READ_MARKERS` 增补 `引擎设置`,
  快读断言集扩展到该页。既有 7 个用例的断言未删除、未弱化。

### 可达性核验(防把结论建立在抓不住缺陷的断言上)

临时仅移除呈现门(其余改动保留)重建后:快读单测失败
(`expect(screen.queryByText("正在读取引擎设置")).toBeNull()` 收到元素)、E2E
`settings handoff…` 与 `a slow engine read…` 同时失败;恢复修正版重建后,3 个新
E2E 与 3 个新单测全部通过。新断言能捕获 B52.2-02,已证。

### 受影响测试实际结果(全部实测)

```text
python3 scripts/check_governance.py              → PASS(实现前后各一次)
git diff --check                                 → 干净
npm run typecheck                                → PASS(6s)
npx eslint <3 个改动 ts/tsx>                      → PASS(修 1 处 prefer-const 后)
npx prettier --check <3 个改动路径>                → PASS(先 --write 后复核)
npm run test -- run src/features/configuration/ConfigurationPage.test.tsx
  src/features/operations/AutomationSettingsPage.test.tsx
  src/shared/ui/read-reveal.test.tsx
  src/shared/auth/AuthorizedReadBoundary.test.tsx → 4 files / 62 tests passed(41.98s)
npx vitest run src/features/operations/
  AutomationSettingsPage.test.tsx -t "Slice52 RO-3" → 3 passed(1.91s,新用例确已执行)
npm run build                                    → PASS(产物 grep 到
  `mf-automation-settings mf-content-settle`,证明改动入包)
npm run test:e2e -- tests/e2e/page-transition.spec.ts → 10 passed(39.1s;
  既有 6 + B52.2-01 修正轮 1 + 本轮 3)
可达性互换(临时去门重建)          → 快读单测 1 failed、快读/慢读 E2E 2 failed(预期)
恢复重建后重跑 3 个新 E2E          → 3 passed(4.1s)
```

调试期失败仅两类且非用例逻辑:eslint `prefer-const` 一处(当轮修正)、误用不存在
的 vitest `--reporter=basic` 参数(改用默认报表重跑);最终形态全部用例首轮即绿。
失败路径测试在可达性互换下仍通过属预期:它记录的是既有恢复分支,非闪现判别器。

**时间约束:** 计时窗口 15:01:22 → 交接约 15 分钟(此前为文档与代码阅读,未运行
测试);全部测试/构建/静态检查命令累计约 2.5 分钟(含报表参数报错与可达性互换的
两轮运行)≈ 16%,低于 30% 上限。

### 剩余风险与待 B

- 未执行 B 分工的全量门禁:全 Web 单测 `run`、全仓 lint/format、page-transition
  之外的 E2E、`automation-settings.python.spec.ts` 等 Python harness(面板改动
  直接影响该设置旅程,本轮未新增 Python 用例,既有回归由 B 按原验收计划执行)、
  TAC 设置页桌面/390px 同视口改前改后人工比较。
- 本轮未改 CSS 与共享组件,呈现参数仍为 400ms/settle 0.7·170ms/entry 窗口 320ms/
  入场 0.5·260ms;B 若在真实视口发现设置页节奏问题,请在同 Task 给单点 FIX 指示。
- 快读单测与 E2E 的“提示从未上屏”依赖观察落在共享揭示窗口内(与其余页面同一
  机制);极慢 CI 停顿理论上可误报,本轮各次运行均未出现。
- 既有 403 文案定位失败事实保留;本 Task 未宣称旧 E2E 全绿;Slice52 仍 ACTIVE,
  RO-4 仍留待后续授权规划,本轮不改 Slice/Roadmap/Progress/合同。

## Developer fix completion report — B52.2-02(修正轮 3,接入推挤)

**READY FOR B REVIEW(修正轮 3)** — Task Base `4cf0efdf23981351ee3c7ef19d599726a070a4bb`
(保持不变)→ 实现 checkpoint `35fec54c`(web 源码与测试,3 个文件),本报告为其后的
docs checkpoint。工作区:分支 main,治理检查 PASS(实现前后各一次),预存跟踪变更
`mediaflow/.DS_Store` 与全部未跟踪文件保留未动,暂存区只含本 Task 文件;未推送、
未发布、未读取运行数据库/私密配置/用户媒体,夹具均为既有 Node fake-server 与本地
Python stub。本轮只处理 B 判定的同一 P1:“引擎等待区域 → 就绪表单 → 下方规则就绪
内容”的接入推挤,不改其他页、不动 52.1 已交付结果。

### 根因与修正(真实源码身份)

- **根因确认(B 命中)**:`ConfigurationPage.tsx` 的 `RuleReadinessPanel` 随配置状态
  立即渲染,位于引擎区域**之后**的正常文档流中;`AutomationSettingsPanel.tsx` 的读取
  有多个会改变该区域高度的视觉阶段(首次 0 高度 → 400ms 后等待横幅 → 表单,以及
  无发布/读取失败分支),每次阶段变化都把已显示的阅读块在**单帧**内推走。
  `mf-content-settle` 只过渡 opacity,不协调任何空间——B 的 frame 探针正是这个机制。
- **修正(commit `35fec54c`,语义变更 `AutomationSettingsPanel.tsx` +125/−6;
  其余 diff 为 children 块因新增一层包裹的 prettier 重排,无逻辑变化)**:
  - 新增 `useReadStageHandoff(stage)`:把面板(含 `AuthorizedReadBoundary` 的全部
    分支)包进 `div.mf-engine-read-region`;按读取视觉阶段
    (`reading` / `reading-with-wait` / `engine-ready` / `no-published-settings` /
    `engine-unreadable` / `read-failed`)在无依赖 `useLayoutEffect` 中记录真实渲染
    高度,**仅在阶段本身变化且高度不同且非 reduced-motion** 时,用一次 Web Animations
    (常量 `ENGINE_HANDOFF_MS = 300`,ease-out)把旧高度插值到新高度;插值期间仅临时
    `overflow: hidden`,结束后即释放。普通重渲染只重记高度、不打断进行中的交接;
    下一阶段从当前在屏高度起算;卸载时取消动画。
  - 效果:引擎区域上方接入新阶段时,下方“整理规则就绪状态”阅读块从一次单帧跳变
    (实测 703px/581px)变为**分摊多帧的平顺滑动**,全程保持可见;这正是 B 允许的
    “平顺变化”,且不规定固定像素高度或骨架。
  - **不延后任何东西**:请求、启用条件、400ms 呈现门(快读仍 0 帧提示)、错误直达、
    授权分支、已就绪内容、Save/Active/采用读回/未知提交核对语义、查询键与 5s 回读
    一律未改;高度差 <1px(re jsdom 零布局)直接跳过,不调用 animate。
- **未改动**:`ConfigurationPage.tsx`、`LoadingPanel.tsx`、`RefreshControl.tsx`、
  `read-reveal.ts`、`styles.css`、`AppShell.tsx`、两库刷新预留行、九页其余读取接入、
  Router/AuthBoundary/Query/公共 Modal、后端/权限/schema/任务引擎。

### 覆盖(新增测试,均在真实现有侧栏入口上)

- `web/tests/e2e/page-transition.spec.ts`:`SettingsFrame` 探针增记
  `readiness`(该阅读块是否渲染)与 `readinessTop`(逐 rAF 文档绝对 top);新增共享
  断言 `expectReadinessKeptThroughHandoff`:①工作区状态出现的首帧该块即在屏;
  ②其后任何帧不得消失;③位置变化必须分摊——**单帧位移 ≤ 总位移的 50%**(允许
  平顺滑动,拒绝一帧整跳,不是“所有帧坐标相等”的过强断言)。接入三处既有用例:
  快读用例(桌面 + 缓存重进 + **新增 390×844 同侧栏入口**)、慢读用例(覆盖等待
  横幅出现与表单接管两次交接全程)、失败恢复用例(错误分支接入同样不推挤)。
  快读 0 帧横幅、慢读单段无缝横幅、失败文案、零写入等既有断言未删未弱化。
- `src/features/operations/AutomationSettingsPage.test.tsx`:快读、慢读两用例补
  “下方就绪块在读取等候期间与表单接管后始终在屏”的真实 `/ui-v2/configuration`
  入口断言(jsdom 无布局,位移分帧由上列 E2E 承担)。

### 可达性核验(防把结论建立在抓不住缺陷的断言上)

**先写测试、在改前(工作区原样)构建上运行**:三用例中 2 failed、1 passed——
快读用例 `biggestStep 703 > 351.5`(单帧整跳 = 总位移,正是 B 的 442.5→1146.2)、
慢读用例 `biggestStep 581 > 351.5`;失败恢复用例通过(其错误横幅较矮,未越过阈值,
如实记录——它是恢复路径的断言,不是本次推挤的判别器)。修正后同一套断言全部通过。
即:新断言在真实入口上能抓住 B 报告的突然挤走,且不依赖固定时长或 CSS 值。

### 受影响测试实际结果(全部实测)

```text
python3 scripts/check_governance.py                → PASS(实现前后各一次)
git diff --check                                    → 干净
npx prettier --check <3 个改动路径>                  → PASS
npx eslint <3 个改动 ts/tsx>                         → PASS
npm run typecheck                                   → PASS
npm run build                                       → PASS(3 次:改前基线、
  移除修正的隔离复现、终版;全部 E2E 均跑在终版产物)
npm run test -- run AppShell/modal-card/read-reveal/
  AuthorizedReadBoundary/ConfigurationPage/
  AutomationSettingsPage/StorageFilesPage/
  MediaLibraryFilesPage 8 个受影响单测文件            → 8 files / 166 tests passed(49.5s)
npm run test:e2e -- tests/e2e/page-transition.spec.ts
                                                    → 终版 10 passed(38.8s;
  既有 6 + B52.2-01 修正 1 + 设置 3,设置 3 含本轮新断言与 390px 段)
可达性互换(改前产物,先跑)                  → 快读/慢读 2 failed(703/581 单帧),
  失败恢复 1 passed,如实记录
npm run test:e2e -- --config=playwright.python.automation.config.ts
  tests/e2e/automation-settings.python.spec.ts      → 12 passed / 3 failed(43.7s)
```

关于 Python 设置旅程 3 个失败(`system runtime settings publish 1025…` /
`share one organizing allowance…` / `keep an old summary…`,均超时在
`organizeOneFileThroughFiles` 的 Files `目录` 字段):**在同一工作区移除本修正、
重建后原样复现同样 3 个失败**(用例名单一致),且失败点在 Files 批量整理侧、
改动仅限设置面板呈现——判定为本环境既有失败,不在本 Task 掩盖、删除或顺手修复,
交 B 按验收计划定归属。调试期无其他失败;未删减任何既有断言。

### 时间约束

本轮起点(首个 git/治理/文档阅读命令)未取时间戳,按对话顺序估计约 15:26,
其间无任何测试执行;首个实测时间戳 15:32:43 至交接完成(15:47:22)为 14.7 分钟。
上述全部测试/构建/静态检查命令累计执行约 4.3 分钟(各命令首尾时间戳相加,含改前
基线、隔离复现实验与终版复跑)。按含阅读期的轮次总时长(约 21–22 分钟)计 ≈ 20%;
即便只按 15:32:43 起的可考实施窗口(14.7 分钟)计 ≈ 29%。两种口径均低于 30% 上限,
未以等待凑时间。

### 剩余风险与待 B

- 交接呈现参数:滑动 300ms ease-out、等待门 400ms、settle 0.7·170ms、entry 窗口
  320ms、入场 0.5·260ms。TAC 按完整过程判定;若 B 在真实视口(390px 下单次位移
  约 1275px)认为节奏不当,请同 Task 给单点 FIX 指示。
- 已知边界:采用详情 `<details>` 原生展开不产生 React 提交;若在展开期间恰好发生
  读取阶段变化,起算高度可能差一个详情块高度(单次小位移),现实路径罕见,记录备查。
- reduced-motion 下无插值、阶段直接落位,与既有静态语义一致。
- 本轮未跑:B 分工的全量 Web 单测 `run`、全仓 lint/format、page-transition 之外的
  E2E(`automation-settings.python.spec.ts` 已实跑并见上,含 3 个既有失败)、
  TAC 九页桌面/390px 同视口改前改后人工比较;两库与探索本轮无代码变更,未重跑。
- 既有 403 文案定位失败事实保留;本 Task 未宣称旧 E2E 全绿;Slice52 仍 ACTIVE,
  RO-4 仍留待后续授权规划,本轮不改 Slice/Roadmap/Progress/合同。
