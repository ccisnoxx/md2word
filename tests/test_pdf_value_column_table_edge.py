"""参数列取证的 PDF 表框侧缘归属回归。"""
from dataclasses import replace
import unittest

from app.services.document_ir.pdf_value_column_observer import PdfValueColumnPage, PdfValueColumnWord
from app.services.document_ir.pdf_value_column_table_edge import find_pdf_table_edge


class PdfValueColumnTableEdgeTests(unittest.TestCase):
    def setUp(self):
        self.original = (50.0, 70.0, 449.5, 230.0)
        self.layout = (50.0, 70.0, 450.0, 230.0)
        self.page = PdfValueColumnPage(
            width=500.0, height=500.0, page_count=1, words=(), rectangles=(),
            horizontal_lines=tuple((50.0, y, 450.0) for y in (70.0, 110.0, 150.0, 190.0, 230.0)),
            vertical_lines=((50.0, 70.0, 230.0), (450.0, 70.0, 230.0)),
            extractor_version="test",
        )

    def test_uses_measured_right_edge_without_moving_the_other_three_edges(self):
        proof = find_pdf_table_edge(self.page, self.original, self.original, ())
        self.assertIsNotNone(proof)
        self.assertEqual(proof.side, "right")
        self.assertEqual(proof.corrected_bbox, self.layout)
        self.assertEqual(proof.wall, 450.0)
        self.assertEqual(proof.vertical_lines, ((450.0, 70.0, 230.0),))

    def test_recovers_clipped_left_edge(self):
        original = (50.5, 70.0, 450.0, 230.0)
        proof = find_pdf_table_edge(self.page, original, original, ())
        self.assertIsNotNone(proof)
        self.assertEqual(proof.side, "left")
        self.assertEqual(proof.corrected_bbox, self.layout)
        self.assertEqual(proof.wall, 50.0)

    def test_preserves_measured_stroke_cap_and_allows_bracketed_header_fill(self):
        page = replace(
            self.page,
            horizontal_lines=tuple((x, y, 450.125) for x, y, _ in self.page.horizontal_lines),
            rectangles=((400.25, 70.125, 449.875, 109.875),),
        )
        proof = find_pdf_table_edge(page, self.original, self.layout, ())
        self.assertIsNotNone(proof)
        self.assertEqual(proof.corrected_bbox, (50.0, 70.0, 450.125, 230.0))
        self.assertEqual(proof.wall, 450.0)
        self.assertEqual(proof.horizontal_lines, page.horizontal_lines)

    def test_intact_search_limit_or_missing_connection_leave_original(self):
        for name, page, original, layout in (
            ("intact", self.page, self.layout, self.layout),
            ("limit", self.page, (50.0, 70.0, 448.75, 230.0), (50.0, 70.0, 448.75, 230.0)),
            ("vertical gap", replace(self.page, vertical_lines=(
                self.page.vertical_lines[0], (450.0, 70.0, 110.0), (450.0, 123.0, 230.0),
            )), self.original, self.layout),
            ("only one row", replace(self.page, horizontal_lines=self.page.horizontal_lines[:2]),
             self.original, self.layout),
        ):
            with self.subTest(name=name):
                self.assertIsNone(find_pdf_table_edge(page, original, layout, ()))

    def test_limit_applies_to_the_measured_end_including_the_cap(self):
        page = replace(
            self.page, horizontal_lines=tuple((x, y, 450.5) for x, y, _ in self.page.horizontal_lines),
        )
        self.assertIsNotNone(find_pdf_table_edge(page, self.original, self.original, ()))
        layout = (50.0, 70.0, 449.49, 230.0)
        self.assertIsNone(find_pdf_table_edge(page, self.original, layout, ()))

    def test_rejects_protected_regions_even_when_the_tables_share_the_edge(self):
        for neighbor in ((449.75, 110.0, 470.0, 180.0), (450.0, 70.0, 480.0, 230.0)):
            with self.subTest(neighbor=neighbor):
                self.assertIsNone(find_pdf_table_edge(self.page, self.original, self.layout, (neighbor,)))

    def test_rejects_added_strip_with_words_or_unexplained_paint(self):
        box = (449.75, 120.0, 460.0, 125.0)
        for page in (
            replace(self.page, words=(PdfValueColumnWord("note", box, ((449.75, 123.0),)),)),
            replace(self.page, unmapped_glyph_regions=(box,)),
            replace(self.page, unsupported_regions=(box,)),
            replace(self.page, opaque_fill_regions=(box,)),
            replace(self.page, rectangles=((425.0, 74.0, 449.9, 90.0),)),
        ):
            with self.subTest(page=page):
                self.assertIsNone(find_pdf_table_edge(page, self.original, self.layout, ()))

    def test_rejects_competing_walls_connected_neighbor_and_stray_line(self):
        duplicated = replace(
            self.page,
            horizontal_lines=tuple((x, y, 450.25) for x, y, _ in self.page.horizontal_lines),
            vertical_lines=self.page.vertical_lines + ((450.25, 70.0, 230.0),),
        )
        neighbor = replace(self.page, horizontal_lines=self.page.horizontal_lines + ((450.0, 110.0, 480.0),))
        stray = replace(self.page, horizontal_lines=self.page.horizontal_lines + ((445.0, 134.0, 449.75),))
        for page in (duplicated, neighbor, stray):
            with self.subTest(page=page):
                self.assertIsNone(find_pdf_table_edge(page, self.original, self.layout, ()))

    def test_rejects_two_sides_that_independently_look_correctable(self):
        original = (50.5, 70.0, 449.5, 230.0)
        self.assertIsNone(find_pdf_table_edge(self.page, original, self.layout, ()))
