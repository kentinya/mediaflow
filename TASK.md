# Task PATCH-20261122-1 — 手动整理弹窗状态与排版修复

Next Action: Developer 按本 Task 开始实施，完成受影响验证后交 B 独立审查。

用户明确要求激活本独立修复 Task。优先级为第一屏「准备中」→ 第三屏「整批复核」→ 第二屏「逐项复核」。
`PLANNED` 表示已激活、待 Developer 开始。 [Development Workflow](docs/development-workflow.md#31-independent-minor-bugs)

```text
Task ID: PATCH-20261122-1
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: 8ce6c2092c328a15c44493f51ae4690b15680960
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: USER AUTHORIZED
```

### 目标与调查基线

用户在资源库文件页选择单文件、多文件或文件夹，打开整理弹窗后能直接看懂进度和下一步。方案就绪后，
逐项查看来源、目标和操作，必要时完成现有修正，再核对整批范围及实际影响、明确确认。受理后打开准确的
任务详情。真实失败要说明阶段、已保存状态、已知效果和可用的下一步；重开继续使用同一次整理。
适用 `V2-OPS-010/015/017–019` 和 `REQ-RECOVERY-007/009`。
[产品旅程](docs/product-experience.md#current--manual-organize-dialog-slice53-pass--closed) · [现行架构](docs/architecture.md#current--manual-organize-dialog-slice53-pass--closed)

规划前 `main` 指向上述 Base，工作区与暂存区干净，仓库可写，治理检查通过。调查用相同产品代码构建，
在隔离 Python/API/SQLite/Worker 和合成文件上查看桌面、390px 页面，覆盖 1、10、100 个文件，发出的
执行请求数为零。主要缺口如下。

- **第一屏**的 Files 正常准入和来源占用后的兄弟项准入都把 `False` 传入 `MediaDiscovery.error`，
  SQLite 读回文本 `0`。弹窗将非空错误当成真正失败，显示红色「失败说明：0」。排队标题和正文又同时
  提示正在检查；多选路径在同一段全部展开。[准入初始化](mediaflow/application/media_discovery.py#L546) · [准备呈现](web/src/features/operations/ManualOrganizeDialog.tsx#L1539)
- **第三屏**先显示方案 UUID、版本和前三条完整目标路径，清单重复显示路径并在弹窗内另设滚动区。
  100 文件样本中，90 条入选记录的窄屏首屏只读得完一条，未纳入的 10 条及确认受阻原因在下方。
  该样本的后端返回方案失效，确认关闭，观察结果用于验收信息位置与排版。[整批复核](web/src/features/operations/ManualOrganizeDialog.tsx#L2308)
- **第二屏**把来源和目标合成一个文本块，完整路径换行时难以区分起止。[来源与目标](web/src/features/operations/ManualOrganizeDialog.tsx#L1953)

激活前 `main` 指向规划提交 `44349174a2569a1bbe236279e3623b065316eecc`，工作区与暂存区干净，
治理检查通过。Base 至激活前仅有规划文档变更。 [Slice 57 终审](SLICE.md#a-final-review--pass--closed)

### 实施顺序

1. **准备中。** 修正相关 Files 准入的无错误初值。对已有正常排队记录的旧 `0` 哨兵做窄范围读侧兼容，
   保留真实错误、原有记录与恢复入口。按后台事实显示一处主要阶段与可用进度，排队、检查、等待稳定和
   分析各有明确状态；多选先显示文件／文件夹数量，完整范围可展开。真实失败、排除与超限说明可就近
   查看，保留同一准备的读取和原目录缩小范围等现有动作。技术信息放在可展开的诊断里。
2. **整批复核。** 首屏集中显示实际选入数量、操作、未纳入数量和实际影响，确认受阻时在确认按钮附近
   显示主要原因和现有下一步。保留覆盖与清理的独立明确授权。把 UUID、版本和完整内部标识放在诊断中，
   去掉首屏预先拼接的三条路径。下方使用行间距和对齐一致的清单，文件、操作和目标易于扫读，窄屏按项
   堆叠并允许长文件名与路径换行。采用同一个可滚动正文，保留稳定底栏。入选项完整可核对；未纳入项可
   展开查看各自原因，并可定位回原逐项复核。移动后的来源效果与覆盖、清理分别按实际操作说明。
3. **逐项复核。** 已生成完整方案时，「来源」和「目标」各有标签、上下两行，长路径在各自字段内换行。
   保持现有操作、附件、选择、逐项修正和保存后重新分析规则。无完整路径时沿用真实等待或阻断状态。

复用 `ManualOrganizeDialog`、现有弹窗壳、数据模型和确认逻辑，样式限整理弹窗。资源库入口和任务中心
的「继续整理」使用同一呈现。Task 范围止于这三个既有步骤及队列错误初值的修正。Task Center 详情、
四类恢复工作区、方案有效性和选择资格裁决，以及执行、权限、存储、数据迁移均在范围外。

### 验收

- [ ] 新准入及既有旧 `0` 记录的正常等待界面没有失败提示，也不提前显示正在检查或遍历完成。单选、
  多选、目录范围可核对；实际阶段与计数和同一次准备一致。读失败和真实失败可辨，下一步可用；101 个
  主文件的范围上限仍按现有规则结束并提示缩小选择。
- [ ] 1 项、10 项和 100 项场景在桌面、390px 及短视口清楚显示批量摘要和对齐清单。长中文或长英文
  文件名与深路径可读，首屏能看到实际影响与未纳入数量，确认受阻时按钮旁能读到原因。整批清单只有
  一处正文滚动，无横向溢出；可用键盘展开详情并返回准确文件。
- [ ] 逐项复核上的来源、目标分行且完整可辨。返回、关闭、继续整理与同一准备的后端轮询保持既有行为；
  逐项草稿、纳入状态和已选子集可核对，浏览与展开均无执行请求。
- [ ] 有效方案只确认所选且可执行的条目，未就绪、暂不纳入、已受理和历史不确定项均按原规则处理。
  失效方案、未取得危险效果授权时按钮保持不可提交；正常确认只发一条精确请求并打开准确任务详情。
  确认响应丢失时仍核对原请求，兄弟项重新分析后的新摘要不替换原请求。

### 测试分工

**Developer** 扩展直接受影响的 API 和弹窗测试，覆盖正常排队、旧哨兵／真实失败、阶段反馈、批量摘要与
逐项路径。复用隔离浏览器夹具验证长路径及混合状态的实际布局。回归用例更新可见文案断言，保留业务断言。

在仓库根目录运行以下检查。

```sh
python3 scripts/check_governance.py
.venv/bin/python -m unittest discover -s tests -p 'test_media_discovery.py'
.venv/bin/ruff check mediaflow/application/media_discovery.py tests/test_media_discovery.py
.venv/bin/ruff format --check mediaflow/application/media_discovery.py tests/test_media_discovery.py
git diff --check
```

在 `web/` 目录运行以下检查。

```sh
npm run test -- run src/features/operations/ManualOrganizeDialog.test.tsx src/entities/operations/discovery.test.ts
npm run typecheck
npm run lint
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts -g 'manual organize readability'
```

**B** 独立审查完整 Base..候选。运行上述非浏览器检查，并在 `web/` 使用候选产品构建运行完整弹窗原生组
`npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts`。
在该组以 `manual organize readability` 标记新增复现，保存桌面、390px、短视口同屏证据，并核对 Files
及任务中心继续入口。按实际键盘、滚动、读失败、危险授权与提交结果验收，明确区分有效的混合子集与失效
方案。T3 覆盖准入状态数据到 Web 的链路、现有同弹窗确认与交接；此方案只修初值、既有读取解释和呈现。

Developer 交接记录候选 SHA 与受影响检查结果。B 记录实际验收及 PASS / FIX REQUIRED，PASS 后恢复
`NO ACTIVE IMPLEMENTATION TASK` 通知。未开始实施。
