# Task 45.2 — 新建整理的同页摘要与精确确认

遵循 [Development Workflow](docs/development-workflow.md)，从属于已提交的
[Slice45 Contract](SLICE.md)。规划/审查读取 [B 经验](docs/agent-experience/task-planner-reviewer.md)，
实现读取 [Developer 经验](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: 45.2
Parent Slice: 45
Status: PLANNED
Task Base: 1fbb709e9273d9b6b7fa3648a1eb2cfceaf0b743
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Next Action: DEVELOPER IMPLEMENTS TASK 45.2
```

## Goal

操作者从任务中心或 ResourceLibrary Files 选择真实文件/目录，明确准备后在同一创建界面
查看完整且精确的计划摘要，选择就绪子集并明确确认整理，随后跟踪真实 Worker 执行及逐项结果。
完成 **RO-2** 及其必需的 **RO-6 共享编排/验证部分**；沿用 RO-1 查询与 RO-4 详情/结果能力。
普通旅程不再要求独立 Scan、手工 Freeze/内部意图管理或独立 Preview 页面。

适用要求：V2-OPS-006/009/010，V2-UX-001–003，V2-AUTH-001–003，V2-SAFE-001，
UX-001–007/010，REQ-LIB-*、REQ-SCAN-002/003、REQ-ORG-*、REQ-ATT-*、REQ-TASK-*、
REQ-RESULT-*、REQ-SAFE-*。具体创建旅程见 [最终页面规范第 3 节](docs/task-center-page-spec.md)。

## Why This Task Exists / Previous Review

规划前治理 PASS；已提交 `HEAD:SLICE.md` 与 Roadmap 均为 Slice45 ACTIVE，工作树 Contract
与 HEAD 一致。Slice Base 不变；Task Base 是规划前的实际 HEAD，不随后续规划提交移动。

**Task45.1 B PASS：** 审查 `99cbf2fd9233cd01d9b6d9c8d29748a52bd7a914..53299fd5b3105919c240b0067eac3ebfa889ddc6`；
报告 Head 为本 Task Base（两者间仅 TASK.md）。九视图查询、当前问题及 Task/type 文件定位
完成；上轮 pre-Task 修复遗漏和主体布局 P1 已解决。B 独立相关回归 262 tests，通过；隔离候选
全量 2461 tests / 174.758s / OK（7 skipped），并复现真实配置失败、决定/恢复转换与原生浏览器。
匹配原始证据复用 Web 全量、真实 Python 浏览器和 Docker security 门禁。主工作区全量的一个
schema48 环境失败未被改记绿；人工 schema48 Base 对照及干净候选通过证明其环境性质，未读取
用户运行库。完整 B 判定/原始证据：
`.git/validation-evidence/53299fd5b3105919c240b0067eac3ebfa889ddc6/b-review5-20261016/INDEX.md`。
仅本地可达，未推送。历史 Task45.1 原计划和 Developer 报告保留在 Task Base 的 TASK.md。

PASS 后复核：RO-1 / S-1 完成；RO-2 / S-2 未完成；RO-3 / S-3/4 的列表定位完成而处理/摘要
未完成；RO-4 / S-5 保留既有详情控制，继续时同页重新授权尚缺；RO-5 / S-7 未完成；
RO-6 / S-6 的新创建/恢复编排及 Slice-final 仍缺。因此 **NEXT TASK**，不提交 Closure Packet。

实际实现可以复用，但尚不能满足新创建结果：

- `OrganizeNewPage.tsx` 只选择资源库后跳 Files；`StorageFilesPage.tsx` 将单/多文件送往
  intent，把目录/混合选择送往 discovery，然后分别跳 intent/Preview 页面。
- `OrganizeDiscoveryPage.tsx` 要求显式 Freeze，再进入 intent；`OrganizeIntentPage.tsx`
  生成 Preview 后再跳 `OrganizePreviewPage.tsx` 确认。不能只把这些页重命名为“摘要”。
- `MediaDiscoveryService` / `MediaDiscoveryWorker` 已有受限发现、真实稳定观察、过滤、附件
  归属、固定配置、控制及原子 finalize；应复用并在显式准备授权下安全组合内部步骤。
- `ManualOrganizeIntentService` / `ManualOrganizePreviewService` 已有 live Storage 来源、
  生产策略与完整计划、逐项 findings、只读保护和不可变 Preview；但完整分析目前由 API
  同步调用，长准备仍需接入既有持久工作/常驻 Worker，不能靠浏览器维持长请求。
- `ManualOrganizeExecutionService.begin_web_execution` / `ManualOrganizeExecutionWorker`
  已有精确选择、独立影响许可、原子准入和真实执行；`OrganizePreviewPage.tsx` 有可复用的
  摘要展示、确认与未知响应对账，现有返回上下文/详情/结果无需另建。

这是来源选择到执行结果的完整跨层单元，不按摘要字段、入口或文件/目录分别拆 Task。
后续只按仍缺结果规划恢复处理/继续授权和全入口 Scan 退役，不预先授权下一 Task。

## User Journey

| 环节 | 本 Task 必需行为 |
|---|---|
| 用户目标 | 理解所选真实来源将如何整理，只执行明确确认的精确就绪范围 |
| 入口 | 任务中心醒目的“新建整理任务”；Files 单项、多项、文件夹/混合选择的整理动作 |
| 可见状态 | 当前资源库/范围；持久准备阶段/等待/失败；发现完整性、主文件与附件、就绪/未就绪；同页精确摘要及当前允许动作 |
| 可用动作 | live 选择范围；明确准备；安全补正并重新准备；展开逐项方案；选择就绪项及必要影响许可；“确认整理 N 项”；查看已有执行及返回 |
| 成功结果 | 一次原子准入精确子集；在原生界面跟踪 Worker/OrganizerExecutor，独立结果可回到任务中心/Files |
| 失败结果 | 来源变化、边界不完整、未就绪、缺权限/Worker/pin、重复/过期/未知提交均解释受影响范围与持久状态，不伪造执行失败或成功 |
| 恢复路径 | 修正准备输入/依赖、读取已有准备/执行、明确更新摘要或缩小范围；未知响应先核对精确请求，不能自动重发或换 pin |

## Implementation Scope

### 1. 一个创建工作区与所有新建入口

- 在共享 Shell 内提供原生创建工作区，复用 Files 的 ResourceLibrary/live Storage 浏览及选择
  行为；选择器可以嵌入工作区或复用现有组件，不要求复制任意 Storage 路径/内部 ID。
- 任务中心新建与 Files 单项/有界多项/目录/混合选择进入同一应用旅程，保留各自返回上下文。
  创建只提供整理；MediaLibrary 不成为来源。普通文件维护不进入媒体策略流程。
- 当前创建界面贯通准备进度、可补正 findings、同页摘要与确认；不再要求操作者管理
  discovery→Freeze→intent→Preview 四套页面。安全、无新 human intent 的内部步骤由既有
  持久编排承接，读/刷新/重连本身不提交后续命令。
- 新建入口不提供独立 Scan/Preview 替代步骤。已有创建深链/准备历史应到达对应可读状态或
  当前创建工作区，不因打开旧链接自动创建工作。后续恢复仍使用的旧 Preview 表面在该 Task
  保持兼容，不能提前切断尚未重构的恢复/继续路径；通用诊断 DryRun/Rules 不退役。

### 2. 显式、耐久且零媒体变更的准备

- Domain/ports → Persistence → Application → API/Worker → typed Web/测试一起完成。
  复用已有发现/意图/完整生产 Preview/planner，只补必需的耐久协调、读投影和准入；
  不建立第二套队列、策略解释器、配置或恢复引擎。长发现/分析复用常驻 Worker 及现有工作模型。
- 准备请求有有界范围和可对账的耐久身份，迅速返回；显示实际排队、阶段、稳定等待、控制及
  per-item findings。刷新/断连/重启能读取相同准备，不要求原 HTTP/浏览器存活。
- 单文件、多文件与目录都应用原固定配置的扩展名/include/exclude/depth/临时文件过滤和真实
  elapsed 稳定观察；必要观察在整理内部完成，不能提示先手动 Scan、依赖 FileIndex 授权、
  降低稳定性或因首次观察就假定稳定。复用已有附件/Trailer 归属，避免重复主文件。
- 完整分析使用同一 Recognition→TypePolicy→Metadata Provider→Naming→Classification→Plan
  语义及 capability/conflict/hash/attachment 规则。保持 Type C 复用 A 策略仍为 C。
- 准备全段零 Storage mutation、不授予执行权限；允许用户显式准备所必需的 Provider 访问，
  GET/导航/轮询不调用 Provider。未就绪仅作为准备 findings，不制造正式执行待办。
- 配置在准入边界固定；合法历史 pin 不因新 Active 发布失效或改绑。缺失/损坏原上下文明确
  拒绝并指引；显式开始新方案与旧准备区分。处理来源变化须更新精确摘要及新意图。

### 3. 同页精确摘要、补正与明确确认

- 摘要显示来源/范围与发现完整性、主文件/附件数、就绪和未就绪项、操作、目标媒体库/目录、
  可展开来源→目标与识别/身份/策略解释、冲突/capability、覆盖及来源清理的实际影响。
  未知/不可用/排除与失败区分，不能把 Preview 成功叫整理成功。
- 未就绪项保留自身输入、原因和合法补正入口；复用已有允许的类型/身份等选择及配置修复指引，
  在准备界面完成必要的安全补正与显式重新生成摘要，不借正式执行恢复队列伪造 blocker。
  不允许任意 provider payload、目标路径或绕过 TypePolicy 的独立策略组合。
- 有界完整来源和必要分析完整性是可确认前置。material budget/depth/time/source 上限等
  不完整拒绝可执行前 N；已有 isolated read-error subset 仅在生产规则允许且明确展示缺口、
  用户显式接受已知范围时沿用，不能用普通 checkbox 绕过 material refusal。
- 用户选择精确就绪子集，按钮显示“确认整理 N 项”。确认单独表达 mutation intent，覆盖与
  来源清理分别按实际计划及政策许可请求。未选/未就绪保持独立可读、可补正，不自动加入
  当前或后续执行，不伪造为 success/ignore/正式执行失败。
- 确认复用现有原子 admission/one-shot authority、RBAC、source/plan/config/version/子集
  校验、claim/lease/fence 和 OrganizerExecutor。API 与 Web 同权威，浏览器不获得 raw token。
  不新增操作、fallback 或破坏性权限。
- 并发/重复确认收敛为同一精确执行或明确拒绝，不重复消费权限。丢响应/重连先查该次耐久
  请求；无法证明时保留 unknown 和下一步，不猜最近记录、不自动 POST 重试。
- 受理立即可跟踪真实执行/Task/Result，关联准备与确切子集。未选项仍能从本准备读取/继续
  补正；重复打开不自动执行。执行后的问题复用现有诊断/恢复入口；本 Task 不重做五类恢复。

### 4. 兼容与所有权

- 必要增量 schema/索引/关联保留旧 intent/Preview/Scan/DryRun、Result、pin、执行授权及历史
  意义，补真实旧版本迁移/重开/失败原子性证明；不要仅为页面步骤重建数据模型。
- 限创建/Files handoff、发现/准备/Preview、既有 execution、必要 Worker 装配/注册/ready、
  统一库存关联、返回上下文和测试/验收工具。普通 Files/MediaLibrary 命令及其他页面不重构。
- 不修改 SLICE.md、Roadmap、Progress、稳定需求或已接受 CURRENT 声明；如确需改变架构
  Contract 或验收含义先交 B/A。报告事实与实际架构影响，供 A 收尾 reconciliation。
- 保留所有预存脏文件：`docs/pics/操作与任务.png` 的删除意图，未跟踪的两张自动化页图、
  各处 `.DS_Store`、`output/imagegen/slice45-task-center-v1.zip`。
  `config/alist.json` 保持 ignored/untracked/unstaged，不读取/输出私密配置。

## Acceptance Criteria

- [ ] **AC-1：** Task Center 与 Files 的单/多文件、目录及混合来源完成同一个原生创建旅程；
  live ResourceLibrary 权威、返回、深链、窄屏和键盘可用；没有独立 Scan/Preview 创建步骤。
- [ ] **AC-2：** 显式准备有耐久进度和恢复读取，长发现/完整分析经真实 Worker；合法过滤、
  附件和 elapsed 稳定观察真实，GET/重连无工作或 Provider 副作用，确认前零媒体变更/零授权。
- [ ] **AC-3：** 同页摘要完整可解释，逐项来源/目标、附件、影响和完整性真实；未就绪可补正，
  未选/未就绪状态独立保留；material incomplete 不允许执行任何 first-N prefix。
- [ ] **AC-4：** “确认整理 N 项”只原子准入精确就绪子集及明确允许的影响，实际 Worker/
  OrganizerExecutor 结果与摘要一致；成功、未选和准备 findings 不相互改写。
- [ ] **AC-5：** 来源/版本/方案变化、缺 pin、权限或 Worker 不足、并发/重复和丢响应均有
  原生可行下一步；合法旧 pin 保持，unknown 先核对、无自动重发或 uncertain replay。
- [ ] **AC-6：** 旧历史和仍在用的恢复/继续/诊断读取兼容；无第二套权威，RBAC/脱敏/
  memory-only auth/Storage confinement/Type C 身份等不变量及普通 Files 行为不回归。
- [ ] **AC-7：** T4 全部门禁有精确候选与耐久原始证据；production build 和容器真实 Worker
  上完成新创建摘要/确认旅程，实际视觉检查通过；checkpoint 只含本 Task。

## Required Tests

按 workflow 分阶段验证。T4 来自持久准备/Worker、精确授权与实际 mutation 边界；不因主要
呈现为页面整合降级。每个命令记录 cwd、候选和实际结果。现有环境主工作区默认 runtime 库
比本分支新；全量在同一候选的干净隔离 checkout 执行，保留用户库，不改测试/隐藏失败。

### Development and correction feedback

1. 根目录：`.venv/bin/python -m unittest tests.test_media_discovery tests.test_manual_organize_intent tests.test_manual_organize_preview`：
   live 来源、稳定性/完整性、附件、pin、prepare findings 与 Type C。为新增持久准备行为补测试，
   如新建模块，报告加入实际命令，不用现有测试数代替新行为。
2. `.venv/bin/python -m unittest tests.test_v2_manual_organize tests.test_manual_organize_execution tests.test_organizer_mutation_authority tests.test_operations_task_center tests.test_operations_run_inventory`：
   精确子集、独立影响许可、准入原子性/去重、Worker/fence、非重放与库存不伪造待办。
3. `web/`：`npm run test -- run src/features/operations src/entities/operations src/features/library src/shared/navigation src/shared/api`：
   新建/Files 返回、同页阶段/摘要、选择/补正、拒绝/unknown、401/403 和严格 typed contract。
4. 扩展真实 `operations_inventory_harness.py` 与 `operations-inventory.python.spec.ts` 的创建
   分支，通过生产 API/SQLite/Worker 生成状态；fake E2E 与组件测试作反馈，不能替代真实链路。
   覆盖单项/多项/目录/混合、附件、不稳定/排除/空范围、未就绪补正、明确就绪子集；
   budget refusal、读失败合法子集、来源变化、Active A→B 时旧 A pin、原 pin 不可用、
   未知准备/确认准入、并发、Worker 缺失与刷新/重连/重启。明确检查 mutation 与 Provider 计数。

### Final checkpoint gates

最终 executable candidate 先解决已知失败，再完成全部以下门禁；full 包含 focused cases 时不
机械重复。隔离 checkout 使用本环境解释器的绝对路径或安装同一已声明依赖，并记录 identity。

- 根目录：`.venv/bin/python scripts/check_governance.py`、`.venv/bin/ruff format --check .`、
  `.venv/bin/ruff check .`、`.venv/bin/python -m unittest discover -s tests`、
  `.venv/bin/python -m compileall -q mediaflow tests scripts`、`.venv/bin/python -m pip check`。
- `.venv/bin/mediaflow --config config/strategy.example.json config validate` 和
  `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`；
  `rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml` 无匹配（exit 1）；检查新增依赖和 C 身份
  Preview/实际执行回归。仅测试 tmp/fake/local-server，不接生产媒体或真实外部 Provider。
- `web/`：`npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run test -- run`、
  `npm run build`、`npm run test:e2e`。共享 Files/路由/返回/typed contract 要求完整 Web 回归。
- `web/`：`npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts`；
  `npm run test:e2e -- --config=playwright.python.unicode-principal.config.ts tests/e2e/operations-principal-identity.python.spec.ts`。
  新建实际旅程加入前一 spec 的真实 harness；真实 Worker 完成，不以静态响应伪造摘要/执行。
- production build 实际新建→准备→摘要→确认→结果，含 Tasks/Files 返回、就绪子集、补正、
  影响确认与拒绝/unknown/重连；1536×1024 和窄屏/键盘截图/trace。人工查看可见状态、焦点、
  遮挡与信息层级，不能用截图脚本成功代替验收；九视图关键回归复用实际匹配测试覆盖。
- 准备增加/改变 Worker 装配时验证安装及容器边界：
  `.venv/bin/python -m pip wheel . --no-deps -w dist`；
  `.venv/bin/python scripts/wheel_smoke_test.py <本候选生成的确切 wheel 路径>`，并对安装版本
  实际加载新增准备 consumer（扩展 smoke 或增加等价隔离运行，报告精确命令/入口）。
- `.venv/bin/python scripts/docker_files_organize_discovery_browser_proof.py --image mediaflow:task45.2-creation`：
  将已有 isolated production/browser proof 调整为新同页旅程，保留发现/完整性/附件/零变更
  断言，证明常驻 Worker 的长准备、明确子集确认、真实结果和产物 identity。
- `.venv/bin/python scripts/docker_release_security_smoke_test.py --image mediaflow:task45.2-security`：
  仓库 release-security 既有必需门禁。两项 Docker 可共用经证明相同的候选 image digest；
  无需无差别复制 Docker 全矩阵。Docker 不可用/失败如实报告，不隐藏为 PASS。
- 有 schema 变更时将真实旧 schema45 及实际受影响更早 fixture 的 migration/reopen/
  failure-atomicity 回归纳入全量，证明旧历史/pins/权限无改写；无变化则报告 diff，不虚构通过。
- `git diff --check`；完整范围/manifest、私密文件、全部冻结文件和预存脏文件保留检查。

### B independent verification

B 核对 Task Base..Head、原始日志和身份，独立在 production build/真实 Python SQLite Worker
复现：从 Task Center 及 Files 的代表性来源选择开始，准备实际显示摘要；确认前零 mutation、
未就绪不进正式待办；选择少于就绪总量的子集，明确确认后仅该子集/附件实际执行，未选保持；
来源变化拒绝与同页更新、未知提交对账、合法旧 pin 和重连读取。实看桌面/窄屏关键截图。
检查完整 Web/Docker/wheel/迁移等适用门禁的匹配原始证据，缺失/矛盾才重跑，避免机械重复。

### Evidence and rerun rules

沿用 workflow 的 `.git/validation-evidence/<full-source-sha>/<run-id>/` 或 CI artifact 索引，
包括 SHA/dirty content、命令/cwd/runtime/lockfile、安全 fixture/Worker 设置、产物/image/wheel
摘要、exit/counts/skips/duration、首次失败/重复、原始 logs/trace/截图及 AC 映射。`/tmp` 仅
作隔离执行场所，不作唯一证据交接。document-only successor 先证明 executable inputs 不变；
修正源码/测试/harness/config/产物后的 T4 candidate 重做完整指定门禁。缺失/failed/unavailable
如实报告，不能用 Task45.1 的通过声明替代新创建行为证据。

## Non-goals

- 五类恢复的专用决定→安全分析→同页摘要→确认继续，以及暂停任务同页重新授权；这是 RO-3/4
  的下一主要旅程，本 Task 只保留现有兼容与执行后入口，不提前重构它。
- 独立 Scan 在所有 API/CLI/Worker/旧重试入口的全局退役及存量安全停止（RO-5）；
  本 Task 的整理路径自身不能依赖独立 Scan。通用 DryRun/Rules 保留。
- 冻结 Slice43、Automation 定义/模式/Run once/engine settings；不导入冻结分支。
- 跨任务批量 mutation、批量覆盖、任意历史 Reprocess、通用回滚、自动 uncertain replay、
  新 Provider/队列/身份/权限体系、MediaLibrary Organize、Upload/Download 或提高既有界限。
- 非阻塞视觉/文案/可选证明微任务、其他页面重构或 A-owned 文档的交付状态调整。

## Developer Completion Report

Not started. 报告实际变更、命令/结果、候选 SHA、证据索引、剩余 Slice 结果、风险与必要架构
影响；不宣布 Task PASS 或 Slice 完成。复用经验候选至多 1–3 条，供 A 收尾合并。

## B Review Result

```text
Reviewed: NOT REVIEWED
Decision: PENDING
Slice Required Outcomes all satisfied: NO
Next: DEVELOPER IMPLEMENTS TASK 45.2
```
