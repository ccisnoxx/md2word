# BAS-001 合成复现证据

执行日期：2026-10-12（America/Los_Angeles）；HEAD `fcea60ff8c131edff7fd5ba360e1bf4e37ec4227`。
三个探针通过正式 `MinerUToDocumentIRService.convert_zip`；annotation 使用 fake Provider，paragraph 使用正式 Word renderer。所有文本及图片字节为合成输入，无外部调用、凭据或专有样本。

## 精确执行与复现

本次临时文件和命令：

```bash
PYTHONPATH=. .venv/bin/python /var/folders/m5/j06tv2sn1hn93d6f33j559jm0000gn/T/md2word-bas001-fyx7e_tp/probes.py
```

cwd 为 `/Users/sc/PycharmProjects/md2word`，退出码 0。临时脚本在交付前清理；再次复现时将下面完整代码保存到新系统临时目录，替换命令中的脚本路径。结果里的 `译文：` 只是 fake 输出标记，不代表真实译文质量。合成图片仅测试登记字节，不送图片渲染器，不能验证图片视觉效果或文件格式。

```python
"""BAS-001：通过现有入口复现三项缺口；全部输入为合成内容。"""
import io
import json
import tempfile
import zipfile
from pathlib import Path
from docx import Document
from app.services.document_ir.mineru_converter import MinerUToDocumentIRService
from app.services.renderer.word_renderer import DocumentIRWordRenderer
from app.domains.translation.document_ir_translator import DocumentIRTranslationService
from app.domains.translation.models import TranslationProviderResult, TranslationTextItem

class FakeProvider:
    def __init__(self):
        self.ids = []
    def translate(self, request):
        self.ids.extend(item.id for item in request.items)
        return TranslationProviderResult(items=tuple(
            TranslationTextItem(id=item.id, text='译文：' + item.text)
            for item in request.items
        ))

def convert(blocks):
    with tempfile.TemporaryDirectory(prefix='bas001-synthetic-') as tmp:
        path = Path(tmp) / 'input.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('content_list.json', json.dumps(blocks))
            archive.writestr('layout.json', json.dumps({'pdf_info': [
                {'page_idx': i, 'page_size': [600, 800]} for i in (0, 1)
            ]}))
            # converter 只登记字节；此合成资产不送图片渲染器。
            archive.writestr('images/reference.png', b'bas001-synthetic-image-bytes')
        return MinerUToDocumentIRService().convert_zip(
            path, job_id='bas001_probe', source_file_id='synthetic', document_language='en'
        )

annotation = convert([{'type': 'table', 'page_idx': 0, 'bbox': [30,30,400,160],
    'table_body': '<table><tr><td>Parameter</td></tr></table>',
    'table_caption': ['Table 1. Electrical characteristics'],
    'table_footnote': ['Measured at room temperature.']}]).document
provider = FakeProvider()
translated = DocumentIRTranslationService(provider).translate(annotation, term_version=None)
print(json.dumps({'probe': 'annotations', 'provider_item_ids': provider.ids,
    'before': annotation.blocks[0].model_dump(include={'text','captions','footnotes'}),
    'after': translated.blocks[0].model_dump(include={'text','captions','footnotes'}),
    'flags': annotation.quality_flags}, ensure_ascii=False))

paragraphs = convert([
    {'type': 'text', 'text': 'The signal continues', 'page_idx': 0, 'bbox': [30,740,500,780]},
    {'type': 'text', 'text': 'on the following page.', 'page_idx': 1, 'bbox': [30,30,500,70]},
]).document
docx = DocumentIRWordRenderer().render_to_bytes(paragraphs, template_path=None,
    config_path=None, image_loader=lambda asset: b'')
print(json.dumps({'probe': 'paragraphs', 'ir': [
    {'text': b.text, 'page': b.page_index, 'source_index': b.layout.source_index}
    for b in paragraphs.blocks], 'word_paragraphs': [p.text for p in Document(io.BytesIO(docx)).paragraphs if p.text],
    'flags': paragraphs.quality_flags}, ensure_ascii=False))

reference = convert([
    {'type': 'table', 'page_idx': 0, 'bbox': [30,30,400,160],
     'table_body': '<table><tr><td>Parameter</td></tr></table>', 'img_path': 'images/reference.png'},
    {'type': 'image', 'page_idx': 0, 'bbox': [30,200,400,400], 'img_path': 'images/reference.png'},
])
print(json.dumps({'probe': 'reference', 'blocks': [
    {'type': b.type, 'asset_ref': b.asset_ref, 'metadata': b.metadata}
    for b in reference.document.blocks], 'assets': [a.source_path for a in reference.document.assets],
    'image_assets': len(reference.image_assets), 'flags': reference.document.quality_flags}, ensure_ascii=False))
```

## 实际输出

```jsonl
{"probe": "annotations", "provider_item_ids": ["block_0001.text", "block_0001.html.0000"], "before": {"text": "Table 1. Electrical characteristics", "captions": ["Table 1. Electrical characteristics"], "footnotes": ["Measured at room temperature."]}, "after": {"text": "译文：Table 1. Electrical characteristics", "captions": ["Table 1. Electrical characteristics"], "footnotes": ["Measured at room temperature."]}, "flags": ["layout_wide_table:block_0001", "layout_caption_binding:block_0001", "layout_footnote_binding:block_0001"]}
{"probe": "paragraphs", "ir": [{"text": "The signal continues", "page": 0, "source_index": 0}, {"text": "on the following page.", "page": 1, "source_index": 1}], "word_paragraphs": ["The signal continues", "on the following page."], "flags": []}
{"probe": "reference", "blocks": [{"type": "table", "asset_ref": null, "metadata": {"source_type": "table", "bbox": [30, 30, 400, 160], "page_idx": 0, "layout_role_reason": "column_hint=wide;bbox_width=370.00;page_width=600.00"}}, {"type": "image", "asset_ref": "asset_block_0002", "metadata": {"source_type": "image", "bbox": [30, 200, 400, 400], "page_idx": 0, "layout_role_reason": "column_hint=wide;bbox_width=370.00;page_width=600.00"}}], "assets": ["images/reference.png"], "image_assets": 1, "flags": ["layout_wide_table:block_0001"]}
```

## 结论与 flags

- annotations：Provider 仅接收 text 和 HTML cell；text 副本变化，captions/footnotes 原数组未变化。真实缺口路由 TR-401；不修改当前结构保真断言。
- paragraphs：page/source index 为 0/0、1/1；IR 和 DOCX 各保留两段，没有合并为一个段落；路由 IR-203。
- reference：有效 HTML table 的 asset_ref=null，metadata 不保留 img_path；同路径普通 image 生成 asset_block_0002，assets/image_assets 均只有一项；路由 IR-206。
- `layout_wide_table:block_0001` 由合成 bbox 宽度 370/页宽 600 触发布局分类；`layout_caption_binding:block_0001` / `layout_footnote_binding:block_0001` 表示绑定 annotation 的已有事实。paragraph flags 为空。没有新增 flag 类型，也没有将这些信息性标记隐藏或清除；它们不是已实现的 quality_status。
