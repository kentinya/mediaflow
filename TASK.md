# NO ACTIVE IMPLEMENTATION TASK

最近独立修复 **PATCH-20261111-3 — 精简任务详情“文件整理准备”说明** 已由 B
于 2026-11-11 验收 **PASS**，无剩余 Task 阻塞。

- Reviewed Base: `7b6cadd050591c339589d042235013ca9ff1f26d`
- Reviewed Head: `3b710f55201bf7745e766792a58d0090800e379c`
- [固定 B 验收记录](https://github.com/kentinya/mediaflow/blob/7bf958fb1b61b358c5f3f0305fa5137b2caa38f2/TASK.md#b-decision--patch-20261111-3-pass)：完整范围、实际结果、原始失败、证据位置及验证限制。
- [原 Task 与开发指导](https://github.com/kentinya/mediaflow/blob/3b710f55201bf7745e766792a58d0090800e379c/TASK.md)：授权、目标、验收和 Developer 交接。
- 上一独立修复 PATCH-20261111-2 的 [固定 B PASS](https://github.com/kentinya/mediaflow/blob/aff254ce0e3dc8b47714b197a7023509e6cc5f66/TASK.md#b-decision--patch-20261111-2-pass) 保留原范围与结果。

当前行为见 [手动整理旅程](docs/product-experience.md#manual-organize) 和
[任务中心手动受理与确认](docs/task-center-page-spec.md#手动受理与确认)。
独立修复不重开 [Slice54](SLICE.md)，其 PASS / CLOSED、原始 Base／接受 Head、
Roadmap／Progress 及延期保持。下一大 Slice 由 A 单独选择；当前没有授权中的实施 Task。

---

## 规划草案 — PATCH-20261111-4 — 任务详情文件证据就地展开

**仅规划，尚未授权实施。** 用户先要求调查且不改文档／代码，随后明确“规划一个修复
Task”；本次只授权此规划。保留顶部 `NO ACTIVE IMPLEMENTATION TASK`，下列 PLANNED
元数据是待激活草案，不构成实施、启动其他角色、推送或部署授权。用户授权实施时再移除
无活动 Task 通知并激活同一 ID／Base／目标／范围，不静默重定 Base。

Authority: 用户授权的独立呈现修复；生命周期遵循
[Development Workflow](docs/development-workflow.md#31-independent-minor-bugs)。

```text
Task ID: PATCH-20261111-4
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: 42e666ca6c600cbaf93625dd5b389763c28ddade
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Development Authorization: NOT AUTHORIZED — PLANNING ONLY
```

### Goal and actual gap

任务中心 → 打开任务详情 → 点击某文件“查看证据”，在该条目正下方阅读它自己的
处理结果、来源／目标、处理经过及已有恢复操作，关闭后继续查看相邻条目，不必到
整份列表末尾寻找。保留现有一次查看一个文件的语义。

实际根因：`web/src/features/operations/RunDetailTabs.tsx` 的 `inspectItem` 只更新 URL
所属 `evidenceItem`；`RunEvidenceSection` 是整个 `RunItemsSection` 后的兄弟区域，
而主条目行按钮只调用 `onInspectItem(item.itemId)`，所以任意行的证据都落在列表末尾。
操作记录“查看条目”、问题文件入口及批量分析子项也复用该条目选择链路。
现有 `RunDetailTabs.test.tsx`／`operations.spec.ts` 验证内容及开关，未验证相邻位置；
另有 `item=item-9` 且列表不含该文件的有效证据用例，不能因改为行内而丢失。
以上为源码／现有测试静态调查，本轮未声明浏览器复现或产品测试通过。

适用约束：`V2-OPS-005/008/012`、`V2-TASK-003/012–014`，以及
[完整任务／逐项恢复旅程](docs/product-experience.md#tasks-results-and-per-item-recovery)、
[任务正文与文件证据](docs/task-center-page-spec.md#current--任务正文与文件证据)、
[当前投影边界](docs/architecture.md#current--v2-operations-projection-foundations42-amended48)。
本修复只改变现有文件证据的位置，不改变这些已接受结果或安全边界。

### Implementation scope and ordered guidance

1. 在 `RunDetailTabs.tsx` 将证据选择与呈现位置协调起来：目标在当前服务器页时，
   在对应主条目之后呈现唯一证据区域，优先使用合法表格展开行，跨全部 8 列；
   列表下方不再保留重复面板。复用 `RunEvidenceSection` 和既有 query／恢复组件，
   不复制证据读取或产生第二套恢复状态。按钮暴露展开状态及与区域的关联；保留关闭。
2. 处理页外／筛选隐藏／列表空态、读取中或读取失败的选中条目：保留原 `run + item`
   精确读取，在主条目区域、表格之前显示该文件的独立证据卡，说明其不在当前列表中
   或列表尚不可用。读取成功后才展示真实文件名／路径；加载或拒绝不虚构文件信息。
   不在分页结果中插入伪造业务条目、不改计数、不清除筛选／游标、不遍历全量找页。
   目标回到当前页后只保留对应条目下的一个面板。
3. 保留 URL 所属选择、刷新／前后退／认证恢复、操作记录和问题／批量入口的准确性。
   页内切换、轮询更新导致位置迁移或列表暂不可用时，不能重发决定／分析／确认、
   丢失既有未知提交核对记录，或把旧文件的迟到证据／表单显示到新文件；检查组件
   key 和挂载边界，保留原账号／任务／条目隔离及既有恢复能力，不另造恢复协议。
4. 只在必要范围补充 `web/src/shared/ui/styles.css`：证据明显从属于上一条目，
   长路径、诊断、附件及恢复动作可读；390px 下不因表格横向最小宽度把正文／关闭
   动作推到不可读的远处。表格自身可继续内部横向滚动，任务卡和整页不被撑宽。
   关闭回到合理的原触发焦点；正常背景刷新不反复抢焦点或滚动至列表底部。
5. 补充位置、边界与浏览器验证，运行下列受影响检查后提交一个完整实现检查点，
   状态为 READY FOR B REVIEW。若实际必须改变后端或恢复协议，先交 B 重评范围／等级。

允许文件：上述组件／必要样式，直接受影响的 operations 单元／浏览器测试及最小假服务
fixture；确需调整 URL／query 的传参时限于保持现有契约。不得借机重构整个任务详情。

### Acceptance criteria

- [ ] 多条目列表中，首／中／末任意行打开后，唯一证据紧跟所选条目、位于下一业务
  条目和分页／批量区之前；切换到另一个文件后位置和内容都跟随新文件，关闭可回看原行。
- [ ] 保留处理结果→来源／目标→处理经过→实际原因及可展开诊断、附件、日志／审计、
  既有四类恢复动作；流程完成不变为文件成功，未知效果／缺失 Result 不被改写。
- [ ] 有效页外深链接、筛选后隐藏、空页、列表错误仍可独立查看准确文件；权限拒绝、
  不存在、证据读取失败在同一位置显示真实原因及既有安全下一步，不串到邻项。
- [ ] 筛选／翻页／刷新／前后退／重认证及操作记录、问题文件、批量子项入口保持原
  准确任务／文件上下文；列表更新不吞掉证据或制造两个面板，不伪造条目数或自动遍历。
- [ ] A→B 快速切换且 A 迟到、同文件轮询、页内／页外迁移均无错配；既有在途命令、
  未知提交核对和账号隔离保持，打开／关闭／重排证据零写命令、零媒体变更、零自动重放。
- [ ] 1536px 桌面、390px 窄屏及矮窗口可读可操作；展开不使相邻列重叠或整页横向
  溢出。键盘可展开／关闭、状态可感知、焦点合理，现有任务卡关闭／返回行为保持。

### Required tests

#### Developer — affected tests

激活后先运行根目录 `python3 scripts/check_governance.py`。以下命令 cwd 为 `web/`：

```sh
npm run test -- run src/features/operations/RunDetailTabs.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/run-detail-state.test.ts src/features/operations/run-detail-query.test.ts src/features/operations/OperationsInventory.test.tsx
npm run typecheck
npx eslint src/features/operations/RunDetailTabs.tsx src/features/operations/RunDetailTabs.test.tsx tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts
npx prettier --check src/features/operations/RunDetailTabs.tsx src/features/operations/RunDetailTabs.test.tsx src/shared/ui/styles.css tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts
npm run build
npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts
```

静态命令补入本轮其他实际改动文件；运行根目录 `git diff --check`。单元测试应明确验证
业务条目与证据相邻及仅一份，而非只验证区域存在；覆盖上列错误／页外／迟到与恢复核对
风险。浏览器验证可见上下关系、正文宽度、键盘与关闭／返回，检查实际截图；表格增加
展开行后，原列宽／溢出断言要仍验证业务行，不能删断言掩盖正文溢出。

#### B — independent acceptance

审查固定 Task Base..候选完整差异，复核 Developer 结果和执行输入后可复用匹配证据；
独立验证多条目就地展开、页外／列表失败降级、迟到响应及无重复命令。执行上列受影响
单元／E2E 与 `npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run build`。
对新构建另外执行真实 Python／临时 SQLite 的现有相关旅程：

```sh
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/task-flow.python.spec.ts
```

该旅程核对真实 Task 流程／文件结果和精确恢复确认不受呈现迁移影响。所有假服务和原生
fixture 均使用隔离测试数据，不读取生产配置、用户媒体或外部 Provider。B 保留桌面／
窄屏／矮窗口截图及实际结果到稳定忽略目录 `.git/validation-evidence/<candidate>/patch-20261111-4/`。
本 T3 是前端位置与路由／异步／恢复消费者集成修复，不改后端、权限、schema、Storage
或执行引擎；无具体新增影响时不要求全 Python／全 Web／全 E2E、wheel 或 Docker 矩阵。
原生测试若发现实际安全语义改动，由 B 重评并补充适用门禁，不能以 T3 名义跳过。

### Non-goals and workspace

不增加多文件同时展开、自动定位任意服务器页、新证据接口／全局搜索、第二套恢复流程、
恢复表单改版、其他页面重设计或新配置。SLICE／Roadmap／Progress 及已接受 Slice 的
身份／Base／Head／关闭事实保持；本轮只更新 TASK.md，不同步产品说明为“已实现”。

规划基线：`/Users/songzhidong/mediaflow`，`main`，HEAD 为上列 Task Base；治理预检 PASS，
TASK.md／Git 可写，暂存区原为空。预存 `mediaflow/.DS_Store` 修改以及未跟踪的 `.DS_Store`、
`.explore_adapter_block.py`、`.mgmt.log`、`.t*.log`、`15`、各目录 `.DS_Store` 和 `output/`
调查材料原样保留、不纳入检查点。不读取私有配置／运行数据库，不推送或部署。

### Developer completion / B review

尚未实施，产品验收未运行。实施后由 Developer 记录完整 checkpoint、实际行为／测试结果
及风险，交 READY FOR B REVIEW；B 对精确 Base..Head 独立给 PASS／FIX REQUIRED。
修正仍在同一 Task；独立 bug PASS 后恢复简短 NO ACTIVE IMPLEMENTATION TASK 与固定审查
指针，不声明 Slice CLOSED，不规划授权外工作。
