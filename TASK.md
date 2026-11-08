# Task PATCH-20261108-2 — 探索页边界与详情首屏阅读修正

用户于2026-11-08明确要求“激活Task”，此前草案现为正式活动Task。
Developer可按下方固定范围实施；本轮仅完成激活，尚未开始产品实现。

上一项独立修正 `PATCH-20261108-1` 已由 B 独立验收 PASS：
Base `aa752cc3bc194707808a1af79afd8978ce4aef44`，
Reviewed Head `931d8de688e8777c155ca7163475d3d793c14415`，
Implementation Head `e2bb72d8c191d34586a90ff49577680107b0295c`；
完整结果、既有失败及证据限制保留于 `6220e369b4f8b7830a8a67ae9c8a6a3fd6e81134:TASK.md`。
Slice52 保持 PASS / CLOSED，其 Base、验收和 Roadmap／Progress 不变。

Authority: 用户本轮明确提出的三项探索页呈现修正及其后的规划请求；
[Development Workflow](docs/development-workflow.md#31-independent-minor-bugs) 管理独立修正生命周期。
遵循 [B experience](docs/agent-experience/task-planner-reviewer.md) 和
[Developer experience](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: PATCH-20261108-2
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: 37c3287ece5cd7060a887b42fcd84c6b0fc49e7e
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Development Authorization: USER-AUTHORIZED TASK ACTIVATION; DEVELOPER MAY IMPLEMENT THIS TASK
```

### Goal and authorized boundary

一个完整的现有探索旅程修正：用户进入探索直接使用搜索／筛选，内容边界与文件、媒体库、
规则、自动化、任务中心协调；从可见海报打开电影／剧集时，第一眼即可阅读作品信息和
简介开头，横幅只作背景，阅读不受图片干扰；长内容仍可在卡内读完并准确返回。

用户授权的呈现意图为：删除主内容左上角可见“探索”标题；纠正探索距左边栏的距离；
将详情上方横幅转为背景、以下方详情为主体并保证可读性。它们仅调整既有页面呈现，
不新增业务能力、架构／安全边界或重开旧 Slice。

适用现行要求为 `V2-EXPLORE-003–007/009/010/013–015`；完整旅程见
[Product Experience](docs/product-experience.md#current--v2-explore-homepage-slice51-pass--closed)，
共享呈现／读取边界见 [Architecture](docs/architecture.md#current--v2-explore-homepage-slice51-pass--closed)。
用户新要求明确调整 `V2-EXPLORE-012` 的“一个可见标题”呈现及旅程中“先看图片”的顺序；
未来按实际交付协调 CURRENT 文字，保留旧 Slice 的接受事实，不把旧合同追改为新要求。
本轮仅激活本Task，产品实现和必要CURRENT文字协调按下方步骤进行。

### Observed entry, behavior and causes

调查基线即 Task Base。使用已有生产构建、本地 Explore Python harness／Node fake server，
以临时数据库、假 Provider 和拦截图片核对，未使用生产配置、真实 TMDB 或用户媒体。

- `ExplorePage.tsx` 自身渲染可见 h1；同时以该节点命名 section，作为分页空结果与详情
  退出的兜底焦点。删除标题必须同时修正语义／焦点，不能只移除 DOM 或隐藏空白。
- Explore 沿用 `styles.css` 的 Shell `28px 4vw 64px` 内边距。1440px／1920px 宽时，
  内容距侧栏分别为 57.6px／76.8px；上述五个页面均为 23px。探索没有单独的居中限宽问题。
- `ExploreDetailCard.tsx` 将 `DetailBackdrop` 放在网格首行，横跨两列；16:9 横幅先占
  高度，桌面下方才出现 220px 海报与信息，720px 以下又排成横幅、全宽 2:3 海报、信息。
  1440×720 时横幅约381px，占正文可见高度545px的大部分；390×844／390×600 时，
  信息约从屏幕902px处开始，首屏全被图片占用。
- 已有详情内滚动能读到末尾，但该能力不能证明首屏已呈现主体；现有部分 `toBeVisible`
  断言也不能代替 `toBeInViewport`／实际可见区域核对。

规划前治理检查 PASS；工作分支 `main`，HEAD 为上述完整 Task Base，暂存区为空且 Git／
Task 可写。预存已跟踪修改为 `mediaflow/.DS_Store`；未跟踪系统元数据、
`.explore_adapter_block.py`、`.mgmt.log`、`.t*.log`、`15` 及既有 output 材料均保留，
不读取私有配置、不纳入本次 checkpoint。

激活前HEAD为 `f025acccd1ac9a2c034eedf719a2df10a321e5c4`；相对固定Task Base仅有
`TASK.md`规划提交，产品源码、测试和依赖未变，原调查及计划继续适用，不重设Base。
激活前治理检查PASS，暂存区为空，上述预存工作区变更保持且不纳入激活提交。

### Implementation Scope and steps

主要实现位于 `web/src/features/explore/ExplorePage.tsx`、`ExploreDetailCard.tsx` 和
`web/src/shared/ui/styles.css` 的 Explore 专属规则；相关组件／入口测试、E2E 就绪定位及
本地夹具可作直接必要调整。优先复用 `ModalCardShell` 的关闭、焦点、内滚动和背景锁定，
不改变全局 Shell／其他弹卡的几何或生命周期。

1. **建立同视口基线并移除可见标题。** 从正常侧栏／认证后入口保存改前探索与详情截图。
   删除主内容的可见标题及占位，以可访问名称保留探索区域身份；把旧标题的 section 标注、
   ref 和详情兜底焦点迁到合理的可用区域／控件。空结果、失败和翻页后仍有确定焦点，
   正常关闭优先回到原海报；不聚焦不可见节点或导致列表跳顶。
2. **对齐探索内容边界。** Explore 专属地消除 Shell 的第二层宽内边距，按现有紧凑页面的
   桌面左右边界布置搜索、筛选、结果网格和分页。窄屏合理收边，保留390px两列海报、
   长筛选行内部横向浏览及错误提示；不借此统一重设计其他页。
3. **让详情成为首屏主体。** 把真实 `backdropPath` 对应图片移为卡片内装饰背景层，
   不再作为独占16:9正文行；保留可信图片路径／尺寸和原作品身份。桌面采用紧凑海报＋
   正文，手机采用小海报与紧凑信息布局，避免全宽海报再次把正文挤出首屏。
   标题／关闭稳定可达，评分、类型等基本信息和简介开头直接可见；长简介／长原名可换行
   并继续滚动，不能用截断、隐藏信息或只显示摘要替代完整阅读。
4. **保证所有图片下可读并保留恢复。** 使用与现有浅色主题协调的遮罩／渐变和稳定的
   文本底色，不能只在一张偏暗背景下调透明度。正文与关闭／重读控件不受图片加载、
   亮度或裁切影响，背景不拦截指针或键盘。缺图／图片失败直接使用稳定底色，信息位置
   不因图片迟到而下移；详情加载、失败、重读和返回路径保留。
5. **更新直接消费者并验证交付。** 增加首屏、可读性和边界测试，迁移依赖“可见探索标题”
   的入口测试。使用真实页面身份／搜索区域等稳定就绪条件，继续断言成功落到探索及无
   可见标题，不能删除等待或放松断言。仅调整直接依赖的 connect／landing 定位，
   不顺带重构各业务测试。实施时按实际结果最小协调 V2 Requirements、
   Product Experience、Architecture 中标题和详情呈现的现行描述；交候选时不得自称验收PASS。

### Acceptance Criteria

- [ ] 探索主内容没有可见“探索”标题及其空占位；侧栏入口正常。区域可访问名称、搜索、
      空态／失败／分页焦点和详情退出兜底可用，没有失效 ID 或不可见焦点。
- [ ] 1440px和1920px桌面，探索搜索／筛选／海报网格的左右边界与既有紧凑页面协调，
      距侧栏不随4vw继续扩大；390px无横向页面溢出，仍为两列海报。对齐验收使用同视口
      实际页面／几何和整页视觉，不能只检查某个CSS数值。
- [ ] 1440×900、1440×720、390×844、390×600，在详情成功稳定后且未滚动卡片时，
      名称、关闭、TMDB评分／类型等主要信息及至少一行简介正文实际处于卡内可见区域。
      电影／剧集均成立，片长／季集等其余信息保留可达。长名称场景保证主体仍可开始阅读，
      全文通过卡内滚动可达；短简介不为大图产生无意义滚动。
- [ ] 横幅真实作为背景呈现、不独占正文高度；海报辅助识别。明亮、暗色和高反差图片下，
      正文／辅助文字／关闭控件均清楚；普通文字对实际合成背景的对比度至少4.5:1。
      缺图、加载失败／迟到不遮字、不改正文起点、不留下大块图片空位。
- [ ] 长简介能用滚轮、触摸和键盘读到末尾并访问准确作品的TMDB外链；标题／关闭可达，
      图片层不吞交互。正常／较长名称、缺项、详情错误与显式重读均有可用布局。
- [ ] 从列表非顶部进入，加载／失败／重读、卡内滚动、关闭／Escape／浏览器后退前进均
      保持原列表背景位置；返回保留类型、筛选／搜索、成功页和合法入口焦点，宽度不抖动。
      详情开关不重播整页切换，reduced-motion保持可用。
- [ ] 搜索非法输入纠正、筛选待应用／清除、真空态、普通分页、迟到响应隔离及身份／Provider
      错误恢复保持；探索零媒体Storage调用、零业务写入。其他页、其他弹卡、关于与鸣谢
      和必要来源入口不受探索专属样式影响。

### Required Tests

遵循 [test levels and ownership](docs/development-workflow.md#6-test-levels)。
所有运行使用本地夹具／临时根和数据库。下列产品测试是未来实施／验收计划，本轮未执行。

#### Developer — affected tests

根目录：`python3 scripts/check_governance.py`、`git diff --check`。
`web/`：

```sh
npm run typecheck
npm run test -- run src/features/explore/ExplorePage.test.tsx src/shared/ui/AppShell.test.tsx src/shared/ui/modal-card.test.tsx src/features/entry/EntryPage.test.tsx src/routes/router.test.tsx
npm run build
npm run test:e2e -- --config=playwright.python.explore.config.ts tests/e2e/explore.python.spec.ts
npm run test:e2e -- tests/e2e/page-transition.spec.ts
```

对实际新改的TS／TSX运行 `npx eslint <changed-paths>`，对实际新改源码／样式／Task运行
`npx prettier --check <changed-paths>`；从 `web/` 引用根Task使用 `../TASK.md`。
仅有改动涉及新的测试文件时，把它加入直接受影响列表，不把全仓门禁转给Developer。

测试需覆盖可见标题退出与语义／回焦、空态／错误／翻页、背景缺失／失败、真作品字段和
外链、列表状态不串、背景位置不变。扩充现有Explore浏览器旅程，加入四个指定视口的
**未滚动首屏**断言、两种作品类型、长名称／简介、明亮／暗色／高反差图片和缺图。
使用可见区域断言／包围盒与真实滚动，避免只测DOM存在或能滚到底。
开发交接保存同视口改前／改后整页、详情首屏和必要失败态截图，并实际查看。

#### B — independent acceptance and regression

审查完整固定 Task Base..候选，复现原首屏／边距问题并对比候选。`web/`执行：

```sh
npm run typecheck
npm run lint
npm run format:check
npm run test -- run
npm run build
npm run test:e2e -- --config=playwright.python.explore.config.ts tests/e2e/explore.python.spec.ts
npm run test:e2e
```

B负责完整Web单测及默认Node E2E，依据是入口标题就绪断言横跨Entry／Shell与多个
业务测试，且同一共享样式文件承载页面／弹卡；Developer只跑上述直接受影响计划。
默认E2E涵盖九主页面、其他弹卡、认证续转和原有浏览入口，防止遗漏直接消费者。

对标题定位迁移直接涉及的其他Python旅程，B另做有界入口验证；使用原配置、顺序执行：

```sh
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/operations-task-center-visual.python.spec.ts tests/e2e/organize-source-history.python.spec.ts --workers=1 --grep 'the inventory renders real producer runs|capture the|a recorded partial history'
npm run test:e2e -- --config=playwright.python.unicode-principal.config.ts tests/e2e/operations-principal-identity.python.spec.ts
```

这些入口验证不授权改变整理流程。若实际选择保留可访问的标题语义而使部分消费者无需
修改，B依据最终差异缩减对应迁移验证，并记录理由；其他未变Python／发布全矩阵不列为
本Task门禁。若实施触及通用弹层行为或安全边界，先按工作流重评影响和等级。

B实际核对四个指定视口、1920px对齐和390px触摸，检查文字清晰、图层遮罩、首屏主体、
完整长内容、失败恢复及非顶部返回。对比度依据合成后的实际背景核对，不凭遮罩透明度
推断；快速图片／慢图片／图片失败均不得推挤内容。测试和视觉材料保留于忽略证据目录。

既有默认E2E `deep-link.spec.ts` 的403重复提示严格定位失败，历史已由B在前Task Base
复现，详细证据见上方接受记录；这是背景信息，不是本候选的自动豁免。若本轮仍失败，
B用本Task固定Base复现并报告，不能顺带删断言／隐藏失败，也不宣称全E2E全绿。

### Non-goals

不新增详情字段、独立详情深链／持久会话、Provider／图片代理／图片库、主题设置、推荐／
下载／播放；不改筛选或分页语义、全站布局／动画、其他页业务、API／CLI、权限、Active、
Storage、schema或执行引擎；不修无关既有测试失败、不改旧Slice／Roadmap／Progress，
不添加依赖，不推送、发布或部署。

### Developer Completion Report

PENDING — Task已激活，尚未开始实施。Developer完成后记录完整checkpoint、受影响测试实际结果、
必要视觉证据和风险，状态交到 READY FOR B REVIEW；不自评PASS。

### B Review Result

PENDING — 对精确候选独立验收后填写 Reviewed Base..Head、实际结果、限制及
PASS／FIX REQUIRED。通过后恢复紧凑 NO ACTIVE IMPLEMENTATION TASK；
本独立修正不需要A关闭Slice，也不规划下一项。
