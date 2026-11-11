---
doc_status: active
last_verified_commit: null
owner: null
verification_scope: >-
  全文说明/空白模板用途与相应 runner 参数、样本清单的局部静态核对；未运行回归、填验收或签字。输入身份见 ../../../.trellis/tasks/archive/2026-11/11-10-documentation-evidence-governance/research/b3-preparation.md。
---

# 电子元器件 PDF 样例

本页维护本地组件 PDF 样例的组织与记录方法，不代表本批回归通过。原“只在 app/conversion 修复”的职责提示应结合 [现行组件治理说明](../../../docs/dev/component-pdf-regression-governance.md) 阅读，正式转换规则归属 DocumentIR、renderer 与共享 DOCX 规则；本批不改原步骤或执行命令。

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

5. 使用 `acceptance-record-template.md` 记录人工验收结果，并将生成的 DOCX/报告保存在 `tests/tmp/` 或外部证据存储中。
