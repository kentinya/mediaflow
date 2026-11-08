# NO ACTIVE IMPLEMENTATION TASK

PATCH-20261109-2 已由 B 验收 PASS。下方为本次接受的完整 Task／验收记录；不授权新实施。

# Task PATCH-20261109-2 — 查询类型统一与已确认元数据的整理摘要续接

```text
Task ID: PATCH-20261109-2
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PASS
Task Base: 233f6a25769856087d10cb4483c0f1a621a76546
Difficulty: Medium
Test Level: T4
Planner / Reviewer: B
```

用户已明确激活本 Task，并于本轮同意取消跨次整理的历史身份自动复用。
当前实现已完成独立 B 验收，结果 PASS；以下规划与此前返工记录作为本 Task 历史保留。
固定 Base、Difficulty／T4 未变；本次 B 仅验收并收尾，未修改产品源码。

Authority：用户原五点最小修正方案，以及本轮同意的调整：新一次整理重新识别，当前任务继续使用本次已保存的候选；按 [Development Workflow §3.1](docs/development-workflow.md#31-independent-minor-bugs) 处理已有 Rules／Files／Task 恢复旅程的独立缺陷，不创建或重开 Slice。

### Goal

TMDB MetadataPolicy 只用“查询类型”决定允许的查询和身份类型。移除策略“媒体类型”这一重复控制；保留识别结果、候选和 MediaIdentity 自身的电影／电视剧类型，继续驱动正确 Provider 查询、命名和分类。新一次整理不自动带入历史 TMDB 编号及类型，而是按当前来源与查询类型重新识别；本次任务人工确认候选或在整理意图页保存已有候选后，重新分析继续使用本次已保存的编号和类型生成摘要，不重复要求确认同一候选。

完整旅程：整理规则编辑 TMDB 策略 → 保存并读回实际配置 → Files 整理／Task Center 继续原任务 → 展示当前识别和已有合法候选 → 保存候选及类型 → 显式重新分析 → 查看同一工作上下文的摘要 → 另行明确确认执行。保存选择和分析始终零媒体变更。候选无效、策略不兼容、来源／版本变化、Provider 失败时，显示失败阶段、已保存状态及下一步；未知提交先核对已有状态，不自动重发。

需求依据：`REQ-META-001/002/004–008`、`REQ-REC-004`、`V2-RULES-002/004–009`、`V2-OPS-010/012`、`V2-UX-001–003`。遵循 [Rules 旅程](docs/product-experience.md#recognition-and-rules)、[人工整理](docs/product-experience.md#manual-organize)、[逐项恢复](docs/product-experience.md#tasks-results-and-per-item-recovery) 及 [人工整理契约](docs/architecture.md#manual-organize)。既有不可变 pin、来源约束、权限及确认授权保持；不引入新的恢复种类。

### Observed code gap and baseline

以下保留初始 Base 的缺口定位，并标明本轮按当前实现核对的变更点；已运行结果另见 B Review：

- `domain/metadata.py:MetadataPolicy.query_type` 仍从旧 `media_type` 回退；`configuration_objects.py`、`strategy_user_configuration.py` 仍解析／输出策略 `mediaType`。V2 `RulesObjectForm.tsx` 仍并列展示两种控制，`rules-form.ts` 校验／序列化也保留重复字段。
- `application/manual_organize.py` 在 Base 上用策略类型补历史编号；当前候选改为从 evidence 取类型，但 `_default_choice/files_choice_for_source → _choice_for_type → _result_media_type` 仍会将历史身份自动带入新意图。本轮要求移除这条自动初始化路径；不扩展历史类型读取。
- `manual_organize_preview.py:_identity_compatible/_durable_identity_compatible` 和 `strategy_test.py` 的 durable identity 分支仍依赖策略 `media_type`，与已有按 `query_type` 校验的候选选择分支不一致；`task_item_recovery.py` 又直接检查 `media_query_type`。
- `metadata_review.py` 已保存所选 Provider、编号和类型；共享分析已有绑定决定／复用身份入口，需打通其兼容校验及消费链，不另建确认系统。
- API 已投影 `allowedMetadataIdentities`，`entities/operations/organize.ts` 已解析，`api-client.ts:updateOrganizeChoice` 已支持 metadata；`OrganizeIntentPage.tsx:ChoiceEditor` 没有候选控件，提交也没有带所选 metadata。

初始规划前 HEAD 为 Task Base。本轮调整前：仓库 `/Users/songzhidong/mediaflow`，分支 `main`，
HEAD `cad6d35cf1e0a58b5a8af9a0ea06411bcf1a0e9c`；治理检查 PASS，暂存区为空。
既有已跟踪 `mediaflow/.DS_Store` 变更，以及未跟踪系统元数据、调查脚本、日志、`15` 和
`output/` 材料均保留，不纳入本 Task 检查点。

### Implementation Scope

按一个完整行为实施，复用现有配置、候选、选择保存、Worker 分析及摘要服务：

1. **查询类型成为唯一策略控制。** 检查所有 MetadataPolicy 载入、归一化、投影、保存路径及实际消费者。旧配置允许含 `mediaType`，但完全忽略其值，不校验、不回退、不限制查询或身份；缺少 `mediaQueryType` 按既有默认 Auto 处理，非法查询类型仍拒绝。新建／复制／编辑后的策略不保存 `mediaType`。移除 TMDB 策略表单、字段清单、校验和摘要中的重复媒体类型控制；旧 Active／Task 快照只读消费，不重写原文、digest 或历史记录。
2. **统一允许类型。** 在共享边界复用同一规则：Movie 只接受 movie，TV 只接受 tv，Auto 接受 movie 和 tv；非法／缺失类型不能默认成电影。覆盖正常查询、候选确认／修正、意图保存、重新分析、摘要身份复用及核心 runner。None 保留不查询语义，不能通过保存候选绕过 Provider；既有来源绑定、类型完整的离线路径保持可用。
3. **新一次整理重新识别。** 从 Files 新发起整理时，即使同一来源有完整 typed Result、旧执行计划、evidence 或已确认候选，也不自动将它们填入新意图的 metadata。新任务按当前来源、RecognitionType 对应查询类型走正常识别；真正只有编号的历史同样如此。历史 Result／执行记录继续用于查看结果与已有历史提示，不作为自动识别输入。已有 `allowedMetadataIdentities` 可保留完整且符合现有来源／版本／pin 规则的历史候选，但只有用户本次明确选择并保存后才用于分析。来源文件自身的 NFO／外部 ID 识别和 Provider 缓存保持原有行为。
4. **本次任务确认后继续消费保存的选择。** 沿现有 metadata review／correction → 决定绑定 → Worker 重新分析 → durable identity → 摘要链路，使用已保存候选的 Provider、编号和真实类型。详情读取走正确电影／电视剧接口；不重新执行同一候选的自动评分确认，也不创建重复确认记录。摘要复用已持久化身份，不能再查一次 Provider。新阻塞按原阶段显示真实原因。
5. **接通整理意图页候选。** 在每项 ChoiceEditor 展示现有 `allowedMetadataIdentities`，显示片名／年份／电影或电视剧／Provider 编号以区分同号不同类型；不加自由输入或新搜索入口。将明确选择的完整 metadata 与识别类型绑定的策略一起，通过现有 optimistic choice API 保存；保存成功后读回，旧摘要失效，使用现有显式重新分析动作生成新摘要。无候选时解释正常重新识别路径；保存失败保留可修正输入，409 重读合法候选。后端继续校验来源、Provider、查询类型和版本。
6. **文档和测试。** 更新当前配置／规则操作说明与直接受影响示例，明确查询类型、结果类型，以及“新整理重新识别／当前任务继续使用已保存选择”的区别；不改 Slice/Roadmap/Progress 或提前记录交付。

### Acceptance Criteria

- [x] **AC-1 策略保存／兼容：** TMDB 策略页面没有“媒体类型”输入；查询类型可保存／读回。新建、复制、编辑提交及保存结果均不含该策略 `mediaType`。旧键与查询类型冲突、值非法、只有旧键三种输入均按查询类型／默认 Auto 消费；非法查询类型仍报错。旧快照原文／digest 不变。
- [x] **AC-2 一致校验：** Movie／TV 拒绝相反身份，Auto 在正常识别、确认、修正、意图保存、durable identity 与摘要复用中都接受两种合法类型。None 不发查询；合法离线路径不依赖旧键。Provider 不符、身份类型缺失／非法、跨来源／版本／pin 的引用拒绝或回到合法重新识别。
- [x] **AC-3 场景一——重新整理电视剧：** 已完成的历史使用 tv，旧策略 `mediaType=movie`、查询类型 Auto；从 Files 新发起整理时，初始 `choice.metadata` 为空，按当前剧集来源重新识别，不自动使用旧 TMDB 编号。历史含完整类型、仅有编号、没有历史三种情况遵循同一规则。假 Provider 让新识别返回与历史不同的 tv 编号，验证采用新编号、TV 详情接口和剧集命名分类；同号 movie／tv 不串型。新的歧义允许要求本次选择。用户本次明确选取已有合法历史候选并保存时，则按 AC-4/5 使用其真实类型。旧记录保持原样。
- [x] **AC-4 场景二——候选确认后生成摘要：** 原任务停在 Metadata 确认，保存 tv 候选后显式重新分析，在同一任务／原合法 pin 上得到可查看摘要；重新读取／刷新仍保留所选编号和类型。无新歧义时不重复要求确认、不新增同一确认记录；摘要生成不再次访问 Provider。电影候选有对称成功覆盖；新技术失败仍保留已保存决定和真实失败原因。
- [x] **AC-5 意图页闭环：** 每项能从既有候选列表明确选择、保存完整 metadata、读回并重新分析得到新摘要；同号不同类型可区分。空候选、不可用选择、409／403、保存未知、Provider 失败均有准确状态／下一步；不会自动提交、伪造候选或让旧摘要继续获得执行授权。
- [x] **AC-6 安全与兼容：** 读取／保存决定／分析零 Storage 变更；执行仍须原有精确摘要的明确确认。C 复用 A 命名／分类后仍为 C；成功兄弟不重放，未知效果不可重试；既有 pins／fences、RBAC、source confinement 和逐项独立结果无回归。无 schema／迁移或历史回写。

### Required Tests

此 Task 评定 **T4**：修改核心 Metadata、摘要身份校验及 Active 配置消费语义，虽不改 schema／Executor，仍需 B 全量验收。以下命令是计划，尚未运行；Developer 只跑新增／修改及直接受影响测试。

#### Developer — affected tests

在现有测试加入查询类型矩阵、新任务有／无类型历史均重新识别、同号不同类型、确认后不重建 review／不重复 Provider 查询，以及新任务不自动继承历史、前后端完整候选保存断言。Python 使用本地假 Provider、临时 SQLite 和临时 Storage，断言实际调用类型、保存内容、review 数和零 mutation：

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_metadata*.py'
.venv/bin/python -m unittest discover -s tests -p 'test_strategy*.py'
.venv/bin/python -m unittest discover -s tests -p 'test_manual_organize*.py'
.venv/bin/python -m unittest discover -s tests -p 'test_runtime_strategy_configuration.py'
.venv/bin/python -m unittest discover -s tests -p 'test_configuration_objects.py'
.venv/bin/python -m unittest discover -s tests -p 'test_v2_rules*.py'
.venv/bin/python -m unittest discover -s tests -p 'test_v2_manual_organize.py'
.venv/bin/python -m unittest discover -s tests -p 'test_processing_recovery_admission.py'
python3 scripts/check_governance.py
git diff --check
```

对实际修改的 Python 文件执行 `.venv/bin/ruff check <changed-python-files>` 和 `.venv/bin/ruff format --check <changed-python-files>`。若共享调用影响其他现有测试，补跑实际受影响模块并在交接说明依据。

`web/` 目录（意图页若缺独立单测，在现有 OrganizeRouter 测试添加候选交互）：

```bash
npm run test -- run src/entities/rules/rules-form.test.ts src/features/rules/RulesObjectForm.test.tsx src/features/rules/RulesEditPage.test.tsx src/entities/operations/organize.test.ts src/features/operations/OrganizeRouter.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx
npm run typecheck
npx eslint <changed-web-files>
npx prettier --check <changed-web-files>
```

上述 `<changed-web-files>` 必须替换为实际路径；新增测试补上准确路径，不以零测试匹配作为通过。Developer 通过受影响检查后提交候选，不等待 B 全量。

#### B — acceptance and full regression

1. 独立审查整个固定 Base..candidate，核对所有策略旧键的消费者、新任务没有历史身份自动初始化及无 schema／历史改写。在真实 Python/API/SQLite/Worker＋构建后的 Web 上运行 AC-3、AC-4 和 AC-5；通过可记录调用的本地 Provider 验证 TV/Movie 接口、无重复 review 和摘要阶段零 Provider／Storage mutation，刷新后检查持久状态，不能只用 mock API／组件代替验收。
2. 优先扩展现有 `scripts/operations_inventory_harness.py` 和 `web/tests/e2e/organize-source-history.python.spec.ts` 的局部夹具／场景，沿用临时配置、SQLite、Storage 与假 Provider，不新造持久运行引擎。验收执行（cwd `web/`）：

```bash
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/organize-source-history.python.spec.ts
npm run test:e2e -- tests/e2e/manual-organize.spec.ts tests/e2e/rules-identity.spec.ts
```

3. B 执行工作流 [T4 shared full gates](docs/development-workflow.md#shared-full-regression-commands)：完整 Python／Web 回归、静态检查、示例验证、禁止依赖、构建／wheel 及实际受影响的安全和原生门禁。此次不变 Docker／部署契约，不新增外部服务、生产部署或跨版本迁移矩阵；适用的打包／安全门禁不免除。补验 exact-source／pin／版本冲突、失败原子性、C→A 身份及非重放。
4. 记录准确候选 SHA、实际命令／结果／skip／失败与证据路径；不可用必需门禁保留 pending，不以规划、静态定位或过去 PASS 代替实际验收。满足独立 bug 接受标准后结束此 Task，恢复 NO ACTIVE IMPLEMENTATION TASK，不创建后续 Task 或 Slice 关闭记录。

### Non-goals

不改数据库结构、不新增迁移／批量补型、不重写旧配置／Result／review／Task 历史；不删除 MediaCandidate／MediaIdentity／命名／分类中的电影／电视剧类型。不增加历史类型关联／补型或跨任务自动身份复用。不引入新 Provider、搜索算法、自由身份注入、候选搜索页、恢复类型、队列／执行引擎或自动执行；不增加双搜／预算／阈值设置。不改变规则绑定、Storage 变更权限、显式整理确认、未知效果不重放或 Slice52 等已关闭边界。不读用户私有配置／运行数据库／用户媒体，不推送、不发布／部署。

### Developer Completion Report — 调整前候选

以下交接报告保留调整前实现和验证事实；其中历史自动复用的描述已由本轮 Scope／AC-3 取代。

```text
Candidate source checkpoint: 74d3823282549e3b1090cd32a2ed4d361bc16683
Task Base: 233f6a25769856087d10cb4483c0f1a621a76546
Status: READY FOR B REVIEW
```

实际变更：

- `MetadataPolicy.query_type` 只读取 `mediaQueryType`，旧 `mediaType` 仅保留为历史快照的只读字段；
  新增共享的 `allows_media_type`（Movie/TV/Auto/None）并在识别、候选修正、意图保存、durable
  identity、摘要复用和 Task 恢复中复用。非法查询类型仍拒绝；旧媒体类型值不校验、不回退。
- Managed MetadataPolicy 的规范化、Rules 表单 authority、旧版引导表单、摘要和示例不再提供或保存
  `mediaType`；旧键输入仍被接受并忽略，旧 Active 原文／digest／历史记录不重写。手动意图快照增加
  可选 `queryType`，并兼容旧快照缺少该字段的读取。
- 历史 Result 只在自身证据／执行身份给出 Provider＋编号＋类型时形成可复用身份；只有编号时不再
  用策略、Naming 或同号猜测补型，默认选择不生成猜测候选，旧 Result 不修改。
- 预览的 durable identity 校验改用查询类型；保存候选后重新分析可复用已持久化身份，不再访问
  Provider。修正／确认／意图保存都拒绝与 Movie/TV 查询类型相反的身份。
- 整理意图页每项增加既有 `allowedMetadataIdentities` 候选控件，显示片名／年份／电影或电视剧／
  Provider 编号，并保存完整 metadata；同号不同类型可区分。无候选、候选失效、保存冲突和缺少策略
  映射都有明确状态。文件页现有候选控件同步按类型区分同号身份，`updateOrganizeChoice` 支持显式
  清空身份。
- 更新 `config/strategy.example.json`、`config/mediaflow.phase13.2.example.json` 及
  `docs/configuration.md`，明确查询类型与结果媒体类型的区别。

实际执行（Developer 受影响范围）：

| 命令 | 结果 |
|---|---|
| `.venv/bin/python -m unittest discover -s tests -p 'test_metadata*.py'` | 70 passed |
| `.venv/bin/python -m unittest discover -s tests -p 'test_strategy*.py'` | 32 passed |
| `.venv/bin/python -m unittest discover -s tests -p 'test_manual_organize*.py'` | 64 passed |
| `.venv/bin/python -m unittest tests.test_runtime_strategy_configuration` | 11 passed |
| `.venv/bin/python -m unittest tests.test_configuration_objects` | 72 passed |
| `.venv/bin/python -m unittest discover -s tests -p 'test_v2_rules*.py'` | 193 passed |
| `.venv/bin/python -m unittest tests.test_v2_manual_organize` | 43 passed |
| `.venv/bin/python -m unittest tests.test_processing_recovery_admission` | 12 passed |
| `.venv/bin/python -m unittest discover -s tests`（补充全量 Python） | 2669 passed, 7 skipped |
| `web: npm run test -- run`（7 个直接相关文件） | 87 passed |
| `web: npm run typecheck` | PASS |
| `web: npx eslint <changed-web-files>`、`npx prettier --check <changed-web-files>` | PASS |
| `python3 scripts/check_governance.py`、`git diff --check` | PASS |
| `.venv/bin/ruff check/format --check <changed-python-files>` | PASS |

新增覆盖包括：查询类型矩阵与旧键忽略（`test_metadata.py`、`test_configuration_objects.py`、
`test_v2_rules_workspace_commands.py`）、只有编号无类型不生成身份、旧 `mediaType=movie`＋Auto
下历史 tv 身份使用 TV 详情而非电影、durable identity 摘要零 Provider 查询、修正拒绝相反身份，
以及意图页候选选择／同号不同类型区分与完整 metadata 提交（`OrganizeRouter.test.tsx`、
`rules-form.test.ts`）。

已知风险／剩余工作：

- 上述为 Developer 受影响验证，不是 B 验收，也不代表 AC-1–6 已通过。B 仍需在真实
  Python/API/SQLite/Worker＋构建后 Web 上执行 T4 全量、AC-3/4/5 原生旅程、可记录 Provider
  调用、持久刷新、打包／安全门禁及非重放检查。
- 本轮未新增数据库 schema 或迁移；旧手动意图快照缺少 `queryType` 时按兼容比较读取，但 B 仍应
  验证实际旧 pin 的读取路径。
- 工作区既有 dirty/untracked 文件（含 `TASK.md` 规划文本之外的私有输出）保持未纳入源码检查点；
  源码检查点仅含本 Task 文件。未推送、未发布。

### B Review Result — 本轮方案调整后的开发交接

```text
Decision: FIX REQUIRED
Task Base: 233f6a25769856087d10cb4483c0f1a621a76546
Previously Reviewed Head: 79e2b2d8f0185dadfdffdd4adc8f9fd54ab40714
Implementation Head: 74d3823282549e3b1090cd32a2ed4d361bc16683
Plan Revision Starting Head: cad6d35cf1e0a58b5a8af9a0ea06411bcf1a0e9c
Reviewer: B
Review Date: 2026-11-09
Previous R1: WITHDRAWN BY EXPLICIT USER SCOPE CHANGE
Remaining: remove historical identity auto-initialization; update directly affected tests
Next: Developer implements this revised scope in the same Task
```

此前 B 已独立审查固定 Base..79e2b2d8 的全部 34 个变更文件。
用户本轮明确同意取消跨次整理的历史身份自动复用，因此撤销此前 R1 的修正要求：
**不再要求沿 Result→执行条目补读类型，也不要求新整理自动沿用历史候选。**
上轮“COPY 成功后再整理会重新搜索并出现歧义”的实际观察保持事实，按新约定这是允许的结果。
这不是 Task PASS：当前代码还会在历史有同 item evidence 时自动设置 metadata，
必须统一改为新整理重新识别。原始审查与证据见
[调整前 B 检查点](https://github.com/kentinya/mediaflow/blob/cad6d35cf1e0a58b5a8af9a0ea06411bcf1a0e9c/TASK.md#b-review-result)。
Slice52 保持 PASS / CLOSED；本独立 Task 不重开 Slice 或改动 Roadmap／Progress。

**开发指导 — 本轮具体修改**

1. 修改 `manual_organize.py` 的新意图默认选择：检查 `_default_choice`、
   `files_choice_for_source`、`_choice_for_type` 的真实调用，取消从历史 Result/evidence
   自动设置 metadata。RecognitionType 继续按既有当前规则／明确选择确定。
   删除仅服务于历史身份自动初始化且已无消费者的读取代码；不补读执行条目、不增加开关。
   调整 `test_manual_organize_intent.py`、`test_manual_organize_preview.py` 中
   以历史自动带入身份作为成功前提的断言；查询类型矩阵改用本次明确保存候选来验证。
2. 保留 `allowedMetadataIdentities` 的既有合法候选投影和 ChoiceEditor 的显式选择保存。
   保留当前 Task 的 review/correction、已保存 choice、`_bound_metadata_decision` 与
   `durable_identity` 摘要消费路径。只取消新任务的历史自动带入，不能清空本次确认。
   新一次整理是否与历史相同，通过现有任务／意图关系判定，不增加跨任务恢复机制。
3. 沿现有 Files 入口补充回归：第一次选择 tv 候选并完成 COPY → 从 Files 新发起整理
   同一文件 → 初始无固定 metadata → 假 Provider 的新结果决定新摘要。
   使用完整历史身份和仅编号历史验证相同行为；正常 Provider 缓存允许命中，
   测试断言“进入本次识别且不自动钉住旧编号”，不要求实际外网请求或关闭缓存。
   同一 Task 继续确认 tv／movie 候选后，刷新和显式重新分析应使用保存的编号／类型，
   不重复评分确认或创建同一 review，摘要发布阶段不再次查询 Provider。
4. 同步本次 UI 改动直接影响的浏览器断言：
   `web/tests/e2e/rules-readiness.spec.ts:491` 将旧分组“元数据服务与媒体类型”
   改为实际“元数据服务与查询类型”，并验证没有策略媒体类型输入。
   `operations-inventory.python.spec.ts:1562` 附近的歧义旅程仍用
   `tmdb/111`／`tmdb/911`，同步为页面当前带 `/movie` 的完整选择值，
   保留保存、摘要、显式执行断言。前者已实际失败，后者为静态发现，未计作运行失败。
5. 更新 `docs/configuration.md` 的当前说明，写清新整理重新识别、
   当前任务沿用已保存候选，以及历史候选需本次明确选择。
   Developer 仅运行新增／修改和直接受影响测试后提交 READY FOR B REVIEW；
   B 复核完整 Base..新候选并完成 T4 验收。测试用现有 harness 局部夹具，
   不增加入口或流程工具。本轮开发／复核的测试时间各自小于该轮总用时的 50%。

**沿用的已验证事实与待验收项**

- 调整前真实 Python 浏览器的 Metadata 候选确认和修正两条旅程通过，
  可在同一 Task 继续到摘要／实际整理，摘要阶段不重复访问 Provider。
- 调整前 TV 局部夹具从现有 Files 入口产生真实候选；构建后 Web 可选择 702、
  保存 tv 类型、刷新读回并生成 TV／Season 01／S01E01 摘要，明确确认后 COPY 成功。
- 上述结果属于调整前候选；涉及修改的执行输入须在新候选重新验收。
  AC-1–6 当前均保留未最终验收，不把方案调整或旧结果改记为新实现通过。


**调整前 B 实际运行与结果（保留事实，不代表新方案通过）**

| 命令／入口 | 实际结果 |
|---|---|
| `.venv/bin/python -m unittest discover -s tests` | 2669 tests，OK，7 skipped；285.01 秒 |
| `web: npm run test -- run` | 98 files／1469 tests PASS；131.92 秒 |
| `web: npm run test:e2e` | 267 PASS，1 FAIL；192.77 秒；失败为上述 Rules 旧 section 断言 |
| `web: npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts -g 'native Metadata'` | 2 PASS；3.72 秒；真实 Python／API／SQLite／Worker |
| 构建后 Web＋同一现有 harness 的局部 TV 夹具 | 意图页候选保存／刷新／TV 摘要成功；COPY 后重新整理发生重新搜索／歧义 |
| `web: npm run build`、`npm run typecheck`、`npm run lint`、`npm run format:check` | PASS |
| `.venv/bin/python scripts/check_governance.py`、compileall、pip check、两份示例 config validate、`git diff --check` | PASS |
| `rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml` | 无匹配（exit 1） |
| `.venv/bin/ruff format --check .`／`ruff check .` | 被审查前已有的未跟踪 `.explore_adapter_block.py` 语法错误阻断；该文件未改动 |
| 对 `git ls-files -- '*.py'` 的全部 354 个已跟踪 Python 文件执行 ruff format/check | PASS；完整受版本管理源码已检查 |
| `.venv/bin/python -m pip wheel . --no-deps -w dist` | PASS；wheel SHA256 `dc1ca9a6f84eb534d53b6370ddeef021d6f3356c2cce3aa8867a7decf10061b0` |

上轮发现 R1 后未追加完整测试矩阵；R1 现已按用户决定撤销。wheel smoke、
新方案的完整 source-history 原生旅程及最终安全／持久化验收仍待新候选。现有 7 个 Python skips 原样保留；未删断言、加重试或改超时。

可复查的本地证据（忽略目录，不声称远程可访问）：
`.git/validation-evidence/79e2b2d8/b-query-type-review/`。
其中 `tv-history-provenance.json` 保存 Result→执行条目→typed plan 的精确关联；
`tv-reorganize-result.json` 保存第二次选择、摘要和 Provider 调用；
`tv-after-analysis.json`、`intent-tv-saved-desktop.png` 和
`intent-tv-summary-desktop.png` 保存首次选择与成功摘要；
`reorganize-tv-blocked-desktop.png` 保存再次识别产生歧义的可见结果（按新方案允许）。
全量原始日志、结果 JSON 和纯测试夹具数据库 `tv-fixture.sqlite3` 同目录。B 仅修改本 Task 交接；既有 dirty/untracked 文件保留，
没有修改产品源码、推送或部署。本轮只修订 Task，运行治理与文档差异检查；未重跑产品测试。

### Developer Completion Report — 新整理重新识别修正

```text
Candidate source checkpoint: 86d9b7618acd88d640563ffc90f5e9d98c7e8b74
Task Base: 233f6a25769856087d10cb4483c0f1a621a76546
Status: READY FOR B REVIEW
```

实际变更（候选检查点仅含下列 7 个文件）：

- `manual_organize.py`：新 intent item 的 choice 不再从历史 Result/evidence 填入 `metadata`；
  `_choice_for_type` 只按 RecognitionType 映射下游策略，metadata 恒为 `None`；删除仅服务该
  自动初始化的 `_result_media_type`/`_evidence_media_type`。既有 RecognitionType 默认保持不变：
  non-Files 编辑入口沿用历史 Result 类型或首个配置类型，Files 入口继续由 pinned
  RecognitionRule 决定。`allowedMetadataIdentities`、显式 `update_choice`、review/correction →
  durable identity → 摘要链路未改。
- 测试：查询类型矩阵改为“新任务不自动带入 + 本次显式保存 tv 被 Auto 接受 + Movie 查询拒绝”；
  preview 旧 `mediaType` 用例改为本次显式保存 tv 后走 TV 详情；新增 Files 真实入口回归：
  首次 tv 分析并完成 COPY 后，从 Files 新发同一文件，初始 `choice.metadata=None`，假 Provider
  新编号 703 决定新 TV 摘要，零 mutation、旧记录不变；仅编号历史同样不被带入。
- `docs/configuration.md` 补清新整理重新识别、本次显式保存候选被当前任务继续使用、摘要复用
  持久身份、换版本／换 Active 不继承旧候选。
- Rules readiness 断言改为“元数据服务与查询类型”并验证策略媒体类型输入不存在；
  operations-inventory 歧义旅程候选值同步为 `tmdb/111/movie`、`tmdb/911/movie`。

实际执行（Developer 受影响范围）：

| 命令 | 结果 |
|---|---|
| `.venv/bin/python -m unittest tests.test_manual_organize_intent tests.test_manual_organize_preview` | 26 passed |
| `.venv/bin/python -m unittest tests.test_organize_preparation` | 33 passed |
| `.venv/bin/python -m unittest discover -s tests -p 'test_metadata*.py'` | 70 passed |
| `.venv/bin/python -m unittest discover -s tests -p 'test_strategy*.py'` | 32 passed |
| `.venv/bin/python -m unittest discover -s tests -p 'test_manual_organize*.py'` | 64 passed |
| `.venv/bin/python -m unittest tests.test_runtime_strategy_configuration tests.test_configuration_objects` | 83 passed |
| `.venv/bin/python -m unittest discover -s tests -p 'test_v2_rules*.py'` | 193 passed |
| `.venv/bin/python -m unittest tests.test_v2_manual_organize tests.test_processing_recovery_admission` | 55 passed |
| `.venv/bin/python -m unittest tests.test_organize_source_history tests.test_media_discovery` | 23 + 156 passed |
| `web: npm run test -- run src/entities/rules/rules-form.test.ts src/features/rules/RulesEditPage.test.tsx src/entities/operations/organize.test.ts src/features/operations/OrganizeRouter.test.tsx src/features/operations/OrganizeCreationPage.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx` | 6 files／67 passed |
| `web: npm run typecheck`；`npx prettier --check`、`npx eslint` 两个改动 e2e 文件 | PASS |
| `web: npm run build` | PASS |
| `web: npx playwright test tests/e2e/rules-readiness.spec.ts -g 'every family keeps its purpose-built'` | 1 passed |
| `web: npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts -g 'a brand-new ambiguous source'` | 1 passed |
| `python3 scripts/check_governance.py`、`compileall -q mediaflow tests scripts`、`git diff --check` | PASS |
| `.venv/bin/ruff check`／`ruff format --check` 四个改动 Python 文件 | PASS |

已知风险／剩余工作：

- 上述为 Developer 受影响验证，不是 B 验收，也不代表 AC-1–6 已通过。B 仍需在真实
  Python/API/SQLite/Worker＋构建后 Web 上复核完整固定 Base..`86d9b761`，执行 T4 全量、原生
  AC-3/4/5、wheel／安全／非重放门禁并记录证据。
- 新增 Files 回归覆盖“完成 COPY 后新整理重新识别”和“仅编号历史不被带入”；同一任务先人工
  选择候选再继续摘要的路径由既有单元用例覆盖，本轮未在新的 Files 旅程中重复执行，B 应在
  AC-4/AC-5 验收时实际复跑。
- 未改数据库 schema／迁移，未重写旧配置、Result、review 或 Task 历史；本轮未改 Web 产品源码。
- 工作区既有 dirty/untracked 文件（含 `mediaflow/.DS_Store` 和私有输出）保持未纳入检查点；
  未推送、未发布、未部署。

### B Final Review — PASS

```text
Task ID: PATCH-20261109-2
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Decision: PASS
Task Base: 233f6a25769856087d10cb4483c0f1a621a76546
Reviewed Head: fbabe7f80614dd35faa096dcb55198d183784501
Accepted Implementation Head: 86d9b7618acd88d640563ffc90f5e9d98c7e8b74
Reviewer: B
Review Date: 2026-11-09
Difficulty: Medium
Test Level: T4
Task blockers: NONE
Authorized bug acceptance complete: YES
Next: NO ACTIVE IMPLEMENTATION TASK
```

独立审查固定 Base..Reviewed Head 全部 37 个文件（含配置、全部产品消费者、前后端测试、说明和 Task）。
`86d9b761..fbabe7f8` 只有 Task 交接报告，验收执行输入与已审源码一致。
本轮没有修改产品源码，也没有改变 schema／迁移、Executor、Docker 或部署契约。
原 R1 已因用户明确改变方案而撤销；本次按“新整理重新识别／当前任务保留明确选择”验收，
不把旧的历史自动复用要求重新加入范围。Slice52 及 Roadmap／Progress 保持原接受状态。

**用户旅程与 AC 结果**

| 验收 | 实际结果 |
|---|---|
| AC-1 查询类型唯一控制 | Rules 表单及后端 authority 不再提供策略媒体类型；保存、读回和标准化移除旧键，冲突／非法旧值被忽略，只有旧键时默认 Auto，非法查询类型拒绝。已有不可变配置读取保留，未改写旧快照。完整 Rules 与配置集成测试通过。 |
| AC-2 各入口一致 | Movie／TV 类型约束及 Auto 双类型通过领域、意图保存、修正和摘要回归；None 保留不查询及既有类型完整离线路径。Provider、来源版本、pin 与权限校验仍由原服务执行。真实 Auto＋旧 mediaType=movie 的剧集旅程始终用 TV 详情。 |
| AC-3 新整理重新识别 | 自动化真实 API／SQLite／Worker 集成：第一次 TV603 COPY 成功后再次从 Files 发起，初始 metadata=None，新 Provider 结果 TV703 进入剧集摘要；仅编号历史同样重新识别，原603 Result不变。另以构建后 Web 实测：TV702 COPY 成功后，从 Files 选择同一文件→批量整理，新意图仍 metadata=None，并重新搜索形成701/702歧义；本次明确选701后生成新摘要，原702 Result不变。新歧义符合本次用户约定。 |
| AC-4 当前任务确认续接 | 真实 Task Center→元数据恢复→选择TV701→保存并继续分析→原Task进入waiting_confirm并显示TV/Season 01/S01E01摘要；重新打开SQLite，仍仅一个该Task的review，状态resolved、选择701/tv，没有新增重复确认。重新分析只增加一次get_tv(701)，摘要阶段调用数不变。电影候选确认及人工修正两条原生浏览器旅程也通过，并实际执行完成。 |
| AC-5 整理意图页 | 真实 Web 意图页从已有候选选TV702→保存→刷新重新认证→读回702/tv→显式生成摘要→明确确认→同一Task完成COPY。组件覆盖同号movie/tv可区分及完整metadata提交；完整回归覆盖空选、冲突、权限、未知提交核对及Provider失败。旧摘要失效，保存不会自行执行。 |
| AC-6 安全与兼容 | 完整安全／恢复回归覆盖临时Storage零变更分析、明确执行授权、exact source／版本／pin、RBAC、失败原子性、C使用A命名分类仍为C、成功与未知效果不重放。原生摘要读取没有增加Provider调用或目标文件；临时SQLite重开证明旧Result未改。无历史回写。 |

**本轮实际门禁**

证据目录为本机稳定忽略目录 `.git/validation-evidence/fbabe7f8/b-final-review/`，
不是已上传的CI材料。所有测试使用临时配置／SQLite／Storage和本地假Provider，未读用户媒体或私有配置。

| 命令／范围 | 实际结果与证据 |
|---|---|
| `.venv/bin/python -m unittest discover -s tests` | 2671项，OK，7 skipped，301.442秒；`python-full.log`。跳过的是未配置专用环境的Local/SMB/OpenList/S3耐久及真实远端适配器矩阵，非本次变更契约。 |
| `web: npm run test -- run` | 98文件、1469项通过，135.89秒；`web-unit.log`。 |
| `web: npm run test:e2e` | 首跑266通过、2项在context关闭阶段因产物文件ENOENT失败，3.1分钟；`web-e2e.log`。原因是B并行启动原生浏览器套件共用了默认test-results目录，不是产品断言失败。对这两项使用独立output目录补跑：2/2通过，2.6秒，`web-e2e-rerun.log`；未删断言、加重试或调超时。全部268个场景均有本候选通过结果，不声称首跑全绿。 |
| `web: npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/organize-source-history.python.spec.ts tests/e2e/operations-inventory.python.spec.ts -g <history/source/native-Metadata-filter>` | 5/5通过，9.5秒；包含历史来源、首次歧义同页选择与执行、Metadata确认／修正同Task续接；`native.log`。 |
| 真实TV局部夹具 | 复用既有operations_inventory_harness和原生入口，无新增产品路由。意图选择保存／刷新／摘要、COPY、新Files整理、Task Center TV确认续接通过；`tv-current.json`、`tv-copy-success.json`、`tv-new-current.json`、`tv-recovery-result.json`、`tv-reopened-persistence.json`及桌面／窄屏截图。 |
| Python质量 | governance、所有git跟踪Python文件的Ruff检查／格式（354文件）、compileall、pip check、两个示例config validate、Base..Head whitespace均通过；禁用依赖rg无匹配（预期exit 1）。命令与结果见`quality-results.json`及对应日志。未纳入既有未跟踪调查脚本`.explore_adapter_block.py`。 |
| Web质量／产物 | typecheck、lint、format:check、build全部通过，分别有日志；本轮浏览器使用本轮构建产物。 |
| wheel／安装后消费 | `pip wheel . --no-deps -w <evidence>/wheel`与`scripts/wheel_smoke_test.py <exact-wheel>`通过；独立虚拟环境、源码树外加载site-packages、CLI／示例验证／数据库备份恢复及准备／恢复消费者检查通过。wheel SHA-256：`07024680022cafd24e38506ad42a76781f364c1fe1f61bdb6a21863469028814`。 |

B局部浏览器脚本的初次探测有选择器／响应监听路径错误，均发生在实际保存或准入之后；
B读取现有持久记录再继续，没有重复提交。另一个局部脚本原期待新703，但假Provider钩子误用Storage ID，
实际仍返回701/702；已按真实输出验收新歧义与本次明确选择701，未把它记作703自动匹配。
603→703与仅编号历史的自动识别证据来自本轮全量中的生产API／Worker集成用例。
本轮并行运行长门禁时继续审查完整变更；未重复全量套件或以等待凑验收时间。
这些调查失败保留在证据目录，不转交为产品修正。
为独立验证后续摘要，在临时夹具中移除了第一次COPY的目标文件，保留来源和Result；
该操作只是夹具准备，不属于产品恢复动作，首次COPY成功证据已先保存。

本次不改Storage适配器、外部服务或部署契约，未运行生产服务矩阵或Docker发布门禁；
不声称已部署，也未推送。已有SQLite ResourceWarning及jsdom scrollTo提示保留在原日志，测试退出成功。
按停止规则，本独立Task所有授权结果已满足，不再规划后续Task；本地仅提交B验收与no-active指针。

---

## Prior Task History

# NO ACTIVE IMPLEMENTATION TASK

Task PATCH-20261109-1 — 删除文件页整理记录并统一目录接入 — **B PASS**。

```text
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Decision: PASS
Task Base: 45674526b04d3366f533b86e864b3c8d179736ed
Reviewed Head: df565d058acaaf8078ddcb7b20ffa7c89079ac76
Accepted Implementation Head: c1ff542f071dce6829ed497dfe9911df8ad0c3a2
Reviewer: B
Review Date: 2026-11-09
Difficulty: Medium
Test Level: T3
Task blockers: NONE
Authorized bug acceptance complete: YES
Next: NO ACTIVE IMPLEMENTATION TASK
```

完整 Base..Head 独立审查、AC-1–5 结果、实际 T3 命令及证据限制见
[固定 B 验收报告](https://github.com/kentinya/mediaflow/blob/886c320db6916a1f0c3f5c2f2e38b599d14418a5/TASK.md)。
原规划与 Developer 报告见
[候选检查点](https://github.com/kentinya/mediaflow/blob/df565d058acaaf8078ddcb7b20ffa7c89079ac76/TASK.md)。

已接受旅程：文件页选择文件 → 生成摘要 → 离开 → 任务中心打开原任务 →
“继续整理”返回同一摘要（含刷新／重新认证）→ 明确确认一次 → 查看原任务结果。
文件页直接呈现目录读取／列表／错误，未知提交仍按原请求核对。

本独立修正已完成；Slice52 的既有关闭结果、Roadmap 和 Progress 保持。
下一大版本由 A 另行选择，当前没有后续实施 Task。
