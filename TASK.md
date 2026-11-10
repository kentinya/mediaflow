# NO ACTIVE IMPLEMENTATION TASK

[Slice54](SLICE.md) 已在 6351b60433f0e79dac6f5f7150884a1fecb0da43 激活为 ACTIVE。
下方是用户“代替 B 规划第一个 Task”授权下完成的 **Task54.1 规划草案**，不授权实现。
待用户授权实施后移除本通知，保留同一 Task ID／Base／Goal／Scope，按工作流进入实施。
本轮不启动 Developer，不推送或部署。

Planner: A acting as B — USER AUTHORIZED FIRST-TASK PLANNING ONLY.
该角色例外不包含 Task 验收或同一 Slice 的最终 A 验收。Developer 不得自审；后续 B
独立审查实际实现，再由 A 按工作流审查整个 Slice。Slice53 的接受、A53-01 原退回／
修正及验证限制保留于 [固定关闭记录](https://github.com/kentinya/mediaflow/blob/8bc3ef905a76b96ef8ec327154b92e9b9972ea05/SLICE.md#closure-packet-and-a-final-review)。

Next Action: USER AUTHORIZES TASK54.1 IMPLEMENTATION

---

# Task 54.1 — 七类整理规则统一弹窗、可读表单与单项检查

Authority: committed [Slice54](SLICE.md)，激活检查点
6351b60433f0e79dac6f5f7150884a1fecb0da43。生命周期、测试归属及关闭规则仅由
[Development Workflow](docs/development-workflow.md) 定义。阅读角色对应的
[B experience](docs/agent-experience/task-planner-reviewer.md) 或
[Developer experience](docs/agent-experience/developer-implementation-role.md)。

~~~text
Task ID: 54.1
Task Type: SLICE
Parent Slice: 54
Status: PLANNED
Task Base: 6351b60433f0e79dac6f5f7150884a1fecb0da43
Difficulty: High
Test Level: T4
Planner / Reviewer: A acting as B for planning only / independent B review pending
Implementation Authorization: NOT GRANTED — PLANNING DRAFT UNDER NO ACTIVE IMPLEMENTATION TASK
Implementation Checkpoint: NOT SET
~~~

## Goal

完整交付 Slice54 RO-1／RO-2／RO-3 与 V2-RULES-010／011／012：用户从七类清单添加
（含空态）、复制或编辑进入协调弹窗，在同一对象上下文内修改、按需单项测试，一次
保存发布后回原清单。概览独占完整流程检查；编辑深链／刷新／重认证、输入恢复和
准确发布失败／未知核对保持完整。本 Task 不扩大或关闭 Slice。

完整旅程见 [Product Experience TARGET](docs/product-experience.md#target--organizing-rules-dialogs-and-readability-slice54-active)，
七类内容矩阵及边界见 [SLICE.md](SLICE.md)。实际代码缺口：

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
   由最终 A 接受后协调，不提前宣告接受。本轮规划本身不执行本节实施步骤。

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
以下是实施后必需命令，**本轮规划未执行产品验收、不作通过声明**。原生证明必须使用
精确生产构建、临时库／本地假 Provider，禁止私有配置、运行数据库或用户媒体。

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
本轮只规划，后续实施须用户授权；推送、发布与部署不在授权内。

## Developer Completion Report

尚未实现，Implementation Checkpoint NOT SET。实施后填准确 checkpoint、READY FOR B REVIEW、
实际变更／关键决定、affected commands／结果／失败／限制和剩余工作；全量仍待独立 B。

## B Review Result

尚未审查实现，不作 PASS／FIX REQUIRED。后续记录 Reviewed Task Base..Head、
实际独立审查／验收／失败／限制／具体阻塞和同 Task 修正。Task PASS 后重评全部
Slice RO-1／RO-2／RO-3 与必需表面；全满足则停止规划，完成 Slice-final、交
SLICE READY FOR A REVIEW，由 A 终审，不自行宣告 Slice CLOSED。
