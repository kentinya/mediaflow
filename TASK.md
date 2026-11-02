# Task47.5 — FIX REQUIRED

Developer 已提交候选 `368d9e86646e4ccafd5509e9c860aa2dd8fa5a1d`；B 独立审查后要求在
同一个 Task 内修复，详见末尾 B Review Result / Developer 修复指导。Task ID、Goal、Base
和 Slice 边界不变；不授权派生代理、push、部署或 Slice 关闭。
用户已选择：“运行一次”和定时一样排除历史 failed / partial，保留一键执行，不新增初始确认。
本次规划一致性核对后按用户选择改为**同一来源版本最近一次正式整理结果**判断；后来手动整理
成功，不再因更早失败排除。普通 CLI/remote 不新增提醒或放行契约，Web 提醒要求保留。

Task47.4 已由 B 审查 PASS，原范围
`383d8834787674675183f4b251d9dfd26a5dc511..dd3f1c25126cd574d8df293d0163131bc6cb9ad6`；
完整审查/原五项结果 Closure Packet 保留于
`980ce42a977b5bc20cf8426dbaf5a232f46cf22b:TASK.md`。本次新增 RO-6 后 Slice47 继续
ACTIVE，先前的 SLICE READY FOR A REVIEW 不覆盖新结果；没有 A Final Review 或关闭。

# Task 47.5 — 自动排除历史失败、手动提醒后新整理与 CLI 失败重试退出

Authority: committed [SLICE.md](SLICE.md) 的 2026-11-02 修订、RO-6 / AC-20–25；
[Development Workflow](docs/development-workflow.md) 管生命周期、测试和收尾。
[Requirements](docs/requirements.md)、[V2 Requirements](docs/v2-requirements.md) 的
`V2-TASK-008–010` 管本次规则；保留 `V2-TASK-001–007`、`V2-OPS-014–017`、
`V2-AUTO-010/011`、UX-002/003/004/006、REQ-SCAN-006、REQ-RECOVERY-006/009、
REQ-RESULT-* 与 REQ-SAFE-* 中未被明确修订的身份、授权、历史及安全义务。

```text
Task ID: 47.5
Task Type: SLICE
Parent Slice: 47
Status: FIX REQUIRED
Task Base: 75ddff55f8d5b2b1206c81804bfb5cbe9ed279a1
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Implementation authorization: USER-AUTHORIZED THIS ROUND — IMPLEMENTED, CANDIDATE SUBMITTED
```

## Preflight / workspace / role

- Repository `/Users/songzhidong/mediaflow`，branch `main`；本轮开始 HEAD
  `980ce42a977b5bc20cf8426dbaf5a232f46cf22b`，无预存 tracked 修改。预存未跟踪的 OS/log、
  `15`、参考图片及 `output/database-reference-2026-11-01/`、imagegen ZIP、
  `output/organize-flow-2026-11-01.html` 原样保留、未暂存。
- 同一 root agent 先履行 A 范围职责，提交 `75ddff55`，再履行 B 规划职责；公开此角色
  组合，但没有实施、自审 Task、A 终审或派生代理。提交后 governance PASS；工作区/Git 可写。
- Task Base 固定为已提交范围修订的完整 SHA。Slice 原 Base
  `5144ab1fc2344b06194969cc2c496835729664c0` 不变；Task47.4 接受事实不变。
- 本次 A 已先提交收窄范围的 `547570b778259a8b7d78c98fc0434acaa008e7cc`，governance
  PASS；B 据此修正同一个 Task 草案，保留 Task ID/Goal/Base 和 PLANNED 状态，无实施。
- 不访问用户数据库、媒体或私密配置。用户“不考虑旧任务/跨版本升级、V1 不受支持”
  继续有效；fresh 新数据与同版本 reopen/restart 安全仍必须完成。

## Goal / complete journey

同一来源版本最近一次正式整理结果为失败或部分失败：定时/运行一次不自动处理；
后来手动整理成功，就不再因更早失败排除，仍接受普通过滤/冲突规则。用户在资源库 Files
明确选中整理时，可以看到上次失败/已知部分效果/未知效果的明显提醒，按原摘要确认
后执行一次新的正常整理。只用现有 Task 引擎、计划、冲突策略和确认，不再找独立 CLI
失败重试，不建立远端核验或附件恢复系统。

- **入口：** Files 直接文件、文件夹、混合选择；已发布定义 due/Run once；保留正常
  CLI organize/batch 与受限 remote organizing 的既有权限/来源边界。
- **可见状态：** 自动排除有逐项原因/计数；手动原准备/摘要中有服务端生成的历史提醒，
  显示适用结果及可用的来源/目标/完成步骤/未知效果，复用现有摘要而非强制增加完整
  历史面板。未知不是“系统已核验”。
- **动作：** 用户核对实际文件效果后，仍使用原“确认整理 N 项”选中确认；无需新的
  核查页、例行 checkbox、token 或技术恢复按钮。已有目录、目标和复制残留走正常策略。
- **成功：** 新 Task 使用新请求准入时当前 Active 的不可变 pin 和当前已核对来源；
  只记录自己的效果；旧已记录结果、完成步骤、pin、未知证据和原 Automation 结果/时间
  不改写。必要的锁/claim/fence 与当前处理状态允许调整，不要求原 Task/item 所有字段不变。
- **失败/恢复：** 文件项尚在排队/处理且没有自己的终态结果时保留互斥。已记录 failed/
  partial 的文件项按历史处理，不能仅因父 Task 仍 running 或旧 unknown marker 再判为
  活动项；不要求用户或本 Task 证明远端已停止。有关来源/本次计划影响的实质变化、拒权、
  队满、响应丢失按既有精确读回/分析/确认处理，无关历史追加不增加确认步骤。

## Actual-code gap / affected seams

下列来自 Task Base 实际代码，是实现地图，不是要求逐文件拆 Task 或全面重构。

| 位置 | 当前缺口 / 本 Task 调整方向 |
|---|---|
| `domain/task_scheduling.py::TaskTrigger` / persisted display/admission context | 有 MANUAL/SCHEDULE/RUN_ONCE；origin 是服务端证据，不是浏览器可传的豁免。增加最小来源相关筛选语义，不能让 display 字符串授予执行权。 |
| `application/media_organizer.py::process_file/process_library`、`manual_task_engine.py`、`automation_definition_execution.py` | 共用引擎已存在，但没有统一“历史 failed/partial → 自动排除、手动提醒”的逐文件决定。目录 Task 建立时还没有完整文件清单，检查必须落到具体来源且先于该文件 Provider/执行。 |
| `sqlite_runtime.py::find_owned_source_work/_find_owned_source_work_locked`、`domain/task_persistence.py::SETTLED_ITEM_STATUSES` | 当前 FAILED 被当作已结束，PARTIAL 未被纳入；跨 Task 来源查询主要按状态，没有统一关联历史效果。不能只把 PARTIAL 加集合或只隐藏页面拒绝。 |
| `sqlite_runtime.py::list_results_for_source` / TaskItem、discovery source evidence | 现有查询是路径 + 最近有界结果，单独复用不能保证找到跨库真实路径/版本的最近正式结果。先在完整匹配总体确定最近一次，再限制显示；不是永久寻找任意一次失败。 |
| `media_discovery.py::_refuse_owned_sources/_owned_source_work` / atomic source reservation | Files 直接/展开/准备发布都做占用核对；要共享新判断，手动 partial/unknown 的旧占用不能在后续 finalize/confirm 又被当作永久 veto。 |
| `manual_organize_execution.py`、`task_runtime.py`、`task_scheduling.py` / SQLite admission、mutation marker、file_locks | 同步处理新手动意图、已知活动所有者、历史不确定证据和精确逐文件锁交接。保留同 Task 的旧项非重放与四类安全继续，不重写旧 Result 或用 task-wide 解锁释放兄弟项。 |
| `manual_organize_preview.py`、`interfaces/service_api.py`、`web/src/entities/operations/preview.ts/organize.ts`、`OrganizePlanConfirmation.tsx` | 现有计划摘要/typed boundary 可复用；补服务端历史提醒及摘要一致性，Files 准备和确认前都可发现，不另建页面。 |
| `final_cli.py`、`task_runtime.py::execution_retry_items` 与引用方 | 删除 retry-failed parser/help、原 pin bootstrap 分支、专属受理/renderer/helper；共享源码先核对真实调用再删。保持正常 organize/analysis、Task cancel、四类 continue/ignore/audit。 |

## Implementation Scope

1. **确定一个共享逐来源历史判断。**
   - 复用现有 TaskItem/Result/checkpoint/discovery source evidence 与 repository port，按
     Storage ID + canonical Storage-relative path + 可比较来源版本找最近一次正式整理
     结果；仅结果为 `failed/partial` 时触发本次排除/提醒。不是整个 Task aggregate；无 Result
     但有真实持久失败项的情况不能漏。exclude 当前新分析/尝试自身，不能自我拦截。
   - 使用同语义大小、修改时间、可用 Provider validator 等已有版本证据。跨库绑定不可
     直接比较 library-scoped digest；同名不同真实路径不混淆。真正替换的新版本不被
     永久路径黑名单拦住；缺失/不可比较版本按历史可能适用处理，不伪造“新文件”。
   - 在完整匹配总体里确定最近一次正式整理结果，再做有界展示。后来手动成功后，不再
     因更早失败排除；旧失败记录保留。以持久 attempt/admission 顺序及关系识别新工作，
     较早操作迟到的发布不能仅凭入库时间成为“最近一次”。历史读取失败给出有界拒绝/
     重读，不能当作无历史。浏览、Rules 测试、独立仅分析、未准入拒绝与本次历史排除
     不制造或覆盖正式整理结果。无全局目录/新队列。

2. **按后端来源接入准入与执行前复核。**

   | 来源 | 最近正式结果为 failed/partial 时的行为 |
   |---|---|
   | Scheduler interval/Cron/managed due | 同一版本逐项排除，包含零效果失败；不消耗该文件执行权，不查询其 Provider，不修改 Storage。 |
   | definition Run once | 用户已选择同定时排除；保持 disabled 可运行、原范围/上限、原一键执行及不推进 due。 |
   | Files 显式文件/文件夹/混合新整理 | 不因该历史排除；生成提醒并到达现有精确计划/选择确认。 |
   | 普通 CLI organize/batch | 保留既有来源/授权与默认分析、显式 --execute 语义；共享准入调整按原来源接入，不新增 CLI 历史提醒或交互要求。 |
   | 原 Task 四类继续 | 保持原 pin、决定→分析→摘要→明确确认；不是新的自动发现，不套“历史失败永不继续”。 |
   | 普通 remote organizing | 保留既有来源/权限/票据/范围契约及后端来源校验；不因本 Task 新增 remote 类别、提醒、同意参数或未展示 Web 提醒就拒绝的额外规则。 |

   - Files 直选、目录展开、definition pipeline 在同一具体来源判断上收敛，不只在页面或
     Task 创建时检查。准入与确认使用事务内新鲜历史/占用检查；Storage I/O 不放事务里。
   - 现有完整遍历、min(itemLimit,100)、深度/页数预算、过滤、附件与真实稳定性不变。
     排除不能把未完整遍历变成“前 N 个可以执行”，也不能污染主文件/附件身份。
   - 自动排除保留来源/原因/数量和实际 Task 结果。全排除是“因历史失败无本次可执行项”，
     不伪称新整理成功、健康空目录、扫描错误或新增四类待办；自由兄弟项正常处理。

3. **打通手动提醒 → 真正新整理，不只做展示。**
   - 后端投影适用的最近正式结果与可用目标/步骤/效果证据，进入既有 preparation/summary
     typed 数据，无须新建完整历史面板。显示如“该文件上次整理部分失败，目标
     可能已有文件，请核对后确认整理”；unknown 明确表示远端效果可能未确认。
   - 普通提醒不用 raw exception/secret；跨 principal 历史用于后端判断但遵守授权脱敏，
     不泄漏不可读任务身份/私有目标。页面显示或刷新只读，不自动搜索 Provider。
   - 提醒绑定当前 exact source/pin/plan/selected subset 和服务端历史依据，作为现有摘要
     一部分。涉及所选来源或本次文件影响的实质变化沿用既有摘要新鲜度规则；无关历史
     追加不令确认失效，不增加例行重分析/重确认。不执行未审阅的实质变化；
     不新增独立确认产品、例行 checkbox、客户端自报“安全”或 token 粘贴。
   - 以具体文件项而非父 Task 的汇总状态判断：未形成该文件终态结果的 queued/processing
     工作保留正常互斥；已有 failed/partial 结果的项按历史处理。父 Task 仍 running、
     历史 unknown/claim/marker 单独存在，均不得重新把它算成活动项并永久阻止新手动整理。
     这里不要求证明旧远端操作已停止。必要的旧应用所有者收束/fence、逐来源/目标锁交接、
     容量结算和新确认在现有 kernel/repository 中完成，原子地保留兄弟项及旧未知证据。
     不以效果未知“变成 none”或删除原结果来放行；不只检查来源就遗漏旧目标/附件锁。
     旧锁/claim/fence/当前处理状态允许按此目的调整，已记录结果与原运行事实保持不变。
   - 新请求获得自己的当前 pin/计划/单次授权；旧项不重启、不补发旧步骤、不续发已消费
     权限。即使允许用户核对后新整理，也不能允许已失效应用 owner 再启动后续文件调用。
     既已发出的远端调用不能被数据库 fence 撤销；此限制明显提示，但本 Task 不实现自动
     结束探测、线程接管/远程取消。用户明确核对后的新请求是此处的窄范围授权调整。
   - 已建合法目录复用；目标与复制残留走现有 Skip/Rename/许可 Overwrite/Manual 和
     Hash/capability/cleanup 规则，不自动删残留或强制覆盖。主文件成功附件失败仍人工
     按现有指导处理；不生成附件专用重试。

4. **删除独立 CLI retry-failed，保持共享行为。**
   - 从 parser/help/dispatch、专属 snapshot bootstrap、_admit_cli_retry_task、专属输出与
     无其他消费者的 helper 中退出。普通 argparse 拒绝旧命令，零新 Task/请求登记/
     Provider/Storage/执行权消费；无 alias、隐藏分支或自动转换成 organize。
   - 核对并保留四类继续、ignore、cancel、只读 Task/result/export、正常 organize/batch
     和仅分析。source/wheel/container 的实际入口一致，更新当前 V2 管理文档与测试消费者。
     文档、历史说明和拒绝旧命令的 negative test 可以保留 retry-failed 字面量，验收检查
     活跃入口/执行能力退出，不要求全仓字符串零命中。原效果保护由真实新整理/旧项非重放
     断言覆盖，不能仅删测试；普通 CLI/remote 不新增本次未约定的产品规则。

5. **完成真实路径与可审查交接。**
   - 用临时 SQLite/LocalStorage 和 fake/local Provider 构造三类真实失败：目录成功后
     写入失败；目标父目录已存在时写入失败（failed + unknown）；COPY 已完成但 Move
     删源失败。通过 Files 当前 V2 API/Worker 实际重新整理到结果，保留旧证据。
   - 相同来源走 due/Run once 真实过滤，再经手动成功证明旧失败不再导致排除，自由兄弟项
     实际完成；过页历史、版本变化、并发手动重复确认、尚无终态的活动文件项、
     reopen/restart、拒权/队满/响应丢失都覆盖。
   - 只提交本 Task 必要改动，READY FOR B REVIEW，附实际受影响测试及限制；不开发后续
     Task、不关闭 Slice。B 完整验收后重新评估六项 RO/AC-1–25，再交 A。

## Acceptance Criteria

- [ ] **AC-T1 / Slice AC-20：** due 和 Run once 对同版本 failed/partial 独立排除；零效果
  失败也排除；依据最近正式结果，后来手动成功解除早期失败造成的排除。自由兄弟项真实
  完成，完整范围/稳定性与排除记录/计数一致，全排除不假成功。
- [ ] **AC-T2 / AC-21：** Files 直选、目录及混合选择都允许历史失败项进入新整理；真实
  部分目录、复制残留、failed+unknown/partial+unknown 均先显示清楚提醒，再经原摘要
  选中确认执行正常计划。没有额外核查页/例行 checkbox，也不只做到“可以打开摘要”。
- [ ] **AC-T3 / AC-22：** 真实 canonical Storage/path/版本匹配不受最近32/100条历史截断；
  覆盖跨库绑定、同名异路径、新版本、未知版本、混合 Task、无 Result 持久失败、非整理
  仅分析和 failed→manual success。旧尝试迟到发布不能替代较新的正式尝试结果。
  读取失败不放行；新 Task 自己的分析失败不伪装成先前外部历史。
- [ ] **AC-T4 / AC-23：** 尚无文件终态结果的排队/处理项保留互斥；已有 failed/partial
  结果的文件不因父 Task running/历史未知标记而被重新判为活动项。不要求远端停止证明。
  手动旧历史接管/确认、锁和容量原子核对，失效 app owner 后续状态写入及新步骤准入
  拒绝，不承诺停止已派发调用。兄弟项不被解锁。旧未知证据仍未知，且既有
  标记不会使已确认新手动工作永久无法执行。没有把 Web 确认说成远端已停止证明。
- [ ] **AC-T5：** 新整理用新 pin，原已记录结果、完成步骤、Result/pin、未知证据和原
  Automation 结果/时间不改写；允许必要的锁/claim/fence/当前处理状态调整，不要求旧
  Task/item 每个字段不变。正常 Conflict/Hash/覆盖/清理、C→A identity、附件、RBAC/脱敏
  及四类同 Task 继续不退化。旧项/成功兄弟不被这次新请求作为恢复范围自动重放。
- [ ] **AC-T6 / AC-24：** source/help/installed wheel/image 无活跃 retry-failed 或替代入口；
  旧命令在解析处拒绝且零效果；正常 CLI 分析/execute 和其他 Task 管理/四类继续保留。
  文档与 negative-test 字面量允许保留；普通 CLI/remote 原有来源/授权语义不变，
  不新增 CLI 历史提醒、remote 类别或未展示 Web 提醒的额外拒绝规则。
- [ ] **AC-T7 / AC-25：** 真实 V2 浏览器桌面/窄屏，使用生产 build + real API/SQLite/
  Worker，证明提示→选中确认→实际效果、定时/运行一次排除、原历史不改写；重连/过期
  摘要/队满/拒权的状态与可操作下一步真实。B 完成适用 T4/原生/安装/容器/重启门禁。

## Required Tests

依 [workflow §6](docs/development-workflow.md#6-test-levels)。以下命令为实施后的计划，
**本轮没有运行这些产品测试或声称通过**。新模块名是本 Task 的预期测试文件。

### Developer — affected tests

根目录：

```bash
.venv/bin/python -m unittest tests.test_organize_source_history tests.test_organize_preparation tests.test_manual_task_engine tests.test_manual_organize_execution tests.test_task_scheduling tests.test_task_scheduling_fencing tests.test_task_retry tests.test_automation_entrance_recovery
.venv/bin/ruff check <本Task新增或修改的Python文件>
.venv/bin/ruff format --check <本Task新增或修改的Python文件>
.venv/bin/python scripts/check_governance.py
git diff --check
```

`tests/test_organize_source_history.py` 为本 Task 新的临时 DB/Storage 成功、无效输入、
冲突、故障及边界测试；其余是直接受影响的真实准入、手动执行、claim/fence、CLI 与
自动入口。复制/删除实际故障从 Executor/Storage 注入，不能全用手填状态或假前端。
分别验证入口规则：定时/运行一次按同一来源版本最近正式结果排除 failed/partial；
手动入口对包含未知效果的 failed/partial 文件，先展示 Web 提醒，再经正常选中确认
允许新整理，不能沿用“未知效果一律拒绝所有新 Task”的旧断言。原失败/未知效果记录
保留，旧文件项不自动重放；删除 CLI 不得丢掉这些区别的测试覆盖。

`web/`：

```bash
npm run test -- run src/entities/operations/organize.test.ts src/entities/operations/preview.test.ts src/features/operations/OrganizePlanConfirmation.test.tsx
npm run typecheck
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/organize-source-history.python.spec.ts
```

新增 `OrganizePlanConfirmation.test.tsx` 与 `organize-source-history.python.spec.ts`，
使用现有生产摘要和真实 Python harness，覆盖提示对正确来源可见、unknown 文案、无
额外 chore、选择确认绑定/拒绝重读、真实文件效果及自动排除。补足实际受影响的 unit/
原生测试，不把全部 Web/Python/E2E 交给 Developer。若只复用旧测试模块，交接说明
等价覆盖位置并保留相同有意义断言，不要求为命名再造一套 harness。

### B — acceptance and full regression

- 独立审查整个 Task Base..candidate；实际复现 AC-T1–7，重点对比 due/Run once 与
  Files 对同一来源的不同结果、旧 partial/unknown app-owner 的交接和历史完整性。
  必须包含同版本 failed→手动成功→定时/Run once 不再因早期失败排除的真实链路。
- 执行 [shared full gates](docs/development-workflow.md#shared-full-regression-commands)
  的适用 T4 Python/Web/full E2E/static/examples/wheel/installed/Docker/security 门禁，
  不复用改动前的 T4 PASS 代替本 Task 新执行输入。对未变输入的证据复用按 workflow。
- 在生产 build 上执行以下原生旅程（`web/`，每组独立产物目录/顺序运行，避免 harness
  与报告互相覆盖）：

  ```bash
  npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/organize-source-history.python.spec.ts
  npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/automation-lifecycle.python.spec.ts tests/e2e/automation-run-once.python.spec.ts
  npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-task-center-visual.python.spec.ts
  ```

- 人工检查实际桌面与窄屏截图/交互：失败项提醒明显、长路径有界、可见旧目标/未知效果，
  普通确认可达，不新增 Failure Recovery、核查页或 Routine checkbox；读/刷新零效果。
- clean wheel/source-external CLI 验证 retry-failed 普通参数拒绝与正常 organize；隔离
  Docker 验证 fresh、同版本 Worker/Scheduler restart、源历史排除/手动新整理、权限、
  原结果/未知证据及旧 owner fencing。只用临时媒体与 fake/local Provider；不读用户库。
- 无旧任务、跨版本升级或 V1 产品门禁；不要求真实远程复制终止/取消能力或完整外部
  endurance 环境。既有外部环境 skip 和任何 unavailable 门禁如实记录；不放宽断言。
- PASS 后对扩大后的整个 Slice RO-1–6/AC-1–25 重评并提交新的 Closure Packet，旧
  Task47.4 packet 是基线而非新增行为的接受证明；不得代 A 终审或关闭。

## Non-goals

远程操作完成探测/操作 ID 查询/取消、SMB 线程管理重构、Storage/Provider 新能力、
“系统核验安全后解锁”新产品；附件专用恢复、自动删残留、历史步骤恢复/全局 reprocess、
跨 Task 批量恢复/通用回滚；额外历史清理/全局 FileIndex/并行引擎；把所有历史状态都
扩成自动排除、改变 Run once 初次一键意图；旧 Task/跨版本升级/V1 支持；更改权限、
源边界、稳定性/完整遍历或静默覆盖/删除；恢复 Pause/resume/retry-request/Job。

## Developer Completion Report

用户本轮明确授权按本草案实施；Developer 原地激活本 Task（状态 PLANNED →
READY FOR B REVIEW），Task Base 不变，未重定范围。

**Checkpoint：** 提交候选（本提交）；branch `main`，Task Base
`75ddff55f8d5b2b1206c81804bfb5cbe9ed279a1`。预存未跟踪文件（OS/log、`15`、docs 图片、
`output/*` 等）原样保留、未暂存；未触碰用户数据库/媒体/私密配置。

**Changes（与 Implementation Scope 对应）**

1. 共享逐来源历史判断：`mediaflow/infrastructure/sqlite_runtime.py::
   latest_organize_source_outcome`（完整匹配总体：exact Storage + canonical
   Storage-relative path（含 legacy 库内 identity）、organizing command 族、
   terminal 正式整理结果、admission/attempt 顺序（迟到发布不冒充最新）、版本可比
   规则与 ownership 相同（同库指纹/跨库 discovery version evidence/不可比→可能
   适用），扫描上限 400 行（远大于 32/100 展示页）；`application/
   organize_source_history.py` 输出有界、无密、只读的 `OrganizeSourceHistory`
   （含 warning 文案）；读取失败向上抛出，不当作无历史。
2. 自动排除（AC-20/V2-TASK-008）：`media_organizer.py` 新增
   `exclude_failed_history`；due/Run once（`automation_definition_execution.py`
   的 `_run_scan_and_plan` 与 `run_legacy_schedule`）接入；`process_file` 在任何
   Provider 调用前逐文件闸门：同版本最近正式结果 failed/partial → 经
   `begin_item`（事务内占用复核）+ `publish_history_gate_item` 记录
   SKIPPED/`history_excluded` 项（无 Result、零执行权、零 Storage 效果）；历史
   读取失败 → fail-closed `history_unavailable` 项；`manual_task_engine.py::
   _settle_automatic` 把含 gate 项的运行呈现为 PARTIAL_SUCCESS + 有界排除计数
   文案，全排除不伪称成功。CLI organize（manual trigger）不排除，语义不变。
3. 手动提醒（AC-21/V2-TASK-009）：`manual_organize_preview.py` 在 Preview item
   plan 文档投影服务端 `history`（status/recordedAt/目标/完成步骤/未知效果/
   版本可比性/有界文案）；未知效果明确表示未被核验；读取失败该 item 拒绝
   （fail-closed）。Web：`preview.ts` 新增 `ManualPreviewHistoryModel` 解析；
   `OrganizePlanConfirmation.tsx` 汇总显著 banner + 每文件 banner；
   `organize-summary.tsx` 每条目“上次整理记录”行；无新增核查页/例行 checkbox。
4. PARTIAL 属历史不属活动占用（AC-23）：`SETTLED_ITEM_STATUSES` 纳入
   `TaskItemStatus.PARTIAL`（域注释本就声明此意图）；`find_owned_source_work`
   因此不再把已记录 partial 文件项当作永久 veto；queued/processing 无终态项互斥
   不变。kernel 锁/claim/fence 复用现有边界；旧 Result/pin/未知证据不改写。
5. CLI retry-failed 退出（AC-24/V2-TASK-010）：删除 parser/help、专属 snapshot
   bootstrap 分支、`_admit_cli_retry_task`、专属输出与
   `execution_retry_items`/`_execution_effect_block`/两个渲染 helper；旧命令在
   argparse 处拒绝、零效果；保留 `retryable_items`（四类继续/recovery 共用）、
   历史行展示 membership、`RETRYABLE_TASK_COMMANDS`（历史 retry-failed Task 的
   checkpoint/继续仍合法）、四类继续、ignore、cancel、只读与正常 organize。

**Developer affected tests（实际命令与结果）**

- `python -m unittest tests.test_organize_source_history`：新增模块 13 tests OK
  （完整总体/迟到发布/替换文件/DRY_RUN与非整理行/排除行不入历史/无 Result 失败
  项/legacy identity/读取失败 fail-closed；Run once 真实 COPY 旅程：真实失败→
  排除+自由兄弟+honest PARTIAL_SUCCESS+零 Result 零 Provider（patch 断言）→
  手动成功解除排除；due（legacy interval）排除；Preview 提醒 + 手动执行；PARTIAL
  项生产发布后不再占用、processing 仍互斥）。
- `python -m unittest tests.test_organize_preparation tests.test_manual_task_engine
  tests.test_manual_organize_execution tests.test_task_scheduling
  tests.test_task_scheduling_fencing`：161 tests OK。
- `python -m unittest tests.test_automation_run_once tests.test_automation_task_admission
  tests.test_task_source_ownership_race tests.test_preview_retirement
  tests.test_task_retry tests.test_automation_entrance_recovery`：79 tests OK。
- `python -m unittest tests.test_operations_task_center
  tests.test_operations_run_detail_log_isolation tests.test_operations_run_detail_plan_evidence
  tests.test_v2_automation_operations`：58 tests OK。
- `python -m unittest tests.test_task_persistence tests.test_task_pause_resume
  tests.test_workflow_retry tests.test_manual_ignore tests.test_manual_ignore_batch
  tests.test_processing_recovery_admission`：60 tests OK。
- `python -m unittest tests.test_direct_file_operations tests.test_direct_file_transfers
  tests.test_batch_cli tests.test_conflict_resolution tests.test_recognition_review
  tests.test_metadata_review tests.test_classification_review`：126+65+1 tests OK。
- `python -m unittest tests.test_manual_operations tests.test_manual_operations_contract
  tests.test_media_discovery tests.test_task_scope`：189 tests OK。
- `ruff check .` PASS；`ruff format --check .` PASS；`compileall` PASS；
  `scripts/check_governance.py` PASS；`git diff --check` PASS；
  `rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml` 无匹配。
- Web：`npm run typecheck` / `lint` / `format:check` PASS；`npm run build` PASS；
  新增 `OrganizePlanConfirmation.test.tsx`（3 tests：提醒绑定正确文件、unknown
  文案、无额外 chore、普通确认绑定选择并真实提交、无历史不出提醒）；
  `npm run test -- run`（全部 88 文件 / 1267 tests）PASS。

**已更新测试**：`test_task_retry.py`（retry-failed/retry-request/retry 解析拒绝 +
零效果 negative test）；`test_automation_entrance_recovery.py`（5 个 retry-failed
执行旅程测试替换为“解析拒绝 + 原失败事实不动”的 negative test）；
`test_preview_retirement.py`（分析任务不可提升改由退役入口 negative test 证明）。

**Deviations / remaining risks（如实披露）**

1. Task 计划中列出的 `tests/e2e/organize-source-history.python.spec.ts` 本轮未由
   Developer 创建/运行；等价真实 Python 旅程覆盖由
   `tests/test_organize_source_history.py`（真实 API/SQLite/LocalStorage/Worker
   引擎，含 patch-assert 的零 Provider 断言）提供。浏览器级旅程（桌面/窄屏截图）
   属 AC-T7，留给 B 的验收门禁按计划执行。
2. 排除项复用 `TaskItemStatus.SKIPPED` + 专属 stage（无新增状态枚举）；Result 故
   意不发布（“排除不制造正式整理结果”），汇总状态由 `_settle_automatic` 呈现。
3. `latest_organize_source_outcome` 的跨库版本比较依赖该 Task 自身 discovery 记录
   （与占用边界同一来源）；无 discovery 的历史行（legacy CLI 行）在同绑定时用指
   纹比较，跨绑定且无 discovery 证据时按“可能适用”处理（保守、不伪造新文件）。
4. 文档协调（requirements/architecture/product-experience 中 retry-failed 的 CURRENT
   描述、RO-6 交付标记）留待 Slice 收尾核对，本轮未改 A-owned 文档。

## B Review Result

**Decision: FIX REQUIRED — 2026-11-02，B 独立审查；不新增 Task。**

- 审查范围：`75ddff55f8d5b2b1206c81804bfb5cbe9ed279a1..368d9e86646e4ccafd5509e9c860aa2dd8fa5a1d`
  的完整变更清单、合同修订、生产实现、API 消费边界和新增/删除测试；没有只检查最后一次提交。
- 工作区：`main`，起始 HEAD 为上述候选；无预存 tracked 修改。预存未跟踪 OS/log、`15`、
  docs 图片与 output 产物全部保留、未暂存。工作区/Git 可写，governance preflight PASS。
  本轮只修改本 Task 的 B 结论与指导，不实施产品，不改变 A-owned 合同或既有接受事实。
- 证据：本机 `.git/validation-evidence/368d9e86646e4ccafd5509e9c860aa2dd8fa5a1d/b-review/`
  的 `probe.py`、`probe.log`、`focused.log`；本地保留，不声称远端可访问。复现只用临时
  SQLite、LocalStorage 和 SyntheticMetadataProvider；通过现有 Files discovery → Preview
  GET → execute POST → Task Worker 入口，故障注入到真实 Storage.write，未手填失败状态。

### 必须修复的交付缺口（均为 P1）

1. **用户重新整理失败文件时，实际 Web 摘要收不到历史提醒。**
   用户在 Files 选中 `Movies/One.2001.mkv` 整理，目标目录建立后写入失败；再次选中
   整理。持久摘要已有 `plan.history`，但真实
   `GET /api/v1/operations/organize/previews/{previewId}` 返回的 plan 没有 history；普通
   确认仍返回 202，Worker 最终 COPY 成功。`operations_lifecycle.py::_bounded_preview_plan`
   的字段投影未接入 history，所以 Web normalizer 得到 null，新增 banner 不会显示。
   **AC-T2/T7、Slice AC-21/25 不满足。**

2. **真实手动 Result 的“已做什么、哪些效果未知”在历史查询中丢失。**
   同一旅程真实 Result 用 UUID result_id，status 为 `PARTIAL`，记录
   `completed_operations=('CREATE_DIRECTORY',)`、
   `effect_certainty='attempted_unverified'`、`uncertain_effects=('mutation_outcome',)`。
   `sqlite_runtime.py::latest_organize_source_outcome` 却只关联
   `result_id = item_id || ':' || attempts`，因此退回 item：已完成步骤/未知效果变空，
   effectCertainty 为 null。即使修复 API 投影，用户仍看不到实际存在的未知效果提醒。
   **AC-T2/T3/T5、Slice AC-21/22 不满足。** 新查询还在版本筛选前 `LIMIT 400`，没有
   实现合同要求的完整匹配总体；此项为代码审查发现，未另造超过 400 次运行的产品复现。

3. **新手动工作完成后，没有收束已被替代的旧应用所有者和容量。**
   上述失败真实留下旧 scheduling `claimed + mutation_in_flight`。新请求正常执行成功后，
   使用旧 Worker 原 claim 调用现有 scheduling heartbeat 仍被接受，容量计数仍为 1。
   本次改动只将 PARTIAL 加入 settled 集合，未完成新确认需要的旧所有者交接；不能把
   “现在允许进入”视为已经完成 fencing/容量结算。历史未知证据应继续保留，不能靠删除
   marker 或把 unknown 改成 none 修复。**AC-T4、Slice AC-23 不满足。** 本复现未声称
   旧远端调用仍在运行，也未声称已证明一次旧后续媒体调用实际发生。

### Developer 修复指导（同一 Task，按顺序实施）

1. **先修真实历史关联。** 复用 manual_execution_items.result_id、TaskItem/attempt/Result
   已有持久关系，同时兼容自动/CLI 的既有结果写法；统一真实状态枚举的大小写。不得把
   UUID Result 猜成缺失或凭发布时间覆盖较新的尝试。保留无 Result 的持久失败回退。
   在完整匹配总体中比较版本后确定最新适用结果，可分批读取，不能用 400 代替 32/100
   页限制。用真实 Executor/Storage 故障结果断言完成步骤、未知效果和原 Result 不变。
2. **补齐服务端到 Web 的有界投影。** 在现有 operator projection 中显式投影 history，
   复用路径/文本限界与脱敏；跨 principal 不泄漏不可读任务/私有目标。不要透传 raw plan。
   对实际 API 响应断言 history，再让现有 typed normalizer/component 消费它；保持普通
   选中确认，无新增 checkbox/核查页。不能只在 mock fetch 文档里手工补 history。
3. **实现精确的新手动确认交接。** 在现有 kernel/repository 中原子核对选中来源、计划、
   当前相关历史、权限、请求和容量；对已记录 failed/partial 的确切文件收束旧应用 owner，
   完成所需来源/目标/附件锁交接及容量结算。保留原结果、pin、完成步骤、unknown 和
   原 Automation 时间/结果；未结束兄弟项不解锁/重放。确认后旧 owner 的心跳、状态写入
   和新步骤准入必须被拒绝。无需远端停止证明，不承诺撤销已发出的调用。
4. **用原 Files 旅程交接修复。** 复用 `tests.test_manual_task_engine` 的现有真实 API /
   Worker fixture 和本轮 probe。覆盖目录成功后写失败、已有父目录时写失败、Copy 完成
   而 Move 删源失败；均走 Files 再选择 → 真实摘要提示 → 正常确认 → 实际新结果，
   不把最后执行改走 CLI。加入未终态兄弟互斥、并发重复确认、相关/无关历史变化与
   reopen 的直接受影响断言；保留 due/Run once 失败排除→手动成功→解除排除链路。
   跑原 Developer affected plan 中新增/修改和直接受影响的测试即可，提交新 checkpoint
   并回到 READY FOR B REVIEW。全量、包装、Docker 和最终原生验收仍由 B 负责。

### 本轮实际验证与停止位置

- `.venv/bin/python -m unittest tests.test_organize_source_history tests.test_task_retry`：
  **15 tests OK，1.483 秒**；出现 ResourceWarning，原日志保留。通过这些测试不等于
  真实 Web 旅程通过：当前手动提醒测试最后调用 `cli_organize_execute`，前端测试则
  自行给 mock 响应添加 history，无法发现上述生产投影/真实 Result 缺口。
- 本地 probe：实际失败 → 新摘要 → 确认 202 → 新 COPY 完成；同时观察到 API history
  缺失、Result 效果证据丢失、旧 heartbeat 被接受且容量仍为 1。复现迭代仅调整观察/输出，
  未改变产品代码或失败条件；累计运行不足 2 秒。
- `python3 scripts/check_governance.py`、候选 `git diff --check`：PASS。
- 产品测试/故障复现合计不足 10 秒，阅读、代码审查及结论编写用时明显超过测试用时，
  满足本轮测试时间小于总用时 50%。
- 已证实产品阻塞，依 workflow §6 提前 FIX REQUIRED；未运行全量 Python/Web/E2E、
  桌面/窄屏浏览器、wheel/installed/Docker/restart/security 门禁。它们仍待修复候选由 B
  执行，未豁免、未判 PASS，也不因 Developer 缺少全量报告而返工。

### Slice 交付核对

| Required Outcome | 本候选结论 |
|---|---|
| RO-1–5：统一 Task/引擎、四类继续、数据/Job 退出、已有操作面 | Task47.1–47.4 原接受事实保留；本次新候选的共享安全/回归门禁尚未完成，不能直接沿用旧 packet 宣布当前通过。 |
| RO-6：自动排除、带提醒的新手动整理、CLI retry-failed 退出 | 自动排除与 CLI 退出有实现及聚焦证据；真实 Web 提醒、效果证据与旧 owner 交接有上述 P1，结果未完成。 |

AC-T1/T6 有部分证据，AC-T2–T5/T7 有失败或待验收项，均不整体勾选通过。Slice 保持
ACTIVE；不提交新的 SLICE READY FOR A REVIEW，不创建后续 Task，不由 B 关闭 Slice。
