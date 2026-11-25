# Task 59.1 — Files 手动整理流程

Next Action: DEVELOPER FIXES THE LIBRARY-RELATIVE TARGET IN FILES BATCH REVIEW

```text
Task ID: 59.1
Task Type: SLICE
Parent Slice: 59
Status: FIX REQUIRED
Task Base: 3bc9ad99137e5a2f8ff53add92041185ceb8ebbf
Reviewed Implementation Head: 0a3c619c22b89119a3b5611b163c03090545f737
Difficulty: High
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: ORIGINAL TASK 59.1 / SLICE 59 A59-03 CORRECTION SCOPE
```

## B 复核与 Slice 59 交接

**Task 59.1 — FIX REQUIRED（P1，RO-3 / AC-06）。** B 在干净的 `main` 审查完整 Task
`3bc9ad99137e5a2f8ff53add92041185ceb8ebbf..0a3c619c22b89119a3b5611b163c03090545f737`
及 Slice `212acdef5d97c14a01353b22c103d44b911d6147..a14edf202f388851624be62323e622f65a054674`。
`0a3c619c` 为实现候选，其后 `a14edf20` 提交 A 已批准的任务详情状态区合同。
[Slice 验收](SLICE.md#acceptance-criteria)

- **本轮已通过。** 从 Files 选两部影片，为第一部添加中文字幕，排除第二部后进整批复核。图标、
  普通文件名、右侧单独「移动」、一次来源影响和字幕简述都显示。点已选文件名留在整批。
  经概览打开同一文件并回到整批，选择和确认资格仍正确。未纳入区能定位第二部。浏览和扩展证据
  期间零执行提交。核对了桌面、390 × 844 和 390 × 520。
- **当前阻塞。** 从 Files 打开 `ReadabilityOne/ReadableOne.2011.mkv` 的逐项复核，再进整批
  复核。原方案的媒体库是 `Movies`，库根是 `Movies`，库内真实目标从 `Movies/Anime/` 开始，
  Storage 目标从 `Movies/Movies/Anime/` 开始。整批页却显示「目标 Movies：Anime/…」，
  用户会以为确认后影片少进一层目录。`filesTargetLocation` 将已是库内相对路径的
  `destination.relativePath` 再按同名库根截掉一层。失败的实页断言对照了浏览器实际取得
  的媒体库和方案响应，以及原逐项复核的完整目标。
  [目标呈现](web/src/features/operations/ManualOrganizeDialog.tsx#L260) ·
  [方案目的地](mediaflow/application/operations_lifecycle.py#L1363)

**实跑。** 治理、差异、类型、构建、改动文件 ESLint／Prettier、组件 57 项、浏览器布局与 Files
64 项通过。原生首跑 7 项通过，101 文件用例因旧文案定位失败。`a261b93f` 已将失败结论与下一步
渲染为独立标题和段落。B 按现行页面更新该断言，复跑验证真实超限、原历史只读、零提交及同文件
缩小范围后重新受理，测试提交为 `d1fcb501`。额外的字幕和往返实页用例通过，精确目标比对失败。
本机日志及截图位于 `.git/validation-evidence/0a3c619c22b89119a3b5611b163c03090545f737/b-task59.1-review/`。

**Slice 59 — FIX REQUIRED。** RO-1 准备、概览和 100/101 上限通过。RO-2 的决定与回落沿用已验
交付。RO-3 的精确选择、两次确认、原任务交接及本轮已选文件交互通过，整批显示的真实目标待修。
RO-4 原批准范围沿用 Task 59.2 PASS（`171b3de6:TASK.md`）。A 最新批准的状态区已形成后续 Task
59.3 草案，见上述本机证据目录的 `task59.3-status-draft.md`。当前 Task 59.1 通过后再激活该计划。

## 目标、范围与 Developer 开发指导

Files 用户在确认前看到的目标必须与同一方案、逐项复核和实际将执行的目标一致。修改范围为
已选 Files 整批文件行的目标显示。

1. 确认库身份后，`filesTargetLocation` 直接使用方案的 `destination.relativePath` 作为库内路径。
   用现有目标库、Storage 和精确目标校验对应关系。库根用于校验 Storage 路径，保留库内路径中
   恰好与库根同名的合法目录。需要显示精确路径时使用 `destination.storageRelativePath`。
2. 复用 `one file separates source and target` 的真实 Files 用例。核对逐项方案、库根和整批页的
   完整目标目录，覆盖 `Movies` 库下仍有 `Movies/Anime` 的既有夹具。强化十文件用例，核对
   实际库内路径，保留普通文件名、一次来源影响、可展开附件、未纳入定位和原确认子集。

## 验收与测试

- [ ] 经 Files 逐项复核进入整批时，「目标 Movies：Movies/Anime/…」与原方案一致。桌面和 390 px
  对照目录与底栏，核对只有明确确认才执行。原两次确认及任务中心续作继续通过。
- [ ] Developer 在 `web/` 运行受影响用例、类型、构建、改动文件 ESLint／Prettier。B 独立复核
  完整 Task 差异和真实目标读回，再重评 Slice。各轮测试墙钟低于本轮用时一半。

```sh
npm run test -- run src/features/operations/ManualOrganizeDialog.test.tsx
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts tests/e2e/operations-inventory.python.spec.ts --grep 'one file separates source and target|ten files keep an aligned batch summary|second confirmation on the same Task|101-file directory|initial manual preparation remains reachable in place'
```

[开发与验收分工](docs/development-workflow.md#6-test-levels)
