# Task PATCH-20261109-2 — 查询类型统一与已确认元数据的整理摘要续接

```text
Task ID: PATCH-20261109-2
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: READY FOR B REVIEW
Task Base: 233f6a25769856087d10cb4483c0f1a621a76546
Difficulty: Medium
Test Level: T4
Planner / Reviewer: B
```

用户已明确激活本 Task。实现范围、验收标准、测试分工和非目标如下；实施候选完成后进入 READY FOR B REVIEW。

Authority：用户本轮明确的五点最小修正方案；按 [Development Workflow §3.1](docs/development-workflow.md#31-independent-minor-bugs) 处理已有 Rules／Files／Task 恢复旅程的独立缺陷，不创建或重开 Slice。

### Goal

TMDB MetadataPolicy 只用“查询类型”决定允许的查询和身份类型。移除策略“媒体类型”这一重复控制；保留识别结果、候选和 MediaIdentity 自身的电影／电视剧类型，继续驱动正确 Provider 查询、命名和分类。重新整理不会把历史电视剧编号当电影查询；人工确认候选或在整理意图页保存已有候选后，重新分析能继续生成准确摘要，不重复要求确认同一候选。

完整旅程：整理规则编辑 TMDB 策略 → 保存并读回实际配置 → Files 整理／Task Center 继续原任务 → 展示当前识别和已有合法候选 → 保存候选及类型 → 显式重新分析 → 查看同一工作上下文的摘要 → 另行明确确认执行。保存选择和分析始终零媒体变更。候选无效、策略不兼容、来源／版本变化、Provider 失败时，显示失败阶段、已保存状态及下一步；未知提交先核对已有状态，不自动重发。

需求依据：`REQ-META-001/002/004–008`、`REQ-RECOG-004`、`V2-RULES-002/004–009`、`V2-OPS-010/012`、`V2-UX-001–003`。遵循 [Rules 旅程](docs/product-experience.md#recognition-and-rules)、[人工整理](docs/product-experience.md#manual-organize)、[逐项恢复](docs/product-experience.md#tasks-results-and-per-item-recovery) 及 [人工整理契约](docs/architecture.md#manual-organize)。既有不可变 pin、来源约束、权限及确认授权保持；不引入新的恢复种类。

### Observed code gap and baseline

以下为 Base 上的静态定位，尚未运行产品复现或验收，不能作为修复成功证据：

- `domain/metadata.py:MetadataPolicy.query_type` 仍从旧 `media_type` 回退；`configuration_objects.py`、`strategy_user_configuration.py` 仍解析／输出策略 `mediaType`。V2 `RulesObjectForm.tsx` 仍并列展示两种控制，`rules-form.ts` 校验／序列化也保留重复字段。
- `application/manual_organize.py` 的 `_choice_for_type/_metadata_authorities` 用策略类型补历史编号；`PersistentResultRecord` 本身没有独立媒体类型字段。必须检查结果关联的既有类型证据，不能从当前策略或编号猜类型。
- `manual_organize_preview.py:_identity_compatible/_durable_identity_compatible` 和 `strategy_test.py` 的 durable identity 分支仍依赖策略 `media_type`，与已有按 `query_type` 校验的候选选择分支不一致；`task_item_recovery.py` 又直接检查 `media_query_type`。
- `metadata_review.py` 已保存所选 Provider、编号和类型；共享分析已有绑定决定／复用身份入口，需打通其兼容校验及消费链，不另建确认系统。
- API 已投影 `allowedMetadataIdentities`，`entities/operations/organize.ts` 已解析，`api-client.ts:updateOrganizeChoice` 已支持 metadata；`OrganizeIntentPage.tsx:ChoiceEditor` 没有候选控件，提交也没有带所选 metadata。

规划前：仓库 `/Users/songzhidong/mediaflow`，分支 `main`，HEAD 为 Task Base；`python3 scripts/check_governance.py` PASS，工作区／Git 可写，暂存区为空。既有 dirty/untracked 文件均保留，不纳入本 Task。

### Implementation Scope

按一个完整行为实施，复用现有配置、候选、选择保存、Worker 分析及摘要服务：

1. **查询类型成为唯一策略控制。** 检查所有 MetadataPolicy 载入、归一化、投影、保存路径及实际消费者。旧配置允许含 `mediaType`，但完全忽略其值，不校验、不回退、不限制查询或身份；缺少 `mediaQueryType` 按既有默认 Auto 处理，非法查询类型仍拒绝。新建／复制／编辑后的策略不保存 `mediaType`。移除 TMDB 策略表单、字段清单、校验和摘要中的重复媒体类型控制；旧 Active／Task 快照只读消费，不重写原文、digest 或历史记录。
2. **统一允许类型。** 在共享边界复用同一规则：Movie 只接受 movie，TV 只接受 tv，Auto 接受 movie 和 tv；非法／缺失类型不能默认成电影。覆盖正常查询、候选确认／修正、意图保存、重新分析、摘要身份复用及核心 runner。None 保留不查询语义，不能通过保存候选绕过 Provider；既有来源绑定、类型完整的离线路径保持可用。
3. **历史复用只取结果自身事实。** 从同一来源／版本 Result、分析证据或计划身份中读取准确 Provider＋编号＋类型。历史只有编号、没有类型时，不生成完整可复用身份或自动默认候选，让原有识别流程重新识别；禁止以策略类型、Naming 类型、同号或不相关结果补型。来源／occurrence／pin 约束不放宽。
4. **确认后继续消费保存的选择。** 沿现有 metadata review／correction → 决定绑定 → Worker 重新分析 → durable identity → 摘要链路，使用已保存候选的 Provider、编号和真实类型。详情读取走正确电影／电视剧接口；不重新执行同一候选的自动评分确认，也不创建重复确认记录。摘要复用已持久化身份，不能再查一次 Provider。新阻塞按原阶段显示真实原因。
5. **接通整理意图页候选。** 在每项 ChoiceEditor 展示现有 `allowedMetadataIdentities`，显示片名／年份／电影或电视剧／Provider 编号以区分同号不同类型；不加自由输入或新搜索入口。将明确选择的完整 metadata 与识别类型绑定的策略一起，通过现有 optimistic choice API 保存；保存成功后读回，旧摘要失效，使用现有显式重新分析动作生成新摘要。无候选时解释正常重新识别路径；保存失败保留可修正输入，409 重读合法候选。后端继续校验来源、Provider、查询类型和版本。
6. **文档和测试。** 更新当前配置／规则操作说明与直接受影响示例，明确策略查询类型和结果媒体类型的区别；不改 Slice/Roadmap/Progress 或提前记录交付。

### Acceptance Criteria

- [ ] **AC-1 策略保存／兼容：** TMDB 策略页面没有“媒体类型”输入；查询类型可保存／读回。新建、复制、编辑提交及保存结果均不含该策略 `mediaType`。旧键与查询类型冲突、值非法、只有旧键三种输入均按查询类型／默认 Auto 消费；非法查询类型仍报错。旧快照原文／digest 不变。
- [ ] **AC-2 一致校验：** Movie／TV 拒绝相反身份，Auto 在正常识别、确认、修正、意图保存、durable identity 与摘要复用中都接受两种合法类型。None 不发查询；合法离线路径不依赖旧键。Provider 不符、身份类型缺失／非法、跨来源／版本／pin 的引用拒绝或回到合法重新识别。
- [ ] **AC-3 场景一——重新整理电视剧：** 历史关联身份为 tv，旧策略 `mediaType=movie`、查询类型 Auto；从 Files 重新整理，使用 tv 身份和 TV 详情接口，绝不把同号当电影查询。用相同 Provider 编号的 movie／tv 夹具证明没有串型；摘要的集信息、命名／分类按真实 tv 身份。只有历史编号无类型时走重新识别，不复用猜测身份、不修改旧 Result。
- [ ] **AC-4 场景二——候选确认后生成摘要：** 原任务停在 Metadata 确认，保存 tv 候选后显式重新分析，在同一任务／原合法 pin 上得到可查看摘要；重新读取／刷新仍保留所选编号和类型。无新歧义时不重复要求确认、不新增同一确认记录；摘要生成不再次访问 Provider。电影候选有对称成功覆盖；新技术失败仍保留已保存决定和真实失败原因。
- [ ] **AC-5 意图页闭环：** 每项能从既有候选列表明确选择、保存完整 metadata、读回并重新分析得到新摘要；同号不同类型可区分。空候选、不可用选择、409／403、保存未知、Provider 失败均有准确状态／下一步；不会自动提交、伪造候选或让旧摘要继续获得执行授权。
- [ ] **AC-6 安全与兼容：** 读取／保存决定／分析零 Storage 变更；执行仍须原有精确摘要的明确确认。C 复用 A 命名／分类后仍为 C；成功兄弟不重放，未知效果不可重试；既有 pins／fences、RBAC、source confinement 和逐项独立结果无回归。无 schema／迁移或历史回写。

### Required Tests

此 Task 评定 **T4**：修改核心 Metadata、摘要身份校验及 Active 配置消费语义，虽不改 schema／Executor，仍需 B 全量验收。以下命令是计划，尚未运行；Developer 只跑新增／修改及直接受影响测试。

#### Developer — affected tests

在现有测试加入查询类型矩阵、历史无类型、同号不同类型、确认后不重建 review／不重复 Provider 查询，以及前后端完整候选保存断言。Python 使用本地假 Provider、临时 SQLite 和临时 Storage，断言实际调用类型、保存内容、review 数和零 mutation：

```bash
.venv/bin/python -m unittest discover -s tests -p '\''test_metadata*.py'\''
.venv/bin/python -m unittest discover -s tests -p '\''test_strategy*.py'\''
.venv/bin/python -m unittest discover -s tests -p '\''test_manual_organize*.py'\''
.venv/bin/python -m unittest discover -s tests -p '\''test_runtime_strategy_configuration.py'\''
.venv/bin/python -m unittest discover -s tests -p '\''test_configuration_objects.py'\''
.venv/bin/python -m unittest discover -s tests -p '\''test_v2_rules*.py'\''
.venv/bin/python -m unittest discover -s tests -p '\''test_v2_manual_organize.py'\''
.venv/bin/python -m unittest discover -s tests -p '\''test_processing_recovery_admission.py'\''
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

1. 独立审查整个固定 Base..candidate，核对所有策略旧键的消费者及无 schema／历史改写。在真实 Python/API/SQLite/Worker＋构建后的 Web 上运行 AC-3、AC-4 和 AC-5；通过可记录调用的本地 Provider 验证 TV/Movie 接口、无重复 review 和摘要阶段零 Provider／Storage mutation，刷新后检查持久状态，不能只用 mock API／组件代替验收。
2. 优先扩展现有 `scripts/operations_inventory_harness.py` 和 `web/tests/e2e/organize-source-history.python.spec.ts` 的局部夹具／场景，沿用临时配置、SQLite、Storage 与假 Provider，不新造持久运行引擎。验收执行（cwd `web/`）：

```bash
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/organize-source-history.python.spec.ts
npm run test:e2e -- tests/e2e/manual-organize.spec.ts tests/e2e/rules-identity.spec.ts
```

3. B 执行工作流 [T4 shared full gates](docs/development-workflow.md#shared-full-regression-commands)：完整 Python／Web 回归、静态检查、示例验证、禁止依赖、构建／wheel 及实际受影响的安全和原生门禁。此次不变 Docker／部署契约，不新增外部服务、生产部署或跨版本迁移矩阵；适用的打包／安全门禁不免除。补验 exact-source／pin／版本冲突、失败原子性、C→A 身份及非重放。
4. 记录准确候选 SHA、实际命令／结果／skip／失败与证据路径；不可用必需门禁保留 pending，不以规划、静态定位或过去 PASS 代替实际验收。满足独立 bug 接受标准后结束此 Task，恢复 NO ACTIVE IMPLEMENTATION TASK，不创建后续 Task 或 Slice 关闭记录。

### Non-goals

不改数据库结构、不新增迁移／批量补型、不重写旧配置／Result／review／Task 历史；不删除 MediaCandidate／MediaIdentity／命名／分类中的电影／电视剧类型。不引入新 Provider、搜索算法、自由身份注入、候选搜索页、恢复类型、队列／执行引擎或自动执行；不增加双搜／预算／阈值设置。不改变规则绑定、Storage 变更权限、显式整理确认、未知效果不重放或 Slice52 等已关闭边界。不读用户私有配置／运行数据库／用户媒体，不实施产品代码、不推送、不发布／部署。

### Developer Completion Report

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

### B Review Result

PENDING — Developer 已提交源码检查点与交接报告；当前没有 B 验收结论。


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
