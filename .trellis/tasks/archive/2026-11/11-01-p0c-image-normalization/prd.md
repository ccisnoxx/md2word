# P0c：Word 不兼容图片的最小规范化

## 目标与业务结果

MinerU 包内**已通过安全校验、Pillow 能解码**、但 python-docx 无法识别的图片，不再导致整个任务以 `invalid_image_asset` 失败（普通图片）或在渲染期以 `table_placeholder_integrity_failed` 失败（表格占位参考图），而是无损地转成 Word 可接受的格式后继续转换，并在质量报告中留下可见 warning。Word 本来就能接受的图片保持原字节不变。

## 背景与证据（基线 `a6d2207c`，含 P0a、P0b）

- `artifact_validator._validate_asset` 先用 Pillow 安全解码（格式白名单 PNG/JPEG/GIF/BMP/TIFF/WEBP、解压炸弹防护），再对**必需图片**用 `WordImage.from_blob` 检查**原字节**；失败即 `invalid_image_asset` / `unreadable_or_unsupported_image`，整任务失败。
- python-docx 1.x 按文件头签名识别格式。实验（Pillow 12.2、python-docx 当前安装版本）结论：
  - 被拒：WebP（任意模式）、CMYK JPEG（APP14 `Adobe` 段，无 JFIF）、无 APP0/APP1 的 JPEG；
  - 接受：PNG、带 JFIF/Exif 的 JPEG、TIFF、BMP、GIF。
  - WebP→PNG 重复编码 3 次输出哈希一致；CMYK→RGB 后可被识别。
- 表格参考图走同一 `_validate_asset(required=False)`，**不做** Word 检查；缺表格 HTML 时它作为 `mineru_reference` 占位图经 `add_picture` 写入 DOCX，WebP 会在渲染期失败。
- 字节流向：`ValidatedImage.content` → `MinerUImageAsset` → 登记 `image_asset` 文件（MIME 取自验证器）→ IR 资产 checksum 取自登记文件 → 渲染按 file_id 读回；`image_evidence` 只核对“DOCX 媒体 = 登记资产 = IR checksum”，不与 MinerU 原包比对。因此在验证器源头替换字节，下游证据链自洽。
- 验证器 warning 只累加 `document_base.warning_count`，使 `quality_status` 为 `warning`（不阻断审批），不进入自由 quality flags。

## 规格冲突（需用户决定）

`word-generation-rules.md` **IMAGE-001** 现为“资产位于包根内，**原字节不转码/重采样**”，并保留 `5d4a02d7` 的源字节原则；`tests/test_mineru_artifact_validator.py` 把“WebP 必需图片失败”写成了断言。本任务提出收窄例外：

- **D1（必选）**：修订 IMAGE-001——仅当图片通过安全解码且 python-docx 拒绝原字节时，允许无损转码为 PNG；其余图片原字节不变，仍禁止重采样、缩放、压缩。未获批准则本任务不实施。
- **D2（推荐：全部转 PNG）**：三类被拒图片统一按解码像素无损编码为 PNG（CMYK 先转 RGB）。备选：无 APP0 的 RGB/灰度 JPEG 仅插入 JFIF 头、不重新压缩——字节更接近原文件但多一条代码路径。
- **D3（推荐：包含）**：表格占位参考图同样规范化，修复同类渲染期失败。
- **D4（推荐：记 warning）**：每次规范化在验证报告中记一条 `image_asset_normalized` warning（定位到来源块），任务 `quality_status` 因此可能从 `passed` 变为 `warning`。

### 决策记录

2026-11-01 用户确认 D1–D4 均按推荐方案执行：修订 IMAGE-001 例外；统一转 PNG；包含表格参考图；记 `image_asset_normalized` warning。

## 范围与要求（按推荐决策）

1. 规范化只在验证器内、安全校验与 Pillow 解码通过之后进行；触发条件是 `WordImage.from_blob(原字节)` 失败（必需图片与表格参考图都适用）。
2. 输出 PNG：保持像素尺寸；CMYK/YCCK→RGB，带透明度的模式→RGBA，其余按 Pillow 安全转换到 RGB/RGBA/L；保留源 DPI（若有）；多帧图取首帧。输出必须再通过 `WordImage.from_blob`，且不超过现有单文件字节上限，否则仍按原错误失败。
3. 输出确定：同一输入字节得到同一输出字节。
4. 资产来源可追溯：登记文件 MIME 为 `image/png`、文件名扩展名随实际格式；文件 metadata 记录源格式与源字节 sha256。
5. 验证报告记录 `image_asset_normalized` warning（`facts.reason` 为受控值），并加入事件/安全投影白名单。实施调整：仅正文必需图片记 warning；表格参考图只规范化不记 warning——参考图仅供 QA，或作为占位写入时已由 `table_noneditable_placeholder` 阻断项覆盖，再记 warning 会让 DOCX 无变化的任务出现质量噪音。
6. 修订 IMAGE-001 与 INPUT-002 相关描述及自动验证条目。

## 非目标

- 不处理 EXIF 方向、色彩管理（ICC）、超大图降采样、动图保留；不对 Word 已接受的图片做任何改写。
- 不放宽格式白名单、解压炸弹、路径、ZIP 与单文件大小等安全边界。
- 不实现原 PDF 回退裁切、页面降级或部分成功（属 P1）。
- 不改 `mineru-artifact-validator/v3` 版本号与 policy 版本（新增 warning 码为增量）。

## 验收条件

- AC1：WebP、CMYK JPEG、无 APP0 JPEG 作为普通图片时任务成功，DOCX 内媒体为 PNG，`image_evidence` 认证通过；验证报告含对应块的 `image_asset_normalized` warning。
- AC2：PNG、带 JFIF 的 JPEG、TIFF、BMP、GIF 的资产字节与原包逐字节一致，且不产生该 warning（保留既有断言）。
- AC3：WebP 表格参考图在缺 HTML 时作为占位图成功写入 DOCX。
- AC4：不可解码、非白名单格式（含 EPS 不触发 Ghostscript）、解压炸弹、规范化后仍不被 Word 接受或超限的图片，仍以原错误码失败。
- AC5：同一图片被多个块引用时只解码、规范化一次（保留缓存断言的语义）；同一输入多次转换输出字节一致。
- AC6：P0a 失败诊断测试改用真正不可读的图片后仍覆盖页级与文档级场景。

## 不变量

- 安全校验全部发生在规范化之前；规范化只消费已安全解码的像素。
- 下游证据链（登记文件 checksum、IR asset checksum、DOCX 媒体字节）一致。
