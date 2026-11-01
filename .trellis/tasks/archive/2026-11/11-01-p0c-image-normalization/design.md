# P0c 技术设计（按 PRD 推荐决策）

## 1. 责任边界

- 唯一 owner：`app/services/document_ir/artifact_validator.py::_validate_asset` 的检查阶段。规范化写成同文件内私有函数 `_word_compatible_png(content, *, max_bytes) -> bytes | None`，不新建模块（只有一个调用点）。
- `ValidatedImage` 增加可选字段 `normalized_from: tuple[str, str] | None`（源格式、源字节 sha256）；`content`/`mime_type` 为规范化后的值。
- 下游只做透传：`mineru_converter` 把来源信息放入 `MinerUImageAsset`；`execution` 登记时按 MIME 决定文件扩展名、写 metadata；表格参考图沿用 `ValidatedImage` 即自动得到规范化字节。

## 2. 验证器流程变更

现状（必需图片）：Pillow 安全解码 → `WordImage.from_blob(原字节)` → 失败即 `invalid_image_asset`。

变更后（必需图片与表格参考图共用；结果缓存在 `_ImageInspection`）：

```
Pillow 安全解码（不变）
→ WordImage(原字节) 通过：word_supported=True，字节不变
→ 不通过：_word_compatible_png(原字节)
     → 成功且 WordImage(新字节) 通过：content=新字节, mime=image/png, normalized_from=(格式, sha256)
     → 否则：word_supported=False（必需图片报原 invalid_image_asset；参考图保持既有 valid/invalid 判定不变*）
```

\* 参考图原先不做 Word 检查。为避免改变 `table_checks.reference_status` 语义，参考图规范化失败时仍按原逻辑返回 valid（原字节），仅在规范化成功时替换字节；渲染期行为与现状相同。

- `_ImageInspection` 增加 `normalized_content`/`normalized_from`，同一路径只解码、只规范化一次；`WordImage.from_blob` 调用次数在缓存语义上保持“每个路径至多一次原字节检查 + 一次新字节检查”。
- 每个引用该图的**必需图片块**记一条 warning（表格参考图不记，理由见 PRD 范围 5；`add_issue` 按 `(code, json_pointer, field)` 去重）：`code="image_asset_normalized"`、`severity="warning"`、`stops_conversion=False`、`field="image_source"`、`facts={"reason": "word_incompatible_raster"}`。

## 3. `_word_compatible_png`

```python
with warnings.catch_warnings():
    warnings.simplefilter("error", Image.DecompressionBombWarning)
    with Image.open(io.BytesIO(content)) as image:
        image.seek(0)
        mode = image.mode
        target = "RGBA" if mode in {"RGBA", "LA", "PA"} or (mode == "P" and "transparency" in image.info) else ("L" if mode in {"L", "1"} else "RGB")
        converted = image.convert(target)
        options = {"dpi": image.info["dpi"]} if valid_dpi(image.info.get("dpi")) else {}
        buffer = io.BytesIO(); converted.save(buffer, format="PNG", **options)
```

- 不设置 `optimize`、不写文本块与时间戳，保证确定性；输出超过 `policy.max_file_bytes` 返回 None。
- 捕获与原解码相同的异常集合，失败返回 None，由调用方按原错误处理。

## 4. 报告与投影白名单

- `app/services/renderer/evidence.py`：`REPORT_CODES` 加 `image_asset_normalized`，`REPORT_REASONS` 加 `word_incompatible_raster`。不改 validator/policy 版本。
- `base_quality` 无需改动：warning 自动计入 `warning_count`。

## 5. 资产登记

- `MinerUImageAsset` 增加 `normalized_from: tuple[str, str] | None = None`。
- `execution` 登记 `image_asset`：文件名 `{asset_id}_{源 stem}{实际扩展名}`（扩展名由 MIME 推导，仅规范化时与源不同）；metadata 增加 `normalized_from_format`、`normalized_from_sha256`（仅规范化时）。资源包 manifest 保持 v1，`mime_type` 已体现实际格式。
- IR block metadata 增加 `mineru_asset_normalized_from`（源格式），便于审核定位。

## 6. 规格修订

- IMAGE-001 预期输出改为：“Word 可识别的资产保持原字节；仅安全解码通过而 python-docx 拒绝原字节的资产，无损转为 PNG 并记 `image_asset_normalized` warning；一律禁止重采样、缩放与压缩。”
- INPUT-002 自动验证条目补充规范化用例。

## 7. 兼容、风险与回滚

- 行为变化仅限原先必然失败的输入；已成功任务的字节、哈希与报告不变。
- JPEG 照片转 PNG 体积会增大（数据手册中少见）；如需控制，改用 D2 备选。
- 风险：CMYK→RGB 无 ICC 色彩管理，颜色可能偏差（warning 已提示人工复核）。
- 回滚：回退提交即恢复“失败关闭”；已生成的 DOCX 不受影响。
