#!/usr/bin/env python3
"""在隔离的生产 Docker Compose 拓扑中验证启动初始化和动态模板目录。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

import requests
from docx import Document

from template_catalog_mineru_fixture import BODY_MARKER, CONTROL_DIR


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.services.auth.service import hash_password  # noqa: E402


DOCKERFILE = Path("docker/prod/Dockerfile")
COMPOSE = Path("docker/prod/docker-compose.yml")
SEED = Path("resources/template_configs/templates_manifest.yaml")
SOURCE_PDF = ROOT / "tests/fixtures/p1_translation_samples/pdfs/en-datasheet-smoke.pdf"
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TEMPLATE_ID = "catalog-compose"
TEMPLATE_LAYOUT = Path("resources/template_configs/catalog-compose.yaml")
TEMPLATE_ROUTE = f"/api/v1/templates/{TEMPLATE_ID}"
JOBS_ROUTE = "/api/v1/document-jobs"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def template_docx(version: int) -> bytes:
    document = Document()
    document.sections[0].header.paragraphs[0].text = f"Catalog template version {version}"
    result = BytesIO()
    document.save(result)
    return result.getvalue()


def check_wheelhouse(wheelhouse: Path) -> None:
    lock = (ROOT / "requirements/locks/cp311-linux-amd64.txt").read_text()
    expected = sorted(re.findall(r"--hash=sha256:([a-f0-9]{64})", lock))
    actual = sorted(hashlib.sha256(wheel.read_bytes()).hexdigest() for wheel in wheelhouse.glob("*.whl"))
    require(actual == expected, "wheelhouse 必须与仓库 Linux amd64 锁中登记的 wheel 哈希一一对应。")


class Compose:
    def __init__(self, context: str, directory: Path, wheelhouse: Path, *, image: str | None = None) -> None:
        self.project = f"md2word-catalog-{secrets.token_hex(6)}"
        self.image = image or f"{self.project}:candidate"
        self.docker = ["docker", "--context", context]
        self.command = [
            *self.docker, "compose", "--project-name", self.project,
            "--env-file", str(directory / ".env"), "-f", str(directory / COMPOSE),
            "-f", str(directory / "fixture.compose.json"),
        ]
        self.directory = directory
        self.wheelhouse = wheelhouse
        self.passwords = {role: secrets.token_urlsafe(24) for role in ("admin", "operator")}

    def prepare(self, *, invalid_auth_file: bool = False) -> None:
        for path in ("app", "scripts", "resources", "requirements/locks"):
            shutil.copytree(ROOT / path, self.directory / path, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(self.wheelhouse, self.directory / "requirements/wheels")
        for path in (COMPOSE, DOCKERFILE, ".dockerignore", "sitecustomize.py"):
            destination = self.directory / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / path, destination)

        deploy = self.directory / "deploy"
        deploy.mkdir()
        users = [
            {"id": f"fixture-{role}", "username": role, "password_hash": hash_password(password), "role": role,
             "tenant_id": "default", "company_id": "default", "status": "active"}
            for role, password in self.passwords.items()
        ]
        (deploy / "auth_internal_users.json").write_text(
            '{"users":' if invalid_auth_file else json.dumps({"users": users}), encoding="utf-8",
        )
        (self.directory / TEMPLATE_LAYOUT).write_text("schema_version: template-config/v1\n", encoding="utf-8")
        fixture = self.directory / "mineru_fixture.py"
        shutil.copyfile(Path(__file__).with_name("template_catalog_mineru_fixture.py"), fixture)
        env = {
            "APP_ENV": "prod",
            "APP_VERSION": self.project,
            "DEPLOYMENT_ID": self.project,
            "MD2WORD_IMAGE": self.image,
            "MD2WORD_API_BIND_HOST": "127.0.0.1",
            "MD2WORD_API_BIND_PORT": "0",
            "DATA_DIR": "/app/var",
            "JOBS_REPOSITORY_BACKEND": "mysql",
            "JOBS_MYSQL_HOST": "mysql",
            "JOBS_MYSQL_DATABASE": "md2word",
            "JOBS_MYSQL_USER": "md2word",
            "JOBS_MYSQL_PASSWORD": secrets.token_urlsafe(24),
            "MYSQL_ROOT_PASSWORD": secrets.token_urlsafe(24),
            "JOBS_ARTIFACT_STORAGE_BACKEND": "local_object",
            "JOBS_ARTIFACT_OBJECT_STORE_PATH": "/app/var/object_artifacts",
            "JOBS_WORKER_MODE": "external",
            "JOBS_ACCESS_MODE": "token",
            "JOBS_ACCESS_TOKEN": secrets.token_urlsafe(24),
            "ADMIN_TOKEN": secrets.token_urlsafe(24),
            "AUTH_JWT_SECRET_KEY": secrets.token_urlsafe(32),
            "AUTH_INTERNAL_USERS_FILE": "deploy/auth_internal_users.json",
            "DOCUMENT_JOBS_WORKER_BACKEND": "celery",
            "DOCUMENT_JOBS_CELERY_BROKER_URL": "redis://redis:6379/0",
            "DOCUMENT_JOBS_CELERY_RESULT_BACKEND": "redis://redis:6379/1",
            "MINERU_API_TOKEN": "local-fixture-only",
            "MINERU_POLL_INTERVAL_SECONDS": "5",
            "TEMPLATES_MANIFEST_PATH": str(SEED),
            "TEMPLATES_STORAGE_PATH": "/app/var/config/templates",
            "TEMPLATE_STATE_PATH": "/app/var/config/template_state.json",
            "DEFAULT_TRANSLATION_MODE": "direct",
            "TRANSLATION_PROVIDER_BACKEND": "disabled",
        }
        (self.directory / ".env").write_text("".join(f"{key}={value}\n" for key, value in env.items()))
        # Compose 插值优先读取宿主变量。测试用值也覆盖同名宿主变量。
        self.env = {**os.environ, **env}
        override = {"services": {service: {"platform": "linux/amd64"} for service in ("api", "worker", "redis", "mysql")}}
        override["services"]["worker"].update(
            command=["python", "/fixture/mineru_fixture.py"],
            volumes=[{"type": "bind", "source": str(fixture), "target": "/fixture/mineru_fixture.py",
                      "read_only": True, "bind": {"create_host_path": False}}],
        )
        (self.directory / "fixture.compose.json").write_text(json.dumps(override))

    def run(self, *args, capture=False, check=True):
        return subprocess.run(
            [*self.command, *args], env=self.env, cwd=self.directory,
            text=True, check=check, stdout=subprocess.PIPE if capture else None,
        ).stdout

    def verify_health_dependency(self) -> None:
        services = json.loads(self.run("config", "--format", "json", capture=True))["services"]
        api = services["api"]
        require("app.main:create_app" in api["command"] and "--factory" in api["command"],
                "API 应通过 Uvicorn 工厂完成启动初始化。")
        require(services["worker"]["depends_on"]["api"]["condition"] == "service_healthy",
                "合并后的 Compose 配置应要求 API 健康后才能启动 Worker。")
        require("/api/v1/health/live" in " ".join(api["healthcheck"]["test"]),
                "API 应使用生产环境的存活探针。")

    def cold_start(self) -> dict:
        self.run("up", "-d", "--no-build", "--wait", "--wait-timeout", "240")
        containers = self.application_containers()
        api_state = containers["api"]["State"]
        worker_started = containers["worker"]["State"]["StartedAt"]
        successful_probe = next((probe for probe in api_state["Health"]["Log"] if probe["ExitCode"] == 0), None)
        require(api_state["Health"]["Status"] == "healthy" and successful_probe is not None,
                "API 未记录成功的健康检查。")
        healthy_at = successful_probe["End"]
        require(datetime.fromisoformat(healthy_at) <= datetime.fromisoformat(worker_started),
                "Worker 在 API 健康检查成功前已启动。")
        restart_counts = {name: container["RestartCount"] for name, container in containers.items()}
        require(all(count == 0 for count in restart_counts.values()), "空库首次启动期间 API 或 Worker 发生重启。")
        self.wait_worker()
        return {"api_started_at": api_state["StartedAt"], "api_healthcheck_succeeded_at": healthy_at,
                "worker_started_at": worker_started, "restart_counts": restart_counts}

    def assert_initialization_failure_blocks_worker(self) -> dict:
        failed_up = subprocess.run(
            [*self.command, "up", "-d", "--no-build", "--pull", "never", "--wait", "--wait-timeout", "240"],
            env=self.env, cwd=self.directory, text=True, capture_output=True, check=False,
        )
        api = self.container("api")
        worker = self.container("worker")
        require(failed_up.returncode != 0 and api is not None,
                "API 初始化失败场景未按预期拒绝 Compose 启动。")
        api_health = api["State"]["Health"]["Status"]
        require(api_health != "healthy", "错误的内部账号配置未阻断 API 健康探针。")
        logs = self.run("logs", "--no-color", "--tail", "80", "api", capture=True)
        reason = "AUTH_INTERNAL_USERS_FILE 不是合法 JSON。"
        require(reason in logs, "API 日志缺少预期的内部账号初始化失败原因。")
        if worker is not None:
            require(worker["State"]["Status"] == "created" and worker["RestartCount"] == 0,
                    "API 初始化失败时 Worker 容器已被启动。")
        return {"compose_exit_code": failed_up.returncode, "api_health": api_health, "api_error": reason,
                "worker_state": worker["State"]["Status"] if worker is not None else "absent"}

    def worker_python(self, code: str, *args: str) -> str:
        return self.run("exec", "-T", "worker", "python", "-c", code, *args, capture=True).strip()

    def wait_worker(self) -> None:
        code = (
            "import socket; from app.workers.celery_app import celery_app; "
            "assert celery_app.control.ping(destination=['celery@' + socket.gethostname()], timeout=3), 'Celery 无响应'"
        )
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            result = subprocess.run(
                [*self.command, "exec", "-T", "worker", "python", "-c", code], env=self.env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                return
            time.sleep(2)
        raise TimeoutError("隔离 Celery Worker 未就绪。")

    def container(self, service: str) -> dict | None:
        container_id = self.run("ps", "--all", "--quiet", service, capture=True).strip()
        if not container_id:
            return None
        return json.loads(subprocess.check_output([*self.docker, "inspect", container_id], text=True))[0]

    def application_containers(self) -> dict:
        api = self.container("api")
        worker = self.container("worker")
        require(api is not None and worker is not None and api["Id"] != worker["Id"],
                "API 和 Worker 必须运行在独立容器。")
        return {"api": api, "worker": worker}

    def restart(self, service: str) -> dict:
        before = self.application_containers()
        self.run("restart", service)
        self.run("up", "-d", "--no-build", "--pull", "never", "--wait", "--wait-timeout", "180")
        self.wait_worker()
        after = self.application_containers()
        for name in before:
            require(before[name]["Id"] == after[name]["Id"], f"容器 {name} 被意外替换。")
            restarted = before[name]["State"]["StartedAt"] != after[name]["State"]["StartedAt"]
            require(restarted == (name == service), f"预期只重启 {service}，容器 {name} 状态不符。")
        return {"service": service, "container_id": after[service]["Id"],
                "before": before[service]["State"]["StartedAt"], "after": after[service]["State"]["StartedAt"]}

    def topology(self) -> dict:
        containers = list(self.application_containers().values())
        require(containers[0]["Image"] == containers[1]["Image"], "API 和 Worker 必须使用同一镜像身份。")
        processes = {}
        for service in ("api", "worker"):
            code = (
                "import hashlib, json, os, platform, sys; from pathlib import Path; p=Path(sys.argv[1]); "
                "print(json.dumps({'uid': os.getuid(), 'seed_writable': os.access(p, os.W_OK), "
                "'architecture': platform.machine(), 'seed_sha256': hashlib.sha256(p.read_bytes()).hexdigest()}))"
            )
            process = json.loads(self.run("exec", "-T", service, "python", "-c", code, str(SEED), capture=True))
            require(process["uid"] != 0 and not process["seed_writable"] and process["architecture"] == "x86_64",
                    f"{service} 应运行在 Linux amd64，使用非 root 用户且 bundled seed 不可写。")
            require(process["seed_sha256"] == hashlib.sha256((ROOT / SEED).read_bytes()).hexdigest(),
                    f"{service} bundled seed 的 SHA-256 与仓库不一致。")
            processes[service] = process
        writable_volumes = [
            {(mount["Name"], mount["Destination"]) for mount in container["Mounts"] if mount["RW"] and mount["Type"] == "volume"}
            for container in containers
        ]
        require(writable_volumes[0] == writable_volumes[1] == {(f"{self.project}_md2word-var", "/app/var")},
                "API 和 Worker 应仅共享生产运行卷 /app/var。")
        return {"image_id": containers[0]["Image"], "processes": processes,
                "shared_runtime_volume": f"{self.project}_md2word-var"}

    def release(self, job: dict) -> None:
        self.worker_python(
            "from pathlib import Path; import sys; p = Path(sys.argv[1]); p.parent.mkdir(exist_ok=True); p.touch()",
            str(CONTROL_DIR / job["id"]),
        )

    def template_assets(self) -> dict:
        result = self.worker_python(
            "from pathlib import Path; import hashlib, json, sys; root=Path('/app/var/config/templates') / sys.argv[1]; "
            "print(json.dumps({str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() "
            "for p in root.rglob('*.docx')}))",
            TEMPLATE_ID,
        )
        return json.loads(result)


class Acceptance:
    def __init__(self, compose: Compose, client: requests.Session) -> None:
        self.compose = compose
        self.client = client
        self.refresh_address()
        self.admin = self.login("admin")
        self.operator = self.login("operator")
        self.jobs: list[dict] = []

    def refresh_address(self) -> None:
        address = self.compose.run("port", "api", "8000", capture=True).strip()
        require(address.startswith("127.0.0.1:"), "测试 API 端口必须绑定本地回环地址。")
        self.base = f"http://{address}"
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                response = self.client.get(f"{self.base}/api/v1/health/live", timeout=3)
            except requests.ConnectionError:
                pass
            else:
                if response.status_code == 200:
                    return
            time.sleep(1)
        raise TimeoutError("隔离 API 在 Docker 发布的回环端口不可用。")

    def request(self, method: str, path: str, expected: int | tuple[int, ...], **kwargs):
        if path.startswith("http://"):
            url = urlsplit(path)
            path = url.path + (f"?{url.query}" if url.query else "")
        response = self.client.request(method, self.base + path, timeout=25, allow_redirects=False, **kwargs)
        acceptable = (expected,) if isinstance(expected, int) else expected
        require(response.status_code in acceptable,
                f"{method} {path.split('?')[0]} 返回 {response.status_code}，预期 {acceptable}。{response.text[:500]}")
        return response

    def login(self, role: str) -> dict:
        body = {"username": role, "password": self.compose.passwords[role]}
        response = self.request("POST", "/api/v1/auth/login", 200, json=body)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def initialized_data(self) -> dict:
        accounts = {}
        for role, headers in (("admin", self.admin), ("operator", self.operator)):
            account = self.request("GET", "/api/v1/auth/me", 200, headers=headers).json()
            require(account["id"] == f"fixture-{role}" and account["role"] == role, "内部账号导入结果不符。")
            accounts[role] = account["id"]

        acceptance_runs = self.request("GET", "/api/v1/acceptance/runs", 200, headers=self.admin).json()["items"]
        require({item["tier"] for item in acceptance_runs} == {"P0", "P1", "P2"}, "Acceptance 初始记录不完整。")
        defaults = {}
        for name, route, key in (
            ("term_rules", "/api/v1/term-rule-sets", "id"),
            ("translation_terms", "/api/v1/translation-term-sets", "set_id"),
            ("translation_profiles", "/api/v1/translation-profiles", "id"),
        ):
            items = self.request("GET", route, 200, headers=self.admin).json()["items"]
            require(items, f"未读取到 {name} 初始记录。")
            defaults[name] = {}
            for item in items:
                resource_id = item[key]
                detail = self.request("GET", f"{route}/{resource_id}", 200, headers=self.admin).json()
                defaults[name][resource_id] = self.version_snapshot(detail["versions"])
                require(defaults[name][resource_id]["default"] == detail["default_version"],
                        f"{resource_id} 默认指针与版本状态不一致。")

        templates = self.request("GET", "/api/v1/templates", 200, headers=self.admin).json()["items"]
        selected = [item for item in templates if item["is_default"]]
        require(len(selected) == 1, "全局默认模板缺失或不唯一。")
        template = selected[0]
        versions = self.request("GET", f"/api/v1/templates/{template['id']}/versions", 200,
                                headers=self.admin).json()["items"]
        template_snapshot = self.version_snapshot(versions)
        require(template_snapshot["default"] == template["version"], "模板目录默认指针与版本状态不一致。")
        defaults["template"] = {"id": template["id"], **template_snapshot}
        return {"accounts": accounts, "defaults": defaults,
                "acceptance_runs": {item["id"]: item["updated_at"] for item in acceptance_runs}}

    @staticmethod
    def version_snapshot(versions: list[dict]) -> dict:
        default = [item for item in versions if item["is_default"] and item["status"] == "published"]
        require(len(default) == 1 and default[0]["snapshot_hash"], "已发布默认版本或其快照摘要缺失。")
        return {"default": default[0]["version"], "versions": {
            str(item["version"]): {"status": item["status"], "snapshot_hash": item["snapshot_hash"]} for item in versions
        }}

    def upload_pdf(self, headers: dict, *, hold=False) -> str:
        content = SOURCE_PDF.read_bytes()
        filename = "hold-fixture.pdf" if hold else "fixture.pdf"
        registration = self.request(
            "POST", "/api/v1/files/upload-url", 201, headers=headers,
            json={"filename": filename, "mime_type": "application/pdf", "size_bytes": len(content)},
        ).json()
        self.request("PUT", registration["upload_url"], 201,
                     headers={**headers, "Content-Type": "application/pdf"}, data=content)
        return registration["file_id"]

    def create_job(self, headers: dict, *, selection: str | None = None, hold=False, expected: int | tuple[int, ...] = 201):
        body = {"source_file_id": self.upload_pdf(headers, hold=hold), "mode": "direct_pdf_to_word", "document_language": "en"}
        if selection is not None:
            body["template_version_id"] = selection
        response = self.request("POST", JOBS_ROUTE, expected, headers=headers, json=body)
        return response.json()["job"] if expected == 201 else None

    def wait_job(self, job: dict, headers: dict, *, held=False) -> dict:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            current = self.request("GET", f"{JOBS_ROUTE}/{job['id']}", 200, headers=headers).json()
            if held and current["status"] == "running" and current["stage"] == "parsing" and current["mineru_batch_id"]:
                return current
            if current["status"] in {"succeeded", "failed", "canceled"}:
                require(not held, f"任务 {job['id']} 在测试放行前已进入 {current['status']}。")
                return current
            time.sleep(1)
        raise TimeoutError(f"任务 {job['id']} 未在时限内进入预期状态。")

    def download_docx(self, job_id: str, headers: dict) -> bytes:
        grant = self.request("GET", f"{JOBS_ROUTE}/{job_id}/download-url", 200, headers=headers).json()
        return self.request("GET", grant["download_url"], 200).content

    def successful_docx(self, job: dict, headers: dict, version: int, status: str = "published") -> dict:
        done = self.wait_job(job, headers)
        require(done["status"] == "succeeded", f"任务 {job['id']} 生成失败：{done['error_code']} {done['error_message']}")
        bound = done["request_snapshot"]["resources"]["template"]
        require(bound["resource_id"] == TEMPLATE_ID and bound["version"] == str(version) and bound["status"] == status,
                f"任务 {job['id']} 的模板快照与预期不一致。")
        content = self.download_docx(job["id"], headers)
        document = Document(BytesIO(content))
        require(any(BODY_MARKER in paragraph.text for paragraph in document.paragraphs),
                f"任务 {job['id']} 的 DOCX 缺少 MinerU 夹具正文。")
        require(any(f"Catalog template version {version}" in paragraph.text
                    for section in document.sections for paragraph in section.header.paragraphs),
                f"任务 {job['id']} 的 DOCX 页眉未使用绑定模板。")
        evidence = {"id": job["id"], "template_version_id": done["template_version_id"],
                    "snapshot_status": status, "snapshot_hash": bound["snapshot_hash"],
                    "docx_sha256": hashlib.sha256(content).hexdigest()}
        self.jobs.append(evidence)
        return evidence

    def upload_template(self, version: int) -> None:
        route = "/api/v1/templates" if version == 1 else f"{TEMPLATE_ROUTE}/versions"
        data = {"layout_config_path": str(TEMPLATE_LAYOUT)}
        if version == 1:
            data.update(template_id=TEMPLATE_ID, name="Compose fixture")
        result = self.request("POST", route, 201, headers=self.admin, data=data, files={
            "template": (f"catalog-v{version}.docx", template_docx(version), DOCX_TYPE),
        }).json()
        require(result["version"] == version, f"模板上传未得到版本 {version}。")
        if version > 1:
            require(result["status"] == "draft", "新上传的版本应是 draft。")

    def check_legacy_replacement(self) -> None:
        result = self.request("PUT", f"{TEMPLATE_ROUTE}/file", 200, headers=self.admin, files={
            "template": ("catalog-v3.docx", template_docx(3), DOCX_TYPE),
        }).json()
        require(result["version"] == 1, "旧文件替换入口不得改变已发布的默认版本。")
        versions = self.request("GET", f"{TEMPLATE_ROUTE}/versions", 200, headers=self.admin).json()["items"]
        require({item["version"]: item["status"] for item in versions} == {1: "published", 2: "published", 3: "draft"},
                "旧文件替换入口应登记第三个草稿，并保留已有版本。")

    def publish(self, version: int, job: dict, *, make_default: bool) -> None:
        result = self.request("POST", f"{TEMPLATE_ROUTE}/versions/{version}/publish", 200, headers=self.admin, json={
            "make_default": make_default, "verification_job_id": job["id"],
            "publish_reason": "Compose 版本验证", "verification_note": "已核对验证任务的 DOCX 页眉和正文",
        }).json()
        require(result["status"] == "published", f"模板版本 {version} 未发布。")

    def assert_catalog(self, *, visible: bool) -> None:
        items = self.request("GET", "/api/v1/templates", 200, headers=self.operator).json()["items"]
        target = [item for item in items if item["id"] == TEMPLATE_ID]
        if visible:
            require(len(target) == 1 and target[0]["is_default"] and target[0]["version"] == 1,
                    "重读目录未保留自定义模板和版本默认选择。")
        else:
            require(not target, "停用或删除模板仍出现在公开目录中。")
            self.request("GET", TEMPLATE_ROUTE, 404, headers=self.operator)
            self.request("GET", f"{TEMPLATE_ROUTE}/download", 404, headers=self.operator)

    def assert_new_bindings_rejected(self, source: dict) -> None:
        for selection in (TEMPLATE_ID, f"{TEMPLATE_ID}@1"):
            self.create_job(self.admin, selection=selection, expected=404)
        self.request("POST", f"{JOBS_ROUTE}/{source['id']}/clone", 404,
                     headers=self.admin, json={"config_strategy": "keep_source_snapshot"})

    def run(self) -> dict:
        before = self.compose.topology()
        cold_data = self.initialized_data()
        self.upload_template(1)
        self.create_job(self.operator, selection=f"{TEMPLATE_ID}@1", expected=(400, 403))
        validation = self.create_job(self.admin, selection=f"{TEMPLATE_ID}@1")
        self.successful_docx(validation, self.admin, 1, status="draft")
        self.publish(1, validation, make_default=True)
        self.request("PATCH", f"{TEMPLATE_ROUTE}/default", 200, headers=self.admin)
        retained_job = self.successful_docx(self.create_job(self.operator), self.operator, 1)

        self.upload_template(2)
        draft2 = self.create_job(self.admin, selection=f"{TEMPLATE_ID}@2")
        self.successful_docx(draft2, self.admin, 2, status="draft")
        self.publish(2, draft2, make_default=False)
        self.check_legacy_replacement()
        existing_data = self.initialized_data()
        restarts = []
        for service in ("api", "worker"):
            restart = self.compose.restart(service)
            self.refresh_address()
            self.admin = self.login("admin")
            self.operator = self.login("operator")
            self.assert_catalog(visible=True)
            require(self.initialized_data() == existing_data, f"重启 {service} 后，既有账号、默认资源或版本记录发生变化。")
            job_id = retained_job["id"]
            previous_job = self.request("GET", f"{JOBS_ROUTE}/{job_id}", 200, headers=self.operator).json()
            artifact_hash = hashlib.sha256(self.download_docx(job_id, self.operator)).hexdigest()
            require(previous_job["status"] == "succeeded"
                    and previous_job["template_version_id"] == retained_job["template_version_id"]
                    and previous_job["request_snapshot"]["resources"]["template"]["snapshot_hash"] == retained_job["snapshot_hash"]
                    and artifact_hash == retained_job["docx_sha256"], f"重启 {service} 后，既有任务或 DOCX 发生变化。")
            subsequent_job = self.successful_docx(self.create_job(self.operator), self.operator, 1)
            restarts.append({**restart, "retained_job_id": job_id, "retained_docx_sha256": artifact_hash,
                             "subsequent_job_id": subsequent_job["id"]})

        self.request("PATCH", "/api/v1/templates/default/default", 200, headers=self.admin)
        closed = self.create_job(self.admin, selection=f"{TEMPLATE_ID}@2", hold=True)
        self.wait_job(closed, self.admin, held=True)
        self.request("POST", f"{TEMPLATE_ROUTE}/versions/2/disable", 200, headers=self.admin)
        self.compose.release(closed)
        failed = self.wait_job(closed, self.admin)
        require(failed["status"] == "failed" and failed["failed_stage"] == "rendering",
                f"显式禁用已绑定版本未在渲染阶段拒绝任务 {closed['id']}。")
        events = self.request("GET", f"{JOBS_ROUTE}/{closed['id']}/events", 200, headers=self.admin).json()["items"]
        require(any("resource_snapshot_invalid_status" in event["payload"].get("blocking_quality_flags", [])
                    for event in events), "显式禁用未记录稳定原因码。")

        retained = self.compose.template_assets()
        require(len(retained) == 3, "已登记的三个 DOCX 版本应存在于共享卷。")
        for operation in ("disable", "delete"):
            if operation == "delete":
                self.request("PATCH", TEMPLATE_ROUTE, 200, headers=self.admin, json={"enabled": True})
            held = self.create_job(self.admin, selection=f"{TEMPLATE_ID}@1", hold=True)
            self.wait_job(held, self.admin, held=True)
            if operation == "disable":
                self.request("PATCH", TEMPLATE_ROUTE, 200, headers=self.admin, json={"enabled": False})
            else:
                self.request("DELETE", TEMPLATE_ROUTE, 200, headers=self.admin)
            self.assert_catalog(visible=False)
            self.assert_new_bindings_rejected(held)
            self.compose.release(held)
            self.successful_docx(held, self.admin, 1)
        require(self.compose.template_assets() == retained, "目录删除后历史 DOCX 字节发生变化。")
        after = self.compose.topology()
        require(after == before, "验收前后的镜像、运行用户或 bundled seed 哈希不一致。")
        return {"topology_before": before, "topology_after": after, "restarts": restarts, "jobs": self.jobs,
                "cold_initialized_data": cold_data, "retained_data": existing_data,
                "disabled_version_job_id": closed["id"], "disabled_version_reason": "resource_snapshot_invalid_status",
                "retained_assets": retained}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker-context", required=True, help="隔离的 Docker context")
    parser.add_argument("--wheelhouse", type=Path, required=True, help="生产 Linux amd64 锁对应的 wheel 目录")
    parser.add_argument("--report", type=Path, help="可选的 JSON 验收证据路径")
    args = parser.parse_args()
    wheelhouse = args.wheelhouse.resolve(strict=True)
    check_wheelhouse(wheelhouse)
    scratch = ROOT / "tests/tmp"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="template-catalog-compose-", dir=scratch) as temporary:
        directory = Path(temporary)
        compose = Compose(args.docker_context, directory / "healthy", wheelhouse)
        compose.prepare()
        compose.verify_health_dependency()
        compose.run("build", "api")
        try:
            try:
                cold_start = compose.cold_start()
                with requests.Session() as client:
                    client.trust_env = False
                    report = Acceptance(compose, client).run()
                    report["cold_start"] = cold_start
            except (Exception, KeyboardInterrupt):
                compose.run("logs", "--no-color", "--tail", "50", check=False)
                raise
            finally:
                compose.run("down", "--volumes", "--remove-orphans")

            failed = Compose(args.docker_context, directory / "invalid-auth", wheelhouse, image=compose.image)
            failed.prepare(invalid_auth_file=True)
            failed.verify_health_dependency()
            try:
                report["initialization_failure"] = failed.assert_initialization_failure_blocks_worker()
            except (Exception, KeyboardInterrupt):
                failed.run("logs", "--no-color", "--tail", "50", check=False)
                raise
            finally:
                failed.run("down", "--volumes", "--remove-orphans")
            if args.report is not None:
                args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
            print(json.dumps(report, ensure_ascii=False))
        finally:
            subprocess.run([*compose.docker, "image", "rm", compose.image], check=True)


if __name__ == "__main__":
    main()
