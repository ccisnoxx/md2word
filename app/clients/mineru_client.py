from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class MinerUError(RuntimeError):
    pass


class MinerUClient:
    API_BASE = "https://mineru.net/api/v4"
    PATH_BATCH_UPLOAD = "/file-urls/batch"

    def __init__(self, *, api_token: str, model_version: str = "vlm") -> None:
        if not api_token:
            raise ValueError("api_token 不能为空")
        self.api_token = api_token
        self.model_version = model_version
        self.logger = logging.getLogger("system")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_token}",
            }
        )
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST", "PUT"}),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def upload_files_batch(
        self,
        file_paths: list[Path],
        *,
        task_uuids: list[str] | None = None,
        enable_formula: bool = True,
        enable_table: bool = True,
        language: str = "en",
        callback: str | None = None,
        seed: str | None = None,
    ) -> tuple[str, list[str]]:
        if not file_paths:
            raise ValueError("文件列表不能为空")
        if len(file_paths) > 200:
            raise ValueError("单次申请链接不能超过 200 个")

        request_files: list[dict[str, Any]] = []
        for index, file_path in enumerate(file_paths):
            if not file_path.exists() or not file_path.is_file():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            entry: dict[str, Any] = {"name": file_path.name, "is_ocr": True}
            if task_uuids and index < len(task_uuids):
                entry["data_id"] = task_uuids[index]
            request_files.append(entry)

        payload: dict[str, Any] = {
            "files": request_files,
            "model_version": self.model_version,
            "enable_formula": enable_formula,
            "enable_table": enable_table,
            "language": language,
        }
        if callback:
            payload["callback"] = callback
        if seed:
            payload["seed"] = seed

        response = self.session.post(self._url(self.PATH_BATCH_UPLOAD), json=payload, timeout=30)
        result = self._check_response(response, "申请上传URL")
        data = result.get("data") or {}
        batch_id = data.get("batch_id")
        file_urls = data.get("file_urls") or []
        if not batch_id:
            raise MinerUError("申请上传URL失败: 响应缺少 batch_id")
        if len(file_urls) != len(file_paths):
            raise MinerUError(f"URL数量({len(file_urls)})与文件数量({len(file_paths)})不匹配")

        for file_path, upload_url in zip(file_paths, file_urls):
            with file_path.open("rb") as handle:
                put_response = requests.put(upload_url, data=handle, timeout=300)
            if put_response.status_code != 200:
                raise MinerUError(f"上传失败: {file_path.name}, HTTP {put_response.status_code}")

        self.logger.info("MinerU upload_files_batch submitted batch_id=%s files=%s", batch_id, len(file_urls))
        return str(batch_id), [str(url) for url in file_urls]

    def _url(self, path: str) -> str:
        return f"{self.API_BASE}{path}"

    @staticmethod
    def _check_response(response: requests.Response, action: str) -> dict[str, Any]:
        if response.status_code != 200:
            raise MinerUError(f"{action}失败: HTTP {response.status_code}, body={response.text}")
        try:
            result = response.json()
        except ValueError as exc:
            raise MinerUError(f"{action}失败: 响应不是合法 JSON") from exc
        if result.get("code") != 0:
            raise MinerUError(
                f"{action}失败: code={result.get('code')}, msg={result.get('msg')}, trace_id={result.get('trace_id')}"
            )
        return result
