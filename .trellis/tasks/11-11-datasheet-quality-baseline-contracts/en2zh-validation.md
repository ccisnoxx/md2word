# 英译中首轮实测与缺测项

日期：2026-11-11。代码基线为 `26dbfb20`。本轮将真实 PDF 任务与真实翻译回放分开记录。原始 direct 基线、校核后的三表观测及既有 P0 和技术 Token 门槛保持原值。

## RS2G04 完整链路复验

本地 `.env` 更新 MinerU Token 后，同一配置的只读预检返回 HTTP 200，业务码为 `-60012`（预检查询的批次不存在）。随后提交 RS2G04 Rev A.4 第 6 页原始 PDF 切片。隔离 API 和 Celery Worker 完成真实 MinerU `vlm` 解析、DeepSeek 翻译及 Word 渲染。通过签发的内部下载地址取得可打开的 DOCX，文件内容与注册主件的 SHA-256 一致。应用任务重试 0 次。[本次可复算观测](en2zh-rs2g04-live-observations.json) · [下载的中文 Word](../../../tests/tmp/datasheet-en2zh-live-20261111/rs2g04-live-20261111T124043105544Z/RS2G04-p6.zh.docx)

| 指标 | 观测 |
| --- | --- |
| PDF 提交到取得下载授权 | 32.245 秒，从申请 PDF 上传地址前计时 |
| 文档任务提交到取得下载授权 | 32.234 秒，从首次创建文档任务前计时，任务状态轮询间隔 2 秒 |
| DeepSeek 翻译分项 | USD 0.001626756，按实际回执用量和非高峰费率估算。缓存命中输入 4,352、未命中输入 214、输出 2,636 Token |
| MinerU 解析分项 | USD 0。完成 1 页，按用户于 2026-11-11 确认的本次免费额度计入 |
| 单文档总成本 | USD 0.001626756（估算），解析和翻译两项合计 |

本次单文档成本和成功端到端延迟纳入扩展样本英译中完整链路基线，样本数为 1。MinerU 任务回执无金额，费用以用户对本次免费额度的确认为依据。DeepSeek 费用按实测用量和官方费率估算。[DeepSeek 官方费率](https://api-docs.deepseek.com/quick_start/pricing/) · [MinerU 额度查询说明](https://mineru.net/doc/docs/index_pro/#额度查询)

实际译文中的 13 个块和 3 个资产与源 IR 对应，标注技术 Token 3/3。目标表的 4×4 行列与两处合并匹配，新解析结果的 DOCX 未标重复表头，结构完整匹配为 0/1。该 DOCX 为可下载的内部草稿，等待[人工验收](en2zh-human-review.md)。

## 先前运行

| 路径与样本 | 实测结果 | 计时 | 翻译费用估算 |
| --- | --- | --- | --- |
| PDF → 隔离 API/Celery → MinerU，SN74AC244 规格页 3–6 | `mineru_failed`，未进入翻译，未产生 DOCX | 首次提交后 2.060 秒观察到失败，任务状态轮询间隔 2 秒 | 未调用翻译；MinerU 费用无可归因凭证 |
| 保存的 MinerU 包 → DeepSeek → 本地正式渲染，SN74AC244 规格页 3–6 | 两次真实回放均未通过翻译完整性校验。小批次复验返回 147 项，1 项触发 `translation_integrity_technical_mismatch`，未产生 DOCX | 28.051 / 36.340 秒，本地回放各次耗时 | 两次回放的 4 份响应合计 USD 0.01586022 |
| 保存的 MinerU 包 → DeepSeek → 本地正式渲染，RS2G04 Rev A.4 第 6 页 | 中文 DOCX 可打开，目标原生表结构 1/1，标注技术 Token 3/3。仍有 `formula_text_fallback` 标志 | 9.443 秒，本地回放耗时 | 1 份响应估算 USD 0.002063724 |

[PDF 任务原始观测](en2zh-live-observations.json)与[真实翻译回放观测](en2zh-replay-observations.json)分别使用固定样本和模式。PDF 任务使用回环 API、Celery Worker、独立 Redis、SQLite 和本地对象存储。仅对隔离进程开启翻译，禁用远程回调、全文调试归档和发布。失败后用相同 MinerU 客户端认证配置做只读查询，返回 HTTP 401。没有将本地回放的耗时填到成功端到端延迟中，也未用隔离 SQLite 批次代替 P1 的 MySQL 正式门禁。

回放复用已登记的 PDF 和 MinerU 解析结果。RS2G04 派生样本 `gsx-rs2g04-esd-page` 对原 PDF 第 6 页用 Poppler 切页，MinerU v2 和 `layout.json` 同步截取第 6 页，保留相关图像，页号从零起算。目标表的位置从 `/5/4` 变为 `/0/4`，原始表 HTML 指纹不变。原 PDF 和派生页分别保留自身指纹和校核绑定。翻译前后的 13 个块 ID、类型和顺序一致，3 个资产引用保留。Word 含两张原生表，只有 ESD Ratings 表纳入本轮标注分母。LibreOffice 实际渲染为两页；中文版式没有同模式批准基准，视觉偏差保留缺测。

费用依据 [DeepSeek 官方价格表](https://api-docs.deepseek.com/quick_start/pricing/)（2026-11-11 查验）。请求模型为 `deepseek-v4-flash`，按官方别名规则采用 Flash 非高峰费率。每百万缓存命中输入、未命中输入、输出 Token 分别为 USD 0.003、0.15、0.60。只对应用实际收到用量的响应估算，包含先前运行的失败尝试。先前运行缺少可归因的解析费用，单文档总成本缺测。

旧 Token 声明的有效期于 2026-07-15 09:30:16（北京时间）结束，更新前使用旧 Token 和 UID 的只读查询得到 `HTTP 401 / A0202`。人工修改次数和验收耗时按实际审核轮次回填。新增门槛待首轮数据齐备后再定。

```bash
task_dir=.trellis/tasks/11-11-datasheet-quality-baseline-contracts
.venv/bin/python scripts/ops/datasheet_quality_metrics.py "$task_dir/en2zh-live-observations.json"
.venv/bin/python scripts/ops/datasheet_quality_metrics.py "$task_dir/en2zh-replay-observations.json"
.venv/bin/python scripts/ops/datasheet_quality_metrics.py "$task_dir/en2zh-rs2g04-live-observations.json"
```
