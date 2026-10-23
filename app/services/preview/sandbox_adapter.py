"""生产进程适配器；批准的 launcher/validator 与隔离部署是外部启用前置。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import tempfile
import time

from pydantic import ValidationError

from app.services.preview.executor_protocol import (
    PROTOCOL, ExecutorCapabilities, ExecutorResult, OutputFile, render_request,
)
from app.services.preview.models import (
    PreviewFailure, PreviewPage, PreviewPolicy, PreviewResult, sha256, validate_docx, validate_result,
)


class SandboxWordPreviewProvider:
    """只有固定 hash 的批准部署 profile 可以启动进程，不提供裸引擎回退。"""

    def __init__(self, *, backend: str = "disabled", launcher: str = "", profile_path: str = "",
                 profile_id: str = "unconfigured", profile_sha256: str = "", temp_root: str | None = None):
        self.backend = backend
        self.launcher = Path(launcher) if launcher else None
        self.profile_path = Path(profile_path) if profile_path else None
        self.profile_id = profile_id
        self.profile_sha256 = profile_sha256
        self.temp_root = temp_root

    def _approved_launcher(self, policy: PreviewPolicy) -> Path:
        if self.backend == "disabled":
            raise PreviewFailure("preview_disabled" if policy.backend == "disabled" else "preview_provider_unavailable")
        if (policy.backend != "sandboxed" or policy.profile_id != self.profile_id
                or policy.profile_sha256 != self.profile_sha256):
            raise PreviewFailure("preview_profile_unavailable")
        if not self.launcher or not self.launcher.is_absolute() or not self.launcher.is_file() or self.launcher.is_symlink():
            raise PreviewFailure("preview_provider_unavailable")
        try:
            if not self.profile_path or not self.profile_path.is_absolute() or self.profile_path.is_symlink():
                raise PreviewFailure("preview_profile_unavailable")
            raw = self._read_regular(self.profile_path, 65536)
            profile = json.loads(raw)
            if sha256(raw) != policy.profile_sha256 or profile["profile_id"] != policy.profile_id:
                raise PreviewFailure("preview_profile_unavailable")
            if (profile["launcher_sha256"] != sha256(self._read_regular(self.launcher, 16 * 1024 * 1024))
                    or profile["protocol_version"] != PROTOCOL):
                raise PreviewFailure("preview_profile_unavailable")
            guarantees = {"no_network", "no_macros", "private_mount", "unprivileged", "resource_limits", "terminate_domain"}
            if (not isinstance(profile.get("approval_reference"), str) or not profile["approval_reference"].strip()
                    or any(profile.get("sandbox", {}).get(key) is not True for key in guarantees)):
                raise PreviewFailure("preview_sandbox_unavailable")
            for name in ("max_temp_bytes", "max_cpu_seconds", "max_memory_bytes", "max_processes"):
                if type(profile["limits"][name]) is not int or getattr(policy, name) > profile["limits"][name]:
                    raise PreviewFailure("preview_sandbox_unavailable")
            if not os.access(self.launcher, os.X_OK):
                raise PreviewFailure("preview_provider_unavailable")
            return self.launcher
        except PreviewFailure:
            raise
        except (OSError, ValueError, KeyError, TypeError):
            raise PreviewFailure("preview_profile_unavailable") from None

    def render(self, docx: bytes, *, policy: PreviewPolicy) -> PreviewResult:
        launcher = self._approved_launcher(policy)
        validate_docx(docx, policy)
        started = time.monotonic()
        budget = min(policy.timeout_seconds, policy.deadline_seconds)
        try:
            with tempfile.TemporaryDirectory(prefix="word-preview-", dir=self.temp_root) as tmp:
                root = Path(tmp)
                source = root / "source.docx"
                source.write_bytes(docx)
                source.chmod(0o400)
                (root / "out").mkdir(mode=0o700)
                capabilities_path = root / "capabilities.json"
                code = self._run([str(launcher), "describe", "--protocol", PROTOCOL,
                                  "--result", str(capabilities_path)], root, budget, policy)
                if code != 0:
                    raise PreviewFailure("preview_provider_unavailable")
                capabilities = ExecutorCapabilities.model_validate_json(self._read_regular(capabilities_path, 65536))
                if (capabilities.profile_id != policy.profile_id or capabilities.profile_sha256 != policy.profile_sha256):
                    raise PreviewFailure("preview_profile_unavailable")
                if not capabilities.pdf_full_decode or (policy.render_pages and not capabilities.png_decode):
                    raise PreviewFailure("preview_sandbox_unavailable")
                remaining = budget - (time.monotonic() - started)
                if remaining <= 0:
                    raise PreviewFailure("preview_timeout", retryable=True)
                request_path, result_path = root / "request.json", root / "result.json"
                input_hash = sha256(docx)
                request_path.write_text(json.dumps(render_request(input_hash, len(docx), policy, max(1, int(remaining * 1000)))), encoding="utf-8")
                code = self._run([str(launcher), "render", "--protocol", PROTOCOL, "--request", str(request_path),
                                  "--result", str(result_path)], root, remaining, policy)
                if code not in {0, 20, 21, 22, 23, 24, 25}:
                    raise PreviewFailure("preview_unexpected_error")
                result = ExecutorResult.model_validate_json(self._read_regular(result_path, 1_048_576))
                if (result.input_sha256 != input_hash or result.profile_id != policy.profile_id
                        or result.profile_sha256 != policy.profile_sha256
                        or (result.provider_id, result.provider_version) != (capabilities.provider_id, capabilities.provider_version)
                        or sha256(self._read_regular(source, policy.max_input_bytes)) != input_hash):
                    raise PreviewFailure("preview_output_invalid")
                if code != 0:
                    expected = {20: "preview_input_invalid", 21: "preview_resource_exceeded", 23: "preview_output_invalid",
                                24: "preview_engine_failed", 25: "preview_engine_failed"}
                    if code == 22 and result.error_code in {"preview_provider_unavailable", "preview_profile_unavailable", "preview_sandbox_unavailable"}:
                        expected[22] = result.error_code
                    if code not in expected:
                        raise PreviewFailure("preview_unexpected_error")
                    if (result.status != "error" or result.error_code != expected[code] or result.pdf is not None
                            or result.pages or result.page_count is not None):
                        raise PreviewFailure("preview_output_invalid")
                    raise PreviewFailure(expected[code], retryable=code == 25)
                if result.status != "ok" or result.error_code is not None or result.pdf is None or result.page_count is None:
                    raise PreviewFailure("preview_output_invalid")
                if result.page_count > policy.max_pages or len(result.pages) > policy.max_pages:
                    raise PreviewFailure("preview_resource_exceeded")
                if (len(result.pages) != result.page_count if policy.render_pages else bool(result.pages)):
                    raise PreviewFailure("preview_output_invalid")
                pdf = self._output(root, result.pdf, "out/preview.pdf", "application/pdf", policy.max_output_bytes)
                remaining_bytes = policy.max_output_bytes - len(pdf)
                pages = []
                for index, page in enumerate(result.pages):
                    if page.page_index != index:
                        raise PreviewFailure("preview_output_invalid")
                    content = self._output(root, page, f"out/page-{index:06d}.png", "image/png", remaining_bytes)
                    remaining_bytes -= len(content)
                    pages.append(PreviewPage(page_index=index, content=content, width=page.width, height=page.height))
                output = PreviewResult(pdf=pdf, page_count=result.page_count, pages=tuple(pages), provider_id=result.provider_id,
                                       provider_version=result.provider_version, profile_sha256=result.profile_sha256)
                validate_result(output, policy)
                if time.monotonic() - started >= budget:
                    raise PreviewFailure("preview_timeout", retryable=True)
                return output
        except PreviewFailure:
            raise
        except (ValidationError, ValueError, OSError, TypeError):
            raise PreviewFailure("preview_output_invalid") from None

    @staticmethod
    def _read_regular(path: Path, limit: int) -> bytes:
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)), "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise PreviewFailure("preview_output_invalid")
            if info.st_size > limit:
                raise PreviewFailure("preview_resource_exceeded")
            data = stream.read(limit + 1)
            if len(data) > limit:
                raise PreviewFailure("preview_resource_exceeded")
            return data

    def _output(self, root: Path, descriptor: OutputFile, expected_path: str, mime: str, budget: int) -> bytes:
        if descriptor.path != expected_path or descriptor.mime_type != mime or (root / "out").is_symlink():
            raise PreviewFailure("preview_output_invalid")
        content = self._read_regular(root / expected_path, budget)
        if len(content) != descriptor.size_bytes or sha256(content) != descriptor.sha256:
            raise PreviewFailure("preview_output_invalid")
        return content

    def _run(self, argv: list[str], root: Path, timeout: float, policy: PreviewPolicy) -> int:
        # 环境不继承宿主凭据；launcher 必须自行使用批准的绝对引擎路径。
        environment = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": str(root), "TMPDIR": str(root)}
        process = subprocess.Popen(argv, cwd=root, env=environment, shell=False, start_new_session=True,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + timeout
        try:
            while process.poll() is None:
                if time.monotonic() >= deadline:
                    raise PreviewFailure("preview_timeout", retryable=True)
                self._check_temp(root, policy.max_temp_bytes)
                time.sleep(min(0.02, max(0.001, deadline - time.monotonic())))
            self._check_temp(root, policy.max_temp_bytes)
            return process.returncode
        finally:
            # 即使父 launcher 已退出，也终止仍属于本次进程组的子进程。
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                pass
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=1)

    @staticmethod
    def _check_temp(root: Path, limit: int) -> None:
        total = 0
        for directory, dirs, files in os.walk(root, followlinks=False):
            for name in dirs + files:
                info = (Path(directory) / name).lstat()
                if stat.S_ISLNK(info.st_mode):
                    raise PreviewFailure("preview_output_invalid")
                total += info.st_size
                if total > limit:
                    raise PreviewFailure("preview_resource_exceeded")
