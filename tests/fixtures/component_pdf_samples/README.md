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

1. 使用正式项目 PyCharm 配置入口或 worktree 调试环境在本地复现问题，输入路径可以指向 `md2word_main/mineru_result/`。
2. 添加最小化 MinerU 结果包：

   ```bash
   .venv/bin/python scripts/dev/manage_component_pdf_samples.py \
     add-mineru-sample \
     --sample-id ti-opamp-opa228-p1-smoke \
     --brand texas-instruments \
     --category op-amp \
     --product OPA228 \
     --title "OPA228 第 1 页排版烟测" \
     --source-pdf "md2word_main:test_pdf/OPA228_P1.pdf" \
     --mineru-package /path/to/mineru_result/OPA228_P1.pdf-uuid \
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

5. 使用 `acceptance-record-template.md` 记录人工验收结果，并将生成的 DOCX/报告保存在 `tests/tmp/` 或外部证据存储中。
