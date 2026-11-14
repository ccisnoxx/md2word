"""生产 Compose 专项的 MinerU I/O 夹具，由真实 Celery 启动入口加载。"""

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path
from zipfile import ZipFile


BODY_MARKER = "Template catalog fixture body"
CONTROL_DIR = Path("/app/var/template-catalog-compose-gates")
RESULT_URL = "https://template-catalog-test.invalid/result.zip"


class FixtureMinerU:
    def upload_files_batch(self, file_paths, *, task_uuids, **_options):
        (source,), (data_id,) = file_paths, task_uuids
        held = source.name.startswith("hold-")
        return f"{'hold' if held else 'ready'}:{data_id}", []

    def query_batch_extract_results(self, batch_id):
        mode, data_id = batch_id.split(":", 1)
        ready = mode == "ready" or (CONTROL_DIR / data_id).is_file()
        result = {"data_id": data_id, "state": "running"}
        if ready:
            result.update(state="done", full_zip_url=RESULT_URL)
        return {"batch_id": batch_id, "extract_result": [result]}

    def download_result_zip(self, result_url, output_path):
        if result_url != RESULT_URL:
            raise ValueError("MinerU 夹具收到非预期的下载地址。")
        blocks = [
            {"type": "title", "text": "1 Features", "text_level": 1, "page_idx": 0, "bbox": [72, 80, 260, 105]},
            {"type": "text", "text": BODY_MARKER, "page_idx": 0, "bbox": [72, 120, 380, 145]},
        ]
        with ZipFile(output_path, "w") as archive:
            archive.writestr("content_list_v2.json", json.dumps(blocks))
            archive.writestr("layout.json", json.dumps({"pdf_info": [{"page_idx": 0, "page_size": [612, 792]}]}))
        return output_path


if __name__ == "__main__":
    # 脚本由只读挂载点启动，生产代码仍从镜像加载。
    sys.path.insert(0, "/app")
    from app.domains.document_jobs.mineru_execution import MinerUExecution

    MinerUExecution.build_mineru_client = lambda self: FixtureMinerU()
    runpy.run_path("/app/scripts/dev/run_document_worker.py", run_name="__main__")
