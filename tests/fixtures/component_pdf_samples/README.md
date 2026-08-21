# 电子元器件 PDF 样例

这个目录按品牌和元器件分类沉淀电子元器件 PDF 回归样例。它用于本地转换能力加固和反复排版回归，不替代 P0 Golden Sample 发布门禁。

## 目录形态

```text
tests/fixtures/component_pdf_samples/
  manifest.yaml
  acceptance-record-template.md
  samples/
    <brand>/
      <category>/
        <sample-id>/
          mineru/
            *_content_list_v2.json
            images/
```

`brand`、`category` 和 `sample-id` 使用小写 kebab-case。仓库内只提交小型、最小化的 MinerU 结果包或公开样例。专有 PDF 和大型输出文件应保留在仓库外，并通过 manifest 引用。

## 本地闭环

1. 使用正式项目 PyCharm 配置入口或 worktree 调试环境在本地复现问题，输入路径优先指向正式项目根目录的 `mineru_result/`。
2. 添加最小化 MinerU 结果包：

   ```bash
   .venv/bin/python scripts/dev/manage_component_pdf_samples.py \
     add-mineru-sample \
     --sample-id ti-opamp-opa228-p1-smoke \
     --brand texas-instruments \
     --category op-amp \
     --product OPA228 \
     --title "OPA228 第 1 页排版烟测" \
     --source-pdf "local:mineru_result/OPA228_P1.pdf-uuid/<origin>.pdf" \
     --mineru-package mineru_result/OPA228_P1.pdf-uuid \
     --tag datasheet \
     --tag op_amp \
     --acceptance-focus "标题和第一段保持可读" \
     --apply
   ```

3. 只在 `app/conversion` 中修复转换行为。
4. 运行电子元器件样例回归：

   ```bash
   .venv/bin/python scripts/dev/run_component_pdf_regression.py
   ```

5. runner 会在批次目录生成 `manual-signoff-template.yaml`。复制为 `manual-signoff.yaml`，使用 Word 或 WPS 完成整文档检查并填写实际页数、空白页、关键内容组落页、表格挤压、栏平衡、图片清晰度和字体替换结论。LibreOffice 只能作为辅助证据。
6. 将签字应用到同一批次；脚本会校验源码 commit/dirty 状态和 DOCX SHA-256，旧批次签字不能跨版本或跨产物复用：

   ```bash
   .venv/bin/python scripts/dev/run_component_pdf_regression.py \
     --apply-manual-signoff tests/tmp/component_pdf_regression/<run_id>
   ```

`report.json` 中的自动回归 `summary.ok` 与 `manual_visual_acceptance` 分开记录：客户端视觉结论不会被伪装成确定性 OOXML blocker。生成的 DOCX、报告和签字保存在 `tests/tmp/` 或外部证据存储中，不提交客户 PDF 或大型产物。
