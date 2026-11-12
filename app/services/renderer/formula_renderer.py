from __future__ import annotations

# app/services/renderer/formula_renderer.py: 公式段落、行内混排公式与 Word 域代码的写入 helper。

from dataclasses import replace
from html import escape
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.run import Run
from docx.text.paragraph import Paragraph

from app.conversion.docx_rules.formula import (
    FORMULA_OUTPUT_VERSION,
    MathSpan,
    _OmmlParser,
    formula_block_span,
    render_formula,
    scan_math_spans,
    sha256_text,
)
from app.conversion.docx_rules.terminology import TerminologyReplacer
from app.services.renderer.template_config import TemplateConfigPackage, TemplateParagraphStyleConfig
from app.services.renderer.text_renderer import CaptionBookmarks


class WordFormulaRendererMixin:
    """公式写入与来源登记；段落样式、run 写入和行内标记解析由 WordTextRendererMixin 提供。"""

    def _fill_formula_paragraph(
        self,
        paragraph: Any,
        text: str,
        template_config: TemplateConfigPackage,
    ) -> None:
        self._apply_named_style(paragraph, template_config.normal.word_style_name)
        self._apply_paragraph_style(paragraph, template_config.normal)
        self._append_formula(paragraph, formula_block_span(text), template_config.normal)

    def _append_formula(
        self,
        paragraph: Any,
        span: MathSpan,
        style: TemplateParagraphStyleConfig,
        *,
        bold: bool = False,
        italic: bool = False,
        _native_marks: bool = False,
        _native_references: CaptionBookmarks | None = None,
    ) -> None:
        # 历史内容认证仅在独立 scratch part 安装逐式重放；正式写入继续共享 parser。
        replay = getattr(paragraph.part, "_md2word_formula_replay", None)
        result = replay(span) if replay is not None else render_formula(span)
        for element in result.elements:
            if element.tag == qn("w:r"):
                run = Run(element, paragraph)
                semantic = (run.bold, run.italic, run.font.subscript, run.font.superscript)
                self._apply_run_style(run, style)
                run.bold = bold or semantic[0]
                run.italic = italic or semantic[1]
                run.font.subscript = semantic[2]
                run.font.superscript = semantic[3]
            elif _native_marks and (bold or italic):
                for run in element.iter(qn("m:r")):
                    existing = run.find("./" + qn("m:rPr") + "/" + qn("m:sty"))
                    value = existing.get(qn("m:val"), "p") if existing is not None else "p"
                    combined_bold, combined_italic = bold or "b" in value, italic or "i" in value
                    # 复用原数学样式 owner，在预期投影冻结前合并外层真实 marks。
                    _OmmlParser._apply_math_style([run], "bi" if combined_bold and combined_italic
                        else "b" if combined_bold else "i")
            if element.tag == qn("m:oMath") and style.font_size is not None:
                # 数学 run 不继承相邻文字的直接字号；否则窄表格仍会用模板字号裁切公式。
                for math_run in element.iter(qn("m:r")):
                    properties = OxmlElement("w:rPr")
                    for tag in ("w:sz", "w:szCs"):
                        size = OxmlElement(tag)
                        size.set(qn("w:val"), str(int(style.font_size * 2)))
                        properties.append(size)
                    # OMML run 的属性位于 m:rPr 之后、末尾的 m:t 之前。
                    math_run.insert(len(math_run) - 1, properties)
        if _native_marks and _native_references and result.mode == "semantic_runs":
            # 同 part 的临时段落不进入最终 DOM；原文字 owner 先完成脚本与 REF 的实际输出。
            prepared = Paragraph(OxmlElement("w:p"), paragraph._parent)
            for element in result.elements:
                run = Run(element, paragraph)
                self._add_text_run(prepared, run.text, style, bold=bool(run.bold), italic=bool(run.italic),
                    subscript=bool(run.font.subscript), superscript=bool(run.font.superscript),
                    reference_bookmarks=_native_references, _native_reference_script=True)
            result = replace(result, elements=tuple(prepared._p))
        # 预期投影在元素进入最终 document DOM 以前确定。
        expected_output_sha256 = result.expected_output_sha256
        context = getattr(paragraph.part, "_md2word_formula_context", None)
        anchor = None
        if context is not None:
            source_hash = sha256_text(span.source)
            source_index = next((index for index, source in enumerate(context.formula_sources)
                if index not in context.used_formula_sources
                and (source["block_id"], source["field"]) == context.formula_location
                and source["source_sha256"] == source_hash and source["boundary"] == span.boundary), None)
            if source_index is None:
                raise ValueError("公式写入位置与源 DocumentIR 不匹配")
            context.used_formula_sources.add(source_index)
            occurrence = len(context.formula_entries) + 1
            anchor = f"md2w_formula_{occurrence:06d}"
            context.formula_entries.append({
                "occurrence": occurrence,
                "source": dict(context.formula_sources[source_index]),
                "anchor": anchor,
                "mode": result.mode,
                "reason": result.reason,
                "output_projection_version": FORMULA_OUTPUT_VERSION,
                "expected_output_sha256": expected_output_sha256,
            })
            bookmark = OxmlElement("w:bookmarkStart")
            bookmark.set(qn("w:id"), str(1000000 + occurrence))
            bookmark.set(qn("w:name"), anchor)
            paragraph._p.append(bookmark)
        paragraph._p.extend(result.elements)
        if anchor is not None:
            bookmark = OxmlElement("w:bookmarkEnd")
            bookmark.set(qn("w:id"), str(1000000 + occurrence))
            paragraph._p.append(bookmark)

    def _set_formula_source(self, document: Any, block_id: str, field: str) -> None:
        """在实际内容写入点登记来源；同原式不能靠库存顺序猜测所属位置。"""
        context = getattr(document.part, "_md2word_formula_context", None)
        if context is not None:
            context.formula_location = (block_id, field)

    def _render_mixed_math(
        self,
        paragraph: Any,
        text: str,
        style: TemplateParagraphStyleConfig,
        terminology: TerminologyReplacer | None,
        reference_bookmarks: CaptionBookmarks | None,
        *,
        _native_literal: bool = False,
        _spans: tuple[MathSpan, ...] | None = None,
    ) -> bool:
        spans = scan_math_spans(text) if _spans is None else _spans
        placeholder_tag = "md2w-formula"
        while placeholder_tag in text.lower():
            placeholder_tag += "-internal"
        chunks: list[str] = []
        position = 0
        for index, span in enumerate(spans):
            chunks.extend((text[position:span.start], f'<{placeholder_tag} data-index="{index}"></{placeholder_tag}>'))
            position = span.end
        chunks.append(text[position:])
        soup = BeautifulSoup("<root>" + "".join(chunks) + "</root>", "html.parser")
        root = soup.find("root")
        if root is None:
            raise ValueError("内联文本容器无法解析")

        def visit(parent: Tag, *, bold: bool = False, italic: bool = False, subscript: bool = False, superscript: bool = False) -> None:
            for child in parent.children:
                if isinstance(child, NavigableString):
                    raw = str(child)
                    prepared = (escape(raw, quote=False) if _native_literal and (subscript or superscript)
                                else self._prepare_text_for_rendering(raw, terminology, _native_literal=_native_literal))
                    if _native_literal or self._looks_like_inline_markup(prepared):
                        prepared_soup = BeautifulSoup(prepared, "html.parser")
                        self._render_inline_children(prepared_soup, paragraph, style, bold=bold, italic=italic, subscript=subscript, superscript=superscript, reference_bookmarks=reference_bookmarks)
                    else:
                        self._add_text_run(paragraph, prepared, style, bold=bold, italic=italic, subscript=subscript, superscript=superscript, reference_bookmarks=reference_bookmarks)
                elif isinstance(child, Tag):
                    name = child.name.lower()
                    if name == placeholder_tag:
                        self._append_formula(paragraph, spans[int(child["data-index"])], style, bold=bold,
                            italic=italic, _native_marks=_native_literal,
                            _native_references=reference_bookmarks if _native_literal else None)
                    elif name == "br":
                        paragraph.add_run().add_break()
                    else:
                        visit(child, bold=bold or name in {"b", "strong", "th"}, italic=italic or name in {"i", "em"}, subscript=subscript or name == "sub", superscript=superscript or name == "sup")

        visit(root)
        return True

    def _add_complex_field(
        self,
        paragraph: Any,
        instruction: str,
        result: str,
        style: TemplateParagraphStyleConfig,
    ) -> Any:
        begin_run = paragraph.add_run()
        begin = OxmlElement("w:fldChar")
        begin.set(qn("w:fldCharType"), "begin")
        begin_run._r.append(begin)

        instruction_run = paragraph.add_run()
        instruction_text = OxmlElement("w:instrText")
        instruction_text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        instruction_text.text = instruction
        instruction_run._r.append(instruction_text)

        separate_run = paragraph.add_run()
        separate = OxmlElement("w:fldChar")
        separate.set(qn("w:fldCharType"), "separate")
        separate_run._r.append(separate)

        result_run = paragraph.add_run(result)
        self._apply_run_style(result_run, style)

        end_run = paragraph.add_run()
        end = OxmlElement("w:fldChar")
        end.set(qn("w:fldCharType"), "end")
        end_run._r.append(end)
        return result_run

