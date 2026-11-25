# Task 59.3 — 任务详情状态与进度

Next Action: DEVELOPER IMPLEMENTS THE APPROVED RUN DETAIL STATUS PRESENTATION

```text
Task ID: 59.3
Task Type: SLICE
Parent Slice: 59
Status: PLANNED
Task Base: d1ea5f667c5ebc08e1a6835030197c1724f4f4d2
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: SLICE 59 RO-4 / AC-06 TASK DETAIL STATUS PRESENTATION
```

## B 复核与 Slice 59 交接

**Task 59.1 — PASS。** B 从干净的 `main` 审查完整 Task
`3bc9ad99137e5a2f8ff53add92041185ceb8ebbf..d1ea5f667c5ebc08e1a6835030197c1724f4f4d2`
及完整 Slice `212acdef5d97c14a01353b22c103d44b911d6147..d1ea5f667c5ebc08e1a6835030197c1724f4f4d2`。
在 `ReadabilityOne` 和 `ReadabilityTen` 从现有 Files 入口读回方案。逐项复核的 Storage 目标和整批
确认的库内目标都保留完整路径，在桌面、390 × 844、390 × 520 一致。补验从 `Dialog` 选两部影片，
确认前逐项与整批均显示同一目标，临时媒体根无变更。只确认第一部，实际 Worker 将其移到
`Movies/Movies/Anime/…` 对应位置，第二部留在原处，只有一笔执行提交。
[目标展示](web/src/features/operations/ManualOrganizeDialog.tsx#L270)

治理、全区间差异检查、类型、构建、改动文件 ESLint／Prettier 通过。57 项原组件及 2 项新增组件测试
共 59 项通过，Files 和任务中心布局浏览器 64 项通过，原生回归 10 项通过。另有 1 条真实目标与
最终 Storage 效果的补验通过。本机日志及截图在
`.git/validation-evidence/d1ea5f667c5ebc08e1a6835030197c1724f4f4d2/b-task59.1-review/`。
上轮阻塞见 `f97c9199:TASK.md`。

**Slice 59 仍为 FIX REQUIRED。** RO-1 的准备、概览和 100/101 文件边界，RO-2 的四类决定及回落，
RO-3 的整批复核、明确确认和原任务交接均通过。RO-4 原有共用操作区、原位续作焦点及四类恢复
沿用 Task 59.2 PASS，见 `171b3de6:TASK.md`。剩余为 A 在 `a14edf20` 批准的任务详情状态区。
[Slice 验收](SLICE.md#acceptance-criteria)

## 目标与真实入口

用户从任务中心打开原任务，能读到当前阶段、接下来可做什么、后台进度在计什么，以及文件已经
产生的效果。通过现有「继续整理」核对和明确确认原方案，回到同一任务查看实际结果。异常时，
在状态区和对应文件证据可读到原因、影响及下一步。

B 用 Files 留下 `Two.2002.mkv` 的未确认方案并打开原任务。读回为待确认一项、文件结果零项，
`progress.kind=organize` 且 `processed=1/1`，当前页面仍显示「已处理 1 / 1 个主条目」。
明确确认并由 Worker 完成后，同一任务才产生一份文件结果。此时页面同时显示「已完成」
「本次整理已完成」和一行重复说明。真实前后读回及桌面、390 px 截图在本机
`.git/validation-evidence/0a3c619c22b89119a3b5611b163c03090545f737/b-task59.1-review/`。
A 批准的状态区预览 SHA-256 为 `f7bf7d04beffdb7f4b2b548f5a65f126288a43a753bb9f889135bc79640e8f7d`。
[合同](SLICE.md#ro-4--任务详情正文易读保留原入口与同任务恢复)

## 范围与 Developer 开发指导

1. 收拢 `OperationsLanding.tsx` 中的 `runStatusHeadline` 和 `RunFlowSummary`。进度上方用
   一个标题表达实际状态或阶段。正常完成用「流程已完成」，直接接进度和文件结果。混合结果、
   恢复成功、失败、取消、效果待核对和缺失结果仍呈现各自结论、具体原因与适用入口。
2. 「等待确认」从同一任务的当前读回取得范围，提示与共用「继续整理」的实际资格一致。
   `progress.dispositions.waiting` 还包含等待识别、元数据和分类，`filesPreparation.continuable`
   表示可打开原卡。遇到混合任务时，从现有问题读回及确切关联的准备和当前方案取得可确认范围。
   复用原准备／方案查询与既有确认资格。只有合计或读取暂不可用时，说明能核实的等待状态和
   当前合法动作。已执行的兄弟文件继续报告自己的结果。
3. 在 `RunDetailTabs.tsx` 的 `ProgressCard` 按实际阶段说明进度。现有 `processed` 会计入已进入
   等待的条目，`kind=organize` 也会出现在等待确认阶段。准备或分析已满时标明其口径和待确认状态，
   执行阶段继续使用后端真实进度，证据缺失时保留未知说明。独立文件结果继续采用既有正式结果及
   效果确定性。范围限 Web 详情正文，沿用持久状态、API、动作权限、顶栏操作、页签、原位续作和记录。
   [状态区](web/src/features/operations/OperationsLanding.tsx#L1883) ·
   [进度与文件结果](web/src/features/operations/RunDetailTabs.tsx#L952)

## 验收与测试

- [ ] 从实际 Files 留下已分析但未执行的方案，从任务中心打开同一任务。桌面和 390 px 核对单一
  「等待确认」、准确范围、合法下一步和进度口径。沿原按钮继续并明确确认，读回同一任务。
  正常完成只显示一个「流程已完成」，紧接相应进度和正式结果。
- [ ] 从现有入口核对纯等待确认、部分已执行且仍待确认或待决定、只有业务问题、分析进行中、混合
  文件结果、任务失败、协作取消／核对、效果不明和读取失败等适用状态。核对原因、已知效果与原有
  文件证据入口；「操作记录」往返、续作关闭及原焦点仍可达。
- [ ] Developer 在 `web/` 运行类型、构建、改动文件 ESLint／Prettier 和下列受影响测试。更新
  受新状态文案影响的定位，继续检查流程、原因和实际文件效果。B 审查完整 Task 和 Slice，按 T3
  从真实入口对照批准预览，核对确认前后及异常结果，再补齐适用的 Slice 最终门禁。各轮测试墙钟
  低于本轮用时一半。

```sh
npm run test -- run src/features/operations/OperationsInventory.test.tsx src/features/operations/RunDetailTabs.test.tsx
npm run test:e2e -- tests/e2e/task-center-layout.spec.ts tests/e2e/operations.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/task-flow.python.spec.ts tests/e2e/manual-organize-dialog.python.spec.ts --grep 'initial manual preparation remains reachable in place|the selected run detail reads progress|a mixed file population completes|a saved flow failure stays authoritative|an acknowledged cancellation|101-file directory'
```

[开发与验收分工](docs/development-workflow.md#6-test-levels)
