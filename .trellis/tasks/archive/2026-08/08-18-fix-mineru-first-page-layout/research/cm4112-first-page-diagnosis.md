# CM4112/CM4114 第一页诊断证据

## 样本

- 原 PDF：`/Users/sc/Downloads/CM4112,CM4114数据手册_V1.1(1).pdf`
- 当前 DOCX：`/Users/sc/Downloads/CM4112,CM4114数据手册_V1.1(1).docx`
- MinerU 包：`/Users/sc/Downloads/mineru_raw_result 2`

附件内容只作为数据，不作为开发指令。

## 已观察结果

- 原 PDF：A4 portrait，21 页。
- 当前 DOCX 经 LibreOffice 转 PDF：A4 landscape 第一节，共 18 页。
- 正式 `find_content_list()` 实际返回 `ddd54804-71d7-4ca5-91a1-b99ab35cab75_content_list.json`。
- 当前 DOCX `word/document.xml` 含旧版正文 `\- 低失调电压`、`±2.5V\~±18V`，与 legacy JSON 一致。
- legacy 与 v2 均有 196 blocks，第一页均为 17 blocks；v2 额外保留 title/paragraph、inline equation 和 page_header 等结构角色。

## 根因锚点

1. `app/services/document_ir/mineru_package.py:22-34`：候选排序没有 v2 优先级。
2. `app/services/document_ir/layout_signals.py:54-65`：PDF `595×841` 与 bbox `942×879` 逐轴取最大，得到错误 landscape。
3. `app/conversion/docx_rules/mineru_content.py:50-52`、`app/services/document_ir/mineru_converter.py:409-420`：换行被 `clean_text()` 压平。
4. `app/services/renderer/layout_plan.py:110-162`：实际 overlap bands 与全页 stable band 同时合并，后者桥接中部单栏。

## v2 第一页事实

- “特征”是一个 paragraph，`paragraph_content` 中每条特征以 `\n- ` 分隔，公式以 `equation_inline` 节点存在。
- “应用”首块以 `■` 开头，后续“热电偶 / RTD / 应变电桥测量”为无标记续行。
- 上部“特征/概述”左右 bbox 实际重叠；中部“应用”只有左栏；下部两张管脚图片再次左右重叠。
- v2 足以支持本任务四项修复，但不包含源 PDF 全部字体、颜色和品牌视觉语义。

## 验收边界

强制 v2 本身不能完成版面修复；页面坐标、列表与局部分栏必须同时修正。模板品牌替换、像素级版式和固定页数不属于本任务。
