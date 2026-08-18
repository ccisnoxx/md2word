# 实施计划

## 执行顺序

1. **v2 输入优先**
   - 在 `mineru_package.find_content_list()` 增加明确格式优先级。
   - 增加同包 v2/legacy 内容冲突及 legacy-only 回退测试。

2. **页面坐标空间**
   - 在 `layout_signals.build_pages()` 用物理页宽高比等比包络 bbox extent。
   - 增加 `595×841 + 942×879` portrait 回归；保留现有 landscape 与无 layout 用例。

3. **列表换行与 inline 公式保真**
   - 在共享 `mineru_content.py` 增加保守的多行列表拆分规则，并让 v2 `equation_inline` 保留数学边界。
   - 在 `mineru_converter.py` 对 legacy text 与 v2 paragraph_content 复用列表规则，生成 list/list_items。
   - 增加 v2 多条特征、无标记续行及“普通文本 + inline equation + 普通文本”的 IR/renderer 测试。

4. **局部双栏**
   - 收紧 `layout_plan._detect_two_col_bands()`：实际重叠区存在时不再叠加总体稳定区间。
   - 增加“上双栏/中单栏/下双栏”回归；保留现有纯非重叠 stable hint 测试。

5. **语义分页**
   - 先写失败测试，复现同方向页面取消硬分页后：页顶 heading 和带 caption/context 的独立表格组没有 `pageBreakBefore`。
   - 在 `word_renderer.py` 只为这两类源页顶部内容传递分页语义；在现有表格 caption/context 首段落应用同一属性。
   - 断言无 break-only 段落、普通续页不强制分页、方向变化仍为 `NEW_PAGE`、表格重复表头和 `cantSplit` 不变。

6. **公式输入精确提取**
   - 在 `_formula_text()` 优先精确读取 v2 `content.math_content`，禁止递归收集 `math_type`。
   - 增加两个真实形状测试，断言 IR `latex` 不含尾随 `latex`/资产路径。

7. **公式预处理与高频语法矩阵**
   - 在现有 `_OmmlParser` 入口统一做公式内 OCR token compact 与 TeX 包装/空格归一化。
   - 扩充既有结构命令和共享符号映射，覆盖 R7；不增加 parser 层或第三方依赖。
   - 用一组表驱动输入同时覆盖 formula block、正文 inline 与 HTML table cell；保留未知/畸形公式失败用例。
   - 为 CM4112 两式断言 `m:f`、`m:rad`、上下标/平方、`≤`、`Ω`、中文与紧凑标识符，并断言无目标 TeX 残留。

8. **集成复核**
   - 检查 diff，确认没有样本特例、重复入口、静默回退、完整旧页流迁移或模板改动。
   - 用正式本地转换入口重新生成 CM4112 DOCX，确认实际输入为 v2。
   - LibreOffice 转 PDF/PNG，对照源 PDF 检查第一页、表格页、工作原理页及两处公式页。
   - 用既有 SC2167 空白页样本/测试复核没有恢复 break-only 空页。

## 必需验证

定向自动化：

```bash
.venv/bin/python -m unittest \
  tests.test_document_ir_mineru_converter_layout \
  tests.test_document_ir_word_renderer_layout \
  tests.test_text_render_characterization
```

若公式质量断言位于独立既有测试模块，实施时把该模块补入上面的必需命令；不创建只为编排测试的 wrapper。

正式样本：

```bash
.venv/bin/python scripts/dev/run_local_mineru_conversion.py \
  --input '/Users/sc/Downloads/mineru_raw_result 2' \
  --output <temp-dir>/cm4112-fixed.docx

soffice --headless --convert-to pdf --outdir <temp-dir> <temp-dir>/cm4112-fixed.docx
pdftoppm -png -r 150 <temp-dir>/cm4112-fixed.pdf <temp-dir>/word-page
```

运行前按脚本真实 CLI 参数校对命令，不猜测选项名。视觉验收至少比较：

- 源 PDF 与 Word 第一页；
- Word 当前第 3、4 页对应的表格组边界；
- “工作原理”前一页和新页；
- 分式页与总延时公式页。

结构验收至少检查：

```text
页面：portrait、w:pageBreakBefore、无 break-only 页
表格：tblHeader、cantSplit、表格/行数未丢失
公式：m:f、m:rad、m:sSub/m:sSup、目标符号、latex residue
```

## 可选验证

```bash
.venv/bin/python -m unittest \
  tests.test_page_flow_characterization \
  tests.test_page_layout_characterization \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_generated_word_keeps_renderer_ooxml_semantics
```

旧 runtime 测试只用于确认共享文本规则没有意外破坏兼容路径；不把旧 runtime 新增功能作为本任务交付。

完整后端套件不作为默认门禁；本次未改公开合同、数据库或任务状态。若定向检查暴露共享渲染回归，再补对应相关测试，不直接扩成全仓修复。

## 实施前门禁

- `prd.md`、`design.md`、`implement.md` 经用户确认。
- `implement.jsonl` 与 `check.jsonl` 含真实规范和两份研究上下文。
- 当前主工作区不在干净 `main` 且有大量无关改动；开始产品代码编辑前必须确认可安全实施的位置，禁止切分支、清理或覆盖用户改动。

## 提交与回滚

- 完成验证后先向用户展示提交范围并请求确认；不自动提交或推送。
- 各步骤按现有模块边界独立，可按单文件/单测试回退；不得使用 `git reset --hard` 或 `git checkout --`。
