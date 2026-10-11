# Slice 44 文件夹整理完整旅程审查 — A

日期：2026-10-11。角色：A — Slice Owner / Architect / Final Reviewer。
Reviewed Range：`853973dbbf8289fa2ad40657033e94e870a690e4..7e2ab801eaef25b083640813375a49f536ae202f`。
工作区起点：`d76103797dea6d827d3275c30dd98a01b9ca3d0e`，相对于 Implementation Head 仅有审查/交接文档变化。

**结论：FIX REQUIRED，共 8 组已证实的 P1；A44-6/A44-7 扩充关联复现，A44-8 至 A44-13 为本轮补充。**
本轮沿整个 RO-6 旅程集中审查，没有在发现首个 blocker 后停止检查。每组按业务缺口归并，
不把同一问题的不同复现拆成新 Slice。没有改变 Contract、Base、Implementation Head、100 个
主媒体上限或 Deferred，没有实现产品代码、创建 Task、关闭 Slice 或选择下一 Slice。

## 集中缺陷清单

| ID / 严重程度 | 用户能遇到的情况 | 已复现事实 | 最小修正方向 |
|---|---|---|---|
| A44-6 / P1 | 重复提交或网络响应丢失后，重复创建或恢复到另一次申请 | 并发同 scope/pin 产生两条记录；交换两个目录顺序也产生两条；原工作掉出最近 50 条后重提又创建；真实 Web 丢失响应后选择了另一个 pin、另一个根下的 discovery | 持久化层原子去重并正确规范化集合身份；恢复可靠关联实际申请，保留 actor/library/Storage/scope/pin 隔离；不能靠最近列表或路径字符串猜测 |
| A44-7 / P1 | 排除、稳定性配置未生效，直接选子目录又绕过策略 | 生产加载器不读取自定义过滤/稳定性；配置 maxDepth=1 时从父目录排除的深层文件，直接选择其目录便成为主来源；已有 DIRECTORY 排除规则也可被直接选择绕过 | 接通受支持的 Web/API 配置、验证、原子发布和 exact-pin Worker 消费；对全部入口统一执行资源库根下的过滤/深度语义 |
| A44-8 / P1 | 等待文件稳定时反复扫描，别的工作难以推进，等待最终变成预算拒绝 | 同一等待项连续被领取，另一 discovery 保持 queued；常驻循环的短路分支不调用后续 manual/transfer runner；100 文件等待 60 秒的案例，时钟尚未到观察时间，100 次领取已耗尽 10000 条预算 | 以持久化的适当观察时机推进等待项、让其他工作获得领取机会；等待不能忙循环或把重复无效观察变成正常稳定流程的永久拒绝；保留真实间隔、累计边界和 fencing |
| A44-9 / P1 | 合法长路径打不开发现页；普通长文件名使整个发现永久排队 | 1222 字符真实 Local 路径 API 返回 200/completed，真实 Web 持续显示“无法读取发现状态”；179 字符 Local 文件名触发 ManualSourceIdentity 的 128 字符限制，两次实际 Worker 领取均返回 None，状态仍 queued、failure=null | 对齐实际支持的路径/文件名范围以及所有 API、Web、身份构建边界；保留精确名称；个别条目错误必须持久化、可诊断并隔离，不能吞掉异常后无限重领整批 |
| A44-10 / P1 | 混合选择中一个文件无法读取，页面仍声称完整发现 | 选 Gone.mkv + Good/ 后前者消失，或选 Denied.mkv + Good/ 后前者 stat 被拒绝：status=completed、errorEntries=1、incomplete=false；Finalize 201，只冻结正常来源 | 把文件观察失败和目录读取失败一致纳入真实部分发现、独立错误及明确子集复核；不能把未知来源悄悄变成“完整范围已发现” |
| A44-11 / P1 | 单个分页目录被错误判为打开太多目录 | 真实 managed OpenList HTTP/Worker，只请求一个目录；1000 次分页被计为 1000 个目录，第 1001 页前因 directory_limit 停止；只有一个去重主来源，条目、分页和时间均未超各自上限 | 独立计算目录、页、条目消耗；按正确持久化单位和实际待处理范围判定边界，不放宽安全上限、不允许可执行截断前缀 |
| A44-12 / P1 | Trailer 被当作第二部电影；普通电影目录误超主媒体上限 | 实际发布并启用附件策略后，One.2001-trailer.mp4 既被既有 AttachmentDiscovery 识别为主片附件，又成为冻结 intent 的独立主来源；51 部主片 + 51 个对应 Trailer 被拒绝为 primary_limit | 在 folder-to-intent 交接保留既有主文件/附件语义，主媒体只计一次；预告片不能因视频扩展名而获得第二份独立主媒体身份；复用已有关联规则，不新建匹配引擎 |
| A44-13 / P1 | 不服务文件夹发现的 Worker 被显示为可用，申请一直排队 | 实际注册 live、schema=45、commands=(scan,) 的 Worker，discovery API 投影 worker.ready=true；同一 WorkerService 的 media_discovery command-readiness 则明确 false | 从真实发现命令能力与兼容性投影 readiness，区分缺失/过期/不支持 Worker 并给出有效恢复动作；不影响已有 manual/transfer readiness |

这 8 组均对应当前 RO-6 或它明确要求的安全/用户结果，未增加新的产品能力。
A44-8 的非零稳定性用例、A44-7 的 DIRECTORY 规则用例明确使用领域策略注入：生产配置通路
目前被 A44-7 阻断。它们证明已有 Worker/策略实现仍存在缺陷，不能把“接好配置”当作完整修复。
其余 managed 深度、长路径/长文件名、读取失败、分页、附件、readiness 与原子提交用例不依赖
注入过滤/稳定性对象。readiness 注册与单文件权限失败分别使用实际仓储注册和受控 Storage
错误；没有更改产品返回值来伪造缺陷。

## 各组证据与验收关联

### A44-6 — Admission 与未知响应恢复

关联 RO-6、Acceptance 30/31，actor/scope/pin 和配置根隔离。

- 原并发复现保留在 `a-final-review3/admission-probe-receipts.json`：同一 actor/library/scope/pin，
  两个 HTTP 202、两个 UUID、两条 queued 记录。协调仅放在原仓储 insert 前，产品行为未更改。
- `boundary-receipts.json` 的 `scopeOrderDuplicates`：`[A,B]` 与 `[B,A]` 创建两份工作。
  `deduplicate_scope` 保留提交顺序，`discovery_scope_signature` 直接序列化顺序。
- `admissionWindowEviction`：原申请仍 queued，后来 50 次其他范围申请使它掉出最近窗口，
  再提交原范围又创建新记录。仅扩大列表窗口不能提供持久化唯一性。
- `native-negative-receipts.json/wrongPinRecovery`：真实浏览器 POST 已成功持久化，故意丢掉
  响应；随后实际导入/验证/激活新 revision，把资源库 root 改为 `new-root`，另一次同路径申请
  在该 pin 下合法创建。Files 自动读取最近列表并进入后者，未恢复最初申请。
  `native-negative-durable-receipt.json` 证明两个 discovery 的 snapshot ID 不同，execution Tasks=0。
- 代码：`media_discovery.py:233`、`:293`；`media_discovery.py` 对应仓储插入在
  `sqlite_runtime.py:9953`；`domain/media_discovery.py:167`、`:782`；
  `StorageFilesPage.tsx:1946` 使用排序后 newline 拼接路径匹配，未证明实际 admission/pin 身份。

恢复须同时覆盖并发、顺序/重叠规范化、历史量、响应丢失和同时发生的新激活。
终态后的明确 successor 仍合法，不同 actor/library/Storage/scope/pin 不能合并；普通读取不授予执行权。

### A44-7 — 配置与全部选择入口的策略一致性

关联 RO-6、Acceptance 28/30，真实 Active 与运行时一致性。

- 原真实导入/验证/激活/加载证据保留在 `a-final-review3/managed-policy-receipt.json`；
  不把探针字段名当成预定 schema。当前缺的是受支持配置通路，不是要求接受任意未知 JSON 键。
- `boundary-receipts.json/configuredDepthBypass` 使用实际 production loader：`maxDepth=1`。
  选择 `Movies` 排除 `Movies/Sub/Two.mkv`；选择 `Movies/Sub` 却以 completed 接受它。
- `directExcludedDirectory`：已有 DIRECTORY 排除规则在遍历父目录时生效，直接选择被排除目录
  时未执行相同策略。此规则用例明确注入领域对象，因为生产映射尚缺。
- 代码：`runtime_configuration.py:332`；`configuration_objects.py:338`；
  `media_discovery.py:218`、`:1088`、`:1113`、`:1545`。

补齐配置时须保留 legacy 默认/不暴露字段、无效输入恢复、原子 Active 保持，以及发布/重启/
新旧 pin 隔离。入口选择方式不能改变同一个资源库文件的既定策略适用范围。

### A44-8 — 稳定等待的调度与预算

关联 RO-6、Acceptance 28/29/30，以及批次/工作独立性。

- `boundary-receipts.json/waitingStarvation`：12 次实际 MediaDiscoveryWorker 领取同一旧等待项；
  第二项一直 queued。随后按实际 AutomationWorker 的 resident 分支组合运行 4 次，后续
  manual/transfer runner spy 调用数为 0。没有伪造发现领取或仓储结果。
- `waitingConsumesBudget`：100 个文件需 60 秒稳定大小，冻结受控时钟用于模拟尚未到期的快速
  领取；实测 100 次领取、约 3.507 秒，状态永久 partial_success/entry_limit、visitedEntries=10000。
  不把受控时钟用例说成已经完成真实 60 秒生产等待；它证明领取缺少 due-time 门控和等待预算处理。
- 代码：`sqlite_runtime.py:10128` 按 created_at 领取 waiting_stability，release 后立即可再领；
  `media_discovery.py:1241`；`automation.py:886`、`:902`；`final_cli.py:4048`。

修复须使真实非零等待可完成，同时保留正常工作公平推进、持久化观察、restart、controls 和
累计安全边界。不能靠清零计数、虚构稳定时间、静默冻结前 N 项或增加新队列解决。

### A44-9 — 名称/路径的跨层兼容与错误隔离

关联 RO-6、Acceptance 27/29/30、Required native Web/API surface，精确名称与恢复。

- `native-negative-receipts.json/longPathNativeFailure`：六段合法 Local 目录构成 1222 字符路径，
  每个 basename 在 Local 限制内、总路径小于 4096、深度小于 32。API 为 200/completed，
  production-built Web 的正常认证旅程显示“无法读取发现状态 / 请刷新后重试”，无法读取清单。
- `boundary-receipts.json/longPath` 还保存实际 discovery list payload；同一前端 normalizer
  会因该条目的长 finding/source 拒绝整份发现列表。
- `failure-isolation-receipts.json/legalLongFilenameStrandsBatch`：一个 179 字符普通 Local
  文件名与一个正常文件在同一目录；Worker 报 bounded ValueError notice，未持久化失败，
  lease 过期后第二次领取再次失败。durable attempts=2，仍 queued/failure=null，整个批次未推进。
- 代码：`entities/operations/discovery.ts:17`、`:295`、`:340` 把路径限制为 1024；
  `domain/manual_organize.py:268` 把 filename 和 ID 共用 128 字符限制；
  `media_discovery.py:973`、`:1385`；`media_discovery_worker.py:85` 仅 notice 后返回 None。

不得截断、trim 或改写真实名字以掩盖问题；支持范围需要跨各层一致，真实拒绝必须有独立、
有界、持久化原因及有效下一动作，并保留其他条目结果。

### A44-10 — 文件读取失败的真实部分状态

关联 RO-6、Acceptance 29/31，已知子集显式复核与失败恢复。

`boundary-receipts.json/missingExplicitFileFalseComplete` 和
`failure-isolation-receipts.json/permissionDeniedFileFalseComplete` 保存完整 authenticated API
readback 与 Finalize 结果。一个来源消失或未知/权限拒绝后，正常目录仍有一个主来源；
API errorEntries=1，但 incomplete=false、status=completed，消息宣称 whole admitted scope 完成。
冻结请求返回 201 且仅有一个 intent item。没有声称丢失文件被执行或发生媒体删除。

代码 `media_discovery.py:871` 的文件观察错误只加计数并 return，未设置 degraded/incomplete；
目录读取错误在 `:1045` 会设置 partial_success/read_failure。需要统一业务事实而保留每项独立性。

### A44-11 — 分页、目录和精确边界

关联 RO-6、Acceptance 29，Storage paging 与具体上限的真实含义。

`boundary-receipts.json/paginatedDirectoryCounting` 使用实际配置发布、production OpenList
HTTP adapter、本地 loopback server 和真实 Worker；未替换 `Storage.list_page`。
该服务器每页重复同一个合法媒体 basename，符合本 Slice 已接受的非原子重复页兼容场景。
去重来源始终为 1，共有 1001 页，maxPageFetches=2000、maxVisitedEntries=10000、
maxVisitedDirectories=1000。只访问一个不同目录，却在完成第 1000 页后记录 directory_limit。

代码 `media_discovery.py:1063` 每页加 visited_directories，`:1013` 用该值拒绝下一步。
附加的精确边界用例见下面 P2；不得用提高上限或允许截断前缀掩盖计数单位问题。

### A44-12 — 主媒体与 Trailer 附件重叠

关联 RO-6、Acceptance 27/28/29/31，既有附件关联和主媒体计数。

- `attachment-boundary-receipts.json/trailerAdmittedAsPrimary` 使用实际发布的启用附件策略、
  production runtime loader、真实 Local/SQLite/API；没有过滤/稳定性注入。
  既有 `AttachmentDiscovery` 将 `One.2001-trailer.mp4` 关联为 Trailer；冻结 intent 却把它
  与 `One.2001.mkv` 一起列为两个主 item。
- `trailer-bound-receipt.json`：51 部主片及其 51 个对应 Trailer，实际主媒体小于 100，
  仍被当作 102 个候选，在 primary_limit 下停为不可冻结的 100 项前缀。
- 代码 `media_discovery.py:916`、`:972` 仅按视频扩展名/过滤做主来源；
  `attachments.py:107` 已有 Trailer 关联语义。

证据只证明错误独立主身份和错误限额，未声称 Executor 已经重复移动文件。修复保留原路径、
字幕语言后缀、NFO/图片/Trailer/conflict/policy 行为；不扩建一般 Extras 关键词系统。

### A44-13 — Worker 命令能力的真实可用性

关联 RO-6、Acceptance 30、Final Validation Expectations 的 unsupported-command Worker 状态。

`boundary-receipts.json/unsupportedWorkerFalseReady` 保存实际 SQLite Worker 注册和两种
readiness 结果。同一 live、当前 schema Worker 仅支持 scan，API discovery.worker.ready=true；
`evaluate_command_readiness((media_discovery,))` 为 false/unsupported_command。

代码 `service_api.py:12488` 调用 manual-organize readiness；`automation.py:391` 检查 live/schema，
未检查发现命令。需要以实际命令能力解释 queued 的原因与恢复，而不是只显示进程存活。

## 非阻塞项与边界

- P2：`attachment-boundary-receipts.json` 的精确 entry/directory/page budget=1 用例在工作
  已完成、没有下一页时仍被判超限。属于边界质量问题，可与 A44-11 一并考虑，不能单独阻止 PASS。
- P2：安全深度注释声明相对所选目录，实际按资源库绝对深度；直接选择 32 段目录后，仅一层
  子目录就拒绝。证据 `safetyDepthAbsolute`；真实定义/说明需要一致，保持安全上限。
- 已知 P2：queued/paused 文案把未完成遍历显示为完整、concurrent-Save 可选断言、Move summary copy。
  这些不作为本轮 P1 判定理由。
- 没有以未知 P0、安全恐吓、未来 Provider/Extras/大目录自动拆分、一般配置重设计或其他 Deferred
  作为 blocker。所有探针仅使用合成临时媒体/本地服务。新负面探针的 Storage content/mutation=0、
  execution Tasks=0；正常端到端 proof 的一次移动只发生在它自己的临时根并经明确确认。

## 旅程覆盖与实际验证

| 旅程环节 | 本轮检查/证据 | 当前结论 |
|---|---|---|
| List/grid、目录/文件/混合选择、Operations 入口/返回 | 真实 Python + production-built native proof；53 项相关 Web 测试 | 正常受测旅程通过；A44-9 的长名称路径例外 |
| Scope 去重、未知响应、新旧 Active/root | 原并发 receipt + scope 顺序/历史窗口 probes + 实际浏览器丢响应/新发布 | A44-6 未满足 |
| 扩展名、临时文件、Include/Exclude、深度、稳定性 | 生产 loader 原证据、真实 managed 深度、领域策略明确标注的控制时钟 probes | A44-7/A44-8 未满足 |
| Paging、100/101、entry/directory/page/depth/time、cyclic cursor、恶意路径/link | 127 项 focused Python、native limit proof、真实 OpenList 1001 页、精确边界 probes | 原拒绝/fencing 场景保持；A44-11 未满足；P2 独立标注 |
| 丢失/权限拒绝/子树失败、已知子集、解释与恢复 | 单文件缺失/权限失败实际 API、长名 lease/restart、既有子树失败测试 | A44-9/A44-10 未满足 |
| Worker 状态、稳定等待、pause/Continue/cancel、lease/restart、旧 owner | 当前 127 项 focused Python + native acknowledged Continue；实际命令 readiness/领取 probes | 先前 control/ownership 修正保持；A44-8/A44-13 未满足 |
| Frozen manifest、并发 Finalize、原路径、C→A、附件、Preview | 当前 focused Python、native exact Preview；附件重叠与主媒体限额 probes | 原原子 Finalize/C/manifest 场景通过；A44-12 未满足 |
| 确认、权限/能力/冲突、来源变化、结果、partial/uncertain、index-sync/non-replay | unchanged exact-execution 模块的 focused 回归 + native 一次确切 Move 与不重放；既有 T4 evidence | 受测执行门保持；不从 discovery/读请求推导执行权 |

实际结果：

- 本轮 focused Python：**PASS**，127 tests，22.215 秒，0 failure/error/skip。
  命令：`.venv/bin/python -m unittest tests.test_media_discovery tests.test_media_discovery_provider_manifest tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution`。
- 本轮 focused Web：**PASS**，3 files / 53 tests，35.03 秒；包括 discovery normalizer、Discovery
  page 和 StorageFilesPage。命令：`npm run test -- --run src/entities/operations/discovery.test.ts src/features/operations/OrganizeDiscoveryPage.test.tsx src/features/library/StorageFilesPage.test.tsx`，cwd=`web`。
- 本轮正向 native browser proof：**PASS**，11 browser cases，4 类选择、pause/Continue、限额、
  readback、一次经确认的真实 temporary Local Move 及 non-replay；截图和 API/Worker 记录保留。
- 本轮补充负面 probes：20 个已复现情形，归入上面 8 个 P1 和独立 P2，详见 JSON receipts；
  **REPRODUCED** 表示缺陷被证实，不能记作产品 PASS。
- 上一轮对同一 executable candidate 的全量 Python：**PASS**，2384 tests、7 skipped、420.213 秒。
  本轮重核 625 个 B-indexed inputs（排除审查/交接文件）、178 个 B artifacts，均无 mismatch。
  source/tests/configuration/dependencies/既有 built Web 未改变，不重复制造新的全量记录。
- 全量 Web/E2E/Docker/wheel/migration/security：沿用已核对的同候选 B 原始 evidence；本轮未再次
  独立运行，**NOT RUN**。7 个真实外部服务/耐久 profiles 的 SKIP/UNAVAILABLE 保持，未变成 PASS。
- 负面 native harness 的 import/activation 参数遗漏和 reload 后未重新认证的首轮失败原日志均保留；
  修正的只是本地 probe harness，不改产品、不放宽断言、不删除原错误证据。

本地 evidence root：
`.git/validation-evidence/7e2ab801eaef25b083640813375a49f536ae202f/a-folder-sweep/`。
原两项及之前修正复验仍在 sibling `a-final-review3/`；原 B/Developer 记录保持完整。
Evidence index 记录命令、实际 exits、候选/构建/probe/artifact hashes、首失败与复用范围；未推送。

## 交接

SLICE.md 的 current A Final Review 是决定权威；本文件提供集中复现、严重程度、覆盖和最小修正方向。
TASK.md 保持 NO ACTIVE IMPLEMENTATION TASK；B 根据整份清单规划聚焦 correction 并完成自己的
实施/复验循环，之后提交更新的 Closure Packet，A 审查新的完整 Base..Implementation Head。

原治理脚本仍拒绝工作流规定的 `FIX REQUIRED + NO ACTIVE IMPLEMENTATION TASK`；实际 FAIL
单独记录，不能冒充产品 blocker、制造 Task 或把状态改为 ACTIVE 来隐藏矛盾。未更新 Roadmap/
Progress/CURRENT 为已关闭；没有 Closure Reconciliation。

NEXT ACTION: B PLANS ONE FOCUSED CORRECTION TASK
