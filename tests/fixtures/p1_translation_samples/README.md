# P1 Translation Acceptance Samples

本目录用于 P1 英文 PDF 英译中实验链路和人工质量验收。`manifest.yaml` 维护样本清单，`acceptance-record-template.md` 记录术语命中、结构不变性和人工质量反馈。

当前正式样本集复用已版本化的真实英文 OPA228 datasheet PDF，来源为 `tests/fixtures/golden_samples/pdfs/`。`pdfs/en-datasheet-smoke.pdf` 仅保留为历史 smoke 文件，不属于当前 formal beta gate。

默认执行参数：

```text
mode=en2zh_pdf_to_word
document_language=en
translation term/profile 使用线上当前默认 published 版本
```

验收时应确认：

- AI 调用审计记录只包含 metadata、哈希和脱敏摘要。
- 仅任务请求 `debug_full_text=true` 且配置开启时保存全文调试归档。
- 生成的中文 DocumentIR 保持 block 顺序、block 类型、资产引用和公式内容不变。
- 人工记录术语命中、结构不变性和翻译质量反馈。

线上验证使用独立脚本：

```bash
P1_TRANSLATION_BASE_URL="http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}" \
P1_TRANSLATION_USERNAME=admin \
P1_TRANSLATION_PASSWORD='<admin-password>' \
.venv/bin/python scripts/ops/run_p1_translation_regression.py
```

默认只运行 `source_status=available` 的样本。正式 beta gate 需要 `target_sample_count=3` 个真实英文 datasheet，并设置 `P1_TRANSLATION_FORMAL=1`；脚本输出 `tests/tmp/p1_translation_runs/<run_id>/report.json`、`report.md` 和 `manual-signoff-template.yaml`。admin 填写 `manual-signoff.yaml` 后执行：

```bash
.venv/bin/python scripts/ops/run_p1_translation_regression.py \
  --apply-manual-signoff tests/tmp/p1_translation_runs/<run_id>
```
