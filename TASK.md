# Task 59.2 — 任务中心运行详情正文

Next Action: DEVELOPER RESTORES THE EXACT CONTINUE FOCUS AFTER A RECOVERED DETAIL READ

```text
Task ID: 59.2
Task Type: SLICE
Parent Slice: 59
Status: FIX REQUIRED
Task Base: 868ff9daab6972473cfb7344ca02cbdbc30077cf
Reviewed Implementation Head: 666aa348292de0d5b8caa9a4f6a19e7185bbadb7
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: ORIGINAL TASK 59.2 / SLICE 59 A59-03 CORRECTION SCOPE
```

## B 复核与 Slice 59 交接

**Task 59.2 — FIX REQUIRED（P1，RO-4 / AC-04）。** B 从干净的 `main` 开始，审查完整 Task
`868ff9daab6972473cfb7344ca02cbdbc30077cf..666aa348292de0d5b8caa9a4f6a19e7185bbadb7`
及完整 Slice `212acdef5d97c14a01353b22c103d44b911d6147..666aa348292de0d5b8caa9a4f6a19e7185bbadb7`。
上轮决定和修正前证据见 `c929bd96:TASK.md`。
[Slice 验收](SLICE.md#acceptance-criteria)

- **已通过。** 从 Files 为 `Two.2002.mkv` 生成方案，先不确认，再从任务列表打开同一任务。
  「任务详情」与「操作记录」共用「继续整理」「取消运行」「导出结果 JSON」，桌面右侧同排，
  390 × 844 和 390 × 520 整组在页签下方。主按钮、红色取消描边及尚无结果时的导出说明与当前状态
  相符。键盘从「操作记录」依次到继续、取消。正常关闭及放弃草稿均回到原页签、记录筛选和继续按钮。
  实点「操作记录」中的取消，读到「取消请求已受理；当前状态：已取消」，切回详情仍为同一已取消任务。
  另从已有结果的任务实际下载有界 JSON。四类原生恢复、同任务新摘要和两次确认的原请求核对通过。
- **当前阻塞。** 在同一个待确认任务的「操作记录」筛选为「运行日志」，点「继续整理」，打开「修正识别或作品」
  并改动尚未保存的识别类型。任务详情一次后台读取暂不可用，原整理卡和草稿仍在。点「重新读取任务」
  恢复后，选「关闭整理弹窗」和「放弃草稿并关闭」。原任务、页签和筛选正确，焦点却停在「关闭详情」。
  用户用键盘继续核对时，得重新走到原按钮。沿用已有单次读取失败用例，两次实跑都复现。运行详情
  发生临时读失败时以提示替换正文，原链接随之移除。成功读回后出现新的同任务链接。共用弹窗仍持有
  原链接，关闭时因它已移除而把焦点转给「关闭详情」。
  [失读分支](web/src/features/operations/OperationsLanding.tsx#L1725) ·
  [现有回落](web/src/features/operations/OperationsLanding.tsx#L922) ·
  [弹窗焦点](web/src/shared/ui/modal-card.tsx#L251)

**Slice 重评。** RO-1 的 Files 准备与概览、RO-2 的四类决定及回落沿用前轮的 Files 证据。
RO-3 的精确子集和原受理核对本轮通过，整批复核的已选文件名、文件图标、库路径、单次来源影响
和字幕简述仍待原 Task 59.1。此前已从 Files 选两项、排除一项并进入有中文字幕的整批复核，
实测点击已选文件名会离开整批；这段 Files 实现与已取证候选 `3d39ec02` 一致。
RO-4 共用操作区本轮通过，恢复读取后的原入口焦点仍待当前 Task 59.2。Slice 59 仍为 FIX REQUIRED。
[整批文件行](web/src/features/operations/ManualOrganizeDialog.tsx#L4870) · [Files 差异记录](SLICE.md#acceptance-criteria)

**实跑。** 治理、两段完整差异检查、类型、构建、改动文件 ESLint／Prettier 通过。三个组件文件
127 项、任务中心和布局浏览器 39 项、原生回归 10 项通过。B 用同一已有 Files→任务中心用例补验。
正常关闭、放弃草稿及从「操作记录」实际取消通过；恢复读取后退出的焦点另跑两次失败。首次补
验的临时脚本出现局部变量重名，修正后运行了正常路径。截图原型的已有结果与真实未确认任务不同，
真实任务继续显示为何暂不可导出。日志和桌面、390 × 844、390 × 520 截图在本机
`.git/validation-evidence/666aa348292de0d5b8caa9a4f6a19e7185bbadb7/b-task59.2-review/`。

## 目标、范围与 Developer 开发指导

用户从同一任务的「继续整理」打开原整理卡。任务详情临时读取失败且重新读取成功后，关闭整理卡
回到原任务、原页签、原筛选和当前的「继续整理」，可直接继续键盘操作。范围限原 Task 59.2 的
任务中心续作关闭交接。

1. 从 `RunDetailPanel` 的「继续整理」保存本次打开所对应的任务和触发入口。在
   `OrganizeContinuationHost` 结束关闭、底层卡恢复交互时，让焦点交接能定位同一任务当前渲染的
   继续按钮。复用现有弹窗焦点归还和 `preventScroll`，让它在正文经实际失败及恢复而重建后也能
   回到原入口。
2. 继续按原 `run + dialog=organize` 和现有详情读模决定按钮资格。直接访问续作地址或合法按钮已
   消失的关闭沿用现有详情关闭按钮／页面标题回落。保留现有读取提示、草稿丢弃确认、取消资格、
   导出和正式确认交接。
3. 在已经覆盖临时读失败的原生用例补足从「操作记录」出发，到恢复读取再关闭的焦点断言。
  同时确认同一任务、原「运行日志」筛选及「继续整理」按钮的实际焦点，复用用例现有的真实准备、
   单次读取失败、重新读取与丢弃操作。
   [原生用例](web/tests/e2e/operations-inventory.python.spec.ts#L5263)

## 验收与测试

- [ ] 从 Files 留下未确认方案，从原任务「操作记录」选「运行日志」后继续整理；在现有读取失败夹具
  中改动识别类型，重新读取成功后放弃草稿并关闭。核对同一任务、原筛选、列表上下文、继续按钮
  焦点、零新增提交，并可再次从该按钮进入原计划。
- [ ] 复验正常关闭、放弃草稿、直接续作地址的焦点回落，以及同组操作在桌面和 390 px 仍可达。
  复用当前任务的取消核对及有界导出测试。
- [ ] Developer 运行改动文件 ESLint／Prettier、类型和构建，再运行下列直接受影响测试。B 复核
  新候选的完整差异和原 T3 旅程。各轮测试墙钟低于本轮用时一半。

```sh
npm run test -- run src/features/operations/OperationsInventory.test.tsx src/features/operations/RunDetailTabs.test.tsx
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'initial manual preparation remains reachable in place|detail tab and filter context|the eligible run exports'
```

[开发与验收分工](docs/development-workflow.md#6-test-levels)
