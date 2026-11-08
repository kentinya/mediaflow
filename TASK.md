# NO ACTIVE IMPLEMENTATION TASK

下方是 **Task52.2 规划草案（PLANNED；尚未授权实施）**。本轮用户要求 B 基于真实代码
规划和复核；本计划不自行启动 Developer，不授权推送、发布或部署。用户明确要求实施后，
移除此声明，沿用同一 Task ID/Base/Goal/Scope 进入实施。

Task52.1 已由独立 B 复核 **PASS**，原始 Base
`c7913f6a751ee980db2b82ffaefec40d3d43528c` → 已审实现
`62a158f684996372b08b7a570368ffcf1b4cb194`；完整计划、返工、实际结果与限制见
[固定复核报告](https://github.com/kentinya/mediaflow/blob/4cf0efdf23981351ee3c7ef19d599726a070a4bb/TASK.md#b-review-result)。
报告后继只有 TASK.md 变化，不改变执行输入。本次规划不重新签署该实现的验收。
其导航 E2E 中 403 文案定位失败、在原 Base 的同样复现及补充原生行为通过事实保留，
不宣称所有旧 E2E 全绿。

全 Slice 重评：RO-1 探索布局／完整详情和 RO-2 有界浏览／准确返回已由 Task52.1 完成；
RO-3 九页切换／实际读取接入及两库刷新尚未交付，由本计划覆盖；RO-4 自动化旧打开链路
尚未交付，留待后续授权规划。Slice52 仍 ACTIVE，未达到交 A 终审的条件。
Slice/Roadmap/Progress 中旧“首次规划”措辞的事实协调留给其所有者，本轮不改变合同。

# Task52.2 — 九个主页面切换、读取接入与两库刷新体验

Authority: committed [Slice52 Contract](SLICE.md) at
`c7913f6a751ee980db2b82ffaefec40d3d43528c`；生命周期及测试分工遵循
[Development Workflow](docs/development-workflow.md)。实施者阅读
[Developer experience](docs/agent-experience/developer-implementation-role.md)，审查者阅读
[B experience](docs/agent-experience/task-planner-reviewer.md)。

```text
Task ID: 52.2
Task Type: SLICE
Parent Slice: 52
Status: PLANNED
Task Base: 4cf0efdf23981351ee3c7ef19d599726a070a4bb
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B / independent B review of Developer checkpoint
Implementation Authorization: NOT YET AUTHORIZED
```

## Planning checkpoint and workspace

本轮规划起点：`/Users/songzhidong/mediaflow`，分支 `main`，HEAD即上述Task Base；
治理检查PASS，TASK.md与Git可写，暂存区为空。预存跟踪变更 `mediaflow/.DS_Store`；
未跟踪 `.DS_Store`、`.explore_adapter_block.py`、`.mgmt.log`、`.t*.log`、`15`、
`docs/`／`docs/pics/`／`output/`／`testdata/`／`web/`元数据及 `output/` 下既有调查／
预览材料均保留。本轮只维护并checkpoint根TASK.md，不读取运行数据库、私有配置或用户媒体。

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
| 设置 `/configuration` | `ConfigurationPage` / fetchConfigurationStatus；状态就绪后显示现有配置工作区 |

## Implementation Scope and Developer guidance

代码范围为上述九页**必要的读取呈现**、`AppShell.tsx`、`LoadingPanel.tsx`、
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

- [ ] **TAC-1 九页完整过程：** 上表九页在桌面和390px实际侧栏切换时，从离开原页、等待
  到目标内容就绪均舒缓；没有明显闪白、干扰阅读的明暗突变、突兀推挤／非预期来回位移。
  共享页头／导航稳定，正常页面布局／高度差异和协调占位替换允许。比较改前／改后过程，
  不以固定时长、CSS值、任意几何变化或单张停稳截图判断。
- [ ] **TAC-2 读取接入：** 每页首次快读、有效缓存返回、实际慢读均可用；快读不突兀闪现
  等待提示／骨架，慢读有稳定可辨反馈，内容平顺接入。数据一旦就绪可交互；读取照原有
  依赖及时开始，不为动画添加网络延时或串行请求。
- [ ] **TAC-3 两库刷新：** 分别完成冷读、缓存返回、手动快／慢刷新、普通操作后的更新；
  不再瞬时插入“正在刷新当前目录”推挤列表，也不将闪现搬到固定位置。慢刷仍有可访问
  的忙碌反馈，同条件成功内容保留；空、无 Active、失败与权限状态及原恢复入口清楚。
- [ ] **TAC-4 归属与恢复：** A→B→C快切、浏览器前后退、认证续转到原目标，URL／选中
  导航／内容一致；两库快换库／路径的迟到读取不串结果。真实失败可以通过现有入口恢复，
  不将等待当空态、不无限占位、不隐藏失败。共享鉴权语义保持。
- [ ] **TAC-5 同页与弹卡：** 同页分页／筛选／标签、切库／路径、刷新及弹卡开关不重播
  整页入场；任务／存储／库／自动化卡的遮罩覆盖完整视口，卡片内容与操作完整可用，
  长内容可在卡内滚动，背景及焦点正确恢复。简短卡片不要求铺满视口或出现滚动条。
  未保存选择保留原输入和URL；reduced-motion静态清楚可操作。
- [ ] **TAC-6 已交付及安全：** Task52.1 的浏览位置、分页、详情及慢读时继续搜索输入
  保持；纯探索／导航零任务准入／配置发布／媒体 mutation。普通文件命令只由用户原入口
  明确提交一次，进度、独立结果及未知请求核对不因呈现更新丢失或重放。

## Required Tests

按[工作流测试分工](docs/development-workflow.md#6-test-levels)。下列命令是未来候选的
实施／验收计划，本轮只读规划没有执行产品测试。

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
`NotificationRouter.test.tsx`、`ConfigurationPage.test.tsx`（均位于对应 feature），以及新增
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
```

全 Web 单元由 B 负责：共享 Shell、CSS 与读取反馈被九页及弹卡消费，是本 Task 的具体
共享影响依据。原生范围限共享导航／两库／探索和新增Python接入用例，不扩成全部E2E。
根目录治理及 `git diff --check`；若改 Python harness，再跑其受影响检查。T3不要求
全Python、wheel、Docker或生产矩阵。记录精确候选、实际命令／结果／失败与证据；已有
403定位失败事实保留，不自动删除断言或当新阻塞，按该候选实际行为核对。

## Non-goals

不实施 RO-4 自动化旧打开／definition／editor退出；保留其现有入口及命令。
不重做九页业务、主题／设置或设计系统；不扩展API／Provider／Storage／schema／权限／
队列／恢复引擎，不修改公共Modal生命周期，不更改已接受Slice结果／延期，不修无关
基线定位问题或创造流程工具Task。Slice终审前的现行文档协调由对应所有者处理。

## Developer Completion Report

尚未实施。交接时填写精确实现SHA、READY FOR B REVIEW、变化、受影响测试实际结果、
总耗时／测试耗时、剩余工作和风险；B的完整验收尚待执行。

## B Review Result

本轮为规划，尚无 Task52.2 实现候选；不签署产品 PASS / FIX REQUIRED。
实施后按工作流独立审完整 Base..Head，明确阻塞及用户操作例子；PASS后重新核对全部
Slice结果，已满足就交A，不为可选清理继续规划。
