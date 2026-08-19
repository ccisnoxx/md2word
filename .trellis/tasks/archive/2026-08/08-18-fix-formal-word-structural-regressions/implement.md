# 实施计划：正式 Word 链路结构性回退

## 1. 开发前与基线

1. 读取本任务 `prd.md`、`design.md`、本文件、`research/current-chain-audit.md` 及 implement manifest 中全部规范。
2. 确认工作区只包含本任务规划文件；不得覆盖用户或其他任务改动。
3. 先运行当前正式 converter、renderer、formal adapter 和相关 document job 定向测试，记录基线；失败时区分当前改动与既有问题。
4. 在改产品代码前更新 `.trellis/spec/backend/word-generation-rules.md` 的目标规则和冲突矩阵，使 R1–R4 的唯一 owner、失败策略和 v1/v2 兼容边界可审查。

## 2. 测试先行：四个根因

1. 在 `tests/test_document_ir_mineru_converter_layout.py` 增加真实 v2 nested chart 形状：`content.image_source.path`、rich `chart_caption`、inline equation、footnote；先证明当前降级，再锁定 image/asset/inventory 合同。
2. 在 `tests/test_document_ir_word_renderer_layout.py` 增加：
   - v2 图注/“图 13 显示了……”保持普通段落；
   - 显式 v2 heading、v1 heading-like、v2 bullet/TOC 保持；
   - “左右文字 + 单侧栏尾 + paired images”仅一组普通双栏 section；
   - 真实文字双栏 gap 和 wide block 不被归并；
   - source/IR/layout/DOCX expected/actual 与 blocking flags。
3. 在 `tests/test_conversion_sandbox_dev_tools.py` 增加 formal adapter 失败关闭测试：阻断时不发布目标 DOCX；成功时 evidence 包含完整性计数。
4. 在 `tests/test_fastapi_jobs_backend.py` 增加两个最小 workflow 回归：source→IR gate 得到 `document_ir_failed`，IR→DOCX gate 得到 `render_failed`，均不登记成功 Word 文件。

## 3. R1：chart 与 source inventory

1. 在 `DocumentIRMetadata` 增加向后兼容的 source inventory 字段。
2. 在 converter 的允许过滤/归一化后计算 inventory；把 `chart` 明确映射为 `image`，复用现有 asset/caption/footnote/reassociation 路径。
3. 新增 `app/services/document_ir/integrity.py`，实现最小 source→IR evidence、blocking flags、`DocumentIntegrityError` 和 fail-closed 入口。
4. converter 返回结果前执行 source gate；不得让 missing chart asset 或声明结构降级继续进入 renderer。
5. 运行 converter/IR contract 定向测试。

## 4. R2：v2 显式标题语义

1. 收紧共享 heading 规则，排除编号图/表 caption/reference；同步 DOCX analyzer 使用共享结论。
2. 在单次 `_RenderContext` 记录 v1 才允许 heading inference；v2 paragraph 保留 TOC/list 入口但不再升级 heading。
3. 更新或拆分现有 `test_render_to_bytes_promotes_heading_like_paragraphs_to_word_headings`，明确它只保护 v1；新增 v2 反例。
4. 运行共享 text characterization 与 renderer 文本/TOC/list/field/formula 定向测试。

## 5. R3：双栏区域收敛

1. 在 `layout_plan.py` 对初始 regions 做单侧栏尾的窄后处理；不修改 bbox 分类阈值，不在 renderer 复制检测。
2. 保留 `word_renderer.py` 的一次 native columns 和现有 paired-image tabs；仅在需要传递明确 region 语义时做最小修改。
3. 验证 native column、wide restore、single-column gap、paired image order、semantic page break 和 orientation 共同回归。

## 6. R4：IR→layout/DOCX evidence 与失败关闭

1. 扩展 `docx_quality.py` 的确定性 OOXML 计数时只增加本任务需要的字段；不加入页数/像素推断。
2. 扩展 `renderer/evidence.py`：计算 body block、image drawing、table、v2 heading expected/actual，生成 `blocking_quality_flags`；保持现有 `quality_flags` 非阻断含义。
3. formal adapter 先构造 evidence、执行 gate，再写最终 DOCX。
4. document job 在进入 uploading 前执行同一 renderer gate；沿用当前 stage/error 分类和失败事件。
5. 运行 evidence、formal adapter、document job 定向测试，确认失败时没有成功文件/event。

## 7. R6：富文本题注逻辑分组

1. 修改 converter 的 caption value-level 归一化：flat rich-node list 合成一条 caption；string list 和多个 nested rich groups 保持多条。复用现有文本/公式归一化与片段拼接，不修改全局 `collect_text_from_fields()`。
2. 更新真实 v2 nested chart 测试，删除把 inline node 固化成多条 caption 的错误断言；新增多逻辑 caption、table caption/context 和严格图片对冲突负例。
3. 增加 OOXML 断言：图号/SEQ、正文、`±18V)` 在同一个题注段落，不出现只含公式碎片的独立 `w:p`。
4. 不修改 image/table renderer 的“一 caption 元素一段落”合同，不修改 section、page break 或 DocumentIR schema。

## 8. R7：正式本地入口默认资源与字体配置

1. 在 formal local adapter 的 request 构造边界复用 `Settings`：显式 template/config 优先；省略时使用当前默认 template/v2 config；`no_template=True` 只清空 template，不清空 config。
2. 不修改 renderer 的 `load(None)` 语义，不让线上 Template Version 路径回退 bundled 配置，不改已发布 v2 YAML 字节。
3. 在 conversion sandbox 增加最小入口测试，证明省略参数时可见 Word 文本写入 `宋体/Arial/Arial/Times New Roman` 四槽，显式路径与 `no_template` 行为不变。
4. OOXML 字体对账只覆盖有可见 `w:t`/field result 的 Word run；图片、tab、field 控制 run 和 OMML 不误报。公式继续记录独立 `m:mathFont` 与客户端缺字体风险。

## 9. 集成与真样本验证

1. 使用正式入口生成独立候选，禁止覆盖用户原文件：

   ```bash
   .venv/bin/python scripts/dev/run_local_mineru_conversion.py \
     '/Users/sc/Downloads/mineru_raw_result 2' \
     --output /tmp/md2word-cm4112-structural-fix/cm4112-fixed.docx \
     --translation-mode direct
   ```

2. 核对 IR/source inventory、layout plan 与 DOCX：21 个 source pages；38 chart + 15 image → 53 image blocks/drawings；8 tables；显式 heading 数一致；blocking flags 为空；chart 不在 unsupported flags。
3. LibreOffice 26.2.4.2 转 PDF/PNG，逐页检查首页、图表页、工作原理、表格页、空白页和总页数变化并解释。
4. 使用本机 WPS 打开候选并复核首页栏流、图表可见性、栏平衡、工作原理起页、表格、图 33 前后页和请求字体/缺失字体状态；记录 WPS 版本、候选 hash 和结论。未实际观察不得写通过。
5. 若真样本失败，回到对应通用 owner 和最小测试，不增加型号/文字特例。

## 10. 最终质量门禁

按由小到大的顺序执行，避免重复跑完整门禁发现单点问题：

```bash
.venv/bin/python -m unittest tests.test_document_ir_mineru_converter_layout
.venv/bin/python -m unittest tests.test_document_ir_layout_contract
.venv/bin/python -m unittest tests.test_document_ir_word_renderer_layout
.venv/bin/python -m unittest tests.test_text_render_characterization
.venv/bin/python -m unittest tests.test_conversion_sandbox_dev_tools
.venv/bin/python -m unittest <新增的 FastAPI 定向测试方法>
.venv/bin/python -m compileall app scripts tests
git diff --check
.venv/bin/python scripts/ops/check_release.py
```

最终 review 必须检查：

- 没有第二套 chart/image parser 或 heading heuristic；
- blocking 与 non-blocking flags 没有混用；
- v1 兼容没有泄漏到 v2；
- layout tail 归并没有吞 wide/真实 gap；
- 本地/线上失败边界都在写入或上传最终 DOCX 之前；
- 一条 rich caption 不再成为多个 IR captions/Word 段落，真实多题注仍保持独立；
- formal local 默认资源只在入口解析一次，renderer 与线上版本 owner 没有 hidden fallback；
- 字体断言区分可见 Word run、OMML 数学字体和客户端字体安装状态；
- 新增/修改的 Python 注释、docstring、错误消息和开发者可见输出符合项目中文约定。

## 11. 回滚点与完成条件

- source gate、语义 gate、layout merge、renderer gate 分别保持可定位 diff；任何失败不得通过放松为 warning 规避。
- AC1–AC14 全部有实际证据，相关 spec 状态与回归矩阵已更新，implement/check agent 均通过后才进入提交确认。
- 不在本任务修复 Out of Scope 问题；发现时只记录剩余风险。

## 12. 实施结果（2026-08-19）

- R1：converter 在归一化边界写入 source inventory，`chart` 复用 image/asset 路径；缺失声明 payload 在 source→IR 边界失败关闭。旧 IR 没有 inventory 时仅跳过无法证明的 source 对账。
- R2：v2 paragraph 只保留显式语义，标题文本推断限制在 v1 兼容；图/表题注、列表、目录项和技术公式表达由共享语义 owner 排除。
- R3：layout plan 合并有证据的单侧栏尾，同时保留 wide block、真实单栏 gap 和严格图片对边界；renderer 未新增第二套检测。
- R4：renderer evidence 对账可见 body/layout、drawing、table 和 v2 heading，formal adapter 与 document job 均在发布/上传前执行同一失败关闭。
- 自动验证：116 项任务定向测试通过，`compileall` 和 `git diff --check` 通过；checker 最终运行的 `scripts/ops/check_release.py` 通过（36 个目标组、202 项测试）。首次发布门禁发现 3 个共享标题 analyzer 回归，已在共享语义 owner 修复后重跑通过。
- 真样本：CM4112 为 21 个 source pages、196 个 source/IR blocks、53/53 drawings、8/8 tables、18/18 headings，阻断标记为空。LibreOffice/WPS 完成范围、hash 和未完成边界见 `research/cm4112-validation.md`。
- R6：`_captions()` 在 converter 边界把 flat rich-node list 合并成一条逻辑题注，string list 与多个 nested rich groups 保持独立；renderer、section 与 DocumentIR schema 未改变。图 33 在 IR/OOXML 中成为单条完整题注，SEQ/bookmark、table context 与 COL-003 共同回归通过。
- R7：formal local `run_conversion()` 省略资源时绑定 `Settings.default_template_path/layout_config_path`；显式路径优先，`no_template` 只禁用 DOCX 模板，默认资源缺失显式失败。renderer 的 `load(None)`、线上固化 Template Version 与已发布 seed 字节未改变。
- R6/R7 自动与真样本证据：相关五模块 118 项测试通过；追加实现后的任务上下文校验通过，`scripts/ops/check_release.py` 再次通过（36 个目标组、202 项测试）。新 CM4112 候选保持 196/196 blocks、53/53 drawings、8/8 tables、18/18 headings，`blocking_quality_flags=[]`。666/666 个可见 Word run 写入 `宋体/Arial/Arial/Times New Roman`，OMML 保持独立。LibreOffice 23 页、WPS CLI/GUI 20 页；WPS GUI 第 12 页为图 31～33 三图及完整题注，第 13 页直接以“工作原理”起页，旧 `±/18V)` 碎片稀疏页消失。WPS 仍提示“缺失字体”且 CLI 有替换字符，属于目标系统字体安装边界。AC10 仍因未完成 WPS GUI 全 20 页逐页复核而保持未通过，QUALITY-003 仍为 `planned`。
