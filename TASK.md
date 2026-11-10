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
Implementation Checkpoint: 7584bd3fd5274822b403e8b9758dcc87d9322670
Next Action: DEVELOPER CORRECTS TASK54.1 EDIT BACKGROUND STABILITY
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
Implementation Checkpoint: 7584bd3fd5274822b403e8b9758dcc87d9322670
Candidate range: cd9b5c7e..7584bd3f(本报告随后单独 docs 提交)
~~~

### B54-06 修正落点

- **同一核对上下文贯穿核对/采用/复核。**`VerifyPanelState` 增加随
  `runVerification` 同一次双读带回的 `formAuthority`:
  a)“采用当前值”在替换值与配套基线的同时 `setAuthority(formAuthority)`,
  表单目录、`save()` 校验和 `RulesObjectTestPanel` 的
  `authorityIdentity(authority.active)` 一起切到已核对 Active;
  b)“保留输入,重新复核”把本次 `fetchRuleFormAuthority` 的模型与保留
  输入、fresh 基线一同落地,投影改记“当前输入 + 其配套基线”(此前
  旧读值配新基线属拼接,按指导不可保留);c)草稿核对的采用也携带
  开卡读取到的配套 authority。采用/复核前的阻断、读回失败保留输入与
  核对入口,均为既有行为未变。
- **读到不同版本保持待核对。**新增 `divergent` 结论:核对双读
  (form-authority 与对象投影)或草稿核对(authority 与 projection)
  观察到不同 Active 身份时,展示两次读取序号、不提供采用/复核按钮、
  不保存不重发,仅提供“重新核对”;读取对齐后重新核对即恢复可采用
  的一致上下文。不改后端并发规则与分析协议。
- **Active 变化使旧证据失效而不自动重跑。**卡片向测试面板传
  `publicationEpoch={pairedBaseline.expectedVersion}`:采用或复核使
  配套 Active 移动时(即使候选内容不变)旧结果立即标记过期,重跑由
  操作者显式执行并提交当前候选。

责任定位与 B 指导一致:`runVerification` 早已读到新 form-authority,
此前只取其 identity,`authority` 状态停留于开卡读取——本修复把该读取
作为核对上下文的一部分传递下去。

### 新增测试(RulesEditPage.test.tsx,3 例)

夹具按真实围栏语义服务:过期 PUT、过期 analysis 都以当前 Active 版本
拒绝(409 `configuration_version_conflict`),当前身份才 200。

1. **采用后单项测试**:初读 v1 → 乙发布 v2 → 保存 409 → 核对 →
   采用 → 单项测试;断言分析请求 `expectedVersion/expectedRevisionId`
   为 v2、`candidate.values` 为乙的新对象、结论显示且无“测试未完成”、
   全程恰 1 次 PUT、保存重新可用且从未自动重发。
2. **保留输入,重新复核**:v1 先跑一次(请求身份 1)→ 保存 409 →
   核对 → 复核;候选未变而旧结果立即显示过期 → 重跑以 v2 身份提交
   保持的候选(结论 ×2)→ 保存以 v2 基线恰一次 200 发布、关闭回
   清单并显示发布事实。上轮草稿隔离与未知不重发用例保持通过。
3. **分歧读取保持待核对**:核对时 form-authority v2、对象 v1 → 面板
   显示“两次读取不能拼成同一套…”,无采用/复核、零 PUT/分析;读取
   对齐后“重新核对”恢复为可采用的 v2 上下文。

**失败复现(真实失败保留):**临时中和 adopt/recheck 的两处
`setAuthority` 传递后,用例 1/2 如期失败于
`expectedVersion: 1`(即 B54-06 的复现:分析仍带旧身份);恢复后
18/18 通过。

### 原生 proof 扩充(scripts/rules_workspace_browser_proof.py)

在既有真实 Python/API/SQLite 夹具中加入双管理员冲突旅程:乙经真实
HTTP PUT 发布(200)→ 甲带 v1 基线保存被真实围栏拒绝(409
`configuration_version_conflict`)→ “读取当前 Active 核对”→ 采用 →
旧结果过期 → 显式单项测试;随后唯一一次显式 Save 以采用后的上下文
发布 200,回到清单。按实际请求核对:分析请求
`expectedRevisionId/expectedVersion/expectedDigest` 恰为乙发布的
Active 身份、`candidate.values` 为乙的新描述、HTTP 200、结论
“类型定义有效;可选关联规则试识别未运行”写入 evidence。分阶段证据:
浏览器恰 2 个 mutation(1 拒绝 + 1 发布)、窗口外零写、分析请求不
计入 mutation、可执行工作前后一致。

**计数语义更正(请 B 留意):**旧 `_activation_count` 查询的
`managed_configuration_audit` 表在 mediaflow 源码中并不存在,计数恒
为 0;上一轮“rules 发布记 rules_edit 而非 activate 行、激活计数不变”
实际是对不存在表的空计数结论。本轮改查真实表
`configuration_change_audits`,proof 现断言 journey 前后 `activate`
行恰 +2(乙发布 + 甲发布;被拒的 409 不 compose 任何行)、
`successor_draft_create`/`draft_edit` 恰 +4(2 次发布 + 2 次离线分析
暂存)、`validate` +2,并以 Active revisionId/digest 更替与
revisionSequence 单调前进佐证后继;`version` 字段(后继恒为 2,
`create_successor_draft` 固定起点,非发布计数)只记录不断言。其余
proof(files_toolbar/files_organize_discovery/rules_object_analysis)
仍查询同一不存在表,属既有范围外问题,本轮未动,提请后续任务处理。

### 实际执行的 Developer 命令与结果

- `python3 scripts/check_governance.py`:PASS(实施前、提交前各一次)。
- 根目录 `.venv/bin/python -m unittest tests.test_v2_rules_workspace_commands
  tests.test_v2_rules_object_analysis tests.test_v2_rules_workspace_previews`:
  184 tests OK(11.6s)。
- `git diff --check`:PASS。
- `web/` `npm run typecheck`:PASS;`npx eslint src/features/rules
  src/routes/router.tsx src/shared/ui/modal-card.tsx
  src/shared/navigation/destination-model.ts`:PASS;
  `npx prettier --check`(同范围):PASS。
- `web/ npm run test` 受影响批次 9 文件 157 项 PASS(13.5s;上轮
  154 项 + 本轮 3 项新用例)。
- `web/ npm run build`:PASS,产物 `index-B8zhZdNT.js`、
  `index-ByxQof0I.css`(含本轮新文案)。
- `web/ npm run test:e2e -- tests/e2e/rules-readiness.spec.ts
  tests/e2e/rules-identity.spec.ts`:17 passed(15.4s)。
- 原生主旅程第 4 次运行 PASS:
  `MF_PROOF_ARTIFACTS=$PWD/.git/validation-evidence/task54-1/developer-rules-workspace-b54-06`
  `.venv/bin/python scripts/rules_workspace_browser_proof.py` →
  `PASS: reference-aligned rules workspace through the real Python boundary`,
  33 张截图(新增 `stale-conflict-verify`、`stale-conflict-adopted-test`),
  evidence `b54_06`:乙发布 200、甲 409、分析请求身份 = 乙的
  Active 身份、结论非空、最终发布 200;审计
  `{activate:1, draft_import:1, validate:1}` →
  `{activate:3, draft_edit:4, successor_draft_create:4, validate:3}`,
  Active revisionSequence 1→5 / version 1→2,
  `unexpectedMutations=[]`。前三次失败保留并按真实行为修正:
  ①RO-2 后卡停在“单项测试”页,未切回“设置”导致名称不可见;
  ②③按 `version` 断言 +2 失败,据此改用真实审计表计数(见上)。
- 变更 proof 文件:`ruff check`/`ruff format --check` PASS,
  `python -m compileall -q scripts/rules_workspace_browser_proof.py` PASS;
  根预存 `.explore_adapter_block.py` 未触碰。

### 本轮用时与测试占比

本轮总用时约 55 分钟;测试执行累计约 7 分钟(受影响单测与静态检查约
1.5 分钟、build/e2e 约 1 分钟、proof 4 次约 4.5 分钟),占比约 13%,
低于本轮要求的 30%。

### 剩余风险与限制(交 B)

- T4 全量门禁(Python/Web 全量、Node E2E、打包与源码外 smoke)及其余
  三个原生 proof(analysis/identity/classification)归 B;本轮未执行。
- “activate 恰 +2”为本轮新断言口径(更正旧空计数),B 复跑时可直接
  对照 evidence `safety.auditBefore/auditAfter`;如对发布计数口径有
  不同意见请在审查中指出。
- 核对双读分歧在原生层由单测用例 3(Fetch 桩)覆盖,proof 未构造
  服务端两读分歧夹具;与既有 B54-01 双管理员原生复现的分工不变。
- 未改后端并发规则、分析协议、`modal-card`、preview 后端/API;Slice/
  Roadmap/Progress 与产品文档本轮未改。

## B Review Result

~~~text
Reviewed: 6351b60433f0e79dac6f5f7150884a1fecb0da43..576aca4562689d5b663eba1789837357711b5979
Implementation: 7584bd3fd5274822b403e8b9758dcc87d9322670
Decision: FIX REQUIRED
Task blocker: B54-07 — 普通编辑弹窗使原清单上下跳动
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP
~~~

已独立核对完整 Task Base..Head、当前已提交 Slice 合同及三项结果。实现到本轮交接
`7584bd3f..576aca45` 只有 Task 文档，生产构建／原生／全量测试匹配当前实现。工作区
main，预存系统元数据、日志、调查材料和私有文件保留；本轮只提交根 Task 的审查结果。

### 已通过的修正与 Slice 结果

- B54-06 已通过真实复现：甲持有 v1，乙发布 v2，甲保存收到真实 409，核对并采用后，
  单项测试与显式重跑均使用 v2 revisionId／sequence／digest 和乙的新对象，HTTP 200，
  显示真实结论。原生主脚本还验证旧结果过期、采用后再次明确保存 200。
- 上轮草稿隔离、Back→继续→刷新／重认证、Create/Copy 恢复、双管理员草稿采用／复核、
  真实发布丢响应后的未知核对均在本候选重新走通，未自动重发保存。
- 七类各自的 Add/Copy/Edit 共 21 个真实入口均打开当前卡片；七类 Edit 的单项测试均
  返回真实 200、Provider 调用与媒体 Storage 读取均为 0。其定义／条件／引用／命名／
  分类／操作结果保持各自作用域，不作全图成功声明。
- RO-2 的卡内分区、字段／内部动作和结论层级已有交付；检查了七类桌面、390px 与矮
  窗口截图、底栏／关闭可达及 Tab 回圈。RO-3 的表单完整预览移除、概览完整流程和
  共享 API 保留已通过当前原生／Python 回归。复杂内容与慢读取的最终视觉检查仍随
  修正候选完成，不把现有顶层截图等同于全部视觉验收。
- RO-1 的“背景位置稳定”未完成：如下 B54-07。保持同一 Task，不规划新 Task，暂不
  提交 Slice Closure Packet；Slice／Roadmap／Progress 和既有接受事实不变。

### B54-07 · P1：普通编辑弹窗挤动背景清单

**真实旅程：**1536×1000 下打开识别类型清单，搜索 `Normal`，点击现有行“编辑”。
弹窗出现时，顶栏新增不可用的文件搜索框，主内容前新增 `Edit rule object`；原清单页头、
分类导航与表格一起下移 34px。点击“取消”后三处又一起移回，搜索仍为 `Normal`、
scrollY 始终为 0。具体读数：页头 y 78→112→78，导航 158→192→158，表格
375→409→375。此处是实际画面上的整体位移，非仅 CSS 值或 DOM 形式差异。

这未满足 Slice RO-1 的背景位置稳定及 AC-2/7；既有独立整页 Edit 的 Shell 呈现进入了
新的列表背景。根因在 `AppShell.tsx`：`searchIsRules` 只识别 `/rules`，而当前 Edit 路由
已由 `RulesEditPage` 挂载同一 `RulesWorkspacePage`，仍被 Shell 当成旧整页入口。

**开发指导：**复用已有 Rules 主页面身份，将 Rules 清单与合法 Edit 路由按同一清单
表面处理，统一顶栏占位搜索与 `.mf-page-context` 的显示判断。保持清单页头／导航／
筛选／表格位置，保留卡片自己的类别／名称／ID 和原 Edit URL。仅调整必要的 Shell
判定，不改其他页面布局、认证、发布或导航模型；原 Base/Goal/Scope、High/T4 保持。

**验收与 Developer 受影响测试：**

1. 从七类实际清单逐个打开编辑并取消／保存返回，原背景不因增删旧整页说明而上下
   移动；列表／Add／Copy／Edit 使用一致的 Rules Shell，原筛选／合法滚动／回焦保持。
2. 旧 Edit URL 的直达／刷新／重认证仍打开准确对象，桌面／390px 的顶栏与原列表协调；
   同页弹卡不重播主页面动画。以同视口前／中／后截图和原列表元素位置核对。
3. 在现有 `AppShell.test.tsx` 与 Rules 旅程补回上述实际约束；扩充主原生脚本的同视口
   编辑返回场景，保留已通过的领域／发布／未知／B54-06 断言。不要另建测试平台。
4. Developer 跑 `web/ npm run typecheck`，变更文件的 ESLint／Prettier，以及
   `npm run test -- run src/shared/ui/AppShell.test.tsx src/features/rules/RulesWorkspacePage.test.tsx src/features/rules/RulesEditPage.test.tsx src/routes/router.test.tsx`；
   新构建后跑原 Task 的 Rules 原生主旅程，变更 Python proof 的 Ruff／compileall。
   其他直接受影响测试沿用 Required Tests；全量和最终矩阵仍由 B 负责。修正仍在 Task54.1。

### 本候选 B 全量、原生与打包证据

本机目录：`.git/validation-evidence/576aca45/task54-1-b/`。以下结果属于固定候选，
不能作为后续可执行变更已通过的声明。

| 检查（工作目录） | 实际结果／日志 |
|---|---|
| 治理、完整 Base..Head `git diff --check`（根） | PASS |
| `.venv/bin/python -m unittest discover -s tests`（根） | 2678 tests OK，7 个既有外部服务／endurance skip，312.615s；`python-full.log` |
| `npm run test -- run`（web） | 99 文件、1516 项 PASS，148.57s；`web-full-unit.log` |
| `npm run test:e2e`（web） | Node 假服务 Chromium 268 项 PASS，190.95s；`node-e2e.log` 与产物目录 |
| `npm run typecheck/lint/format:check/build`（web，各独立 npm 命令） | 全部 PASS；对应日志。新资产 `index-B8zhZdNT.js`／`index-ByxQof0I.css` |
| Ruff（根） | 原始 `ruff format --check .`／`ruff check .` 被预存未跟踪 `.explore_adapter_block.py` 语法错误挡住，原日志保留；所有受版本控制 Python 文件的 format/check PASS（355 文件）。未修改或纳入该调查文件 |
| compileall、pip check、两份 example config validate（根） | 全部 PASS；对应日志；禁止依赖检索 exit 1、无匹配 |
| 新 wheel 与 `scripts/wheel_smoke_test.py <exact-wheel>`（根） | 构建、安装至独立临时 venv、源码外 CLI／持久化／消费者 smoke PASS；`wheel-build.log`／`wheel-smoke.log` |
| `scripts/rules_workspace_browser_proof.py`（根，精确新资产） | PASS，33 张截图；真实乙发布→甲 409→核对采用→v2 分析→明确发布。真实审计 activate 1→3、Active sequence 1→5、可执行工作不变；`workspace.log` 与 workspace/evidence/matrix |
| 原有 analysis／identity／classification 原生证明（根） | 三者 PASS；`analysis-proof.log`／`identity-proof.log`／`classification-proof.log`。B 在忽略目录仅将旧整页／抽屉／表单完整预览选择器适配为现有卡片和对象测试；原领域、特殊 ID、路径／显式转换、零效果断言保留，原始及适配 JS 并存。analysis 审计观察使用真实表名，入口仍为原脚本的真实 Python/API/SQLite 夹具 |
| 补充真实旅程（同一 Python 夹具） | `recovery-journeys.log`／`native-evidence.json`：上轮恢复场景 PASS；`surfaces-evidence.json`：21 个模式、7 个离线局部结果及三视口记录，Active 未变；`background-evidence.json`：B54-07，截图 background-list/edit |

wheel：`mediaflow-2.0.0.dev0-py3-none-any.whl`，SHA-256
`20118bd0832468b77f6687126ed2c314b031505d7450591938b5f7b8aa991a92`。
Docker／依赖／容器执行路径未变，广域 Docker 发布矩阵不适用；未声称外部服务或
endurance 已运行。原生矩阵虽通过多个入口，B54-07 仍使本 Task 无法 PASS。

本轮并行测试的实际墙钟区间约 335 秒（并行重叠不重复计时；各进程 real 累加约
733 秒），记录在 `test-wall-time.json`；本轮审查总时长超过 12 分钟，按实际墙钟占比
低于用户要求的 50%。未读取运行数据库、私有配置或用户媒体。
