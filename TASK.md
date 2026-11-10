# Task 54.1 — 七类整理规则统一弹窗、可读表单与单项检查

Authority: committed [Slice54](SLICE.md)，激活检查点
6351b60433f0e79dac6f5f7150884a1fecb0da43。生命周期、测试归属及关闭规则仅由
[Development Workflow](docs/development-workflow.md) 定义。阅读角色对应的
[B experience](docs/agent-experience/task-planner-reviewer.md) 或
[Developer experience](docs/agent-experience/developer-implementation-role.md)。

用户于 2026-11-10 明确“激活 Task”，正式授权 Task54.1 在既定边界内实施。
原 Task Base／Goal／Scope／验收与测试归属不变；本激活检查点未开始产品代码实现。
A 代行 B 的例外只涵盖首个 Task 规划，不包含 Developer 自审或代行最终 A 验收。
Slice53 的接受、原退回／修正与验证限制保留于
[固定关闭记录](https://github.com/kentinya/mediaflow/blob/8bc3ef905a76b96ef8ec327154b92e9b9972ea05/SLICE.md#closure-packet-and-a-final-review)。

~~~text
Task ID: 54.1
Task Type: SLICE
Parent Slice: 54
Status: FIX REQUIRED
Task Base: 6351b60433f0e79dac6f5f7150884a1fecb0da43
Difficulty: High
Test Level: T4
Planner / Reviewer: A acting as B for planning only / B independent review
Implementation Authorization: USER AUTHORIZED TASK ACTIVATION ON 2026-11-10
Implementation Checkpoint: c96cc4aa3ad88ed576391b776d1c17063b226abb
Next Action: DEVELOPER CORRECTS TASK54.1 TEST CONTEXT AFTER RECONCILIATION
~~~

## Goal

完整交付 Slice54 RO-1／RO-2／RO-3 与 V2-RULES-010／011／012：用户从七类清单添加
（含空态）、复制或编辑进入协调弹窗，在同一对象上下文内修改、按需单项测试，一次
保存发布后回原清单。概览独占完整流程检查；编辑深链／刷新／重认证、输入恢复和
准确发布失败／未知核对保持完整。本 Task 不扩大或关闭 Slice。

完整旅程见 [Product Experience TARGET](docs/product-experience.md#target--organizing-rules-dialogs-and-readability-slice54-active)，
七类内容矩阵及边界见 [SLICE.md](SLICE.md)。规划时的实际代码缺口：

- RulesWorkspacePage 的 Add／Copy 用 RulesObjectDrawer，Edit 经独立 RulesEditPage 挂载；
  清单本地搜索／状态／滚动没有统一的弹窗返回模型。Copy 等预填返回才打开，迟到读取
  未与当前打开对象统一隔离。
- 两种表单入口都串联 RulesObjectForm、RulesObjectTestPanel 和默认展开的
  RulesPreviewPanel。局部测试区域类名缺配套 CSS，编辑标题以 ID／Active 序号为主。
  命名模板重复全量变量帮助，Metadata 混合匹配／请求限制，分类内部表格最小宽度
  760px，部分内部按钮和 Organize 原始枚举呈现不协调。
- 抽屉第二次关闭会丢稿，遮罩退出没有共同阻断 saving；unknown 仅存于组件状态，
  Save 未由未知状态统一阻断。Edit 的 reloadActive 先替换 projection 再询问是否
  丢弃输入，不能将值／基线错配带入新卡片。
- 已有 modal-card、类型化字段／校验／草稿及 Python 规则读写／分析服务可复用。

## Implementation Scope

主要表面：web/src/features/rules/、router.tsx 的 Rules 路由、必要 Rules 返回／会话
模块、Rules 作用域 CSS、公共 modal 的必要兼容扩展及直接影响测试／fixture／原生证明。
API 客户端仅作既有请求／投影的必要封装调整，不改后端发布协议或领域行为。

1. **统一入口和返回。** 七类 create／copy／edit 共用卡片旅程，以 mode＋family＋
   source/object ID 限定主体。复用 ModalCardShell、useModalLayer、useModalCardExit；
   公共模块无 Rules 业务。保留旧 edit URL，改为对应清单背景上的同一编辑卡片。
   列表打开保留分类／搜索／状态／滚动／焦点；直达有对应分类默认关闭去向。不保留
   第二套独立整页编辑产品。保留合法 ID 编码及 Python 静态 entry 例外，不扩到资产路由。

2. **读取、草稿和退出。** 一打开就反馈稳定标题／底栏与真实 loading，读取字段权限
   和准确 prefill；Copy 沿用后端新 ID／支持时默认停用、Organize 不发明 enabled。
   迟到、关闭后或旧对象响应不能重新开卡或串值。复用 tab-scoped 输入存储，按当前
   principal 会话、类别／模式／对象隔离；不持久化凭据／临时权限／执行授权。
   设置与测试切换保留字段、样本和证据。Close／Cancel／Escape／遮罩／Back 同一判定：
   在途不能退出或重复提交，未保存明确继续／放弃，重复关闭不能丢稿。取消 Back 后
   地址／背景和刷新恢复仍准确，不能只保留内存。锁滚／占位／回焦／计时器准确释放，
   Tab、背景不可交互和 reduced-motion 可用。

3. **发布与未知核对。** Add／Copy 用 saveRuleObject，Edit 用 editRuleObject；不可变
   ID、ruleCandidateFields／validateRuleCandidate、隐藏值、RBAC、全图适用检查保持。
   预填／候选必须配套合法读取基线；跨发布版本的权限／对象 reads 不可拼成可保存快照，
   不用后台刷新／迟到 authority 给旧值自动换新基线。stale 保留输入，明确采用当前值／
   重新复核后才以配套基线保存。成功保留发布事实并更新清单、关闭回原列表；列表读失败
   另报，不再次发布或回滚。
   提交时冻结 mode／对象／候选／基线；未知标记及核对上下文独立于可改草稿，并在关闭
   重开／刷新／重认证后可核对，换对象或改草稿不能替换原记录，不自动重提。使用现有
   Active／对象只读投影：版本变化或当前同值不能单独证明原保存成功，证据不足时保留
   未知，展示当前值及明确采用／保留输入再复核的安全下一步，不新增请求审计查询或
   幂等协议。核对前禁止无保护普通 Save；取消采用不能先换基线再沿用旧输入。验证
   principal 隔离，不能向新身份展示前一身份草稿／未知记录。

4. **七类内容。** 标题显示动作／类别／真实名称，ID 可查、Edit 不可改。卡内明确
   分区设置和测试，简单定义紧凑，复杂配置分组／渐进展开。完整满足 Slice 七类矩阵：
   条件→输出、类型→四策略、Metadata 匹配／请求限制、电影／剧集模板与集中变量帮助、
   分类内部列表／当前规则／条件／目标、Organize 操作／附件／重复检测／回滚清理。
   已有字段／隐藏值／legacy destination 显式转换保留。中文枚举与单位不改真实值、
   范围或危险默认；内部“完成”不发布，只有外层明确 Save 发布；不依赖整页横向溢出。

5. **检查分界与结果可读。** 移除 Add／Copy／Edit 的 RulesPreviewPanel 完整链路区域
   和动作；无消费者的表单专属 UI 可核对后删除，共享 API／Python preview 不退役。
   Overview 保留 RulesCompleteFlowCheck 原显式精确 Active 检查。单项测试统一输入、
   结果、错误、内部动作样式，先看结论／实际输出／原因／下一步，技术 family／版本／
   统计／JSON 进诊断，保留完整结构证据。测试可选，Save 不强制手动测试；编辑、开关、
   刷新不自动测试。保留非匹配／不适用、合成身份和实时 Metadata 单独意图；候选／
   样本／Active 变化使旧证据失效，迟到结果不冒充当前。概览指引说明仅检查已发布 Active。

6. **真实验证。** 更新旧抽屉几何／整页／预览按钮断言，保留原领域安全覆盖。主要扩充
   既有 scripts/rules_workspace_browser_proof.py，复用其真实 Python／临时 SQLite／
   临时根夹具，完成七类 Add／Copy／Edit、发布／恢复、返回与视觉矩阵；不造新测试平台。
   全程零写改为分阶段证据：打开／编辑／关闭零发布；分析只产生合法非 Active 证据，
   零媒体／可执行工作；每次成功 Save 恰有对应一次发布。不能直接删安全断言。
   未知场景放行真实 Python Save 后丢响应，再真实读回；假服务缺 prefill 不当生产缺陷。

7. **交接。** 跑 Developer affected tests 后提交连贯候选及 READY FOR B REVIEW 报告，
   不等待或代跑 B 全量。修正在同一 Task 循环；文档保持 TARGET，CURRENT／Slice 关闭
   由最终 A 接受后协调，不提前宣告接受。

## Acceptance Criteria

- [ ] AC-1：七类 × Add／Copy／Edit 均为协调居中卡片，含空态添加；只读无写入口，
      无 Active／缺失／拒绝／读取失败真实，打开不创建配置／工作。
- [ ] AC-2：edit 深链、+／@／内部空格／点／合法文件状后缀 ID、刷新／重认证／
      Back／Forward 到准确对象；关闭恢复分类／筛选／滚动／焦点，直达回对应分类，
      同 Rules 弹卡不重播整页动画。
- [ ] AC-3：预填与发布基线配套，不混对象／版本；Copy 新 ID、原对象不变、支持时
      默认停用、Organize 无 enabled；Edit ID 不变，隐藏字段／合法旧值保持。
- [ ] AC-4：全部退出保护 dirty／saving；明确继续／放弃，重复关闭不丢稿；取消
      Back 后 URL、草稿、刷新／重认证一致，无遗留锁滚／计时器。
- [ ] AC-5：七类均满足 Slice RO-2 内容矩阵；设置／测试切换保留输入／样本／证据，
      命名帮助、条件／引用、分类目标、单位／危险影响清楚，嵌套动作风格一致。
- [ ] AC-6：1536×1000、390×844、1536×700 同视口前后／参考对照可读，长模板／
      名称／路径、深条件、多分类规则和错误无整页横溢或不可达动作；看画面和操作，
      不只用 CSS 值／DOM 形态判断。
- [ ] AC-7：loading→ready／error、已滚动背景、慢权限／prefill、快速换对象和开关
      中间过程协调，标题／底栏稳定，键盘、回焦、背景不可交互及 reduced-motion 可用。
- [ ] AC-8：七类局部检查仅准确候选及必要样本，非匹配／禁用／无关联／阻塞真实；
      默认结论／输出／下一步可懂、完整证据可查，编辑／Active 变更失效且迟到不串项。
- [ ] AC-9：仅概览有完整流程，三种表单模式无旧完整链路区域／按钮／旁路；概览
      精确 Active、合成身份、真实竞争和显式实时 Metadata 保持，局部不冒充全图就绪。
- [ ] AC-10：一次 Save 发布准确完整后继并关闭返回；无效／重复 ID／缺失禁用引用／
      权限／并发 409 均保留旧 Active／可修正输入；测试可选，Save 全图适用检查不减。
- [ ] AC-11：真实发布后丢响应，关闭重开／刷新／重认证／改草稿／换对象不丢原未知
      上下文、不重发；当前一致／变化与原请求事实区分。再有管理员发布或读回失败
      仍给真实下一步，不把新版本当原成功，不把新基线配旧输入。
- [ ] AC-12：已知成功而清单重读失败仍报已发布、仅重读，不再次 Save 或冒充刷新；
      草稿／未知记录只按准确对象及本次明确处置清理。
- [ ] AC-13：C 使用 A Naming／Classification 后仍 C；离线零 Provider、只读完整
      检查、原子激活／隐藏配置／RBAC／引用保护／脱敏和 Executor-only mutation 保持。
- [ ] AC-14：必要共享组件变更不改变自动化、两种库、存储、任务详情／恢复及 Slice53
      原请求核对／逐文件整理／准确 Task 交接；共享完整 preview API 仍可用。

## Required Tests

归属以 [test levels and ownership](docs/development-workflow.md#6-test-levels) 为准。
以下是实施后必需命令；本轮 B 实际结果见文末。原生证明必须使用
精确生产构建、临时库／本地假 Provider，禁止私有配置、运行数据库或用户媒体。
按本轮用户要求，测试执行累计时间（含失败复现）须小于本轮总用时的 50%，交接记录实际用时。

### Developer — affected tests

根目录：

~~~sh
python3 scripts/check_governance.py
.venv/bin/python -m unittest tests.test_v2_rules_workspace_commands tests.test_v2_rules_object_analysis tests.test_v2_rules_workspace_previews
git diff --check
~~~

web/：

~~~sh
npm run typecheck
npx eslint src/features/rules src/routes/router.tsx src/shared/ui/modal-card.tsx
npx prettier --check src/features/rules src/routes/router.tsx src/shared/ui/modal-card.tsx src/shared/ui/styles.css
npm run test -- run src/features/rules/RulesWorkspacePage.test.tsx src/features/rules/RulesEditPage.test.tsx src/features/rules/RulesObjectTestPanel.test.tsx src/features/rules/ClassificationDestinationForm.test.tsx src/entities/rules/rules-form.test.ts src/shared/api/rules-workspace-api.test.ts src/shared/ui/rules-form-styles.test.ts src/routes/router.test.tsx
npm run build
npm run test:e2e -- tests/e2e/rules-readiness.spec.ts tests/e2e/rules-identity.spec.ts
~~~

新增 Rules session／导航／恢复测试加入 affected run 的实际路径；合法重命名测试时报告
新路径、保持原风险覆盖。改到 shared modal／Shell／destination 时加跑对应消费者：

~~~sh
npm run test -- run src/shared/ui/modal-card.test.tsx src/shared/ui/AppShell.test.tsx src/shared/navigation/destination-model.test.ts src/features/operations/AutomationCreateDialog.test.tsx src/features/operations/AutomationLifecyclePage.test.tsx src/features/library/MediaLibraryConfigDialogs.test.tsx src/features/storage/StorageManagementPage.test.tsx src/features/operations/ManualOrganizeDialog.test.tsx
~~~

根目录，已构建生产资产上跑扩充的 Rules 原生主旅程：

~~~sh
MF_PROOF_ARTIFACTS="$PWD/.git/validation-evidence/task54-1/developer-rules-workspace" .venv/bin/python scripts/rules_workspace_browser_proof.py
~~~

主脚本覆盖 AC-1–12 实际入口／发布／恢复／视觉，单元测试补确定性迟到／权限／未知／
冲突。Developer 仅跑上述新改／直接影响和相关静态检查，不跑全 Python／Web／E2E
或 release 矩阵。变更 Python proof 后对实际变更文件跑 Ruff lint／format 与 compileall；
根目录预存 .explore_adapter_block.py 问题不擅自修或纳入提交。

### B — acceptance and full regression

B 审查固定 Task Base..candidate 全部实现／七类字段／隐藏值和所有模式，先复现
读写基线、Back 取消刷新和未知 Save 等关键行为。T4 执行
[共享全量门禁](docs/development-workflow.md#shared-full-regression-commands)，包含 Python、
Web、Node E2E、适用打包及源码外安装 smoke，保留原始失败／skip／限制。匹配的最终
Task 验收可兼作 Slice-final，不机械重复相同输入。

根目录，在精确候选的新生产构建之后：

~~~sh
MF_PROOF_ARTIFACTS="$PWD/.git/validation-evidence/task54-1/b-rules-workspace" .venv/bin/python scripts/rules_workspace_browser_proof.py
.venv/bin/python scripts/rules_object_analysis_browser_proof.py
.venv/bin/python scripts/rules_identity_browser_proof.py
.venv/bin/python scripts/classification_destination_browser_proof.py
~~~

旧 proof 的抽屉／整页／按钮选择器须改为新旅程，但保留特殊 ID、旧目的地转换、
真实局部／完整引擎、身份及零变更证明，不直接删除验证。B 查看七类桌面和复杂场景
390px／矮窗口、改前对照及自动化／库卡片参考，连续检查中间过程和键盘／回焦；
假服务／停稳截图／旧资产单独通过不算原生验收。

若 shared modal／Shell／路由触及这些消费者，再跑相应真实 Python 回归（web/；
独立输出目录避免不同原生配置互盖）：

~~~sh
npm run test:e2e -- --config=playwright.python.automation.config.ts --output=../.git/validation-evidence/task54-1/b-automation tests/e2e/automation-create-dialog.python.spec.ts tests/e2e/automation-lifecycle.python.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts --output=../.git/validation-evidence/task54-1/b-storage tests/e2e/storage-dialog.python.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts --output=../.git/validation-evidence/task54-1/b-organize tests/e2e/manual-organize-dialog.python.spec.ts tests/e2e/operations-task-center-visual.python.spec.ts
~~~

两种库配置／背景恢复在扩充原生主脚本中加入共享受影响 smoke。证据另以准确候选建立
稳定目录；task54-1 路径是命令入口示例，不覆写其他候选原日志。无 Docker／依赖／权限／
容器执行路径变更时广域 Docker 矩阵不适用，B 说明依据。无外部服务／endurance 环境
不得声称已完成对应验证。

## Non-goals

不新增领域字段／条件／求值器、Provider／Storage 操作、schema、权限／发布协议或
执行／恢复引擎；不退役共享完整 preview 后端／API，不重设计概览／清单、全站主题／
动效设置或其他页面业务。不改 Slice53 原请求恢复及执行／Task 交接，不自动保存／
测试／重放未知命令，不隐式转换旧分类或授权覆盖／删除，不扩到 V1／任意资产路由。
不规划下一 Task，不把可选优化当阻塞，不自行更改 Slice／Roadmap 边界或关闭 Slice。
实施已获用户授权，仅限本 Task；推送、发布与部署不在授权内。

## Developer Completion Report

~~~text
Status: READY FOR B REVIEW
Implementation Checkpoint: c96cc4aa3ad88ed576391b776d1c17063b226abb
Candidate range: 6351b604..c96cc4aa(本报告随后单独 docs 提交)
~~~

### 同 Task 修正(B54-01–05)落点

- **B54-01**:`rules-workspace-labels` 的草稿记录改为
  `{ values, readBaseline }` 候选与读取身份成对持久化;`RulesObjectCard`
  以 `pairedBaseline` 跟踪当前输入的配套基线,重开后与本次真实读取的
  Active 身份比较,不一致时直接进入本卡已有的“采用当前值 / 保留输入,
  重新复核”决策面板并阻断保存;采用同时替换值与配套基线,复核保留输入
  时把同一输入与刚读取的 Active 成对重写后才允许保存。双管理员旅程由
  新增单测覆盖(决定前无 PUT、采用后带 v2 说明、复核后带 v2 基线提交)。
- **B54-02**:`rulesCardDraftKey` 改为 `create|*` / `copy|<id>` /
  `edit|<id>`,草稿存储键统一为 principal+family+mode+subject(v3,
  旧版键丢弃);清单草稿提示改用 `hasRuleDraft` 扫描。恢复、采用、
  显式放弃、成功保存只处置对应模式的草稿;Copy 保持后端新 ID + 默认
  停用,单测与原生 proof 同时验证。
- **B54-03**:“继续编辑”改为 `blocker.reset()`(与 Automation 卡
  `cancelDiscard` 同一机制),同时收回放弃提示并把焦点交回卡片;仅
  显式放弃才 `proceed()` 原导航目的地。单元测试验证 prompt 收回、卡片/
  地址/输入保持与再次阻断;真实浏览器地址回退由原生 proof 的
  `goBack → 继续编辑 → toHaveURL(edit)` 旅程验证。
- **B54-04**:`allowlistedDestinationSearch` 的 `/rules` 分支在有效
  family 之外携带闭集 `dialog=create|copy` 与满足后端规则 ID 契约的
  `source`,其余一律丢弃;`destination-model.test` 补 auth-return 用例并
  以 `readRulesDialogSession` 端到端核对;真实浏览器刷新+重连旅程由
  proof 验证(地址、模式与输入均恢复)。
- **B54-05**:单项测试结果以 `结论 / 实际输出 / 原因 / 下一步` 四字段
  开头(新增 `analysisOutput` 按 family 输出实际结果),结果类别/修订/
  family/调用统计/`validated_non_active` 全部进入默认折叠的“诊断信息”,
  完整结构证据与 JSON 保留;测试/重跑与分类内部动作(修正、完成、
  旧版目标转换)接入 `mf-button` 体系;弹窗类名改为 `mf-rules-form-card`
  (限定 `.mf-modal-card` 特异性),与八区导航 `.mf-rules-card` 彻底解耦,
  标题/正文/底栏按卡宽铺开,复杂族 880px。

共享方面:`modal-card.tsx`、preview 后端/API、发布协议、领域行为均未改动;
`AppShell`、e2e 与 proof 的旧断言按统一卡现实更新(见下)。Slice/Roadmap/
Progress/产品文档本轮未改。

### 实际执行的 Developer 命令与结果

- `python3 scripts/check_governance.py`:PASS(实施前与提交前各一次)。
- 根目录 `.venv/bin/python -m unittest tests.test_v2_rules_workspace_commands
  tests.test_v2_rules_object_analysis tests.test_v2_rules_workspace_previews`:
  184 tests OK(11.0s)。
- `git diff --check`:PASS。
- `web/ npm run typecheck`:PASS;`npx eslint src/features/rules
  src/routes/router.tsx src/shared/ui/modal-card.tsx
  src/shared/navigation/destination-model.ts`:PASS;
  `npx prettier --check`(同范围 + 两个 rules e2e spec + AppShell.test):
  PASS(B 实际失败的 8 个文件已全部格式化)。
- `web/ npm run test` 受影响批次:8 文件 125 项 PASS;含
  `destination-model.test` 为 9 文件 154 项 PASS(14.19s);共享消费者
  批次(modal-card/AppShell/destination 及 Automation/Storage/分类弹窗等)
  8 文件 187 项 PASS。新增用例:B54-01 采用/复核双旅程、B54-02
  编辑↔复制↔创建隔离、B54-03 阻断导航继续/放弃、B54-04 白名单回放、
  B54-05 结论优先结构。首批跑出 5 处失败均为新用例自身的适配问题
  (memory history 的 `back()` 不经过 blocker、`expectedVersion` 取
  `revisionSequence`),按实际语义修正“测试写法而非删除覆盖”。
- `web/ npm run build`:PASS,产物 `index-3MBk4Ns8.js`、`index-ByxQof0I.css`。
- `web/ npm run test:e2e -- tests/e2e/rules-readiness.spec.ts
  tests/e2e/rules-identity.spec.ts`:最终 17 passed(14.8s)。更新的旧断言:
  统一卡选择器(`mf-rules-form-card`/`.mf-modal-header`/`.mf-modal-footer`/
  `.mf-rules-card-scroll`)、编辑深链断开前先关闭卡片、保存后回清单而非
  旧整页编辑标题、“ID 不可更改”定位到卡内描述、未触碰副本一次关闭、
  AppShell “不出现第二个 Rules 标题”改为单一清单头 + topbar 无标题。
  首轮暴露 3 处失败,修订后全绿;领域断言(特殊 ID、发布/复制/开关/移除、
  零伪造引用)全部保留。
- 原生主旅程(第 4 次运行 PASS):
  `MF_PROOF_ARTIFACTS=$PWD/.git/validation-evidence/task54-1/developer-rules-workspace`
  `.venv/bin/python scripts/rules_workspace_browser_proof.py` →
  `PASS: reference-aligned rules workspace through the real Python boundary`,
  31 张截图(含 `create-refresh-reconnect`、`back-continue-edit`、`copy-card`、
  `desktop-edit-local-test`、`edit-published-notice`)、evidence.json
  `mutations=[PUT …/objects/recognitionTypes/A]` 恰一条、Active 版本 +1、
  激活计数不变、可执行工作前后一致。前三次失败保留并已修正:①脚本侧
  Metadata 分区名过期(按当前表单 legend 更新期望);②结果摘要异步等待;
  ③激活计数语义(rules 发布记 `rules_edit` 审计而非 `activate` 行,
  按真实后端语义改为“审计激活计数不变 + Active 版本恰 +1”)。
- 变更 proof 文件:`ruff check`/`ruff format --check` PASS,
  `python -m compileall` PASS;根预存 `.explore_adapter_block.py` 未触碰。

### 本轮用时与测试占比

本轮总用时约 70 分钟;测试执行累计约 11 分钟(单测批次约 2 分钟、
三组 e2e 约 3 分钟、proof 4 次约 6 分钟,含 build/静态检查约 1 分钟),
占比约 16%,低于本轮要求的 30%。

### 剩余风险与限制(交 B)

- 双管理员跨发布恢复(B54-01)在原生层的完整双会话复现本轮由确定性
  单测覆盖(读取/恢复/决定/保存全链真实 HTTP stub);原生 proof 已覆盖
  同机制的 Refresh/重连恢复与真实 Back 地址回退,建议 B 用其复现脚本补跑
  双管理员原生旅程作验收复核。
- T4 全量门禁(Python 全量/Web 全量/Node E2E/打包与源码外 smoke)与
  其余三个原生 proof(analysis/identity/classification)未执行,归 B 按
  Required Tests 进行;proof 改为分阶段证据后旧“全程零写”断言已按范围
  要求重构为“除发布窗口外零写 + 恰一次发布”,B 验收时留意该语义变化。
- JS 内 `unexpectedMutations`/本地测试无 Provider 调用的证明限于该
  proof 旅程本身;无外部服务、endurance 环境验证未声称。

## B Review Result

~~~text
Reviewed: 6351b60433f0e79dac6f5f7150884a1fecb0da43..d26e4b210e04f2ec9f617acbf8b1eddf5608ec67
Implementation: c96cc4aa3ad88ed576391b776d1c17063b226abb
Decision: FIX REQUIRED
Task blocker: B54-06 — 核对当前值后，单项测试仍使用旧版本
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP
~~~

完整 Task Base..Head 与本轮修正均已审查；`c96cc4aa..d26e4b21` 只有 Task 交接文档，
本轮构建和复现使用的产品代码与已交接实现一致。工作区 main，预存系统元数据、日志和
调查材料保持原样；本轮只更新根 Task。

### 上轮修正与 Slice 结果重评

- B54-01：真实双管理员旅程中，刷新恢复旧草稿后保存被阻止；采用当前值保留另一管理员
  的说明，明确复核保留输入后才允许保存；两条分支的真实保存均返回 200。
- B54-02：编辑 A 留稿后复制 A，候选为 `A-copy`、默认停用且名称不串稿；复制自己的输入
  也能刷新／重认证恢复。
- B54-03/04：真实 Back→继续编辑→刷新／重认证保留准确 Edit URL 与输入；Create/Copy
  的 dialog/source 和对应输入恢复，未退回普通清单。
- B54-05：卡片与导航样式已分开，桌面正文铺开；测试按钮及结论／输出／原因／下一步
  已呈现，技术信息可展开。核对了七类桌面表单及 390px 识别类型截图。完整复杂窄屏／
  矮窗口／中间过程矩阵仍待最终验收，不将局部观察写作全部通过。
- RO-1 的核对后恢复、RO-2 的精确单项测试仍受 B54-06 阻塞。RO-3 表单完整预览移除、
  概览和共享后端保留已落代码，完整原生回归待修正候选。继续 Task54.1，不规划下一 Task，
  不提交 Slice Closure Packet。

### B54-06 · P1：采用当前值后，单项测试仍带旧版本

**完整复现：**甲从识别类型清单编辑 A 并改名；乙通过现有规则编辑 API 修改 A 的说明并
发布 v2；甲保存收到 409，点击“读取当前 Active 核对”再“采用当前值”。表单已显示乙的
新说明。甲切到“单项测试”并测试该识别类型，真实分析请求仍带 `expectedVersion: 1`，
而候选内容已是 v2，服务端再次返回 409。页面显示英文刷新指引；点击重跑仍使用同一旧
上下文。该完整恢复旅程没有完成 AC-3/8/10，属于既定 RO-1/RO-2 范围。

**开发指导：**在 `RulesObjectCard` 的当前值核对、采用与保留输入复核之间，统一传递
本次配套的表单字段／引用权限、对象值与 Active 身份。现在 `runVerification` 已读取新
form-authority，采用只更新 `projection`/`pairedBaseline`，而 `RulesObjectTestPanel`
继续消费首次打开时的 `authority`。采用／明确复核之后，表单、保存及单项测试必须使用
同一已核对上下文；读回失败保留原输入与核对入口，读到不同版本时保持待核对，不能拼接。
复用现有读取与状态，不改后端并发规则或分析协议。

**验收与受影响测试：**

1. 在 `RulesEditPage.test.tsx` 补齐“初读 v1→乙发布 v2→保存 409→核对 v2→采用当前值→
   单项测试”用例；断言分析请求使用 v2 身份、v2 对象并得到正常结论。
2. 同一冲突入口覆盖“保留输入，重新复核”：保留候选后分析与保存均使用用户明确复核的
   当前身份；已有旧结果应显示过期，重跑提交当前候选。保留上轮草稿隔离及未知不重发覆盖。
3. 在现有 `scripts/rules_workspace_browser_proof.py` 中补入上述双管理员冲突后的单项
   测试旅程，复用临时 Python/API/SQLite 夹具，按实际请求核对身份及结论。
4. Developer 跑原 Required Tests 的受影响批次及变更 proof 的检查，提交同 Task 修正
   checkpoint 和实际结果；T4 全量、其他原生及打包仍由 B 验收。原 Base/Goal/Scope、
   High/T4 和测试归属保持。

### B 实际验证与限制

本轮证据目录：`.git/validation-evidence/d26e4b21/task54-1-b/`（本机）。

- 治理检查、完整 Task `git diff --check`：PASS。
- 新生产构建、TypeScript、受影响 ESLint、Prettier：PASS；产物
  `index-3MBk4Ns8.js`、`index-ByxQof0I.css`。
- Required Tests 的规则／entities／API／styles／routes 加 destination-model 受影响批次：
  9 文件、154 项 PASS，12.42 秒；见 `affected-vitest.log`。
- 原生主脚本 `MF_PROOF_ARTIFACTS="$PWD/.git/validation-evidence/d26e4b21/task54-1-b/workspace" .venv/bin/python scripts/rules_workspace_browser_proof.py`：PASS，31 张截图、恰一次明确
  PUT 发布、Active 恰增一版、可执行工作不变；见 `workspace.log` 与其 evidence/matrix。
- 本轮沿既有清单／编辑／分析入口复现 Back、Create/Copy 恢复、双管理员草稿恢复与两种
  决定、真实发布后丢响应再刷新核对：通过，见 `native-evidence.json`（5.16 秒）。
  保存仍在途时刷新／重认证也保留了原未知记录，见 `inflight-evidence.json`（1.70 秒）。
- B54-06：真实 API 409、核对、采用与再次分析 409 均已记录于 `stale-evidence.json`，
  截图 `stale-adopt-test.png`；显式重跑同样提交旧身份并返回 409。首轮复现 2.02 秒，
  加入重跑操作的记录保留同目录。
- 已证实 P1，按流程提前 FIX REQUIRED；本轮未启动 T4 全量及其他原生／打包门禁，
  修正后由 B 执行。本轮测试执行约 40 秒（含构建、静态、原生及组件批次），占本轮
  审查用时低于 50%。临时数据库／媒体根随夹具清理，未使用运行数据库或用户媒体。
