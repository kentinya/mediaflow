# Task47.5 — FIX REQUIRED

最新候选 `3fb1050065e2e32802e2a03a6da925d15019fdaa`（实现 `13d6d4f4`）经 B 复核，
容量结算、旧批次收尾和简短提醒三项已通过。当前仅有一项 P1：自动入口读取历史与真正
逐文件准入之间存在并发间隙，可能继续整理此时已产生最新失败结果的同版本文件。
详见末尾 B Review Result / Developer 修复指导；不重做已通过的三项修复。
Task ID/Goal/Base 与 Slice 边界不变；不授权派生代理、push、部署或 Slice 关闭。
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
  历史面板。普通提醒用简短人话；可用目标和已知影响放在现有条目详情，内部步骤代码、
  claim/lock/token 不成为必读内容或用户操作。未知不是“系统已核验”。
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

## Developer Completion Report — FIX ROUND（候选 2）

按 B Review 的三项阻塞在同一 Task 内修复；Task ID/Goal/Base 与 Slice 边界不变，
未扩大范围。工作区 `main`，本轮起始 HEAD `76598900`（B 指导澄清提交），无预存 tracked
修改；预存未跟踪文件（OS/log、`15`、docs 图片、`output/*` 等）原样保留、未暂存。
未触碰用户数据库/媒体/私密配置；未 push、未部署、未自判 PASS。

**Changes（对应 B 修复指导 1–3）**

1. **历史事实读取（阻塞 2）**：`sqlite_runtime.py` 重写
   `latest_organize_source_outcome`：
   - Result 关联改走真实持久边界：`LEFT JOIN manual_execution_items mei ON
     mei.task_item_id = i.item_id`，`r.result_id = COALESCE(mei.result_id,
     i.item_id || ':' || i.attempts)`——手动 UUID Result 与自动/CLI/继续
     `item:attempts` Result 各按其真实写法命中，无 Result 的持久失败项仍回退
     item 行；目标/完成步骤/效果确定性/未知证据按 Result 优先读取（COALESCE）。
   - 状态大小写统一为小写（手动 `PARTIAL` → `partial`），排除/提醒判断
     不再漏判。
   - `LIMIT 400` 撤销：新共享迭代器 `_iter_organize_source_outcome_rows_locked`
     以 keyset 分批（每批 400）按 admission/attempt 顺序读取**完整匹配总体**，
     最新可适用行胜出；迟到发布不冒充最新尝试的语义不变。
2. **真实 API → 页面（阻塞 1）**：`operations_lifecycle.py::_bounded_preview_plan`
   新增 `history` 投影与 `_bounded_preview_history`（字段级边界与脱敏：status/
   recordedAt/destinationStorageId/destinationPath/completedOperations/
   uncertainEffects/effectCertainty/versionApplicable/warning），不透传 raw plan。
   真实 Preview GET 现已携带 history，现有 Web typed normalizer
   （`preview.ts::normalizeHistory`）与 `OrganizePlanConfirmation.tsx` banner 直接
   消费，无需前端改动；无新增核查页/例行 checkbox。
3. **逐文件交接与容量结算（阻塞 3）**：
   - 新增迁移列 `task_items.superseded_by_task_id`（additive，fresh 与同版本
     reopen 均安全；`_TASK_ITEM_UPSERT` 不触碰该列）。
   - `admit_manual_execution` 确认事务内新增：被替代源守卫（adopted Task 的
     已交接来源以 `source_superseded` 拒绝）+ 每个确认项的
     `_hand_off_superseded_source_owner_locked`——在同版本最近正式结果为
     failed/partial、旧 owner 为未完成 kernel Task 时：标记旧 item（guarded
     UPDATE，不覆盖已有标记）、仅当变异边界属于被交接项时收束该边界（其他项的
     未验证边界绝不触碰）、无剩余机器工作且无待处理控制时释放名额
     （全部 settled → SETTLED，含诚实聚合修正；仅剩人工决定 → WAITING_HUMAN），
     仍有机器工作则保留原 claim 与 1 个名额。排程/处理中且无终态的来源完全不触碰，
     file_locks 互斥保持原样。
   - `_require_scheduled_item_locked`：已交接 item 的 START/PROGRESS/OUTCOME
     发布一律拒绝（旧 owner 不能再启动后续步骤或改写旧结果）；旧 Result/pin/
     完成步骤/unknown 证据与原 Automation 时间不改写。
   - 公开包装 `hand_off_superseded_source_owner`（独立事务）供仓库级旅程复用。

**Developer affected tests（实际命令与结果）**

- `python -m unittest tests.test_organize_source_history`：18 tests OK（新增：
  手动 UUID Result 完整证据读取 + 大小写统一；>400 行完整总体跨批找到最新可适用；
  手动 Result 越批；真实 Files→引擎旅程两例——单文件 uncertain 失败后新整理
  交接：旧 Task SETTLED、旧 claim 心跳 REJECTED、容量 0、旧 Result/证据逐字段
  不变、标记=新 Task；批 [One,Two] One 失败 Two 未完成：交接后旧 Task 保留
  名额与有效心跳、One 迟到发布被拒（"handed off"）、新 Task 完成、旧 Result 不变）。
  失败注入位于真实 Storage.write/`_ExplodingExecutor` 边界，非手填状态。
- `ManualHistoryWarningJourneyTests` 新增真实 Preview GET 断言（阻塞 1 的 API
  级回归；经突变校验确认真实执行）。
- `python -m unittest tests.test_organize_preparation tests.test_manual_task_engine
  tests.test_manual_organize_execution tests.test_task_scheduling
  tests.test_task_scheduling_fencing tests.test_task_retry
  tests.test_automation_entrance_recovery`：167 tests OK。
- `tests.test_automation_run_once tests.test_automation_task_admission
  tests.test_task_source_ownership_race tests.test_preview_retirement`：73 OK；
  `tests.test_operations_task_center tests.test_operations_run_detail_log_isolation
  tests.test_operations_run_detail_plan_evidence tests.test_v2_automation_operations`：
  58 OK；`tests.test_task_persistence tests.test_workflow_retry
  tests.test_manual_ignore tests.test_manual_ignore_batch
  tests.test_processing_recovery_admission tests.test_manual_operations_contract`：
  55 OK；`tests.test_direct_file_operations tests.test_batch_cli
  tests.test_conflict_resolution`：74 OK；`tests.test_manual_operations
  tests.test_media_discovery tests.test_task_scope`：185 OK。
- `python -m unittest discover -s tests`：**2518 tests OK（skipped=7，既有 skip）**。
- `ruff check .` / `ruff format --check .` PASS；`compileall` PASS；
  `scripts/check_governance.py` PASS；`git diff --check` PASS；
  `rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml` 无匹配（exit 1）。
- Web（cwd `web/`）：`npm run typecheck`、`lint`、`format:check` PASS
  （prettier 对既有 `OrganizePlanConfirmation.test.tsx` 的格式修正 3 行）；
  `npm run test -- run` 88 文件 / 1267 tests PASS；`npm run build` PASS。
- 契约夹具按测试官方路径再生
  （`MEDIAFLOW_UPDATE_FIXTURES=1`）：`manual-operations.json` 仅新增两处
  `"history": null` 字段（真实 API 投影的体现）。

**Deviations / remaining risks（如实披露）**

1. 批量场景中 Two 为"排队机器工作"（PROCESSING、无自身终态）时的**最终收束**
   走既有中断执行恢复路径（reconcile/租约接管），属既有机制；本 Task 只断言
   交接不触碰其边界且名额保留（B 验收表第 2 行要求），未新增恢复能力。
2. 浏览器级旅程（桌面/窄屏截图，AC-T7）未由 Developer 执行，与上轮相同留给
   B 的验收门禁；Web 组件测试经既有 typed normalizer 消费真实 API 形状。
3. 文档协调（requirements/architecture/product-experience 的 CURRENT 描述、
   RO-6 交付标记）仍留待 Slice 收尾核对，未改 A-owned 文档。
4. 交接目标的版本可比性沿用与历史判定/占用边界同一证据链；无可比版本时按
   "可能适用"处理（保守，不伪造新文件）。

## Developer Completion Report — FIX ROUND（候选 3）

针对 B 本轮两条已实测阻塞（批次全部结束后仍占一个名额；批次进行中接手已失败文件后旧批次
结算误报技术失败）及用户确认的简短提醒要求，在同一 Task 内修复；Task ID/Goal/Base 与
Slice 边界不变，未扩大范围。工作区 `main`，本轮起始 HEAD `ccd4781c`，无预存 tracked
修改；预存未跟踪 OS/log、`15`、docs 图片、`output/*` 等原样保留、未暂存。未触碰用户数据库/
媒体/私密配置；未 push、部署、自判 PASS。

**候选：** `13d6d4f487d92e3a9b4b93683c938be139b5decd`（实现 + 测试 + Web + 真实 e2e 的
单一 checkpoint；报告另提交）。范围 `ccd4781c..13d6d4f4`。

**Changes**

1. **结算边界区分“已记录未知效果”与“仍在执行”（阻塞 1）**：
   `sqlite_runtime.release_scheduled_claim` 新增同事务参数
   `close_recorded_unknown_boundary`。仅当（a）marker 指向本 Task 的一个 item，(b) 该 item
   已非 pending/processing，(c) 本 Task 无任何 pending/processing 兄弟，(d) 该 item 的
   attempt 已发布 Result 时，才在同一 release 事务内清除 marker 并照常结算；否则仍以原
   `TaskControlRejected` 保留 claim/名额。Result、unknown effects、completed steps 与
   Automation 记录一律不重写。
2. **共享引擎接入**：`manual_task_engine` 的自动结算（runner 返回）、自动异常路径、手动
   执行结算、discovery/等待人工边界与 cancel 确认均以该标志结算；真实 unproved 边界
   或并发 control 变化仍保留 claim 与名额，不会变成技术失败（`_refusal_keeps_claim`）。
   有 machine work 时自动路径行为不变（不释放）。
3. **旧批次结算不再重发已交接 item（阻塞 2）**：`release_scheduled_claim` 对
   `superseded_by_task_id` 非空的 item 只读其旧终态参与调用方聚合，不再次 PROGRESS 发布，
   因此不会触发 per-file fence 的 `TaskSchedulingError`；旧 Result/行保持原样。
4. **简短提醒（用户已确认）**：`OrganizeSourceHistory.warning()` 收短为“上次整理未完成/
   目标可能已有文件 +（确有 unknown 时）部分存储效果未确认 + 请核对…”，不再把
   CREATE_DIRECTORY/mutation_outcome 等代码或时间戳塞进普通提醒；时间、目标、已完成/
   未确认效果改在既有条目详情以人话展示（`organize-summary.tsx` 映射；未知标识符仍如实
   保留）。聚合提醒抽为共享 `OrganizeHistoryReminder`，Run once 摘要、Files 创建摘要
   与共享 `SamePagePlanSummary` 一致显示；无新增核查页/例行 checkbox/令牌操作。
5. **真实浏览器旅程**：新增 `web/tests/e2e/organize-source-history.python.spec.ts` 与
   harness 控制路由 `seed-recorded-unknown-history`（真实 Files 准入→分析→精确摘要→
   选中确认→Task/Worker 发布，仅 executor 边界注入真实 `PARTIAL`/unknown 结果）。旅程
   实测：种子批次 settled、marker 空、容量与 seed 前相同；Files 提醒与条目详情可见且无
   额外确认物；确认前零效果；普通确认后 Worker 实际 MOVE，来源消失、目标真实存在。

**Developer affected tests（实际命令与结果）**

- `.venv/bin/python -m unittest tests.test_organize_source_history tests.test_task_scheduling
  tests.test_task_scheduling_fencing tests.test_manual_task_engine
  tests.test_v2_automation_run_once`：148 tests OK。
- `tests.test_organize_source_history`（单独，多次）：21 tests OK。新增/改写覆盖：
  批次全成功占 1 名额后释放 0；零效果失败（executor 边界注入 none）结算 0；末项
  partial/unknown 批次 settled、marker 空、容量 0、旧 Result 逐字段不变、成功兄弟独立；
  失败单文件批次**未做任何新整理前**即释放名额，随后 Files 提醒→确认→真实成功；
  接手旧 owner 的 remaining work 仍占 1（原断言保留）。
- `tests.test_task_scheduling.CapacityTransitionTests`：新增
  `test_finished_settlement_counts_a_superseded_item_without_republishing_it`
  （真实 begin_mutation→unknown Result→public hand-off→兄弟成功→旧批次 settle 成功、
  capacity 0、superseded 行/Result 不变）；10 tests OK。
- 直接受影响回归：`tests.test_organize_preparation tests.test_manual_organize_execution
  tests.test_task_retry tests.test_automation_entrance_recovery`（167→188 tests OK）；
  `tests.test_automation_run_once tests.test_automation_task_admission
  tests.test_task_source_ownership_race tests.test_preview_retirement`（106 OK）；
  `tests.test_operations_task_center tests.test_operations_run_detail_log_isolation
  tests.test_operations_run_detail_plan_evidence tests.test_v2_automation_operations
  tests.test_task_persistence tests.test_workflow_retry tests.test_manual_ignore
  tests.test_manual_ignore_batch tests.test_processing_recovery_admission
  tests.test_manual_operations_contract`（113 OK）；
  `tests.test_direct_file_operations tests.test_batch_cli tests.test_conflict_resolution
  tests.test_manual_operations tests.test_media_discovery tests.test_task_scope`（259 OK）。
- 静态：`ruff check .`、`ruff format --check .`、`compileall`、`scripts/check_governance.py`、
  `git diff --check` PASS；`rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml` 无匹配（exit 1）。
- Web（cwd `web/`）：`npm run typecheck`、`lint`、`format:check` PASS；
  `npm run test -- run src/features/operations` 23 文件 / 245 tests PASS；
  `OrganizePlanConfirmation/OrganizeCreationPage/organize/preview` 45 tests PASS；
  `npm run build` PASS。
- 真实 e2e：`npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/organize-source-history.python.spec.ts` **1 passed（Chromium，生产 build +
  real API/SQLite/Worker/LocalStorage）**，覆盖上述容量、提醒、确认、真实 MOVE。

**Deviations / remaining risks（如实披露）**

1. B 的原始 10 文件 Run once 反例以同共享结算边界的真实 Files 批次 + 单文件自动旅程覆盖；
   未再写 10 文件专用 harness 断言，批次在途情形沿用既有 `SupersededOwnerWithRemainingWorkTests`
   的 1 名额断言（未做真实线程暂停写法）。
2. 浏览器旅程覆盖 Files 桌面宽度与提醒/确认/真实效果；窄屏截图、Docker/wheel/installed/
   restart/安全门禁仍是 B 的 T4 验收项，未由 Developer 执行。
3. 未知效果的历史仅按既有 Result 证据展示（humanized），未新增远端完成探测/取消；
   “远端调用可能已发生、无法由本页证明是否完成”仍在 warning 中明示。
4. 文档协调（requirements/architecture/product-experience CURRENT、RO-6 交付标记）
   仍留待 Slice 收尾，未改 A-owned 文档。

**测试时间占比**：本轮实际测试执行（unittest + vitest + Playwright e2e，不含 build/静态检查）
约 4–5 分钟，为本轮总用时（约 30 分钟）的约 15%，低于 30% 上限。

## B Review Result

**Decision: FIX REQUIRED — 候选 3fb10500；原三项修复通过，仅剩下述一项 P1。**

- 完整 Task 范围：`75ddff55f8d5b2b1206c81804bfb5cbe9ed279a1..3fb1050065e2e32802e2a03a6da925d15019fdaa`。
  本轮核对完整 manifest 及此前审查事实，逐项审查 `ccd4781c..13d6d4f4` 的生产、测试、
  Web 与 harness 改动；`13d6d4f4..3fb10500` 只改 TASK.md，执行输入相同。
- 本轮开始 `main` / `3fb1050065e2e32802e2a03a6da925d15019fdaa`，无预存 tracked 修改，
  预存 OS/log、`15`、docs 图片、output 等 untracked 全部保留未暂存。工作区/Git 可写，
  治理预检 PASS；没有实施产品、push、部署、派生代理或 A Final Review。
- 本机证据目录：`.git/validation-evidence/3fb1050065e2e32802e2a03a6da925d15019fdaa/b-review/`。
  其中 `artifact-manifest.json` 记录日志/图片/wheel 摘要，`timing.json` 记录测试窗口；
  原始失败和已适配的成功结果均保留，不声称这些产物远端可访问。

### 原三项修复的实测结论：通过，不再作为阻塞

| 用户结果 | B 独立证据 |
|---|---|
| 整批全部结束后不占名额 | 原 10 文件 Run once probe 重跑：全成功 0；8 成功/2 零效果失败 0；8 成功/1 partial+unknown/1 failed 全部结束后也为 0。实际写入期间整批占 1，Result/unknown 保留。 |
| 旧批次运行中重新整理已失败 A，旧 B 仍可完成并正常收尾 | 原真实线程 probe 重跑：B 的 LocalStorage 写入确实未返回时，新 A 走 Files 提醒/确认后成功；容量 1→2→1。B 返回后旧批次诚实 partial_success、无技术结算错误，最终 0；旧 A Result 不改写。 |
| 简短提醒可见，正常确认可达 | 生产 build 上真实 API/SQLite/Worker 浏览器旅程通过；390×844 窄屏按“Open menu→Files→更多资源库→source”真实入口完成提醒→普通确认→实际 MOVE，截图人工检查，页面无横向溢出、无额外 checkbox/核查页。 |
| 已有目录与 Copy 残留仍能正常新整理 | `residual_probe.py`：已有目标父目录时写入失败（FAILED+unknown）后新 MOVE 成功；COPY 验证完成但 Move 删源失败（PARTIAL+COPY+unknown）后，经现有冲突 Rename 决定→分析→摘要→确认，新 MOVE 成功，原 Result 保留。 |

单文件、识别/元数据/分类/冲突决定与剩余兄弟项的既有旅程进入本轮全量；source-external
已安装 wheel 另跑 6 项真实 API/Worker 旅程通过。等待人工且没有机器工作的 Task 不占槽，
但对应文件仍由原工作保留；processing 文件同样不能另开整理。此前“unknown 就必须永久
占名额”“只重新整理 B 后旧 Task 必须占 1”两项错误前提保持撤回，不恢复旧建议。

### 唯一 P1：自动入口可能使用过期的失败历史判断而误处理文件

**真实用户旅程（Run once 与 Files 两个已有入口并发）：**

1. 自动 Task 已建立，在准备某个文件 A 时读到“没有适用的失败历史”。此时还没有为 A
   建立具体 TaskItem/取得来源占用；外层 Task 不等于已接手目录中的每个文件。
2. 在自动任务真正接手 A 前，用户从 Files 选择同一版本 A，经正常摘要确认执行；真实
   Storage.write 失败，持久记录 `PARTIAL / attempted_unverified`。来源文件没有改变，
   目标目录虽创建，目标媒体文件尚不存在；这个手动工作已经结束。
3. 自动入口应在本次逐文件准入时读到最新 partial 并排除 A，零该项 Provider/媒体效果。
   实际却继续使用第 1 步的旧判断，最终发布 success/COPY，目标媒体文件真实出现。

`admission_history_race.py` 从实际 Run once / Files API 与 Worker 驱动临时 SQLite、
LocalStorage、SyntheticMetadataProvider。只在已有只读历史查询返回与 item 准入之间用
Event 排定交错，不改变查询结果、不手填状态、不构造新产品入口；手动失败通过真实
Storage 写入故障形成。复现断言 `history_excluded != completed` 失败（exit 1），日志明确
记录手动 PARTIAL 在自动文件准入前已落库，随后自动 COPY 成功，新增目标文件数为 1。

**原因与定位：** `MediaOrganizerService.process_file` 先执行 `_automatic_history_gate`
（只读），之后才调用 `KernelTaskCoordinator.begin_item`。后者经
`TaskSchedulingService._begin_item_with_ownership` /
`SQLiteTaskRepository.begin_scheduled_item_with_ownership` 的事务只重新核对当前来源占用，
没有原子复核最新适用正式整理结果；已终态 partial 不再是活动占用，因此旧历史判断可以
穿过这个间隙。due 与 Run once 共用该自动源 gate；本次并发复现使用 Run once，未声称
单独重跑了 due 的同一交错。此缺口属于 AC-T1/T3、Slice RO-6 / AC-20/22 及原计划中
“准入事务内新鲜历史/占用检查”，不是新增产品范围。

### Developer 修复指导（同一个 Task47.5）

1. **在最终逐文件准入事务里复核历史。** 复用现有 kernel/repository 的来源准入边界，
   将服务端自动来源语义、canonical Storage/path、当前可比版本的最新正式结果判断，与
   活动占用核对、该项执行/排除登记原子完成。保留当前历史查询语义，不仅在 Service 里
   再多读一次后仍分开写入；Storage/Provider I/O 仍在事务外，不新建队列或全局 FileIndex。
2. **历史在间隙中变化时，按最终适用结果处理。** 最新 failed/partial 应生成现有有界
   history_excluded 原因/计数，该项不调 Provider、不变更媒体、不制造新的正式整理成功
   Result、不消费该项效果授权；自由兄弟照常处理。历史读失败保持 fail-closed。新的
   真替换版本可正常处理，后来手动成功可解除早期失败排除；旧 Result/unknown/步骤/pin
   和原 Automation 时间/结果不改写。不要靠整库锁或外层目录 Task 抢占所有尚未发现的
   文件，去拒绝当时仍空闲且合法的 Files 请求。
3. **只作用于既定自动入口。** 使用后端已验证的 due/Run once 初次逐文件上下文，不让
   浏览器自报豁免；Files 新整理、普通 CLI/remote 的原有语义与原 Task 四类继续仍按
   原合同处理，不因把检查下沉而新增历史拒绝或确认步骤。保留刚通过的容量、旧批次
   收尾和简短提醒修复；正在处理/待四类决定的文件继续互斥，等待人工不占机器槽。
4. **补真实并发回归并交接。** 将本轮 probe 的同步点纳入现有受影响测试，至少覆盖
   due/Run once 与手动请求的同来源交错：自动旧读后手动 partial/failed 已落库，再让
   自动准入，应排除；证明该项零后续 Provider/Storage 效果，兄弟独立处理，旧结果保留。
   补正常先后顺序、手动后成功/版本替换、历史读取失败及来源已被活动项占用的直接
   影响断言。先跑失败复现及下列直接受影响模块，不交回全量矩阵：

   ```bash
   .venv/bin/python -m unittest tests.test_organize_source_history tests.test_task_source_ownership_race tests.test_task_scheduling tests.test_task_scheduling_fencing tests.test_automation_run_once tests.test_automation_task_admission tests.test_manual_task_engine
   ```

   如接口/投影发生实际变化再补相应 Web 测试。提交新 checkpoint 和实际结果，回到
   READY FOR B REVIEW；B 对修复候选独立执行适用验收与最终 T4 门禁。

### B 已执行的回归与门禁

| 范围 / 命令 | 实际结果 / 日志 |
|---|---|
| `.venv/bin/python -m unittest discover -s tests` | 2522 tests OK，skipped=7，319.418 秒；`python-full.log`。有 ResourceWarning，原样保留，不把 skip 当通过。 |
| Python 静态/依赖/示例 | ruff check/format、compileall、pip check、两份 example config validate、governance、完整 Base..candidate diff check 通过；FFmpeg/FFprobe 搜索无匹配。 |
| Web 质量与全量单测 | typecheck/lint/format/build 通过；88 files / 1267 tests 通过；`web-*.log`。 |
| fake 浏览器与真实历史浏览器 | 默认套件混入新 Python spec 导致端口错误，原 `default-e2e.log` 保留。按下面明确分组，253 fake tests 通过（`fake-full.log`）；原 Python spec 在指定 real config 上 1 passed（`native-e2e.log`），没有删除/减弱断言或漏跑该项。 |
| 真实 Automation / Task Center | automation lifecycle + Run once 指定 `playwright.python.automation.config.ts`：17 passed；Task Center 八视图/同页摘要 production harness：2 passed；`automation-native.log` / `task-center-native.log`。 |
| 窄屏视觉 | B 的只读证据用 spec 保留原断言，补实际移动导航及截图，390×844：1 passed；`narrow-adapted-final.log`、`narrow-summary.png`、`narrow-confirm.png`，人工已检查。 |
| clean wheel / source-external | wheel smoke 通过，外部独立 venv 从 site-packages 导入、当前 6 个真实决定/整理旅程通过；`wheel-smoke.log` / `installed-current.log`。wheel SHA-256 `9c9a8b62279f8e4aface4e499052c4ab216cee5a1f6600b429cc0b82de2d57f0`。 |
| Docker fresh/security | exact committed context、四服务、实际手动整理、挂载/non-root/RBAC/脱敏检查通过；`docker-security.log`。系统临时目录 bind 最初不可见，改用已验证可挂载的 `.git/.../docker-tmp` 后通过；初始失败日志保留。 |
| Docker 同版本 restart/faults | API/Worker/Scheduler/Notification Worker 重启、真实 COPY、旧 owner 拒写和 uncertain 非重放通过；`docker-restart.log`。候选 tag `mediaflow:task47-5-3fb10500`，最后 restart build image `sha256:802ccda31fa8e3ae2db76cfb544923d2167c9e8239603401f8ba865b41038813`。 |
| 关键补充复现 | capacity、live-sibling、residual 三类复现通过；仅 `admission-history-race.log` 为上述产品 P1 失败。 |

fake 全量实际命令（cwd `web/`）为：

```bash
npm run test:e2e -- --grep-invert 'a recorded partial history warns, then the confirmed new organize takes effect' --output=<本轮独立fake产物目录>
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/organize-source-history.python.spec.ts --trace=on --output=<本轮独立native产物目录>
```

新 Python case 在正确 real backend 上完整执行，未作为 skip 隐藏失败。默认 config 的
发现分组问题属于测试路由 P2，可随本 Task 修正，不单独建工具 Task，也不把它当新产品阻塞。
旧 `installed_recovery_smoke_test.py` 引用了已不存在的历史测试文件，未声称它通过；B 改用
当前真实测试复制到 source-external venv，实际 installed-package 6 tests OK，不要求
Developer 为历史脚本重建旧产品。原桌面步骤直接用于窄屏时导航超时，B 按实际菜单适配后
通过；相关初始失败保留。另一个 B 桌面截图适配尝试未成功，不替代已通过的原桌面 native
case；不把证据脚本的导航选择问题冒充产品故障。未执行旧任务/跨版本升级/V1 产品门禁。
`image-retired-cli.log` 是未挂载配置时的容器 preflight 拒绝，不计为退役 CLI parser 负例；
AC-24 的 installed/image 专项负例仍由 B 在最终候选补齐，不作为 Developer 的新返工项。

截至 `timing.json` 记录点，按测试日志实际运行区间合并（包含失败的证据准备运行）约
519 秒，本轮审查时长保守下限约 1471 秒，测试占比上界约 35.3%；原始每命令 real 时间
与日志保留，满足测试时间小于本轮总用时 50%。没有为凑比例等待或削减产品断言。

### Slice 结果重评与下一步

| Required Outcome | 本候选评估 |
|---|---|
| RO-1–5 | 原 Task47.1–47.4 接受事实保留；本轮新跑全量、真实 native、installed wheel、Docker fresh/restart/security，未发现新的共享容量/四类继续/旧批次结果故障。A-owned CURRENT/接受文档仍在正式 Slice 关闭时协调。 |
| RO-6 / AC-20–25 | 正常先后顺序下的历史判断、手动提醒/确认与实际效果、结果保留、CLI 入口退役有实现及证据；逐文件自动准入的新鲜历史存在上述 P1，结果未完成。 |

Task 保持 FIX REQUIRED，Scope/Base 不变；不规划下一 Task，不交 SLICE READY FOR A REVIEW，
不由 B 关闭 Slice。下一步只修本 Task 的历史判断/逐文件准入原子性，再由 B 验收。
