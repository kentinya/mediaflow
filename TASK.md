# Task 59.2 — 任务中心运行详情正文

Next Action: DEVELOPER IMPLEMENTS THE APPROVED SHARED RUN DETAIL TOOLBAR

```text
Task ID: 59.2
Task Type: SLICE
Parent Slice: 59
Status: FIX REQUIRED
Task Base: 868ff9daab6972473cfb7344ca02cbdbc30077cf
Reviewed Implementation Head: 0de24f4e5b2e9efc86be86da730cbe9e7f4da5b5
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: ORIGINAL TASK 59.2 / SLICE 59 A59-03 CORRECTION SCOPE
```

## B 复核与 Slice 59 交接

**Task 59.2 — FIX REQUIRED（当前 AC-04/06）。** B 从干净的 `main` 开始，审查完整 Task
`868ff9daab6972473cfb7344ca02cbdbc30077cf..0de24f4e5b2e9efc86be86da730cbe9e7f4da5b5`
及完整 Slice `212acdef5d97c14a01353b22c103d44b911d6147..a99005ea89030c88cc13b6fa582112b0817167e5`。
`0de24f4e` 是开发候选。之后 `a99005ea` 只提交了 A 的批准合同，新增两页签共用的任务顶部操作区
验收。批准预览 SHA-256 `8fca0fe4da050dda2e09fefb4aced52644c35c575034b8a4d05bc94f8f958369`
与合同一致。
[Slice 验收](SLICE.md#acceptance-criteria)

- **上轮两项已通过。** 从 Files 为 `Two.2002.mkv` 生成方案，未确认就返回任务列表。原详情首卡
  显示「等待确认后执行」和确认前的实际影响；点「继续整理」回到原方案，明确确认后同一任务显示
  文件结果。元数据修正和分类的原位证据从当前问题及决定开始，分析后直接显示新摘要和实际目标。
  历史空目标已移出可操作区。四类原生决定、原请求核对、已选与未选兄弟结果分别读回。
- **当前阻塞。** 在同一个尚待确认的真实任务中，「继续整理」和「取消运行」都可用，但仍在「任务
  详情」正文里，顶部只有「导出结果 JSON」。切到「操作记录」后两项操作消失，须切回详情才能继续
  或取消。桌面和 390 px 实页均如此。原因是 `RunDetailTabs` 把当前操作渲染在详情页签内，顶部只
  共同渲染导出。批准预览和现行合同要求共用顶部，桌面右侧按继续、取消、导出排列，窄屏整组在页签
  下方，继续使用主按钮、取消使用红色描边。
  [详情页签和操作](web/src/features/operations/RunDetailTabs.tsx#L873)

**Slice 重评。** RO-1 的 Files 准备和概览、RO-2 的四类决定回落沿用上轮证据。RO-3 的精确子集、
两次显式确认和原受理核对在本候选通过。现行 Files 整批行合同仍待原 Task 59.1，已选文件名、
图标、路径、单次来源影响和普通字幕简述的已复验缺口见 `534e4c75:TASK.md`。RO-4 的状态真值、
原位恢复和导出通过定向验收，顶部操作区待当前 Task 59.2 修正。Slice 59 仍为 FIX REQUIRED。

**实跑。** 构建、类型、改动文件 ESLint 与 Prettier、治理及差异检查通过。三组组件 126 项、
浏览器布局及任务中心 39 项、原生回归 9 项通过。另实跑现有多条目回包核对、元数据修正、分类
及跨页签布局，截取桌面、390 × 844 和 390 × 520。首次截图测试的「操作记录」定位匹配两个
区域，改用确切名称复验。保留最初日志和新的实跑结果。日志与实页截图在本机
`.git/validation-evidence/0de24f4e5b2e9efc86be86da730cbe9e7f4da5b5/b-task59.2-review/`。
批准预览在 `.git/validation-evidence/slice59-offline-task-toolbar/approved/`。

## 目标、范围与 Developer 开发指导

打开可续作任务时，用户在弹窗顶部直接判断可继续、取消或导出的动作。在「操作记录」查看同一任务
后可直接用同一组动作。关闭续作卡回到原页签和按钮，取消时按原任务的实际状态确认结果。范围限
原 Task 59.2 的运行详情。

1. 把任务级按钮放到 `RunDetailTabs` 的共用操作区。桌面保持左侧两个页签、右侧按顺序显示
   「继续整理」「取消运行」「导出结果 JSON」。窄屏整组移到页签下，保留相同阅读和键盘顺序。
   按批准预览为继续使用主按钮，取消使用红色描边。导出继续使用已有资格和反馈。
2. 在 `RunDetailPanel` 复用可续作条件和准确关联；「继续整理」继续使用原任务的
   `run + dialog=organize` 和当前详情上下文。沿用原位关卡与焦点规则。显示「取消运行」使用
   `RunLifecycleControls` 现有后端动作和版本，复用现有点击、提交锁定及重新读取。同一任务的
   请求中、已受理、未知、拒绝和实际已取消继续从原读回呈现，切页签后反馈仍可见。正文保留真实
   等待、进度和适用状态反馈。
3. 保留已审查的文件证据、四类恢复、记录查询和单个导出入口。使用现有任务读模与用户操作路径完成
   此调整。
   [运行详情](web/src/features/operations/OperationsLanding.tsx) ·
   [页签与工具栏](web/src/features/operations/RunDetailTabs.tsx) ·
   [取消控制](web/src/features/operations/RunLifecycleControls.tsx)

## 验收与测试

- [ ] 从现有 Files 留下未确认方案，然后从任务列表打开原详情。核对桌面、390 × 844、390 × 520
  两个页签的顶部按钮、条件、位置、键盘顺序及样式。当前任务尚无结果时保留导出不可用说明。
  从「操作记录」点「继续整理」，关顶层卡回到同一任务、原页签和按钮焦点，再按原路径明确确认。
- [ ] 在现有只可取消、可导出或已结束的相关入口核对各自权限。用原取消旅程核对请求中、已受理、
  实际已取消；原回包异常可在同一任务核对。切换页签后保持反馈和原记录筛选，导出实际结果包。
  复验现有未确认真值、四类决定及新摘要。
- [ ] Developer 运行类型、构建、改动文件 Lint／格式和下列既有入口测试，提交候选和两个页签的
  逐屏对照。可在既有原位续作用例增加顶部按钮、返回焦点及跨页签断言。B 核对完整范围和原 T3
  集成。各轮测试墙钟低于本轮用时一半。

```sh
npm run test -- run src/features/operations/OperationsInventory.test.tsx src/features/operations/RunDetailTabs.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx
npm run test:e2e -- tests/e2e/task-center-layout.spec.ts tests/e2e/operations.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'initial manual preparation remains reachable in place|detail tab and filter context|the eligible run exports'
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/task-flow.python.spec.ts --grep 'an acknowledged cancellation'
```

[开发与验收分工](docs/development-workflow.md#6-test-levels)
