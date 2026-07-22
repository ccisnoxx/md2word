"""统一正式与 legacy DOCX 渲染链的 run 字体槽位写入规则。"""

from __future__ import annotations

from typing import Any

from docx.oxml.ns import qn


def apply_run_fonts(
    run: Any,
    *,
    font_name: str | None,
    western_font_name: str | None,
    complex_script_font_name: str | None,
) -> None:
    """写入东亚、西文和复杂文种字体；缺失的新字段沿用旧字体行为。"""

    western_font = font_name if western_font_name is None else western_font_name
    complex_script_font = font_name if complex_script_font_name is None else complex_script_font_name
    if not font_name and not western_font and not complex_script_font:
        return

    if western_font:
        run.font.name = western_font

    run_properties = run._element.get_or_add_rPr()
    run_fonts = run_properties.get_or_add_rFonts()
    if font_name:
        run_fonts.set(qn("w:eastAsia"), font_name)
    if western_font:
        run_fonts.set(qn("w:ascii"), western_font)
        run_fonts.set(qn("w:hAnsi"), western_font)
    if complex_script_font:
        run_fonts.set(qn("w:cs"), complex_script_font)
