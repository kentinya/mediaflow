# Task PATCH-20261030-3 — 移除任务中心的统计与时区说明

用户于 2026-10-30 明确要求直接移除统计说明整段、“本地时区”标签，并补充删除可展开的
时区说明入口与内容。本轮按直接修改授权实施，B 仍独立验收，不自签 PASS。
前一独立修正的验收见 `a6783b17:TASK.md`；本 Task 不重开 Slice46。

```text
Task ID: PATCH-20261030-3
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: READY FOR B REVIEW
Task Base: 16d8e41775910f8580482a2a68c1fb99fd27613c
Difficulty: Low
Test Level: T2
Planner / Reviewer: B
Implementation Authorization: USER-REQUESTED DIRECT EDIT — 2026-10-30
```

## Goal and scope

进入现有任务中心任一标签后，直接查看统计卡、日期范围及任务列表；删除统计卡下的
“统计按当前筛选后的完整总体计算…”整段，以及本地时区标签、说明按钮、展开内容和
对应本地状态/悬空描述引用/无消费者局部样式。原生开始/结束日期、清除及真实时区转换保留。

只调整上述局部呈现、直接受影响测试和相应现行界面文档。完整旅程继续使用既有入口、
查询、分页、详情、刷新和错误恢复；统计计算/去重/权限/执行语义不变。
依据 `V2-OPS-001/003`、Product Experience 的任务旅程及 task-center-page-spec §2。

## Acceptance

- 八标签下均不再显示上述统计说明、时区标签、说明入口及内容。
- 日期范围、清除、统计数字/待处理提示、任务详情及失败恢复仍正常；日期名称有效，
  不留指向已删除节点的可访问说明引用。
- 桌面与窄屏日期组对齐、可读、不溢出；无后端、时间转换、权限或执行改动。

## Implementation and tests

1. 删除现有 JSX/说明状态和仅供删除内容使用的 CSS；同步原测试，移除退役说明开关用例，
   保留日期范围、刷新、详情及布局回归。
2. 同步现行需求/体验/页面描述；不修改 SLICE/Roadmap/Progress。
3. Developer（cwd web/）：`npm run typecheck`；`npm run test -- run src/features/operations/OperationsInventory.test.tsx`；
   changed-file ESLint/Prettier；`npm run build`；
   `npm run test:e2e -- tests/e2e/task-center-layout.spec.ts`，检查真实桌面/窄屏截图。
4. B 审查完整 Base..candidate 并独立复现删除结果、日期/清除和桌面/窄屏可用性；
   按 workflow 核对适用回归证据，不重复无关全仓/容器矩阵。测试时间低于本轮总用时 50%。

## Handoff

状态 READY FOR B REVIEW；独立 B 验收待执行，不自签 PASS。

Implementation checkpoint：`219fe066f87c1ae48877dcd8490b9ee4782dee84`。
本指针为仅文档的交接后继，不改变已验证产品/测试输入；B 审查完整 Task Base..交接 Head。

- 产品仅删除所指统计说明、时区标签/说明控件及无消费者的局部样式/状态/引用。
  时间转换、查询/轮询、统计计算/去重、权限和执行逻辑未改。
- Developer 实际检查：OperationsInventory **44 passed**；局部 Chromium 布局/交互
  **11 passed**；typecheck、变更 TS/TSX ESLint、四个变更 Web 文件的 Prettier、build、
  治理及 `git diff --check` 均通过。只删除退役说明控件的两项浏览器用例，保留日期、刷新、
  详情和四视口布局覆盖；没有把旧统计/日期行为弱化为仅文案断言。
- 实际检查 1536px 与 320px 截图，删除后日期和列表对齐、文字可读、无页面横向溢出。
  测试进程约 13 秒，全部验证约 22 秒，低于本轮总用时 50%。
- 原始日志/截图/结果位于本机 ignored `.git/validation-evidence/developer-patch-20261030-3/`。
  Chromium/模拟视口证据不代表实机或全部浏览器通过；没有跑全仓/容器回归。
- 文档同步首次因命令 cwd 错误未找到文件，已在正确目录完成；最终静态和产品验证均通过。

## B Review Result

待独立 B 审查完整 Base..交接候选并给出 PASS / FIX REQUIRED；本轮实现者不自评通过。

## Workspace

Branch main；起始 HEAD/Task Base 为上述 16d8e417；开始时无 tracked/staged 改动。
原有 untracked OS 文件、日志、15、自动化参考图片及生成 ZIP 全部保留、不加入 checkpoint。
规划前治理检查 PASS。不规划后续 Task/Slice，不启动子代理，不 push 或部署。
