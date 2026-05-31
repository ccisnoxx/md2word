# P1 Translation Acceptance Samples

本目录用于 P1 英文 PDF 英译中实验链路和人工质量验收。`manifest.yaml` 维护样本清单，`pdfs/` 放英文 PDF，`acceptance-record-template.md` 记录术语命中、结构不变性和人工质量反馈。

当前仓库内置 1 份合成 smoke PDF，用于验证上传、建任务和调试链路的文件合同；正式质量验收仍需要业务补充 1-3 份真实英文数据手册 PDF。

默认执行参数：

```text
mode=en2zh_pdf_to_word
document_language=en
term_version_id=en2zh@v1
```

验收时应确认：

- AI 调用审计记录只包含 metadata、哈希和脱敏摘要。
- 仅任务请求 `debug_full_text=true` 且配置开启时保存全文调试归档。
- 生成的中文 DocumentIR 保持 block 顺序、block 类型、资产引用和公式内容不变。
- 人工记录术语命中、结构不变性和翻译质量反馈。
