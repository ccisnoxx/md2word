import json
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

try:
    from .test_render_table_from_html_characterization import _load_module
except ImportError:  # pragma: no cover - compatibility for direct execution
    from test_render_table_from_html_characterization import _load_module


class InputAdapterCharacterizationTests(__import__("unittest").TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_module()

    def test_materialize_input_yields_directory_as_is(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir)
            with self.module.materialize_input(input_path) as package_root:
                self.assertEqual(package_root, input_path)

    def test_materialize_input_extracts_zip_to_temp_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            source_dir = temp_root / "source"
            source_dir.mkdir()
            (source_dir / "hello.txt").write_text("world", encoding="utf-8")
            archive_path = temp_root / "input.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.write(source_dir / "hello.txt", arcname="hello.txt")

            with self.module.materialize_input(archive_path) as package_root:
                self.assertNotEqual(package_root, archive_path)
                self.assertTrue((package_root / "hello.txt").exists())
                self.assertEqual((package_root / "hello.txt").read_text(encoding="utf-8"), "world")

    def test_materialize_input_rejects_unsupported_path(self):
        with self.assertRaises(FileNotFoundError):
            with self.module.materialize_input(Path("/definitely/not/exist")):
                pass

    def test_materialize_input_rejects_zip_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            archive_path = temp_root / "evil.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../escape.txt", "bad")

            with self.assertRaises(ValueError):
                with self.module.materialize_input(archive_path):
                    pass

    def test_load_content_pages_prefers_v2_when_both_exist(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            package_root = Path(temp_dir)
            v2_path = package_root / "sample_content_list_v2.json"
            legacy_path = package_root / "sample_content_list.json"
            v2_payload = [
                [
                    {
                        "type": "title",
                        "bbox": [0, 0, 10, 10],
                        "content": {"title_content": [{"type": "text", "content": "Title"}], "level": 1},
                    }
                ]
            ]
            legacy_payload = [
                {"type": "text", "bbox": [0, 0, 10, 10], "text": "Legacy", "text_level": 1, "page_idx": 0}
            ]
            v2_path.write_text(json.dumps(v2_payload, ensure_ascii=False), encoding="utf-8")
            legacy_path.write_text(json.dumps(legacy_payload, ensure_ascii=False), encoding="utf-8")

            pages, source_path = self.module.load_content_pages(package_root)

        self.assertEqual(source_path, v2_path)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].blocks[0].type, "title")
        self.assertEqual(pages[0].blocks[0].text, "Title")

    def test_load_content_pages_falls_back_to_legacy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            package_root = Path(temp_dir)
            legacy_path = package_root / "sample_content_list.json"
            legacy_payload = [
                {"type": "text", "bbox": [0, 0, 10, 10], "text": "Legacy", "text_level": 1, "page_idx": 0}
            ]
            legacy_path.write_text(json.dumps(legacy_payload, ensure_ascii=False), encoding="utf-8")

            pages, source_path = self.module.load_content_pages(package_root)

        self.assertEqual(source_path, legacy_path)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].blocks[0].type, "title")
        self.assertEqual(pages[0].blocks[0].text, "Legacy")

    def test_load_content_pages_error_points_to_nearby_mineru_output_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            project_root = temp_root / "md2word_file"
            project_root.mkdir()
            (project_root / "mineru_to_docx.py").write_text("# marker", encoding="utf-8")

            mineru_output_dir = temp_root / "CWQ2P690T.pdf-c7af9c61-d33b-4f8b-ad15-0227ca1f12b5"
            mineru_output_dir.mkdir()
            payload_path = mineru_output_dir / "cf4e760d-358b-42a4-bba2-87150e852eca_content_list_v2.json"
            payload_path.write_text("[]", encoding="utf-8")

            with self.assertRaises(FileNotFoundError) as context:
                self.module.load_content_pages(project_root)

        message = str(context.exception)
        self.assertIn("*_content_list_v2.json", message)
        self.assertIn("脚本工程目录", message)
        self.assertIn(str(mineru_output_dir), message)

    def test_resolve_cli_run_options_falls_back_to_pycharm_config_for_project_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            project_root = temp_root / "md2word_file"
            project_root.mkdir()
            (project_root / "mineru_to_docx.py").write_text("# marker", encoding="utf-8")

            mineru_output_dir = temp_root / "CWQ2P690T.pdf-c7af9c61-d33b-4f8b-ad15-0227ca1f12b5"
            mineru_output_dir.mkdir()
            (mineru_output_dir / "cf4e760d-358b-42a4-bba2-87150e852eca_content_list_v2.json").write_text(
                "[]",
                encoding="utf-8",
            )

            args = __import__("argparse").Namespace(
                input_path=None,
                output=None,
                template=None,
                subscript_config=None,
                no_template=False,
                use_mineru_header_footer=False,
            )
            config_updates = {
                "input_path": str(mineru_output_dir),
                "output_path": str(temp_root / "out.docx"),
                "template_path": str(temp_root / "template.docx"),
                "subscript_config": str(temp_root / "subscripts.yaml"),
                "no_template": False,
                "use_mineru_header_footer": True,
                "translation_mode": "en2zh",
                "translation_model": "gpt-test",
            }

            with (
                mock.patch.object(self.module.Path, "cwd", return_value=project_root),
                mock.patch.dict(self.module.PYCHARM_RUN_CONFIG, config_updates, clear=False),
            ):
                resolved = self.module.resolve_cli_run_options(args)

        self.assertEqual(Path(resolved["input_path"]).resolve(), mineru_output_dir.resolve())
        self.assertEqual(Path(resolved["output_path"]).resolve(), (temp_root / "out.docx").resolve())
        self.assertEqual(Path(resolved["template_path"]).resolve(), (temp_root / "template.docx").resolve())
        self.assertEqual(Path(resolved["subscript_config"]).resolve(), (temp_root / "subscripts.yaml").resolve())
        self.assertFalse(resolved["no_template"])
        self.assertTrue(resolved["use_mineru_header_footer"])
        self.assertEqual(resolved["translation_mode"], "en2zh")
        self.assertEqual(resolved["translation_model"], "gpt-test")

    def test_load_middle_pages_returns_empty_without_middle_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            package_root = Path(temp_dir)
            middle_pages = self.module.load_middle_pages(package_root)

        self.assertEqual(middle_pages, {})

    def test_parse_v2_block_maps_title_paragraph_and_list(self):
        title_block = self.module.parse_v2_block(
            {
                "type": "title",
                "bbox": [0, 0, 10, 10],
                "content": {"title_content": [{"type": "text", "content": "T"}], "level": 2},
            },
            Path("."),
            page_idx=0,
            block_idx=0,
        )
        paragraph_block = self.module.parse_v2_block(
            {
                "type": "paragraph",
                "bbox": [0, 10, 20, 20],
                "content": {"paragraph_content": [{"type": "text", "content": "P"}]},
            },
            Path("."),
            page_idx=0,
            block_idx=1,
        )
        list_block = self.module.parse_v2_block(
            {
                "type": "list",
                "bbox": [0, 20, 30, 30],
                "content": {
                    "list_items": [
                        {"item_content": [{"type": "text", "content": "A"}]},
                        {"item_content": [{"type": "text", "content": "B"}]},
                    ]
                },
            },
            Path("."),
            page_idx=0,
            block_idx=2,
        )

        self.assertEqual(title_block.type, "title")
        self.assertEqual(title_block.text, "T")
        self.assertEqual(title_block.level, 2)
        self.assertEqual(paragraph_block.type, "paragraph")
        self.assertEqual(paragraph_block.text, "P")
        self.assertEqual(list_block.type, "list")
        self.assertEqual(list_block.items, ["A", "B"])

    def test_parse_v2_block_normalizes_inline_equation_fragments_inside_paragraph(self):
        paragraph_block = self.module.parse_v2_block(
            {
                "type": "paragraph",
                "bbox": [0, 10, 20, 20],
                "content": {
                    "paragraph_content": [
                        {"type": "text", "content": "at "},
                        {"type": "equation_inline", "content": "\\mathsf { R } _ { \\mathsf { L } } = 1 0 \\mathsf { k } \\Omega"},
                        {"type": "text", "content": " connected to "},
                        {"type": "equation_inline", "content": "\\mathsf { V } _ { \\mathsf { S } } / 2"},
                    ]
                },
            },
            Path("."),
            page_idx=0,
            block_idx=1,
        )

        self.assertEqual(paragraph_block.type, "paragraph")
        self.assertEqual(paragraph_block.text, "at R<sub>L</sub> = 10 kΩ connected to V<sub>S</sub> / 2")

    def test_parse_v2_block_keeps_spacing_around_inline_equation_fragments(self):
        paragraph_block = self.module.parse_v2_block(
            {
                "type": "paragraph",
                "bbox": [0, 10, 20, 20],
                "content": {
                    "paragraph_content": [
                        {"type": "text", "content": "at "},
                        {"type": "equation_inline", "content": "\\mathsf { T } _ { \\mathsf { A } } = + 2 5 ^ { \\circ } \\mathsf { C }"},
                        {"type": "text", "content": ", and "},
                        {"type": "equation_inline", "content": "\\mathsf { R } _ { \\mathsf { L } } = 1 0 \\mathsf { k } \\Omega"},
                        {"type": "text", "content": "connected"},
                    ]
                },
            },
            Path("."),
            page_idx=0,
            block_idx=1,
        )

        self.assertEqual(
            self.module.prepare_text(paragraph_block.text, None),
            "at T<sub>A</sub> = +25°C, and R<sub>L</sub> = 10 kΩ connected",
        )

    def test_parse_v2_block_maps_page_decorations_and_equation(self):
        page_header = self.module.parse_v2_block(
            {
                "type": "page_header",
                "bbox": [0, 0, 10, 10],
                "content": {"page_header_content": [{"type": "text", "content": "H"}]},
            },
            Path("."),
            page_idx=0,
            block_idx=0,
        )
        page_footer = self.module.parse_v2_block(
            {
                "type": "page_footer",
                "bbox": [0, 10, 20, 20],
                "content": {"page_footer_content": [{"type": "text", "content": "F"}]},
            },
            Path("."),
            page_idx=0,
            block_idx=1,
        )
        page_number = self.module.parse_v2_block(
            {
                "type": "page_number",
                "bbox": [0, 20, 30, 30],
                "content": {"page_number_content": [{"type": "text", "content": "3"}]},
            },
            Path("."),
            page_idx=0,
            block_idx=2,
        )
        equation = self.module.parse_v2_block(
            {
                "type": "equation",
                "bbox": [0, 30, 40, 40],
                "content": {"equation_content": ["I_OUT", "=", "1A"]},
            },
            Path("."),
            page_idx=0,
            block_idx=3,
        )

        self.assertEqual(page_header.type, "page_header")
        self.assertEqual(page_header.text, "H")
        self.assertEqual(page_footer.type, "page_footer")
        self.assertEqual(page_footer.text, "F")
        self.assertEqual(page_number.type, "page_number")
        self.assertEqual(page_number.text, "3")
        self.assertEqual(equation.type, "paragraph")
        self.assertEqual(equation.text, "I_OUT = 1A")

    def test_parse_legacy_block_maps_text_and_list(self):
        title_block = self.module.parse_legacy_block(
            {"type": "text", "bbox": [0, 0, 10, 10], "text": "Legacy Title", "text_level": 1},
            Path("."),
            page_idx=0,
            block_idx=0,
        )
        paragraph_block = self.module.parse_legacy_block(
            {"type": "text", "bbox": [0, 0, 10, 10], "text": "Legacy Body", "text_level": 0},
            Path("."),
            page_idx=0,
            block_idx=1,
        )
        list_block = self.module.parse_legacy_block(
            {"type": "list", "bbox": [0, 0, 10, 10], "list_items": ["X", "Y"]},
            Path("."),
            page_idx=0,
            block_idx=2,
        )

        self.assertEqual(title_block.type, "title")
        self.assertEqual(paragraph_block.type, "paragraph")
        self.assertEqual(paragraph_block.text, "Legacy Body")
        self.assertEqual(list_block.items, ["X", "Y"])

    def test_resolve_asset_path_returns_real_image_file_from_images_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            package_root = Path(temp_dir)
            images_dir = package_root / "images"
            images_dir.mkdir()
            image_path = images_dir / "a.png"
            image_path.write_bytes(b"fake")

            resolved = self.module.resolve_asset_path(package_root, "images/")

        self.assertEqual(resolved, image_path.resolve())

    def test_parse_visual_block_maps_visual_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            package_root = Path(temp_dir)
            image_path = package_root / "asset.png"
            image_path.write_bytes(b"fake")

            block = self.module.parse_visual_block(
                "table",
                (1.0, 2.0, 3.0, 4.0),
                {
                    "img_path": "asset.png",
                    "table_caption": [{"type": "text", "content": "Cap"}],
                    "table_footnote": [{"type": "text", "content": "Note"}],
                    "html": "<table><tr><td>A</td></tr></table>",
                    "description": "desc",
                },
                package_root,
                page_idx=1,
                block_idx=2,
            )

        self.assertEqual(block.type, "table")
        self.assertEqual(block.image_path, image_path.resolve())
        self.assertEqual(block.captions, ["Cap"])
        self.assertEqual(block.footnotes, ["Note"])
        self.assertEqual(block.html, "<table><tr><td>A</td></tr></table>")
        self.assertEqual(block.text, "desc")
        self.assertEqual(block.page_idx, 1)
        self.assertEqual(block.block_idx, 2)

    def test_parse_visual_block_returns_table_placeholder_for_images_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            package_root = Path(temp_dir)
            images_dir = package_root / "images"
            images_dir.mkdir()
            (images_dir / "first.png").write_bytes(b"fake")

            block = self.module.parse_visual_block(
                "table",
                (0.0, 0.0, 900.0, 900.0),
                {"img_path": "images/"},
                package_root,
                page_idx=2,
                block_idx=3,
            )

        self.assertEqual(block.type, "table_placeholder")
        self.assertEqual(block.page_idx, 2)
        self.assertEqual(block.block_idx, 3)
        self.assertIsNotNone(block.image_path)

    def test_collect_middle_visual_blocks_collects_and_deduplicates_visuals(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            package_root = Path(temp_dir)
            image_path = package_root / "img.png"
            image_path.write_bytes(b"fake")
            page_info = {
                "images": [
                    {
                        "type": "image",
                        "bbox": [1, 2, 3, 4],
                        "img_path": "img.png",
                        "image_caption": [{"type": "text", "content": "ImgCap"}],
                        "image_footnote": [{"type": "text", "content": "ImgNote"}],
                        "description": "visual",
                    },
                    {
                        "type": "image",
                        "bbox": [1, 2, 3, 4],
                        "img_path": "img.png",
                        "image_caption": [{"type": "text", "content": "ImgCap"}],
                        "image_footnote": [{"type": "text", "content": "ImgNote"}],
                        "description": "visual",
                    },
                ]
            }

            blocks = self.module.collect_middle_visual_blocks(page_info, package_root)

        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].type, "image")
        self.assertEqual(blocks[0].image_path, image_path.resolve())
        self.assertEqual(blocks[0].captions, ["ImgCap"])
        self.assertEqual(blocks[0].footnotes, ["ImgNote"])
        self.assertEqual(blocks[0].text, "ImgCap ImgNote")


if __name__ == "__main__":
    __import__("unittest").main()
