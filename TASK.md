# Task 59.1 — Files 手动整理流程

Next Action: DEVELOPER ALIGNS THE FILES OVERVIEW AND BATCH CONFIRMATION WITH AC-06

```text
Task ID: 59.1
Task Type: SLICE
Parent Slice: 59
Status: FIX REQUIRED
Task Base: 3bc9ad99137e5a2f8ff53add92041185ceb8ebbf
Reviewed Implementation Head: c109e403cc1733baebf20853d618d170c263d338
Difficulty: High
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: ORIGINAL TASK 59.1 CORRECTION SCOPE
```

## B 复核与 Slice 59 交接

**Task 59.1 — FIX REQUIRED。** 从 Files 批量整理两个就绪文件，打开第二项取消纳入，回到概览。
批准预览和实页的上方均显示 `1 / 2`，实页底部又显示已选、需要处理、可确认三组数字。在
390 × 520 的浏览器里，两排底部内容占用了原本可见的第一条就绪文件。继续点「整批复核」，
实际范围正确，只包含第一项。底部的「返回整理概览」和「确认整理 1 项」上下排列，首屏仅读到
确认状态和计数，需滚动才能看到「来源与目标」。同一可确认状态的批准预览在底部同一行左右
放置两项操作，首屏显示「来源与目标」。在 390 × 844 上也可见两个按钮上下排列，桌面已左右分置。
实页还把「方案标识与诊断」放在三栏计数与所选文件之间。这些差异属于 A59-03 的 Files 正常路径。
[Slice AC-06](SLICE.md#acceptance-criteria)

审查从 `main` 的 `c6c253a8894d2616103e0bc3b888784e456907e2` 开始，工作区与暂存区干净。
独立核对完整 Task `3bc9ad99137e5a2f8ff53add92041185ceb8ebbf..c109e403cc1733baebf20853d618d170c263d338`
与完整 Slice `212acdef5d97c14a01353b22c103d44b911d6147..c109e403cc1733baebf20853d618d170c263d338`。
`c6c253a8` 是交接文档，B 的 `a7b8f0c8056cbd3154547705157d89d1578a76b2` 只更新两个浏览器
用例的界面入口和断言，产品源码和构建相同。原计划与 Developer 实跑交接见 `c6c253a8:TASK.md`，
原 Task 59.2 的功能验收和历史证据见 `aa20989a:TASK.md`。

- **RO-1（AC-01/05/06）。** 读取方案仍在同一准备卡展示后端阶段、来源、范围和进度，读取失败后可重读。
  100 项目录保持 `90 / 0` 和真实的作品搜索修正提示，第 101 项按原规则停止。就绪子集计数修正已通过，
  概览底部的重复计数仍占用窄屏正文。
- **RO-2（AC-02）。** 真实混合批次完成识别、候选、作品搜索、分类与冲突处理。普通及丢回包的冲突
  跳过均读回已跳过，返回概览并保留兄弟结果和选择。十项逐项决定最后只确认一次。
- **RO-3（AC-03/06）。** 两个就绪文件默认 `2 / 2`，暂不纳入一个后为 `1 / 2`。首次只提交第一项，
  真实 Worker 处理后兄弟文件留在原处。从同一任务继续第二项，核对第二次提交的丢回包与实际效果。
  正常整批复核的布局与诊断顺序仍需修正。
- **RO-4（AC-04/05/06）。** 原位「继续整理」、原详情页签与筛选、四类同任务恢复、跨页证据在本轮
  原生回归通过。最终任务详情正文的同状态视觉对照属于原 Task 59.2，等 Files 修正通过后接续。
  Slice 59 仍为 FIX REQUIRED。

受影响组件 **179 项**、Files 与 Task Center 布局 **64 项**、OpenList **1 项**通过。构建、类型检查、
改动文件 ESLint 和 Prettier、治理与差异检查通过。完整原生 Files 首跑 **22/24**，两项旧断言分别
在三栏计数里找「未受理」、在当前界面找旧返回或关闭标签。B 保留两轮原始失败，按现有 UI 验证
展开的未受理文件、拒绝原因、精确范围与零变更；技术失败旅程沿实际按钮返回概览、整批读原因并
重新进入单文件只读原计划。两项更新后 **2/2** 通过，其余 22 项输入相同。另有 **11 项**原生任务中心
用例通过。测试使用真实 API、SQLite、Worker 及临时媒体根和隔离 Provider。

本机证据在 `.git/validation-evidence/c109e403cc1733baebf20853d618d170c263d338/b-task59.1-review/`。
`candidate-screens/` 为三个视口的准备、概览、冲突决定和正常整批复核，`current-readability/` 为
100 项真实阻塞。批准预览文件的 SHA-256 已核对。`approved-screens/subset-*.png` 由本轮从批准预览
的「标准整理」同样取消一项后截取，其他同状态预览也保存在该目录。预览和实页均有一项纳入、一项
未纳入，实页按真实方案显示零附件，预览样例所选文件带一份字幕。冲突选项按各自方案权限显示。

## 目标与 Developer 开发指导

操作者从 Files 在概览确认范围，打开整批后先看到确认状态、三栏数字和所选文件，在固定操作区返回
或提交。范围限 Files 概览和整批复核正文样式。

1. 在 `ManualOrganizeDialog.tsx` 的 Files 概览固定区去掉重复的已选、待处理、已有记录和可确认数字。
   保留正文唯一的三栏以及「整批复核」按钮里的精确已选数量。真实方案阻塞和下一步继续由现有状态卡
   说明。原来检查底部同一计数的用例改在概览同一个三栏上核对，保留 `2 / 2 → 1 / 2`、
   `90 / 0` 和已跳过、已有结果的真实计数。
2. 把 Files 整批的「方案标识与诊断」放到所选文件和未纳入原因之后，继续可展开。三栏之后直接
   阅读「来源与目标」。保留准确的来源、目标、操作、实际来源影响和确有的附件，保留原位拒绝、
   授权、重新分析及提交核对。
3. 在 Files 正常可确认状态，让返回与确认在底部同一行分居左右。现有窄窗 CSS 把确认区设成整行，
   将正常 Files 确认和需要显示较长原因的状态按现有 `confirmationBlocker` 区分布局。在 390 × 520
   保持两项操作可见，让正文首屏露出「来源与目标」，长路径使用现有单正文滚动。保留焦点、键盘、
   reduced-motion 和 Task Center 原位续作的正文。
   [整理弹窗](web/src/features/operations/ManualOrganizeDialog.tsx) · [样式](web/src/shared/ui/styles.css)

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
