from __future__ import annotations

# app/services/renderer/list_numbering.py: 列表项目符号编号定义与段落编号属性的写入 helper。

from typing import Any

from docx.oxml import OxmlElement
from docx.oxml.ns import qn


MD2WORD_RENDERER_BULLET_NUM_ID_ATTR = "_md2word_renderer_bullet_num_id"


class WordListNumberingMixin:
    """同一文档 part 只创建一套项目符号编号定义，并缓存其 numId。"""

    def _apply_bullet_numbering(self, paragraph: Any, *, level: int = 0) -> None:
        normalized_level = min(max(level, 0), 1)
        num_id = self._ensure_bullet_numbering(paragraph)
        paragraph_properties = paragraph._p.get_or_add_pPr()
        num_properties = paragraph_properties.find(qn("w:numPr"))
        if num_properties is None:
            num_properties = OxmlElement("w:numPr")
            paragraph_properties.append(num_properties)

        self._set_numbering_child_value(num_properties, "w:ilvl", str(normalized_level))
        self._set_numbering_child_value(num_properties, "w:numId", str(num_id))

    def _ensure_bullet_numbering(self, paragraph: Any) -> str:
        part = paragraph.part
        cached_num_id = getattr(part, MD2WORD_RENDERER_BULLET_NUM_ID_ATTR, None)
        if cached_num_id is not None:
            return str(cached_num_id)

        numbering = part.numbering_part.element
        abstract_num_id = str(self._next_numbering_id(numbering, "w:abstractNum", "w:abstractNumId"))
        num_id = str(self._next_numbering_id(numbering, "w:num", "w:numId"))

        abstract_num = OxmlElement("w:abstractNum")
        abstract_num.set(qn("w:abstractNumId"), abstract_num_id)
        multi_level_type = OxmlElement("w:multiLevelType")
        multi_level_type.set(qn("w:val"), "hybridMultilevel")
        abstract_num.append(multi_level_type)

        for ilvl, marker, left in ((0, "•", "240"), (1, "–", "480")):
            level = OxmlElement("w:lvl")
            level.set(qn("w:ilvl"), str(ilvl))
            for tag, value in (
                ("w:start", "1"),
                ("w:numFmt", "bullet"),
                ("w:lvlText", marker),
                ("w:lvlJc", "left"),
            ):
                child = OxmlElement(tag)
                child.set(qn("w:val"), value)
                level.append(child)
            paragraph_properties = OxmlElement("w:pPr")
            indent = OxmlElement("w:ind")
            indent.set(qn("w:left"), left)
            indent.set(qn("w:hanging"), "180")
            paragraph_properties.append(indent)
            level.append(paragraph_properties)
            abstract_num.append(level)

        num = OxmlElement("w:num")
        num.set(qn("w:numId"), num_id)
        abstract_num_id_element = OxmlElement("w:abstractNumId")
        abstract_num_id_element.set(qn("w:val"), abstract_num_id)
        num.append(abstract_num_id_element)

        numbering.append(abstract_num)
        numbering.append(num)
        setattr(part, MD2WORD_RENDERER_BULLET_NUM_ID_ATTR, num_id)
        return num_id

    def _next_numbering_id(self, numbering: Any, element_tag: str, attr_name: str) -> int:
        values: list[int] = []
        for element in numbering.findall(qn(element_tag)):
            raw_value = element.get(qn(attr_name))
            if raw_value is not None and raw_value.isdigit():
                values.append(int(raw_value))
        return max(values, default=0) + 1

    def _set_numbering_child_value(self, parent: Any, tag: str, value: str) -> None:
        child = parent.find(qn(tag))
        if child is None:
            child = OxmlElement(tag)
            parent.append(child)
        child.set(qn("w:val"), value)

