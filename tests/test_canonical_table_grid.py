"""TAB-301 模型合同：稳定身份、逐字来源、严格边界及诊断输入保真。"""
from __future__ import annotations

import copy
import hashlib
import json
import unittest

from pydantic import ValidationError

from app.services.document_ir.models import SourceSpan
from app.services.tables.models import (
    CellRun, TableCell, TableGrid, TableQualityFlag, TableSourceFragment,
    canonical_json_bytes, canonical_sha256, cell_content_sha256,
    make_cell_id, make_run_id, raw_html_set_sha256,
)


FRAGMENT_ID = "table-fragment:" + "a" * 64
SECOND_FRAGMENT_ID = "table-fragment:" + "c" * 64
TABLE_ID = "logical-table:" + "b" * 64
RAW_HTML = " \n<table><tr><td>中文 Русский 😀 &amp;  </td></tr></table>\n "
SOURCE = "中文 Русский 😀 &amp;  "


def source_fragment(index: int = 0, raw_html: str | None = RAW_HTML) -> TableSourceFragment:
    return TableSourceFragment(
        fragment_id=FRAGMENT_ID if index == 0 else SECOND_FRAGMENT_ID,
        source_span=SourceSpan(json_pointer=f"/{index}", source_index=index, source_type="table",
                               page_index=9 - index, bbox=(0, 90 - index, 100, 100)),
        html_state="missing" if raw_html is None else "present" if raw_html.strip() else "empty",
        raw_html=raw_html,
        raw_html_sha256=hashlib.sha256(raw_html.encode("utf-8")).hexdigest() if raw_html is not None else None,
    )


def source_cell(fragment_id: str = FRAGMENT_ID, *, source_row: int = 0, source_cell_index: int = 0,
                row: int = 0, column: int = 0, texts: tuple[str, ...] = (SOURCE,)) -> TableCell:
    identity = make_cell_id(fragment_id, source_row, source_cell_index)
    runs = [CellRun(id=make_run_id(identity, index), source_run_index=index, type="text", source=text,
                    bold=index == 0) for index, text in enumerate(texts)]
    return TableCell(id=identity, source_fragment_id=fragment_id, source_row_index=source_row,
                     source_cell_index=source_cell_index, row=row, column=column,
                     rowspan=1, colspan=1, is_header=False, runs=runs,
                     content_sha256=cell_content_sha256(runs))


def table_grid(*, fragments: list[TableSourceFragment] | None = None,
               cells: list[TableCell] | None = None) -> TableGrid:
    fragments = [source_fragment()] if fragments is None else fragments
    return TableGrid(schema_version="canonical-table/v1", table_id=TABLE_ID,
                     source_content_sha256="d" * 64, raw_html_sha256=raw_html_set_sha256(fragments),
                     rows=4, columns=4, source_fragments=fragments,
                     cells=[source_cell()] if cells is None else cells)


class CanonicalTableGridTests(unittest.TestCase):
    def assert_invalid(self, payload: dict, reason: str | None = None) -> ValidationError:
        with self.assertRaises(ValidationError) as caught:
            TableGrid.model_validate(payload)
        error = caught.exception
        if reason is not None:
            self.assertIn(reason, {item["type"] for item in error.errors(include_input=False, include_context=False)})
        # Artifact 重读必须拒绝相同损坏，不能只校验 Python 首次构建。
        with self.assertRaises(ValidationError):
            TableGrid.model_validate_json(json.dumps(payload, ensure_ascii=False))
        return error

    def test_fixed_vectors_keep_identity_and_each_hash_domain_distinct(self):
        grid = table_grid()
        cell = grid.cells[0]
        self.assertEqual(cell.id, "table-cell:4b35788ba7d283d1b3f0eb81c4d539a9aff60dcc3207d78bb472203f80a87fe8")
        self.assertEqual(cell.runs[0].id, "table-run:cce038dd0d78dba419b20aff3232ed81a4cb746e078c27e5997f96d60d382943")
        self.assertEqual(cell.content_sha256, "eb8976c8e7eb2953bd785ca4332ddd54cc49ce38a1b8634010df5c3d5724bffa")
        self.assertEqual(grid.source_fragments[0].raw_html_sha256,
                         "2ad2366df7b9a89a7d6aad7d78de7c4572b4bb88137f7a19093477497d06cc03")
        self.assertEqual(grid.raw_html_sha256, "cfe07f69b5964ac5020cc0007122be242eda100f6dc59bc14ecfbb6aa9c55c64")
        self.assertNotEqual(grid.raw_html_sha256, grid.source_fragments[0].raw_html_sha256)
        self.assertEqual(table_grid(), grid)
        self.assertEqual(canonical_json_bytes({"中": "俄 😀", "a": 1}), '{"a":1,"中":"俄 😀"}'.encode())

    def test_six_runs_multifragment_headers_and_marks_roundtrip_as_json_data(self):
        fragments = [source_fragment(), source_fragment(1)]
        cell = source_cell()
        types_and_sources = [("text", SOURCE), ("protected_token", "VCC2_OUT"), ("formula", r"\frac{a}{b}"),
                             ("superscript", "2"), ("subscript", "CC"), ("line_break", "\n")]
        runs = [CellRun(id=make_run_id(cell.id, index), source_run_index=index, type=kind, source=source,
                        target="目标文本" if kind == "text" else None, bold=index % 2 == 0, italic=index % 2 == 1)
                for index, (kind, source) in enumerate(types_and_sources)]
        payload = cell.model_dump(mode="json")
        payload.update(runs=[run.model_dump(mode="json") for run in runs], content_sha256=cell_content_sha256(runs),
                       is_header=True, rowspan=2, colspan=2)
        cells = [TableCell.model_validate(payload), source_cell(source_row=1, source_cell_index=1, row=1, column=2),
                 source_cell(SECOND_FRAGMENT_ID, row=2, texts=())]
        grid_payload = table_grid(fragments=fragments, cells=cells).model_dump(mode="json")
        grid_payload["header_rows"] = [0, 1]
        grid = TableGrid.model_validate(grid_payload)
        decoded = TableGrid.model_validate_json(grid.model_dump_json())
        self.assertEqual(decoded, grid)
        self.assertEqual([(run.type, run.source) for run in decoded.cells[0].runs], types_and_sources)
        self.assertEqual([run.bold for run in decoded.cells[0].runs], [True, False, True, False, True, False])
        self.assertEqual([run.italic for run in decoded.cells[0].runs], [False, True, False, True, False, True])
        self.assertEqual(decoded.header_rows, [0, 1])
        self.assertFalse(decoded.cells[1].is_header)
        self.assertEqual(decoded.cells[-1].runs, [])
        self.assertEqual(json.loads(grid.model_dump_json()), grid.model_dump(mode="json"))
        self.assertEqual(canonical_json_bytes(decoded.model_dump(mode="json")), canonical_json_bytes(grid_payload))
        self.assertEqual(canonical_sha256(decoded.model_dump(mode="json")), canonical_sha256(grid_payload))

    def test_target_and_geometry_changes_preserve_source_identity_and_content_hash(self):
        original = table_grid()
        payload = original.model_dump(mode="json")
        payload["cells"][0].update(row=2, column=3, rowspan=100, colspan=40)
        payload["cells"][0]["runs"][0]["target"] = "译文 😀"
        changed = TableGrid.model_validate(payload)
        self.assertEqual(changed.cells[0].id, original.cells[0].id)
        self.assertEqual(changed.cells[0].runs[0].id, original.cells[0].runs[0].id)
        self.assertEqual(changed.cells[0].content_sha256, original.cells[0].content_sha256)
        self.assertEqual(changed.source_content_sha256, original.source_content_sha256)
        self.assertNotEqual(canonical_sha256(changed.model_dump(mode="json")),
                            canonical_sha256(original.model_dump(mode="json")))
        identities = {source_cell().id, source_cell(SECOND_FRAGMENT_ID).id,
                      source_cell(source_row=1).id, source_cell(source_cell_index=1).id}
        self.assertEqual(len(identities), 4)
        self.assertNotEqual(make_run_id(changed.cells[0].id, 0), make_run_id(changed.cells[0].id, 1))

    def test_source_marks_and_order_changes_require_new_content_fingerprint(self):
        cell = source_cell(texts=("前", "后"))
        for field, value in (("source", "改动"), ("bold", False), ("italic", True), ("type", "formula")):
            with self.subTest(field=field):
                payload = cell.model_dump(mode="json")
                payload["runs"][0][field] = value
                with self.assertRaises(ValidationError):
                    TableCell.model_validate(payload)
                runs = [CellRun.model_validate(run) for run in payload["runs"]]
                payload["content_sha256"] = cell_content_sha256(runs)
                changed = TableCell.model_validate(payload)
                self.assertNotEqual(changed.content_sha256, cell.content_sha256)
                self.assertEqual(changed.id, cell.id)
        swapped = cell.model_dump(mode="json")
        swapped["runs"][0]["source"], swapped["runs"][1]["source"] = "后", "前"
        runs = [CellRun.model_validate(run) for run in swapped["runs"]]
        self.assertNotEqual(cell_content_sha256(runs), cell.content_sha256)

    def test_missing_empty_whitespace_and_unicode_raw_html_are_lossless(self):
        for html in (None, "", " \t\r\n", RAW_HTML):
            with self.subTest(html=html):
                grid = table_grid(fragments=[source_fragment(raw_html=html)], cells=[])
                decoded = TableGrid.model_validate_json(grid.model_dump_json())
                fragment = decoded.source_fragments[0]
                self.assertEqual(fragment.raw_html, html)
                if html == "":
                    self.assertEqual(fragment.raw_html_sha256,
                                     "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
                self.assertEqual(fragment.html_state, "missing" if html is None else "empty" if not html.strip() else "present")
        fragments = [source_fragment(), source_fragment(1, "")]
        self.assertNotEqual(raw_html_set_sha256(fragments), raw_html_set_sha256(list(reversed(fragments))))
        payload = table_grid(fragments=fragments).model_dump(mode="json")
        payload["source_fragments"].reverse()
        payload["raw_html_sha256"] = raw_html_set_sha256(list(reversed(fragments)))
        self.assert_invalid(payload, "table_model_source_order")

    def test_only_text_accepts_target_and_line_break_requires_newline(self):
        base = source_cell().runs[0].model_dump(mode="json")
        for kind in ("protected_token", "formula", "superscript", "subscript", "line_break"):
            for target in ("", "不能翻译"):
                with self.subTest(kind=kind, target=target), self.assertRaises(ValidationError):
                    CellRun.model_validate({**base, "type": kind, "source": "\n" if kind == "line_break" else "源值",
                                            "target": target})
        for source in ("", "\\n", "\r\n", "换行"):
            with self.subTest(source=source), self.assertRaises(ValidationError):
                CellRun.model_validate({**base, "type": "line_break", "source": source})
        self.assertEqual(CellRun.model_validate({**base, "target": ""}).target, "")

    def test_explicit_revalidation_checks_nested_model_copies(self):
        grid = table_grid()
        original = grid.model_dump_json()
        run = grid.cells[0].runs[0].model_copy(update={"type": "formula", "target": "非法译文"})
        cell = grid.cells[0].model_copy(update={"runs": [run], "content_sha256": cell_content_sha256([run])})
        changed = grid.model_copy(update={"cells": [cell]})
        with self.assertRaises(ValidationError):
            TableGrid.model_validate(changed)
        with self.assertRaises(ValidationError):
            TableGrid.model_validate({**grid.model_dump(), "cells": [cell]})
        self.assertEqual(grid.model_dump_json(), original)

    def test_version_and_all_new_required_fields_are_explicit(self):
        valid = table_grid().model_dump(mode="json")
        for key in ("schema_version", "table_id", "source_content_sha256", "raw_html_sha256", "rows", "columns",
                    "source_fragments", "cells"):
            with self.subTest(missing=key):
                payload = copy.deepcopy(valid)
                del payload[key]
                self.assert_invalid(payload)
        for version in ("canonical-table/v2", None, 1):
            with self.subTest(version=version):
                self.assert_invalid({**valid, "schema_version": version}, "table_model_version")
        self.assert_invalid({**valid, "source_fragments": []})

    def test_strict_scalars_reject_bool_strings_floats_and_invalid_spans(self):
        valid = table_grid().model_dump(mode="json")
        for field in ("rows", "columns"):
            for value in (True, "4", 4.0, -1):
                with self.subTest(field=field, value=value):
                    self.assert_invalid({**valid, field: value})
        for field in ("source_row_index", "source_cell_index", "row", "column", "rowspan", "colspan"):
            for value in (True, "1", 1.0, -1, *([0] if field in ("rowspan", "colspan") else [])):
                with self.subTest(field=field, value=value):
                    payload = copy.deepcopy(valid)
                    payload["cells"][0][field] = value
                    self.assert_invalid(payload)
        for path, field, value in (("run", "source_run_index", True), ("run", "bold", 1),
                                   ("run", "italic", "false"), ("run", "source", 3),
                                   ("cell", "is_header", 1), ("span", "source_index", "0"),
                                   ("span", "page_index", False)):
            with self.subTest(path=path, field=field):
                payload = copy.deepcopy(valid)
                target = payload["cells"][0]["runs"][0] if path == "run" else payload["cells"][0]
                if path == "span":
                    target = payload["source_fragments"][0]["source_span"]
                target[field] = value
                self.assert_invalid(payload)

    def test_identity_and_source_positions_are_unique_ordered_and_not_guessed(self):
        valid = table_grid(cells=[source_cell(), source_cell(source_cell_index=1, texts=("同文", "同文"))]).model_dump(mode="json")
        mutations = {
            "cell_id": lambda p: p["cells"][0].update(id="table-cell:" + "0" * 64),
            "run_id": lambda p: p["cells"][0]["runs"][0].update(id="table-run:" + "0" * 64),
            "duplicate_cell": lambda p: p["cells"].append(copy.deepcopy(p["cells"][0])),
            "duplicate_run": lambda p: p["cells"][0]["runs"].append(copy.deepcopy(p["cells"][0]["runs"][0])),
            "cell_order": lambda p: p["cells"].reverse(),
            "run_order": lambda p: p["cells"][1]["runs"].reverse(),
            "duplicate_fragment": lambda p: p["source_fragments"].append(copy.deepcopy(p["source_fragments"][0])),
            "opaque_table_id": lambda p: p.update(table_id="block_0123"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                payload = copy.deepcopy(valid)
                mutate(payload)
                self.assert_invalid(payload)
        # 上游身份只验证格式，不复制 IR-205 的私有 group/fragment 身份算法。
        self.assertEqual(TableGrid.model_validate(valid).table_id, TABLE_ID)

    def test_hash_and_raw_state_corruption_is_rejected(self):
        valid = table_grid().model_dump(mode="json")
        mutations = {
            "root_raw": lambda p: p.update(raw_html_sha256="0" * 64),
            "source_content_format": lambda p: p.update(source_content_sha256="D" * 64),
            "cell_content": lambda p: p["cells"][0].update(content_sha256="0" * 64),
            "fragment_raw": lambda p: p["source_fragments"][0].update(raw_html_sha256="0" * 64),
            "raw_text": lambda p: p["source_fragments"][0].update(raw_html=RAW_HTML.strip()),
            "html_state": lambda p: p["source_fragments"][0].update(html_state="empty"),
            "missing_hash": lambda p: p["source_fragments"][0].update(raw_html_sha256=None),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                payload = copy.deepcopy(valid)
                mutate(payload)
                self.assert_invalid(payload)

    def test_explicit_headers_and_quality_references_preserve_scope(self):
        fragments = [source_fragment(), source_fragment(1)]
        cells = [source_cell(), source_cell(SECOND_FRAGMENT_ID, row=1)]
        grid = table_grid(fragments=fragments, cells=cells)
        flag = TableQualityFlag(code="table_span_collision", severity="blocker", fragment_id=FRAGMENT_ID,
                                cell_id=cells[0].id, run_id=cells[0].runs[0].id)
        payload = grid.model_dump(mode="json")
        payload.update(header_rows=[0, 1], quality_flags=[flag.model_dump(mode="json")])
        payload["cells"][0]["quality_flags"] = [flag.model_dump(mode="json")]
        self.assertEqual(TableGrid.model_validate_json(json.dumps(payload)).quality_flags, [flag])
        for field, value in (("fragment_id", "table-fragment:" + "f" * 64),
                             ("cell_id", "table-cell:" + "f" * 64), ("run_id", "table-run:" + "f" * 64),
                             ("fragment_id", SECOND_FRAGMENT_ID), ("cell_id", cells[1].id),
                             ("run_id", cells[1].runs[0].id)):
            with self.subTest(field=field, value=value):
                broken = copy.deepcopy(payload)
                broken["quality_flags"][0][field] = value
                self.assert_invalid(broken, "table_model_reference")
        broken = copy.deepcopy(payload)
        broken["cells"][0]["quality_flags"][0] = {"code": "other", "severity": "warning", "cell_id": cells[1].id}
        self.assert_invalid(broken, "table_model_reference")
        missing_source = source_cell("table-fragment:" + "f" * 64)
        broken = copy.deepcopy(payload)
        broken["cells"] = [missing_source.model_dump(mode="json")]
        self.assert_invalid(broken, "table_model_reference")
        for headers in ([1, 0], [0, 0], [-1], [4], [True], [0.0], ["0"]):
            with self.subTest(headers=headers):
                self.assert_invalid({**payload, "header_rows": headers})
        for code in ("", "human readable text", "secret/path", "a" * 65):
            with self.subTest(code=code), self.assertRaises(ValidationError):
                TableQualityFlag(code=code, severity="warning")

    def test_distinct_sources_with_conflicting_anchors_and_oversized_spans_survive(self):
        first, second = source_cell(), source_cell(source_cell_index=1)
        payload = table_grid(cells=[first, second]).model_dump(mode="json")
        payload["cells"][0].update(rowspan=100, colspan=100)
        grid = TableGrid.model_validate_json(json.dumps(payload))
        self.assertEqual(len(grid.cells), 2)
        self.assertEqual([(cell.row, cell.column) for cell in grid.cells], [(0, 0), (0, 0)])
        self.assertEqual((grid.cells[0].rowspan, grid.cells[0].colspan), (100, 100))
        self.assertEqual(grid.quality_flags, [])
        self.assertEqual([cell.quality_flags for cell in grid.cells], [[], []])
        self.assertEqual((grid.rows, grid.columns), (4, 4))
        self.assertEqual(grid.model_dump(mode="json"), payload)
        for field in ("row", "column"):
            broken = copy.deepcopy(payload)
            broken["cells"][0][field] = 4
            self.assert_invalid(broken)
        for rows, columns in ((0, 0), (0, 4), (4, 0)):
            empty = {**payload, "rows": rows, "columns": columns, "cells": []}
            self.assertEqual(TableGrid.model_validate(empty).cells, [])
            self.assert_invalid({**empty, "cells": payload["cells"]})

    def test_safe_errors_exclude_sensitive_values_and_arbitrary_extra_field_names(self):
        marker = "敏感原文_PRIVATE_😀"
        valid = table_grid().model_dump(mode="json")
        cases = []
        for field in ("schema_version", "table_id", "source_content_sha256"):
            cases.append({**valid, field: marker})
        for field in ("source", "target", "type", "bold"):
            payload = copy.deepcopy(valid)
            payload["cells"][0]["runs"][0][field] = {marker: marker} if field != "type" else marker
            cases.append(payload)
        raw_error = copy.deepcopy(valid)
        raw_error["source_fragments"][0]["raw_html"] = marker
        cases.append(raw_error)
        content_error = copy.deepcopy(valid)
        content_error["cells"][0]["runs"][0]["source"] = marker
        cases.append(content_error)
        target_error = copy.deepcopy(valid)
        target_error["cells"][0]["runs"][0].update(type="formula", target=marker)
        cases.append(target_error)
        for path in ("root", "cell", "run", "fragment", "span", "hint", "flag"):
            payload = copy.deepcopy(valid)
            target = payload
            if path == "cell":
                target = payload["cells"][0]
            elif path == "run":
                target = payload["cells"][0]["runs"][0]
            elif path in ("fragment", "span", "hint"):
                target = payload["source_fragments"][0]
                if path == "span":
                    target = target["source_span"]
                elif path == "hint":
                    target["repeated_header_hint"] = {"row_count": 1, "signature": "header"}
                    target = target["repeated_header_hint"]
            elif path == "flag":
                payload["quality_flags"] = [{"code": "table_unknown", "severity": "warning"}]
                target = payload["quality_flags"][0]
            target[marker] = marker
            cases.append(payload)
        for index, payload in enumerate(cases):
            with self.subTest(case=index):
                error = self.assert_invalid(payload)
                safe = error.errors(include_input=False, include_context=False)
                self.assertNotIn(marker, str(error))
                self.assertNotIn(marker, json.dumps(safe, ensure_ascii=False))
                self.assertTrue(all("input" not in item and "ctx" not in item for item in safe))
                self.assertTrue(all(item["type"].startswith("table_model_") for item in safe))

    def test_non_string_input_keys_are_redacted_at_every_model_boundary(self):
        marker = "PRIVATE_KEY_MARKER"
        for key in (marker.encode(), (marker,)):
            for path in ("root", "cell", "run", "fragment", "span", "hint", "flag"):
                with self.subTest(key_type=type(key).__name__, path=path):
                    payload = table_grid().model_dump(mode="json")
                    target = payload
                    if path == "cell":
                        target = payload["cells"][0]
                    elif path == "run":
                        target = payload["cells"][0]["runs"][0]
                    elif path in ("fragment", "span", "hint"):
                        target = payload["source_fragments"][0]
                        if path == "span":
                            target = target["source_span"]
                        elif path == "hint":
                            target["repeated_header_hint"] = {"row_count": 1, "signature": "header"}
                            target = target["repeated_header_hint"]
                    elif path == "flag":
                        payload["quality_flags"] = [{"code": "table_unknown", "severity": "warning"}]
                        target = payload["quality_flags"][0]
                    target[key] = "PRIVATE_VALUE"
                    with self.assertRaises(ValidationError) as caught:
                        TableGrid.model_validate(payload)
                    self.assertNotIn(marker, str(caught.exception))
                    self.assertNotIn(marker, json.dumps(caught.exception.errors(
                        include_input=False, include_context=False)))

    def test_non_utf8_text_is_rejected_before_json_serialization(self):
        # 孤立 surrogate 是非法 UTF-8；不能接受模型后才在输出 Artifact 时失败。
        malformed = chr(0xD800)
        for field in ("source", "target"):
            with self.subTest(run_field=field), self.assertRaises(ValidationError):
                CellRun.model_validate({**source_cell().runs[0].model_dump(), field: malformed})
        for field in ("json_pointer", "source_type"):
            with self.subTest(span_field=field):
                payload = table_grid().model_dump(mode="json")
                payload["source_fragments"][0]["source_span"][field] = malformed
                with self.assertRaises(ValidationError):
                    TableGrid.model_validate(payload)
        payload = table_grid().model_dump(mode="json")
        payload["source_fragments"][0]["repeated_header_hint"] = {"row_count": 1, "signature": malformed}
        with self.assertRaises(ValidationError):
            TableGrid.model_validate(payload)
        payload = table_grid().model_dump(mode="json")
        payload["cells"][0]["runs"][0]["target"] = malformed
        with self.assertRaises(ValidationError):
            TableGrid.model_validate(payload)
        with self.assertRaises(ValidationError):
            TableGrid.model_validate_json(json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
