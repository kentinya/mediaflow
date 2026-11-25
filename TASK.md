# Task 59.1 — Files 四类决定与回概览

Next Action: DEVELOPER CORRECTS THE REMAINING A59-06 FOOTER MISMATCH IN TASK 59.1

```text
Task ID: 59.1
Task Type: SLICE
Parent Slice: 59
Status: FIX REQUIRED
Task Base: 3bc9ad99137e5a2f8ff53add92041185ceb8ebbf
Reviewed Implementation Head: 819c73ddcf75aa39a4686c6cd23141d7180ede99
Planning Contract: 36f60fe0ef75c9cbb9e0b30e258c2d6f4075f24d
Difficulty: High
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: ORIGINAL TASK 59.1 REMAINING A59-06 CORRECTION
```

## 目标

从 Files 原有入口整理一批文件。用户打开某一文件时，先看到当前问题和原因，再选择处理方式。
保存后用同一文件的实际读回判断留在原页还是回概览。后续文件生成新方案时，先前已跳过或忽略的
文件仍能在概览中查到。用户最终从整批复核确认当前方案中的合法子集。
[Slice RO-2、AC-02/06 与 A 终审退回](SLICE.md#a-独立复验--6c54559b--fix-required)

本轮按用户授权代 B 规划。以 `36f60fe0` 固定的最新批准离线稿为准，核对信息顺序、操作位置、
回落和状态反馈。字号、间距和折行按真实内容及视口调整。规划时 `main` 位于该提交，工作区与
Git 可写，治理检查通过，暂存区干净。唯一已有改动是未暂存的 Task 59.3 草稿，原件见接续安排。
[批准版本与设计依据](SLICE.md#授权基线与设计依据)

## 范围与实施步骤

1. **A59-06。** 在 Files 逐项复核中沿用原弹窗标题与关闭入口。正文依次呈现当前文件及来源、
   当前问题和简明原因、允许的决定。识别、元数据候选和分类目标逐行陈列。作品搜索字段按
   标题、年份、作品类型排列，保留查找、输入校验及真实结果。冲突在选项前集中显示一次已有
   目标路径，保留跳过、重命名和覆盖的实际资格及适用授权。共用底栏提供返回概览、可用翻页、
   合法的「保存并重新分析」及允许的忽略。收起重复说明和空方案占位，保留失败原因和合法下一步。
   用 Files 入口限定决定表单的布局与底栏位置，任务中心恢复继续使用自身的行内交互。
   [逐项正文](web/src/features/operations/ManualOrganizeDialog.tsx#L4305) ·
   [共享表单与操作](web/src/features/operations/TaskItemRecoveryPanel.tsx#L367)
2. **A59-07。** 将 Files 概览的已结算记录与当前可执行方案分开投影。校验原准备、原任务及
   持久文件和 TaskItem 的关联，从同一任务的持久条目读回补齐后来摘要移出的跳过、忽略记录。
   优先复用已有精确关联、条目证据及有界只读查询，刷新和关闭重开也按持久事实恢复。合并当前
   摘要和记录时按已证实的文件身份去重，原行已存在时更新同一行。链接缺失或暂不可读时保留
   同一任务的读取反馈和合法重读入口。按准备及任务隔离缓存，迟到的读回只更新对应文件。
   用一套行投影计算待处理、就绪、已有记录及其计数。整批复核和执行仍从当前有效方案、已纳入
   选择及后端资格取交集，保持覆盖和清理许可的原有校验。
   [现有方案与持久条目结合处](web/src/features/operations/ManualOrganizeDialog.tsx#L1135) ·
   [概览行投影](web/src/features/operations/ManualOrganizeDialog.tsx#L1317) ·
   [原任务条目读回](web/src/features/operations/run-detail-query.ts#L56)
3. 保留逐项保存、重新分析、结果读回及回落的现有守卫。证实该文件生成当前可确认方案并回概览时，
   首区显示「整理方案已更新」，紧接具体文件与「整理尚未提交」的反馈。明确跳过、忽略、新问题、
   技术失败分别显示对应结果。仍需修正时留在原文件并保留输入。决定已保存但分析未受理时，
   下一次操作只补分析。受理未知时先核对原条目。用户先行翻页、进入复核或开始新编辑时，迟到
   读回保留当前焦点、所选子集及兄弟草稿。

本轮范围限 Files 逐项决定与回概览。沿用现行写入合约、Task/Plan/Result 与执行权限。
准备页、任务中心列表和详情的后续工作见接续安排。影响核心执行、权限或耐久模型的变更交 B
重评任务与测试等级，并按 Slice 边界处理。

## 验收

- [ ] 从真实 Files 混合批次进入识别、元数据候选、作品搜索修正、分类、目标冲突五种表单。
  在桌面和 390 px 对照批准稿检查真实选项的可读性、字段顺序、冲突目标出现一次、固定底栏、
  键盘顺序和错误反馈。核对允许与拒绝、搜索无结果、保存失败、队列满及受理未知后的合法操作。
- [ ] 先跳过真实冲突，再完成四个兄弟文件的分析。每次更换摘要后核对原 TaskItem 仍为
  `skipped`，概览保留同一个原文件行及「已有记录」计数。验证刷新、关闭后从原准备重开、
  晚到读回、跨准备隔离和重复读回去重。对允许的忽略覆盖同样的持久读回场景。每次生成可确认
  新方案后核对首区标题、具体文件、未提交反馈、就绪和待处理计数。覆盖分析产生下一类问题、
  同类仍需修正及技术失败。用户切换位置或新编辑后，读回只更新对应行。
- [ ] 回看一次整批复核，只列四个当前合法文件并进行一次确认。用原任务 ID、实际提交子集、
  持久结果与临时媒体根核对执行。保存与分析期间零媒体变更，已跳过冲突的源文件和已有目标
  保持原状。复验十项逐个处理后单次确认，以及兄弟分析替换摘要时仍按原提交身份核对未知回包。
- [ ] 任务中心识别、元数据候选和搜索、分类、冲突继续在原任务详情的文件行内操作。核对后端
  资格、同页新计划与显式继续确认，并复验适用覆盖许可。

## 测试

### Developer 受影响检查

在 `web/` 运行以下命令。补强现有混合用例，在后续兄弟分析、摘要替换和原准备重开后断言
跳过记录与计数，并核对提交身份和四文件子集。组件用例覆盖忽略、合并去重、跨准备隔离、迟到
读回、表单顺序与操作资格。原生用例覆盖真实结果、精确提交和未知回包。命令中的文件按候选实际
改动调整检测范围。交接精确 SHA、实际结果和五种表单及概览的桌面／390 px 截图。

```sh
npm run typecheck
npm run build
npx eslint src/features/operations/ManualOrganizeDialog.tsx src/features/operations/TaskItemRecoveryPanel.tsx src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx tests/e2e/manual-organize-dialog.python.spec.ts
npx prettier --check src/features/operations/ManualOrganizeDialog.tsx src/features/operations/TaskItemRecoveryPanel.tsx src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/shared/ui/styles.css tests/e2e/manual-organize-dialog.python.spec.ts
npm run test -- run src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts --grep 'mixed Files decisions|real conflict skip returns|lost decision response returns|ten per-file candidate decisions|unknown original submission is reconciled'
```

### B 独立 T3 验收

从原 Task Base 到 Developer 候选检查完整差异，并核对 Slice 范围。从实际 Files 入口独立复跑
上述组件与原生场景，确认五种表单、跳过后新版摘要与重开、单次执行子集和持久结果。对照批准稿
记录桌面及 390 px 截图。补跑由共享表单影响的任务中心真实恢复路径。在仓库根运行治理与
空白检查。B 在最终候选负责 Slice 全部门禁，按可复用条件保留实际命令、结果和证据。
[门禁与职责](docs/development-workflow.md#6-test-levels)

```sh
# 仓库根目录
python3 scripts/check_governance.py
git diff --check 3bc9ad99137e5a2f8ff53add92041185ceb8ebbf..HEAD
# web/
npm run lint
npm run format:check
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'native recognition recovery|native Metadata candidate recovery|native Metadata correction|native Classification recovery reconciles|native conflict recovery renames|policy-permitted overwrite'
```

## B 复核与 Slice 59 交接

### 2026-11-26 · FIX REQUIRED

B 从干净的 `main` 独立复核原 Task Base 至 `819c73ddcf75aa39a4686c6cd23141d7180ede99`。
治理、Task 和 Slice 区间空白检查、Web 类型、ESLint、Prettier 和生产构建通过。两组组件共
94 项、真实 Python/API/SQLite/Worker 浏览器用例 11 项通过，另有一项混合批次补验通过。

**A59-06 剩余阻塞（P1，RO-2 / AC-06）。** 从 Files 混合批次打开五种决定表单，正文选项、
搜索字段顺序和冲突目标位置已对齐。决定页底栏仍显示「关闭」和「整批复核」，与本文件的处理动作
并列。真实冲突页 390 px 底栏高 161 px，批准稿同状态为 111 px。分类选择后底栏占四行。

1. 为 Files 四类决定使用批准稿的底栏分组。左侧返回概览，右侧依次显示可用翻页和适用的忽略、
   保存或当前恢复动作。关闭走现有顶栏入口及草稿核对，整批复核从概览进入。文件序号使用正文
   当前文件区，草稿提示跟随当前文件。依据视口布局，保持键盘顺序与视觉顺序一致。
2. 在现有混合原生用例中增加决定页底栏可见动作和顺序的验收。覆盖五种表单、首次打开和修改草稿后、
   1440 与 390 px。经返回概览核对原行焦点和选择，再进入整批复核并确认当前合法子集。复验顶栏关闭
   与未保存草稿提示。用上节命令运行直接受影响的组件与原生旅程，提交候选后交 B 独立复验。

[Files 逐项底栏](web/src/features/operations/ManualOrganizeDialog.tsx#L5918) ·
[批准稿四类决定验收](SLICE.md#acceptance-criteria)

**A59-07 已复验通过。** 混合批次先跳过真实冲突。四次后续分析均保留同一 `skipped` TaskItem，
关闭后按准确准备地址重开、再刷新，概览仍有一条记录。重新分析后首区指出具体文件已可确认且尚未
提交。整批只确认四个就绪文件，已跳过的来源和目标保持原状。任务中心原位恢复六条原生回归通过。

本机日志与 1440／390 px 对照图见
`.git/validation-evidence/819c73ddcf75aa39a4686c6cd23141d7180ede99/b-task59.1-review/`。
`review-probe.log` 记录逐次核对和关闭重开，`offline-probe.log` 记录批准稿按钮与视口，
`native.log` 和 `components.log` 记录实际运行。探针初跑的读回字段及场景匹配错误另存日志，修正
探针后执行同一候选。Task 59.1 保持 `FIX REQUIRED`，继续原 Task 修正。

### 此前交接

候选 `6c54559b` 的原 B 交接在 `e0e45bb6:TASK.md`，进度补查在 `f2cd654e:TASK.md`，
Files 精确复核原通过记录在 `43ab597c:TASK.md`。Task 59.2 两页签共用操作、原位续作和焦点的
通过记录在 `171b3de6:TASK.md`。本轮 A 的五种 Files 实景、对照截图与 `live.log` 在本机
`.git/validation-evidence/6c54559b054d75682fc9ead615191d6c0b351285/a-slice59-files-decision-parity/`。

### 接续安排

1. 原 Task 59.1 通过后重新启用原 Task 59.3 修正，沿用其 Base
   `d1ea5f667c5ebc08e1a6835030197c1724f4f4d2`。覆盖 A59-04 的任务详情文字进度与
   A59-05 的同一任务结算后已访问筛选、游标页重新读取，保留选中页签与原文件证据位置。
   原草稿逐字节保存于本机目录
   `.git/validation-evidence/36f60fe0ef75c9cbb9e0b30e258c2d6f4075f24d/b-planning-handoff/task-59.3-preexisting-draft.md`。
   SHA-256 为 `b7dc6466b9eeea12703e2584cd6886e2f7606be35e9335fb24e6f522e7e6a4d4`。启用时按现行提交合同核对草稿顺序和范围。
2. 按剩余结果规划共用准备页。完整准备按真实读回依次呈现「检查所选范围」和「生成整理方案」。
   只读原方案等单步场景直接显示正在做的那一步。已就绪的续作直接进入原复核。随后按实际范围
   规划任务中心「需要处理」至同任务文件恢复的完整旅程。核对原有八种查询与合法深链，在完整
   授权范围内按原任务和文件去重、计数、分页。点文件直达原任务对应行及恢复，关闭返回原筛选和
   焦点。逐 Task 通过后重评全部 Slice 结果，最终由独立 A 终验。
