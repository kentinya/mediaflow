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
Status: READY FOR B REVIEW
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

### 阻塞清单与用户影响（均为 P1）

本次重整保留原三项阻塞，不增加 Task 或扩大合同。第 1、2 项是同一提醒旅程的传输和
事实依据两个缺口；第 3 项是新旧工作的交接。用户不需要阅读或操作内部锁、令牌和执行步骤。

1. **页面没有告知用户“这个文件上次整理未完成”。**
   用户从 Files 整理电影，目标目录建好后写文件失败；再次选中该电影整理。后端摘要里
   虽然有提醒，返回页面时却漏掉了，用户仍可直接确认并执行成功。
   原因是 `operations_lifecycle.py::_bounded_preview_plan` 未投影 `plan.history`；真实
   Preview GET 缺此字段，Web 得到 null。**AC-T2/T7、Slice AC-21/25 未满足。**

2. **后台没有正确读到上次实际做了什么，提醒依据不完整。**
   同一操作已经记录“建过目录、写入效果尚未确认”，历史查询却漏读真实 Result，退回
   一个缺少效果信息的文件状态。即使修好第 1 项，仍会漏掉“上次部分结果无法确认”的提醒。
   后台必须保留完整事实，普通提醒只展示用户需要知道的结论。
   原因是 `sqlite_runtime.py::latest_organize_source_outcome` 只按
   `result_id = item_id || ':' || attempts` 关联；真实手动 Result 用 UUID，记录的
   `PARTIAL / CREATE_DIRECTORY / attempted_unverified / mutation_outcome` 均未被正确读取。
   **AC-T2/T3/T5、Slice AC-21/22 未满足。** 同一查询在版本筛选前 `LIMIT 400` 也不符合
   完整匹配总体要求；这是代码审查发现，未声称跑过超过 400 次产品操作。

3. **重新整理后，旧工作没有按文件交接好，处理名额也没有正确结算。**
   单文件实测：一次整理失败后，经 Files 再次确认的新整理已成功，旧任务却仍保留原
   Worker 资格并占一个处理名额。当前只把 PARTIAL 视作历史，没有实现合同要求的交接。
   **AC-T4、Slice AC-23 未满足。** 已证实旧 heartbeat 被接受和名额仍为 1；没有证实
   重复复制/移动，也没有证明旧远端调用仍在运行。

   批量和定时必须按下面的完整旅程验收，不能把单文件观察直接扩成“整批必须关闭”：

   | 用户旅程 | 交接后的正确结果 |
   |---|---|
   | 一批 A 失败、B 成功、C 仍在排队/处理；用户核对后在 Files 重新整理 A | A 的新请求获得自己的计划和权限；旧工作不能再以被替代的资格处理 A 或改写其结果。B 不重做，C 的合法进度、来源占用和权限保留。 |
   | 上述旧批次仍有 C 在处理 | 旧批次可继续占一个名额；按 Task 计算容量，不按文件各占一份。不能因 A 被接手就释放整批锁或名额。 |
   | 旧批次已没有其他需保留的机器工作，A 的旧执行已按新确认完成收束 | 保留失败/未知效果记录，释放旧工作已不再需要的处理名额；未知历史不能单独永久占住名额。其他真正未结束的调用仍按原安全边界处理。 |
   | 昨晚定时整理 A 失败、B 成功；今天定时或“运行一次”发现 A 和新文件 C | 同版本 A 逐项排除，C 正常处理；自动入口不接手 A、不重启旧 A。排除原因和数量可读，不制造成功整理结果。 |
   | 用户随后从 Files 核对并重新整理 A 成功，再到下一次定时/“运行一次” | 完成 A 的旧执行交接；后来成功解除早期失败造成的排除，之后仍走正常筛选/冲突规则。昨晚失败和时间保留，旧批次其他文件不受影响。 |

   以上批量/定时交接是待验收要求，未声称已实测通过。整批仍合法处理 C 时，同 Task
   的心跳继续有效可以是正常行为；验收必须证明**被替代的 A 的旧执行权限失效**，不能
   单靠父 Task running、旧 marker 或 heartbeat 判断整个批次是否应结束。

### Developer 修复指导（同一 Task，按顺序实施）

1. **修好历史事实读取。** 复用 `manual_execution_items.result_id`、TaskItem/attempt/Result
   的已有持久关系，兼容自动/CLI 结果写法，统一状态大小写；保留无 Result 的持久失败回退。
   不猜 UUID、不凭迟到发布时间替换较新的尝试。在完整匹配总体中比较版本后确定最新结果，
   可分批查询，不能用 400 代替 32/100 的任意截断。真实故障后断言目标、完成步骤、
   效果确定性和未知证据都读得到，原 Result 不改写。
2. **打通实际 API 到页面，并控制提醒复杂度。** 在现有 operator projection 中显式投影
   有界 history，复用路径/文本限界、权限和脱敏，不透传 raw plan。真实 API 响应要能被
   现有 typed normalizer/component 消费；不能只在 mock fetch 文档里手工加 history。
   普通提醒可写成“该文件上次整理未完成，目标位置可能已有部分文件。请核对后再确认整理。”
   只有确实存在未知效果时，再补“上次操作的部分结果无法确认。”文案随实际证据调整，
   零效果失败不暗示已产生部分文件。可用目标、已知影响放在现有条目详情，用人话表达；
   无须新增完整历史面板、技术步骤清单或重复堆叠提醒。保留普通选中确认，不加核查页、
   例行 checkbox 或 token 操作；未知效果不描述为“已核验安全”。
3. **在现有确认事务中完成逐文件交接。** 复用 kernel/repository，原子核对选中来源、
   当前相关历史、计划、权限、请求和容量，处理确切来源/目标/附件锁及旧执行资格。
   只交接已有 failed/partial 结果且本次明确确认的文件，排队/处理且无终态的文件仍互斥。
   被替代的旧执行不得启动后续文件操作或改写旧结果；按实际作用域检验步骤准入和发布拒绝。
   若现有实现需要轮换整个 Task owner，应保留兄弟项及其合法剩余工作，按现有机制由
   有效 owner 继续，不能删除整批锁、重置兄弟状态或扩大权限。旧 owner 仍合法处理其他
   文件时不要求整批 heartbeat 失败；已完全被替代的单文件 owner 不应再维持旧执行资格。
   容量按 Task 的剩余工作结算，仍处理 C 就保留一份，无剩余工作且旧执行已收束才释放。
   原 Result/pin/完成步骤/unknown/原 Automation 时间和结果均保留；不靠把 unknown 改成
   none、删除历史或证明远端停止放行，不承诺撤销已派发调用。
4. **从现有入口补直接受影响的验收。** 复用 `tests.test_manual_task_engine` 的真实 API /
   SQLite/LocalStorage/Worker fixture 和 B probe，不建立新执行/恢复系统。覆盖目录成功后
   写失败、已有父目录时写失败、Copy 完成但 Move 删源失败；均走 Files 再选择 → 真实
   摘要提醒 → 普通确认 → 实际新结果，最后一步不改走 CLI。重点断言以下结果：

   - 真实 API 和页面均有简短提醒；unknown 另有说明，普通确认不增加操作步骤。
   - 批量 A 交接、B 不重放、C 保留互斥/合法执行；分别验证仍有 C 和整批无剩余工作
     的容量，旧 A 的状态写入/步骤准入被拒绝，历史未知证据仍保留。
   - due 与 Run once 都完成同版本失败排除、自由 C 实际处理、手动 A 成功后解除排除；
     自动排除不执行交接、不改写原 Automation 记录，也不重放成功兄弟项。
   - 并发重复确认、拒权/队满回滚、相关/无关历史变化和同版本 reopen，仍遵守原 Task
     受影响测试计划；仅显示或刷新提醒不新增 Provider/媒体效果。

   Developer 运行原 affected plan 的新增/修改和直接受影响测试，记录命令、实际结果及
   剩余限制，提交同一 Task 新 checkpoint 后回到 READY FOR B REVIEW。B 在修复候选上
   独立复核上述旅程并完成原 T4/浏览器/包装/Docker 门禁。测试时间仍须小于本轮总用时
   50%；发现确定阻塞时先修复，不靠重复全量运行消耗时间，也不为比例豁免必要验收。

### 候选 368d9e86 已执行的验证与停止位置

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

2026-11-02 B 指导澄清：用户要求重整阻塞并补充批量/定时说明。本轮开始于 `main` /
`49462ac6654b49c151983ccd1b2cee3a3f5f11cb`，无预存 tracked 修改，预存 untracked 全部
保留未暂存。仅更新本 Task 的说明和开发指导，候选实现、原 Base、FIX REQUIRED 结论及
已有证据不变。本轮未运行产品测试或新增故障探测；只做治理、范围一致性和 diff 检查，
不把批量/定时的待验收要求写成已复现事实。
