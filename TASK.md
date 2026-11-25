# Task 59.1 — Files 手动整理流程

Next Action: DEVELOPER CORRECTS THE FILES BATCH SOURCE AND TARGET ROWS

```text
Task ID: 59.1
Task Type: SLICE
Parent Slice: 59
Status: FIX REQUIRED
Task Base: 3bc9ad99137e5a2f8ff53add92041185ceb8ebbf
Reviewed Implementation Head: c47ab80e4e4beb641804c19e8cda69ec7c146b68
Difficulty: High
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: ORIGINAL TASK 59.1 / SLICE 59 A59-03 CORRECTION SCOPE
```

## B 复核与 Slice 59 交接

**Task 59.2 — PASS。** 从干净的 `main` 审查完整 Task
`868ff9daab6972473cfb7344ca02cbdbc30077cf..c47ab80e4e4beb641804c19e8cda69ec7c146b68`
及完整 Slice `212acdef5d97c14a01353b22c103d44b911d6147..c47ab80e4e4beb641804c19e8cda69ec7c146b68`。
从 Files 留下 `Two.2002.mkv` 的未确认方案，从原任务「操作记录」筛选「运行日志」并继续整理。
更改未保存的识别类型，任务详情后台读取暂时失败时草稿仍在。点「重新读取任务」，关闭整理卡并
放弃草稿，回到同一任务、页签和筛选，底层列表仍在原来的列位置，焦点回到「继续整理」。按 Enter 重开同一方案，
截至重开零新增提交。正常关闭及直接访问续作地址的详情关闭按钮回落通过组件回归。
两页签的共用按钮、桌面及 390 px 排列、有界导出、取消结果和四类原生恢复通过。
[焦点修正](web/src/shared/ui/modal-card.tsx) · [原生验收](web/tests/e2e/operations-inventory.python.spec.ts#L5263)

**Task 59.1 — FIX REQUIRED（P1，RO-3 / AC-06）。** 在 `ReadabilityTen` 的 Files 页面，用
「新建文本文件」为第一部影片添加同名的 `ReadableTen01.2011.zh.srt`。选中前两部影片，在第二部的
逐项复核取消纳入，回到概览进入「整批复核」。三栏准确显示本次确认 1 项、未纳入 1 项、关联附件 1 个。
点击「来源与目标」里唯一已选文件的文件名，会离开整批并进入逐项复核。该行在桌面、390 px 及矮窗
都缺文件图标，标题右侧重复「共 1 项」，路径以 Storage 标识开头，移动的来源影响显示两次。
页面已有中文字幕的类型和语言，但要展开通用附件说明才能看到。根因是 Files 的已选文件仍共用逐项
跳转按钮，其行内分支直接显示 Storage 路径，并在右侧操作和中部详情都显示来源影响。
[当前整批文件行](web/src/features/operations/ManualOrganizeDialog.tsx#L4870) ·
[Slice 验收](SLICE.md#acceptance-criteria)

**Slice 59 — FIX REQUIRED。** RO-1 的 Files 准备和概览、RO-2 的决定与回落已有原 Task 59.1
验收记录（`b4ff62f1:TASK.md`）。RO-3 的精确子集、两次确认和原任务交接本轮通过，剩余缺口集中于
Files 整批文件行。RO-4 的详情正文、四类恢复和原任务续作通过。按 A 已提交的 A59-03 在原 Task 59.1
修正整批文件行，通过后重评完整 Slice。

**实跑。** 治理、差异检查、类型、构建、改动文件 ESLint 和 Prettier 通过。4 组组件 139 项、
任务中心和布局浏览器 39 项、真实 API／SQLite／Worker 原生回归 12 项通过。另从相同的 Files 入口
复现整批差异，核对确认按钮可用、查看文件名只发生页面切换、零执行提交。原生截图与结果在本机
`.git/validation-evidence/c47ab80e4e4beb641804c19e8cda69ec7c146b68/b-task59.2-review/`。

## 目标、范围与 Developer 开发指导

用户从 Files 的「整批复核」一眼核对所选文件的去向、来源影响与关联字幕，并能在按需查看详情后
继续确认当前选中的合法子集。范围是 Files 承载的「整批复核」已选文件行及其适用样式。

1. 在 `ManualOrganizeDialog.renderConfirm` 的 Files 分支把「来源与目标」标题行右侧改为
   「按当前方案」。复用 Files 概览的文件图标呈现方式。整批行采用左侧图标、中间文件名、来源、
   目标、一次来源影响和适用附件简述、右侧单独的操作名称。已选文件名渲染为普通文字。通过
   「返回整理概览」点同一文件进入逐项复核。未纳入区保留现有独立的「查看」入口。
2. 路径使用这份计划实际对应的库。来源的 `resourceLibraryId` 与 Files 已取得的库身份、Storage
   和库根匹配后显示库名与库内相对路径。目标复用预览的 `analysis.classification.mediaLibraryId`
   和 `destination.relativePath`，用已有媒体库读模核对库名、Storage 和根目录。库名或库内相对
   路径无法从现有证据确认时，行内仍显示已核实的路径。通过行内或既有证据查看精确 Storage 标识及路径。
3. 使用现有 `operationLabel`、`operationImpactLabel` 和附件投影。右侧标签仅含「移动」「复制」
   等操作名称；同一行中部说明实际来源影响。已知普通字幕直接显示「中文字幕（.zh.srt）」这样的
   简述；展开仍能核对原来源、目标、操作、异常和合法下一步。无附件时行内省去附件项。
   使用 `.mf-organize-files-batch-list` 的局部样式，保留长路径折行、固定底栏和一个正文滚动区。
   保留真实选中与可确认计数、未受理原因、覆盖与清理授权、提交核对及任务中心续作的现有正文。
   [整批文件行](web/src/features/operations/ManualOrganizeDialog.tsx#L4870) ·
   [已有目标与附件读模](web/src/entities/operations/preview.ts) ·
   [Files 库上下文](web/src/features/library/StorageFilesPage.tsx#L2480)

## 验收与测试

- [ ] 从原 Files 入口选两部影片，给其中一部附带已知语言的字幕，排除另一部。对照批准预览核对
  1280 × 900、390 × 844、390 × 520 的「来源与目标」和底栏。点已选文件名仍留在整批复核，
  Tab 跳过文件名。展开附件查看精确事实；展开未纳入区可定位另一项。经「返回整理概览」打开
  同一文件再回整批，核对原选中范围和确认资格。无附件的既有十文件用例覆盖普通行。
- [ ] 用现有两次确认用例核对确认前零媒体变更、确认后只执行所选范围，另核对 100 项与混合未受理的
  原生入口，以及任务中心「继续整理」的原整批视图与焦点交接。
- [ ] Developer 在 `web/` 运行类型、构建、改动文件 ESLint／Prettier 和下列受影响测试。更新
  原十文件用例中固定的旧文案断言，交接候选 SHA、实际结果及三种视口证据。B 复核原 Task 59.1
  的完整 Base..Head 和本次实际入口，再补齐适用的 Slice 最终门禁。各轮测试墙钟低于本轮用时一半。

```sh
npm run test -- run src/features/operations/ManualOrganizeDialog.test.tsx
npm run test:e2e -- tests/e2e/library-files.spec.ts --grep 'same-page preparation links the summary and confirms one exact subset'
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts --grep 'second confirmation on the same Task|pending owned file beside|one file separates source and target|ten files keep an aligned batch summary|100-file batch'
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'initial manual preparation remains reachable in place'
```

[开发与验收分工](docs/development-workflow.md#6-test-levels)
