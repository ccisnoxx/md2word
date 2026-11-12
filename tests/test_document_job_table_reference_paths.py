"""表格参考图内容入口由 HTTP 层补齐：地址格式、转义与不可用条目的合同。"""

from unittest import TestCase

from app.domains.document_jobs.http_responses import with_table_reference_content_paths
from app.domains.document_jobs.views.translation import (
    DocumentJobTableReferenceListResponse,
    DocumentJobTableReferenceResponse,
)


def _item(asset_id, availability):
    return DocumentJobTableReferenceResponse(
        block_id="block_1", fragment_id="fragment_1", logical_group_id="group_1", page_index=0, bbox=None,
        asset_id=asset_id, file_id="file_1" if asset_id else None, source_status="valid",
        availability=availability, mime_type="image/png", checksum_sha256=None, size_bytes=None,
        display_supported=True, content_path=None,
    )


class TableReferenceContentPathTests(TestCase):
    def test_only_available_items_get_generation_bound_escaped_path(self):
        result = DocumentJobTableReferenceListResponse(
            job_id="job/1", generation=3, ir_file_id="ir 1", evidence_status="registered",
            items=[_item("table-reference:a/b", "available"), _item("asset_2", "expired"), _item(None, "source_missing")],
        )

        projected = with_table_reference_content_paths(result)

        self.assertEqual(
            projected.items[0].content_path,
            "/api/v1/document-jobs/job%2F1/table-references/table-reference%3Aa%2Fb/content?generation=3&ir_file_id=ir%201",
        )
        self.assertIsNone(projected.items[1].content_path)
        self.assertIsNone(projected.items[2].content_path)
        # 用例产出保持不含 HTTP 地址，补齐不修改原对象。
        self.assertIsNone(result.items[0].content_path)
