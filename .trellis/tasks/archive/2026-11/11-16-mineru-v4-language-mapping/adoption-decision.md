# MinerU v1 接入判断与独立 OCR 验证

2026-11-16 确认继续使用云端 v4/vlm，PDF 请求继续显式发送 `file.is_ocr=true`。v4 的语言映射已独立验收，本记录保存另两组实验的接入判断。

## v1/standard 对照

每组上传同一 PDF，使用同一模板、版式 YAML 和符号词典执行 direct。v4 使用 `is_ocr=true`，v1 使用 `ocr_mode=ocr`。首轮 SN74AC244 两份 ZIP 的 4 页页尺寸均为 612×792 pt，11/11 图片引用可解析。v1 原包只有 Middle JSON 与 Structured Content，没有项目输入要求的 Content List，实际转换报 `mineru_content_list_missing`。对照 Word 使用 MinerU 4.1.7 官方导出器离线生成 Content List V2，并将 v1 页几何投影为项目可识别的布局文件。[新版产物合同](https://opendatalab.github.io/MinerU/reference/output_files/)

| 样本 | v4/vlm | v1/standard 经离线适配 |
|---|---|---|
| SN74AC244 原 PDF 第 3–6 页，首轮 | 5.2 表 19×8，额外合并 6 处 MIN/MAX，公式回退 2 处 | 5.2 表 19×8，21 处合并均符合标注，公式回退 7 处 |
| SN74AC244 同一 PDF 重新上传 | 5.2 表 19×8，21 处合并和 3/3 技术标记正确，公式回退 2 处 | 表格和公式指标与 v4 相同，9 个章节和 8 张表顺序也相同 |
| TPLD2001 原 PDF 第 3–4 页 | 一张 22×8 原生表及一张裁图占位，表格质量 `blocked` | 两张原生表（20×8、4×8），无裁图占位，因 `table_render_layout_incompatible` 仍为 `blocked` |

TPLD2001 两路保留了按顺序排列的 20 行、60/60 个引脚标记。v1 的三次 ZIP 下载完成耗时为 14.89、14.50、14.40 秒，对应 v4 为 24.65、30.53、18.18 秒。耗时包括提交、排队、网络和约两秒间隔的轮询。数据未显示可复现的相对表格或阅读顺序提升，故继续用 v4；新版提交、轮询、ZIP 适配及相应的历史回放和在途恢复验收未启动。

## OCR 单变量对照

四次请求均用 v4/vlm，固定 `language=en`。样本为 SN74AC244 原 PDF 第 4 页的电子版，以及同页 240 dpi 栅格化的无文本层扫描模拟件。各自的 true/false 两路上传相同字节。

| 输入 | `is_ocr=true` | `is_ocr=false` |
|---|---|---|
| 有文本层电子版 | 实包 `_ocr_enable=true`，5.2 网格正确，技术标记 3/3，保留脚注引用标记但纯文本回退 1 处 | 实包 `_ocr_enable=false`，网格与技术标记仍正确，公式回退 0 处，5.2 表前脚注引用标记丢失 |
| 无文本层扫描模拟件 | 实包 `_ocr_enable=true`，有两张原生表，5.2 网格有差异，技术标记 3/3，公式回退 1 处 | 实包仍为 `_ocr_enable=true`，所列质量指标相同 |

单个电子页和清晰栅格页不足以支持改变全局默认。`file.is_ocr` 的 API 默认值为 `false`，项目现行请求显式使用 `true`。[云端 v4 参数表](https://mineru.net/apiManage/docs)

## 本地证据

- 首轮 SN74AC244 的报告、ZIP 和 Word 位于 `tests/tmp/mineru-v4-v1-sn74ac244-20261116/`。
- 接入复测和 OCR 的 `report.md`、`cross-and-ocr.json`、源 PDF 切片及各组 ZIP/Word 位于 `tests/tmp/mineru-adoption-20261116/`。这些实验产物留在 Git 忽略目录。
- 两次 SN74AC244 接口对照的源 PDF SHA-256 为 `04c5b23af2877ebd686b032caa25c9f0d2ace7b123fb0d013c83cc562285fc74`。TPLD2001 切片 SHA-256 为 `3eefb3ff6d23abfd2f04b00e3fcc076767dcc8c02fc1d9d391bc08807bc40803`。
