# Task 59.1 — Files 手动整理流程

Next Action: B REVIEWS THE FILES OVERVIEW AND BATCH CONFIRMATION CORRECTIONS

```text
Task ID: 59.1
Task Type: SLICE
Parent Slice: 59
Status: READY FOR B REVIEW
Task Base: 3bc9ad99137e5a2f8ff53add92041185ceb8ebbf
Reviewed Implementation Head: c109e403cc1733baebf20853d618d170c263d338
Difficulty: High
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: ORIGINAL TASK 59.1 CORRECTION SCOPE
```

## Developer 修正交接 — READY FOR B REVIEW

候选：`bf02484162ae9982d697825698ba541646665e02`（父提交
`9c0b9921d792966aeed1ca87d2e839939e44afb0`，Task Base
`3bc9ad99137e5a2f8ff53add92041185ceb8ebbf`）。本轮只改 Files 整理弹窗、共享样式和直接受影响
测试；上一轮 B 复核记录、原 Task 59.2 证据及更早交接保留在 `9c0b9921:TASK.md` 与 Git。

- **概览唯一计数。** 删除 Files 概览固定区的已选、需要处理、已有记录和可确认文本。正文三栏继续
  显示「已选 / 可确认」「需要处理」「已有记录」，「整批复核(已选 N 项)」继续读取精确
  `activeSelection`。组件与两次确认用例改在概览同一三栏和该按钮核对 `2 / 2 → 1 / 2`、
  `90 / 0`、A59-01 的 `1 / 1` 与已有记录 `1`，并断言旧底部文案不再出现。
- **整批正文顺序。** Files 状态卡与三栏之后直接是「来源与目标」；所选文件、未纳入文件和未受理
  原因之后才显示适用的「重新分析同一准备」与可展开「方案标识与诊断」。来源、目标、操作、实际
  来源影响、附件行、拒绝原因、授权和提交核对未改；非 Files 的 Task Center 整批正文保持原顺序。
  组件断言诊断位于「来源与目标」之后。
- **正常确认底栏。** 仅在 `filesHost && confirmationBlocker === null` 时以
  `mf-organize-confirm-submit-inline` 取消窄窗整行回退，让「返回整理概览」与「确认整理 N 项」
  在底部同一行分居左右。存在 `confirmationBlocker` 的长原因状态仍使用原有整行布局；焦点、
  键盘、reduced-motion 及 Task Center 原位续作分支未改。390 × 520 下两项操作在视口内，正文
  首屏露出「来源与目标」，长路径继续使用原单正文滚动。
- **真实视口断言。** 在现有单文件 Files 入口增加真实浏览器检查：1280 × 900、390 × 844、
  390 × 520 分别核对「来源与目标」首屏位置、两项操作同排且在视口内；截图保存于
  `.git/validation-evidence/bf02484162ae9982d697825698ba541646665e02/developer-task59.1-files/`。

实际验证（`web/`，候选 `bf024841`）：`npm run typecheck`、`npm run build`、改动文件 ESLint 与
Prettier、`check_governance.py`、`git diff --check` 通过。组件
`ManualOrganizeDialog.test.tsx` 最终 **56/56** 通过（32.1s）；首跑 54/56，两项旧断言仍按诊断和
重分析旧位置查找，已随真实顺序更新。原生 `library-files` 同页子集 **1/1**（1.5s）；Python
两次确认、双屏计数、单文件、十文件和 100 项组 **5/5**（28.3s）；Task Center 原位续作 **1/1**
（18.9s）；加入视口断言后的单文件复跑 **1/1**（4.9s）。测试墙钟约 2 分钟，低于本轮用时 30%。

剩余风险：长阻塞原因的整行底栏沿用原布局，本轮未单独截图，B 应在 100 项真实阻塞状态复核；
完整原生 Files、Task Center 布局和 Slice Base..Head 仍属 B 的 T3 验收。Task Center 正文本次
未改，原位续作入口回归通过。

## 验收与测试

- [ ] 从现有 Files 入口跑「两次确认」用例。两个就绪项仅留一项已选，概览只读一次三栏计数；
  整批的计数之后能先看实际来源和目标，诊断仍可展开。在 1280 × 900、390 × 844 与 390 × 520
  对照批准预览和首屏，复核底部两项操作位置、正文单滚动区以及键盘返回焦点。随后提交第一项，
  按原任务续作并核对第二次确认。
- [ ] 用现有 100 项用例核对 `90 / 0`、作品搜索修正、实际阻塞与下一步。用一项未受理一项就绪的
  用例核对两项各自去向。真实跳过后的概览继续显示已处理，已选兄弟按原范围继续。
- [ ] Developer 在 `web/` 运行类型、构建、改动文件 ESLint 和 Prettier，运行
  `npm run test -- run src/features/operations/ManualOrganizeDialog.test.tsx`。复用原单文件、十文件与
  两次确认用例，逐视口核对首屏，读取位置检查在测试主动滚动前进行。运行下列直接受影响的入口回归。
  交接候选 SHA、执行结果和视口对照。测试墙钟低于本轮用时一半。

```sh
npm run test:e2e -- tests/e2e/library-files.spec.ts --grep 'same-page preparation links the summary and confirms one exact subset'
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts --grep 'second confirmation on the same Task|pending owned file beside|one file separates source and target|ten files keep an aligned batch summary|100-file batch'
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'initial manual preparation remains reachable in place'
```

B 再查完整 Base..Head，先复验上述可见缺口，再按原 T3 执行 Files 原生和两套布局回归，核对批准
预览、真实效果、失败恢复与原位续作。通过后重评全部 Slice 结果，并接续原 Task 59.2 的任务详情正文。
[开发与验收分工](docs/development-workflow.md#6-test-levels)
