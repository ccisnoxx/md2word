# MinerU v4 解析语言验证

2026-11-16，在本机隔离运行时通过项目 FastAPI 创建任务并持久化快照。单独运行正式解析阶段，使用项目 `MinerUClient` 访问真实 MinerU v4。上传和轮询使用现有项目凭证，采集已序列化的请求 `language`、模型、OCR 开关和受理状态。两份输入各上传一次，沿原批次轮询到 `done`，项目下载并登记 ZIP 后进入 `parsed`。验收以 ZIP 内容为准，范围止于解析。

| 样本 | 任务模式 | 快照与实际请求 | 结果 |
|---|---|---|---|
| TI 中文 OPA228 数据手册第 1 页 | `zh2en` | `ch` | `done` / `parsed`；1 个表格块；中文识别命中“运算放大器”，正文命中 `OPA228` 和 `33 MHz`，表格内命中“器件型号”、`OPA228`、`PDIP`。 |
| ОВЕН 俄文 ПД100 操作手册第 6 页 | `ru2zh` | `east_slavic` | `done` / `parsed`；1 个表格块；俄文正文命中 `Технические характеристики`，表格内命中 `Питание`、`20 мА`、`IP65`。 |

两次申请上传均返回 HTTP `200` 和业务码 `0`。请求发送 `model_version=vlm`、`files[0].is_ocr=true`，结果包均含 `*_content_list_v2.json`。

- 中文来源 [TI OPA228 中文 PDF](https://www.ti.com/cn/lit/ds/symlink/opa228.pdf)。输入 SHA-256 `4eaba05e66a10ae187f958dcd5f86efb89c84b3b307f763c0f6ce1681f3d62be`，ZIP SHA-256 `81a4b05a2193d4c4f585915ec8b7f824ee85f03497816649cc8c8d71cb78ddc1`，批次 `daa24d4d-d179-4fdd-8200-3933f6b49794`。
- 俄文来源 [ОВЕН ПД100 俄文 PDF](https://owen.ru/downloads/re_pd100.pdf)。输入 SHA-256 `232b604528bc4b1799d9f64233337943007de5580507d3a92287dcd9b249f322`，ZIP SHA-256 `996c8c00a79b5da36eb2345e99d087b2aa21a81b262685401d44b896d28de7df`，批次 `de10d610-f1d7-4189-8dac-e4c74dec2866`。

内容核对为所列标记与块类型抽查，翻译、Word 排版和生产部署不属于本次验收。

## 本地定向验证

- 本地实现提交为 `6d006e389cf31cf8bc9c807e27ebab6597787ecf`。
- 最终候选 11 项通过。覆盖五模式的版本化快照与实际序列化请求、无版本资源的创建和继承克隆、历史别名及缺字段、术语重绑保留绑定，以及已有直接资源与解析等待回归。
- 独立复核重放了配置变化后的非版本化任务、复用 ZIP 的术语重绑，以及缺少整个 MinerU 字段的历史克隆，三条路径的语言绑定均符合预期。
- `git diff --check` 和本次修改的 Python 文件语法编译通过。
- 旧用例 `test_historical_direct_read_clone_and_default_retry_keep_lazy_snapshot` 在 `GET` 详情的 `page_quality` 快照投影处失败。已在隔离的未改动 `HEAD` 复现同一断言失败，保留该用例供单独处理。

## 解析接口与 OCR 决策

继续使用 v4/vlm，OCR 请求保持 `file.is_ocr=true`。独立的 v1 样本复测、结果包兼容性和 OCR 对照见[接入判断与独立 OCR 验证](adoption-decision.md)。
