# Task 59.2 — 任务中心运行详情正文

Next Action: DEVELOPER CORRECTS RUN PHASE COPY AND BRINGS THE CURRENT RECOVERY ACTION FIRST

```text
Task ID: 59.2
Task Type: SLICE
Parent Slice: 59
Status: FIX REQUIRED
Task Base: 868ff9daab6972473cfb7344ca02cbdbc30077cf
Reviewed Implementation Head: 3d39ec021599d1eb18b5706b358be6306a676b0e
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: ORIGINAL TASK 59.2 / SLICE 59 A59-03 CORRECTION SCOPE
```

## B 复核与 Slice 59 交接

**Task 59.2 — FIX REQUIRED。** B 从干净的 `main` 独立复核完整 Task
`868ff9daab6972473cfb7344ca02cbdbc30077cf..3d39ec021599d1eb18b5706b358be6306a676b0e`
及完整 Slice `212acdef5d97c14a01353b22c103d44b911d6147..3d39ec021599d1eb18b5706b358be6306a676b0e`。
`a261b93f` 交付详情样式，`3d39ec02` 交付四类恢复与新计划摘要的布局。原规划和上轮 Files 验收
保存在 `b4ff62f1:TASK.md`。本轮依据已提交的 AC-04/05/06（含 `2cc2ae0e`、`e82c0166`、
`60a4b65d`），批准预览的 SHA-256 已校验。
[Slice 验收](SLICE.md#acceptance-criteria)

1. **P1 / AC-04、AC-05。** 从 Files 为 `Two.2002.mkv` 生成方案，未确认就关闭。到任务中心点列表里
   的原任务。首卡显示「正在处理文件」「执行已受理」，下方仍显示「查看整理摘要，确认后执行」
   和「继续整理」。同一任务的持久流程为进行中，已有一个等待项，原旅程截至此时有零次 Execute。
   `a261b93f` 的首卡仅凭流程的 `running` 推断执行已受理。操作者无法从第一屏判断自己是否还要确认。
   [首卡文案](web/src/features/operations/OperationsLanding.tsx#L1944)
2. **P1 / AC-06。** 从任务中心「元数据恢复」打开问题文件，390 px 界面先读到通用处理结果、来源、
   空目标以及重复的待修正信息，实际修正原因和表单在下面。保存后在同一条目生成新方案，首部仍显示
   「没有已记录的目标文件」，往下才出现新摘要里的真实计划目标和「确认继续整理」。`3d39ec02` 的
   四类表单已改为逐行选项，摘要也有实际路径和影响，但它们仍排在通用证据之后。批准预览先提供
   当前决定，分析完成后原位切到新摘要。可操作的决定或计划仍需成为展开区的主体。
   [证据排列](web/src/features/operations/RunDetailTabs.tsx#L1898) ·
   [四类恢复与新摘要](web/src/features/operations/TaskItemRecoveryPanel.tsx#L1982)

**Slice 重评。** RO-1 的准备与概览、RO-2 的 Files 决定回落保留上一轮已审结果。RO-3 的精确子集、
单次确认和原任务续作在本候选原生通过；最新 AC-06 的 Files 行内容仍有待修正。本轮在隔离
`ReadabilityTen` 用 Files 自带的「新建文本文件」加一份同名中文字幕，选择两个主文件并取消一项。
整批正确显示一项确认、一项未纳入、一份附件。标题仍写「共 1 项」，所选文件行缺图标，来源影响重复，
字幕种类和语言需展开才可查。实点已选文件名跳到逐项复核，违反当前合同要求的普通文本。这一处
后续回到原 Task 59.1 的 Files 整批行范围修正。RO-4 的首卡布局、紧凑行、行内历史、记录及同任务
恢复取得当前证据，以上两个 Task 59.2 缺口待修。Slice 59 继续 FIX REQUIRED。

**实跑。** 构建、类型、Lint、Prettier、治理和差异检查通过。4 个组件文件共 179 项，原生 Task、
Files 回归和流程组 17 项，恢复授权与真实效果组 5 项通过。布局首跑 88/90，B 的
`8acd5872fc8768bbcbfbd8595e93642d84c0db48` 仅让两条旧断言从紧凑行打开证据，并核对最新结果和
折叠的上一次尝试均完整，重跑 2/2 通过。保留 Developer 已记录的 Files 作品候选旧入口测试失败，
它仍在等待直接显示逐项页，本轮原生恢复搜索已通过。实际截图覆盖运行详情、记录、证据、四类决定
和新摘要。第一个 Files 截图用例的原夹具无字幕，借现有 Files 创建后复验成功。原始日志和三个视口
截图见本机 `.git/validation-evidence/3d39ec021599d1eb18b5706b358be6306a676b0e/b-task59.2-review/`。
最终 Slice 门禁在修正候选上完成。

## 目标、范围与 Developer 开发指导

用户在原任务详情首屏判断是否还需要决定或确认。点问题文件时，先完成它当前的决定，随后在原位核对
新方案并明确继续。同一文件的结果、尝试和技术依据随时可查。范围限原 Task 59.2 的运行详情正文。

1. 从 `RunFlowSummary` 和 `runStatusHeadline` 修正首卡。流程状态继续读原持久状态。用已有的
   等待、进度、可续作和执行证据说明当前阶段。尚待确认的 Files 工作用实际等待说明和「继续整理」，
   显式确认后再显示这次执行的受理或实际阶段。已有一次确认而另一项仍等待时分别说明两者，沿用原
   任务关联和受理核对。文件成功的文案沿用既有摘要口径。
2. 在 `RunEvidenceSection` 与 `TaskItemRecoveryPanel` 组织同一条目的正文。可操作时，文件标题、
   真实问题与当前决定或新摘要排在前面。仅在已有相应事实时显示实际操作与效果，历史的空目标
   无需在新摘要上方再次占位。只读结果继续先呈现当前结果、来源、目标和实际效果，再展开处理依据、
   历史与诊断。已实现的逐行选项、字段、刷新及失败后的下一步继续使用原接口和权限。
3. 新摘要摆在原文件下，先显示当前可确认文件、来源、目标和影响，其他条目的原因与技术字段按需
   查阅。选择与覆盖、来源清理各自授权仍绑定准确摘要与子集，使用原有的显式确认和原请求核对。
   保留原详情的焦点、跨筛选证据和草稿，以及 Task Center 原位整理卡。
   [运行详情](web/src/features/operations/OperationsLanding.tsx) ·
   [行内证据](web/src/features/operations/RunDetailTabs.tsx) ·
   [同页摘要](web/src/features/operations/SamePagePlanSummary.tsx)

## 验收与测试

- [ ] 保持 `Two.2002.mkv` 的 Files 准备未确认，关闭后从任务列表打开原详情。操作者读到仍待确认，
  用「继续整理」打开原方案并确认一次，再从原任务查看真实执行与文件结果。检查未知总量、失败和
  已取消仍对应实际读回。
- [ ] 从四类问题入口逐屏对照 1280 × 900、390 × 844、390 × 520。问题原因和决定先可读。实际
  元数据搜索修正和分类保存后，在同一条目读到新目标、影响和明确确认。覆盖长路径、键盘、焦点、
  读取失败重读、保留草稿、已有尝试和效果未知。确认前零媒体变更，确认后只发生选中效果。
- [ ] Developer 运行改动文件的 ESLint 与 Prettier、类型检查和构建，复用三个任务中心组件用例、
  两类布局用例及既有原生入口。记录截图、候选和结果。B 在候选上复核完整范围、Task 59.2 的 T3
  门禁及已提交的全部 Slice 结果。测试墙钟低于本轮用时一半。

```sh
npm run test -- run src/features/operations/RunDetailTabs.test.tsx src/features/operations/OperationsInventory.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx
npm run test:e2e -- tests/e2e/task-center-layout.spec.ts tests/e2e/operations.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'initial manual preparation remains reachable in place|selected run detail reads progress|native recognition recovery|native Metadata candidate recovery|native Metadata correction|native Classification recovery|native conflict recovery|policy-permitted overwrite'
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/task-flow.python.spec.ts
```

[开发与验收分工](docs/development-workflow.md#6-test-levels)
