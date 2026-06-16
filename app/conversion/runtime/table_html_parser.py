from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser


@dataclass(slots=True)
class HtmlCell:
    text: str
    rowspan: int = 1
    colspan: int = 1
    html: str | None = None


@dataclass(slots=True)
class HtmlTable:
    rows: list[list[HtmlCell]]

    @property
    def max_columns(self) -> int:
        return max((sum(cell.colspan for cell in row) for row in self.rows), default=0)


class SimpleTableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[HtmlCell]] = []
        self.current_row: list[HtmlCell] | None = None
        self.current_cell: HtmlCell | None = None
        self.buffer: list[str] = []
        self.current_cell_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = dict(attrs)
        if tag == "tr":
            self.current_row = []
        elif tag in {"td", "th"}:
            self.buffer = []
            self.current_cell_chunks = [f"<{tag}{format_html_attrs(attrs)}>"]
            self.current_cell = HtmlCell(
                text="",
                rowspan=safe_int(attrs_map.get("rowspan"), 1),
                colspan=safe_int(attrs_map.get("colspan"), 1),
            )
        elif self.current_cell is not None:
            self.current_cell_chunks.append(f"<{tag}{format_html_attrs(attrs)}>")
            if tag == "br":
                self.buffer.append("\n")
                self.current_cell_chunks.append(f"</{tag}>")
        elif tag == "br":
            self.buffer.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.current_cell is not None and self.current_row is not None:
            self.current_cell.text = "".join(self.buffer).strip()
            self.current_cell_chunks.append(f"</{tag}>")
            self.current_cell.html = "".join(self.current_cell_chunks)
            self.current_row.append(self.current_cell)
            self.current_cell = None
            self.buffer = []
            self.current_cell_chunks = []
        elif self.current_cell is not None:
            self.current_cell_chunks.append(f"</{tag}>")
        elif tag == "tr" and self.current_row is not None:
            self.rows.append(self.current_row)
            self.current_row = None

    def handle_data(self, data: str) -> None:
        if self.current_cell is not None:
            self.buffer.append(data)
            self.current_cell_chunks.append(data)


def parse_html_table(html: str | None) -> HtmlTable | None:
    if not html:
        return None
    parser = SimpleTableHTMLParser()
    parser.feed(html)
    parser.close()
    rows = [row for row in parser.rows if row]
    return HtmlTable(rows=rows) if rows else None


def safe_int(value: str | None, default: int) -> int:
    try:
        return max(int(value or default), 1)
    except (TypeError, ValueError):
        return default


def format_html_attrs(attrs: list[tuple[str, str | None]]) -> str:
    if not attrs:
        return ""
    parts = []
    for key, value in attrs:
        if value is None:
            parts.append(f" {key}")
        else:
            parts.append(f' {key}="{value}"')
    return "".join(parts)
