# PATCH-20261114-1 — 整理来源路径、规则重跑与弹窗体验修复

用户于 2026-11-14 明确“激活Task”，正式授权本独立 Task 实施；原 Task ID、Base、
Goal 与 Scope 保持，移除规划草案限制。B 已独立复核候选 checkpoint
`02ee5fcce7b27ece83f323ddb43beb5ec587c394`，结论 FIX REQUIRED：逐项切换过渡与决定区
视觉层级尚未完成，具体修正指导见下方 B review result。修正留在同一 Task，
不授权启动其他代理、推送或部署。范围为本会话原五项
问题与随后确认的冒号路径拒绝问题。

```text
Task ID: PATCH-20261114-1
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: READY FOR B REVIEW
Task Base: 6bf8f58b8283bc891c4b768208d343d2d52600f2
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Implementation Authorization: USER AUTHORIZED ON 2026-11-14
```

权威：[Development Workflow](docs/development-workflow.md) §3.1、§5–8；
实施前阅读 [Developer experience](docs/agent-experience/developer-implementation-role.md)。
当前 Slice54 保持 PASS / CLOSED；Slice53／54 及既有独立修复只作接受行为参考，
不重开 Slice，不改 SLICE／Roadmap／Progress 的边界和关闭记录。

规划前：仓库 `/Users/songzhidong/mediaflow`，分支 `main`，HEAD 为上述 Task Base；
工作区与暂存区干净、仓库／Git 可写，`python3 scripts/check_governance.py` PASS。
实施前重新记录实际 HEAD／预存变更并运行治理检查，不静默重设 Base。

激活前：分支 `main`，HEAD `f3f1928b96f8d24d92e39475ad01c4731240e33d`；
工作区与暂存区干净、仓库／Git 可写，治理检查 PASS。本次仅修改 TASK.md 的授权与
交接说明，原计划、验收、测试分工和已关闭 Slice 均保持。

## Goal and complete journey

修复现有规则检查与手动整理旅程：规则单项重跑原位更新结果；Files 中真实合法名称
可被精确整理；共享整理卡的准备、逐项决定、等待分析、方案和整批确认协调可读，
切换自然且保持当前工作；修复本次已定位的四项既有失败测试。

适用 CURRENT：`V2-RULES-010–012`、`V2-OPS-018/019`；
[Rules 完整旅程](docs/product-experience.md#current--organizing-rules-dialogs-and-readability-slice54-pass--closed)、
[手动整理旅程](docs/product-experience.md#manual-organize)、
[整理弹窗旅程](docs/product-experience.md#current--manual-organize-dialog-slice53-pass--closed)、
[来源与共享弹窗架构](docs/architecture.md#current--manual-organize-dialog-slice53-pass--closed)。
V1 Requirements 的人工整理／策略测试章节是业务基础，当前入口、单项检查和确认语义
遵守上述 V2 CURRENT，不恢复退役入口。

1. Rules 编辑类型策略 → 单项测试 → 看结论 → 修改输入／显式重跑 → 同一结果位置显示
   新结论或失败与恢复；无自动测试、发布或媒体变更，实时 Provider 仍需明确意图。
2. Files 选择文件／目录／混选 → 整理卡立即显示真实提交／准备状态 → 逐文件选择并
   保存重新分析 → 原位看等待／失败／新方案 → 整批复核 → 一次明确确认所选就绪项 →
   关闭卡并打开后端返回的准确 Task。确认受理不等于文件成功。
3. 失败说明阶段、已保存／已受理状态、已知效果和合法下一步；刷新、重开及 Task Center
   原位继续保持准确上下文。未知 Execute 只核对首次提交，成功／不确定兄弟项不重放；
   结束任务的摘要保持只读。

## Observed defects and bounded scope

| 问题 | 已调查事实与修复边界 |
|---|---|
| 紧急：来源冒号被拒绝 | 用户原路径含两处英文冒号，207 UTF-8 bytes／2 层；原样调用 `bounded_path` 得到 `invalid_path`，仅在内存去冒号后通过。`domain/media_discovery.py:bounded_path` 一律拒绝冒号；`application/manual_organize_preview.py:_normalize_library_relative_path` 有同类下游限制。修复完整实际来源链路，不改原名、不扩大根或权限。 |
| Rules 重跑累积 | `RulesObjectTestPanel.run()` 用 `setRuns([...items, newRun])` 追加；结果内重跑未传被重跑项身份。按原结果位置更新，覆盖 loading／成功／输入无效／请求失败，保留当前性与迟到保护。 |
| 整理正文不协调 | 隔离真实 Python／SQLite／Local fixture 的 1440×900 截图中，当前状态、合法决定、候选卡、当前方案多层嵌套、说明重复，方案落到首屏下方。只调整共享 organizer 局部层级、布局、间距和文案，不重设计 Task Center 详情。 |
| 准备首页难看 | 实际显示英文 `nextAction`／progress message、五组纵排零计数、空原因区、`第 0 / 0 个` 与未就绪动作。queued 且零遍历时还显示“已完整遍历所选范围”：代码把 `incomplete=false` 误当完成。按真实阶段呈现进度和恢复，技术说明归诊断。 |
| 流程切换突兀 | 代码中准备／review／confirm 直接替换正文，翻页只改 index／anchor；已有动画只负责 modal 开关。尚未完成保存分析后各中间帧的动态验收，实施先补观察；不靠重挂整卡、虚假进度或延时提交修饰。 |
| 已知失败测试 | 本基线已复现 Python 消费者白名单 1 项、Node 精确表头定位 1 项及误收入 Node 的 Python 年份搜索 2 项；修复方式见步骤 5，不能删除断言、加重试或放宽超时。 |

原样来源回归样本（只在隔离临时根创建，禁止访问用户媒体／运行库）：

```text
Perfect World Movie: Nine Tribulations Incinerate the Heavens (2026) [tmdbid=1598732]/Perfect World Movie: Nine Tribulations Incinerate the Heavens.2026.2160p.WEB-DL.SDR.42.0Mbps.H.265.Dolby Digital Plus.mkv
```

规划调查只用该字符串做校验复现，没有访问真实路径；去冒号对照只证明校验根因，
不代表完整 API／Worker 执行已通过，完整证明属于本 Task。

## Implementation steps

1. **先修紧急来源路径。** 追踪 Files 返回的相对路径经单文件／目录／混选准入、
   discovery、来源身份、intent、preview、Worker 复核到 Executor 的全部校验。
   允许已支持 Storage 上普通名称内的冒号，保持精确字符，不 trim／URL decode／改名；
   仅对阻断该旅程的校验作必要一致修复。区分名称标点与盘符、URI／UNC、绝对路径、
   反斜杠、NUL、空／点／父目录段；保留字节／深度／数量预算、符号链接和真实根约束。
   不可仅删除 `":" in value` 后停止验证，不可前端绕过后端。来源浏览及下游已有校验
   一并核对；不扩成全仓路径重构。拒绝提示区分路径无效、资源库不可用和条目拒绝，
   复用有界脱敏的原因／下一步。
2. **Rules 原位重跑。** 共用单项面板保留一个当前结果位置，结果内重跑原位更新，
   主检查按钮重复提交也不堆叠整组历史。运行中显示本次状态，失败原位给原因和重试；
   表单／样本／Active 变化仍使旧证据失效。迟到请求不得复活被替换结果、串对象或把
   旧结论当当前；显式实时 Metadata 意图与离线零变更语义不变。
3. **协调整理卡三个阶段。** 沿用既有 library／Automation modal 视觉，标题／关闭／
   底栏稳定，正文内部滚动。准备页以范围、当前阶段和下一步为主，正常等待有真实忙碌
   反馈；问题突出排除、稳定等待、读取失败或 Worker 不可用及恢复。正常等待不要求
   用户操作 Worker；queued／running 不能声称遍历完成，不显示无意义 0/0 或空占位区。
   逐项页优先当前问题与选择／当前方案，减少套框与重复技术说明；有方案时清楚显示
   作品、完整来源→目标、操作／来源保留与附件风险。整批页突出精确所选项和危险效果；
   修订／原始状态／请求身份保留于诊断，不能隐藏阻塞或来源目标。
4. **修复过渡。** 覆盖提交→准备→首个文件、翻页、保存→等待→新方案、逐项↔整批、
   确认→准确 Task 交接。局部过渡保持同一 mounted organizer、itemId 草稿、选择和原
   提交身份；不重播整页动画、不清空闪回、不因轮询回顶。不同文件／分区的滚动与焦点
   明确可预测，长内容替换不能停在无关区域或突然跳位。动画不承担状态权威，不延迟
   真实可操作性；normal／reduced-motion 均可用，不增加动效设置或业务流程状态。
5. **修复已知测试。**
   - `tests/test_task_scheduling.py` 的
     `TransitionBoundaryTests.test_only_the_named_production_files_wire_the_kernel`：
     审查 `task_item_recovery.py:_native_analysis` 为既有同 Task 调度状态只读消费者后，
     精确更新允许集合和解释，保留禁止非预期消费者／第二执行器的相等断言。
   - `library-file-detail.spec.ts` 首项：名称表头的可访问名称含“调整名称列宽”。使用
     稳定准确的表头定位，同时验证列名、调整控件和原只读行为，不删除列断言。
   - `playwright.config.ts` 默认 Node 套件漏排除 `metadata-search-year.python.spec.ts`：
     修正归属，用原 Python 配置实际运行两项；不 skip、藏用例或改假 Provider 降低
     证明。检查其他 Python spec 的归属，仅修同类配置遗漏。
6. **验证与交接。** 运行下述 Developer 受影响检查，记录实际结果／风险，形成完整候选
   检查点 READY FOR B REVIEW。B 独立审核全部 Base..candidate 并运行验收。若实现
   改变现行说明，限必要的当前说明协调，不改已接受历史或 Slice 边界。

## Acceptance criteria

- [ ] 原样样本的单文件、目录、混选可浏览／准入／生成准确计划，来源字符始终一致；
  隔离真实 Python／SQLite／Local／合成 Provider 中一次明确确认后由 Worker 执行，
  准确 Task 交接和来源／目标结果可核对。准入／分析零媒体变更。
- [ ] 非法绝对／盘符相对与绝对／URI／UNC／反斜杠／NUL／点段／越界、超预算和符号
  链接仍拒绝；合法加结构非法的混选不能偷偷只受理合法子集。原业务逐项排除语义
  保留，不放宽资源库 ID、RBAC、Storage 能力、覆盖／删除授权或根约束。
- [ ] 类型策略先检查再连续重跑，结果原位更新、列表不增长；七类共用面板的 loading、
  成功／不匹配／失败、输入失效和迟到结果正确，编辑／切对象不自动发请求。
- [ ] 准备页中文层级协调、真实阶段反馈；无 queued 时已完成、伪百分比、英文原始指令
  作主说明、空原因区或无意义 0/0。Worker／读取故障区分已受理与未受理，给出合法
  下一步，不要求重复提交已受理工作。
- [ ] 逐文件和整批复核同一视觉体系，候选与保存动作、就绪方案与纳入选择清楚；长名称
  和路径完整可查，原选择、附件、冲突和危险授权功能保留。
- [ ] 1440×900、390×844、1280×600 的打开与各流程中间帧自然，无横溢或不可达动作；
  normal／reduced-motion、Tab／Escape／回焦／背景锁滚可用，当前文件和动作不因
  轮询或迟到响应跳位。不能只以 CSS 数值或最终静态图代替视觉验收。
- [ ] 十项歧义仍十次选择／保存分析、最后一次明确确认；翻页零写。保存拒绝、分析
  未受理／已受理／未知、原 Execute 丢响应后兄弟重分析、后台 Task 读取失败、重开／
  重认证、结束只读均保留已接受恢复与原请求非重放语义。
- [ ] 四项原失败在正确套件通过；Node 不误跑 Python-only spec，Python 年份搜索两项
  实际通过，无断言删除、skip 掩盖、额外重试或超时放宽。
- [ ] Developer 检查与 B 的适用 T4 门禁完成；C 使用 A Naming／Classification 仍输出 C，
  发布／固定 pins／并发 fencing／仅 Executor 变更媒体保持。

## Required tests

### Developer — affected tests

精确起始计划如下；新增用例放现有适用文件，必要原生用例补在现有
`manual-organize-dialog.python.spec.ts`／相关 Rules spec。实际改动若影响其他直接
消费者，补跑对应测试并解释；不把全仓套件交给 Developer。

仓库根：

```bash
python3 scripts/check_governance.py
.venv/bin/python -m unittest tests.test_media_discovery tests.test_media_discovery_provider_manifest tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_storage_browser tests.test_local_storage
.venv/bin/python -m unittest tests.test_task_scheduling.TransitionBoundaryTests.test_only_the_named_production_files_wire_the_kernel
git diff --check
```

覆盖原样路径、精确身份、拒绝边界、准入原子性和零变更分析。使用临时根／记录型
Storage／合成 Provider，不用生产媒体或网络 Provider。对实际改动 Python 文件运行
`.venv/bin/ruff check <files>` 与 `.venv/bin/ruff format --check <files>`。

`web/`：

```bash
npm run test -- run src/features/rules/RulesObjectTestPanel.test.tsx src/features/rules/RulesEditPage.test.tsx src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/library/StorageFilesPage.test.tsx
npm run typecheck
npm run lint
npm run format:check
npm run build
npm run test:e2e -- tests/e2e/library-file-detail.spec.ts tests/e2e/rules-identity.spec.ts tests/e2e/manual-organize.spec.ts
npm run test:e2e -- --list
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/metadata-search-year.python.spec.ts tests/e2e/manual-organize-dialog.python.spec.ts
```

实际查看三视口和流程中间帧，记录冒号来源原生链路与逐项／整批切换。默认 `--list`
无 Python-only spec 且保留原 Node 用例；单项结果补重复检查、重跑失败和迟到结果测试。
若修改公共 modal／样式，补跑 `src/shared/ui/modal-card.test.tsx` 与
`tests/e2e/storage-management.spec.ts`、`tests/e2e/automation-presentation.spec.ts`。

### B — independent acceptance and full regression

B 固定完整 Base..candidate 审查，先复现原样路径与安全边界、原位重跑及四项原失败；
再负责 [T4 共享全量门禁](docs/development-workflow.md#shared-full-regression-commands)，
含完整 Python／Web／默认 Node、质量／配置／禁用依赖、新生产构建、精确新 wheel 与
源码外安装 smoke。Developer 不承担这些全量门禁。

另在 `web/` 用生产构建执行：

```bash
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts tests/e2e/metadata-search-year.python.spec.ts tests/e2e/operations-inventory.python.spec.ts
```

独立核对冒号来源准入到真实 Worker 效果、十项一次确认、未知首次 Execute 跨兄弟重分析
与后台读取失败仍准确核对、Task Center 原位继续和历史只读；人工查看三视口及 normal／
reduced-motion 中间帧。Rules 七类共用结果覆盖成功／失败／过期，保留 C→A、零媒体
变更与一次准确发布消费者回归。

无容器／启动／部署路径变更时广域 Docker 矩阵不适用，B 按最终差异说明依据，不能把
本地 fixture 当真实远程适配器支持。七项既有可选外部／耐久跳过和其他实际未运行／
失败如实记录；不改写历史失败，不预填新结果 PASS。

## Non-goals

不新增 Provider／Storage 操作、schema、调度队列或执行／恢复引擎；不改识别／命名／
分类算法和目标命名规则，不为兼容自动改源名称，不扩展资源库 ID 语法；不重设计
Task Center 详情／全站主题／规则清单，不恢复旧接收页、Pause 或 CLI retry-failed。
不增加结果历史产品、动效设置、自动选择／确认、未知效果重放或万能回滚。
不读生产数据库／私有配置／用户媒体，不推送、发布、部署或规划下一 Task／Slice。

## Developer completion report

```text
Candidate: 779e8e1af958822d056ebf1dc62df16666f21d92
Status: READY FOR B REVIEW
Scope: Task Base 6bf8f58b8283bc891c4b768208d343d2d52600f2..779e8e1af958822d056ebf1dc62df16666f21d92
```

完整候选 SHA：`779e8e1af958822d056ebf1dc62df16666f21d92`（本轮修正 commit）。
开发分支 `main`，Task Base `6bf8f58b8283bc891c4b768208d343d2d52600f2`；开始工作区与
暂存区干净，结束时除本轮变更外干净，未推送、未发布、未部署。上轮候选
`02ee5fcc..a109a525` 的实现、路径与规则证据保留；本轮只修复 B 指出的两项弹窗阻塞。

### 变更与关键决定

1. **逐项过渡按真实变化重启。** `ManualOrganizeDialog` 新增稳定的
   `.mf-organize-stage` 内容边界；当前文件、逐项／整批阶段、准备阶段、精确方案身份或
   已保存分析状态变化时，布局 effect 在同一 mounted organizer 上重启 140ms 局部淡入。
   相同阶段轮询的 key 不变，不重启动画、不回顶。动画仅改 opacity／transform，不延迟
   可操作性；`prefers-reduced-motion` 下为 `animation: none`。
2. **回顶、替换与焦点顺序。** 当前文件或阶段变化时先回正文顶部，再在同一内容边界恢复
   焦点（仅当被替换控件已把焦点丢到 body），然后播放淡入；页脚翻页按钮与草稿、选择、
   原提交身份保持挂载。逐项↔整批、保存后等待、新方案到达均沿用同一局部边界。
3. **决定区去套框。** 将“当前状态”内的原生决定表单规则移到共享决定卡规则之后，并用
   `.mf-organize-dialog-body .mf-organize-section-primary` 限定作用域；实际计算样式为
   0 边框、0 内边距、透明背景、0 外边距，候选仍各自 1px 卡片，共享 Task Center 表单
   选择器不受影响。
4. **准备页文案。** queued／running 的进度说明改为“正在检查所选范围；下面的计数是当前
   已完成的真实进度。”，删除“不会声称已完整遍历”这类开发自述。

### 实际检查结果

仓库根：

```text
python3 scripts/check_governance.py                                          PASS
git diff --check                                                             PASS
.venv/bin/python -m unittest tests.test_media_discovery tests.test_media_discovery_provider_manifest \
  tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution \
  tests.test_storage_browser tests.test_local_storage                        263 passed, 14.627s
.venv/bin/python -m unittest tests.test_task_scheduling.TransitionBoundaryTests.test_only_the_named_production_files_wire_the_kernel
                                                                             1 passed, 0.048s
```

本轮未修改 Python 生产或测试文件，故未新增 ruff 对象；上述既有 Python 受影响套件仍复跑。

`web/`：

```text
npm run test -- run src/features/rules/RulesObjectTestPanel.test.tsx src/features/rules/RulesEditPage.test.tsx \
  src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx \
  src/features/library/StorageFilesPage.test.tsx                             5 files / 150 passed, 26.11s
npm run typecheck / lint / format:check                                      PASS
npm run build                                                                PASS
  dist/assets/index-gnk0teDC.css, dist/assets/index-YHsFO1BF.js；保留既有 500kB 体积提示
npm run test:e2e -- tests/e2e/library-file-detail.spec.ts rules-identity.spec.ts manual-organize.spec.ts
                                                                             23 passed, 11.7s
npm run test:e2e -- --list                                                   274 tests / 20 files, 0 个 python.spec
npm run test:e2e -- --config=playwright.python.config.ts \
  tests/e2e/manual-organize-dialog.python.spec.ts tests/e2e/metadata-search-year.python.spec.ts
                                                                             10 passed, 58.2s
```

真实入口的原生断言：十项旅程第 1 项实际计算决定区为 `border 0px / padding 0px /
background rgba(0,0,0,0)`，候选为 `border 1px`；点击“下一项”后同一
`.mf-organize-stage` 节点仍连接，且 `animationstart(mf-organize-stage-in)` 实际发生。
临时原生查看（同一 Files→Dialog 入口，生产构建，隔离 fixture；非耐久证据）：
1440×900、390×844、1280×600 的决定区无横向溢出，决定表单已直接属于“当前状态”；保存后
“零变更分析正在等待”为一次局部淡入（fade 计数 1）；新方案与整批复核可继续；reduced-motion
下 stage 的 `animation-name` 为 `none`、`opacity` 为 1。截图在
`/tmp/mediaflow-verify/`，仅本机开发证据。相同阶段轮询不重启动画由稳定的 stage key 与
effect 相等时直接返回保证。

### 已知限制与剩余工作

- 全量 T4、精确 wheel／源码外安装、完整 Node／Web／Python 全仓门禁仍由 B 在候选
  `779e8e1af958822d056ebf1dc62df16666f21d92` 上执行。
- 动画重启由浏览器 `animationstart` 与临时截图核对；未新增专用动效测试工具。
- 开发截图位于 `/tmp`，不作为耐久证据；B 需在自己的证据目录复核三视口与中间帧。
- 本报告不声明 PASS；B 独立审查完整 Base..candidate 后才能给出结论。

## B review result

### Decision — FIX REQUIRED (2026-11-14)

- Reviewer：B；分支 `main`；复核前工作区／暂存区干净，治理检查 PASS。
- 完整审查范围：`6bf8f58b8283bc891c4b768208d343d2d52600f2` ..
  `a109a525ac389feb2d6baed96657614b69708dfe`（26 个变更文件）。产品实现为
  `02ee5fcce7b27ece83f323ddb43beb5ec587c394`；之后仅 TASK.md 交接报告变化。
- Slice54 仍 PASS / CLOSED。本独立 Task 的路径与规则修复已有通过证据，弹窗的两项
  必需体验结果仍未完成；按 workflow §6 在这些阻塞修复后继续 T4 验收。

### 阻塞及 Developer 修正指导

1. **逐文件翻页仍是直接替换，没有本次承诺的局部过渡。**
   实际旅程：Files → source → Dialog → 选择两个文件 → 批量整理 → 等待真实 Worker
   完成分析 → 第 1 / 2 个 → 下一项。标题、文件名和候选直接变为第 2 项；在本轮新生产
   构建上，等待浏览器连续两帧后仍无任何过渡动画，页头保持同一 DOM 节点。
   `styles.css:10046` 的动画只在元素进入时启动；现有元素仅更新内容，上一项／下一项
   及同文件决定→等待的替换没有重新触发它。逐项↔整批切换会启动动画，覆盖不完整。

   **开发指导：** 在同一 mounted organizer 内，把局部过渡连接到实际当前文件或展示
   阶段的变化。保留逐项表单、草稿和请求身份；处理正文替换、回顶和焦点的先后，形成
   连贯切换。沿现有入口实际观察下一项／上一项、保存→等待→新方案和逐项↔整批；
   相同状态的轮询保持静止，reduced-motion 立即显示可操作内容。复用现有原生测试与
   浏览器观察，不新增业务状态或专门的测试工具。

2. **决定区的去套框样式被覆盖，实际仍有三层卡片。**
   同一旅程在“选择正确的作品”时，仍是“当前状态”外框、决定区内框、候选卡三层。
   1440×900、390×844 和 1280×600 均可见。`styles.css:9982` 新规则与 `:10064`
   原规则优先级相同，后者覆盖前者。实际决定区仍为 `1px` 边框、`13px 14px` 内边距、
   `rgb(248, 250, 255)` 背景，未实现本 Task 的减少嵌套层级。

   **开发指导：** 在 organizer 局部整理两条规则的顺序或作用范围，让决定表单自然属于
   “当前状态”，候选仍各自可选；保持共享 Task Center 表单的既有样式。用三视口实际
   截图核对候选、保存动作、方案的层级与间距。准备页顺带将“不会声称已完整遍历”这类
   开发自述改成直接的阶段说明，如“正在检查所选范围”。

### B 实测与证据

耐久本机证据：`.git/validation-evidence/a109a525/patch-20261114-1-b/`。
本轮使用真实现有 Files 入口、现有 harness Worker 推进入口和生产构建，所有媒体均为
隔离临时 fixture。未访问用户媒体或生产服务。

| 检查 | 本轮实际结果／原始记录 |
|---|---|
| Python 受影响回归及消费者白名单 | 264 tests PASS，14.619s；`python-focused.log`。命令为本 Task Developer Python 起始计划的 7 个模块加精确白名单用例；未执行全仓 discover。 |
| 原样用户路径确认移动 | 1 test PASS，0.090s；`exact-user-path-correct-fixture.log` 与 `exact-user-path.py`。复用现有 API→Worker 用例，在内存去掉样本额外的 `电影/`，并把 fixture 的电影路径识别规则改为匹配原样目录；全部移动／内容／身份断言保留。 |
| Rules／organizer／recovery Web 回归 | 4 files / 87 tests PASS，18.79s；`web-focused.log`。命令：`npm run test -- run src/features/rules/RulesObjectTestPanel.test.tsx src/features/rules/RulesEditPage.test.tsx src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx`，cwd `web/`。 |
| 新生产构建 | `npm run build` PASS；`build.log`；产物 `index-BLjnVQLZ.css`、`index-BsmW6_M_.js`。保留构建体积提示。 |
| Files Node 原失败所在文件 | `npm run test:e2e -- tests/e2e/library-file-detail.spec.ts`，6 PASS，2.1s；`node-library-file.log`。 |
| 年份搜索 Python 原两项 | `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/metadata-search-year.python.spec.ts --output=../.git/validation-evidence/a109a525/patch-20261114-1-b/python-year-artifacts`，2 PASS，5.8s；`python-metadata-year-isolated.log`。 |
| 默认 Node 归属 | `npm run test:e2e -- --list`，274 tests / 20 files，无 `python.spec`；`node-list.log`。 |
| 原生视觉 | `preparation-1440.png`、`fresh-item2-1440.png`、`item2-390.png`、`item2-1280x600.png`、`analysis-wait-1440.png`；直接查看截图。390px 页宽／内容宽均为 390px。翻页事件和实际决定区样式见 `fresh-build-visual.json`；分区与保存事件见 `transition-events.json`。 |
| 治理／报告检查 | `python3 scripts/check_governance.py`、`git diff --check` PASS。 |

实际探测偏差均保留：第一次仅去掉 `电影/` 的路径对照在识别阶段 blocked，原因是 fixture
原规则要求 `/电影/`；调整发布的 fixture 规则匹配原样路径后通过，不归为产品失败。
原生刷新后的两次探测因内存 token 已清除／再次整页导航而超时，随后重新从 Files 选择
另两个 fixture 文件完成新构建复现，不据此认定恢复缺陷。Node 与 Python 首次并行共用
默认 `test-results`，Python 1 PASS / 1 FAIL 于 trace 文件被清理；单独使用上表产物目录
重跑 2 PASS，初次日志仍保留。未改变任何断言或产品代码。

本轮自动化测试进程累计约 50 秒；计入原生交互和上述两次超时仍少于本轮总用时的 50%。
未执行完整 Python／Web／Node、全部真实 organizer 恢复旅程、质量全门禁及 wheel／源码外
安装验收；本次为已证实阻塞后的提前 FIX REQUIRED，尚不具备 PASS 条件。

Developer 按以上两项修正后提交同一 Task 的新 checkpoint，并运行受影响检查；
B 继续复核完整原 Base..新 Head、原生中间帧和所需 T4 门禁。保留原 Base、其余验收与
已通过实现；不重开 Slice，不规划额外 Task。

## Prior accepted Task

PATCH-20261113-3 的 B PASS、精确范围、原始失败和证据限制保留于
[固定接受记录](https://github.com/kentinya/mediaflow/blob/b199b2dd4ba76a5f804cea0d2280b2707f54d357/TASK.md#patch-20261113-3--b-pass)。
本计划不修改既有接受事实；当前闭合指针仍见 SLICE／Roadmap／Progress。
