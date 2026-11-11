"""用临时仓库验证卫生规则、真实 index 与提交钩子的失败边界。"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from scripts.ops import check_repository_hygiene as hygiene


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/ops/check_repository_hygiene.py"
HOOK = ROOT / ".githooks/pre-commit"
CONFIG = ROOT / ".gitleaks.toml"
HASH_FILES = (
    ".trellis/tasks/archive/2026-10/10-22-tr-406-partial-batch-failure-semantics/dependency-intermediate-validation.json",
    ".trellis/tasks/archive/2026-10/10-23-rnd-503-image-group-caption-rendering/b1-build-manifest.json",
    ".trellis/tasks/11-06-dependency-image-baseline/research/source-inputs.json",
)


def private_ip():
    return ".".join(map(str, (10, 20, 30, 40)))


def user_path():
    return "/" + "Users/fixture-developer/private"


def fake_token():
    # 运行时生成伪造内容，不复制历史凭证，也不让测试源码本身包含完整 token。
    return "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"


class HygieneRuleTests(unittest.TestCase):
    def test_real_user_paths_and_json_escapes(self):
        paths = [
            user_path(), "/" + "home/fixture-developer/work",
            "C:" + "\\" + "Users\\fixture-developer\\work",
            "C:" + "\\\\" + "Users\\\\fixture-developer\\\\work",
            "D:" + "/" + "Users/fixture-developer/work",
            user_path().replace("/", "\\/"),
        ]
        for path in paths:
            with self.subTest(style=paths.index(path)):
                hits, text = hygiene.findings("notes.txt", path.encode())
                self.assertTrue(text)
                self.assertEqual(hits, [(1, "user-home-path")])

    def test_placeholders_and_non_private_candidates(self):
        safe = "\n".join([
            "${PROJECT_ROOT}/app", "${DEVELOPER_HOME}/work", "/" + "Users/${USER}/work",
            "/" + "home/<username>/work", "C:" + "\\Users\\$USER$\\work",
            "/root/deploy/project",
            "127.0.0.1", "0.0.0.0", "1.2.3", "10.999.0.1", "v10.20.30.40", "8.8.8.8",
        ])
        self.assertEqual(hygiene.findings("docs/check.md", safe.encode()), ([], True))

    def test_rfc1918_boundaries(self):
        for octets, expected in [
            ((10, 0, 0, 1), True), ((172, 16, 0, 1), True), ((172, 31, 255, 254), True),
            ((192, 168, 1, 1), True), ((172, 15, 0, 1), False), ((172, 32, 0, 1), False),
            ((192, 169, 1, 1), False),
        ]:
            hits, _ = hygiene.findings("config.txt", ".".join(map(str, octets)).encode())
            self.assertEqual(bool(hits), expected)

    def test_exact_deployment_line_fingerprints(self):
        for path, allowed in hygiene.PRIVATE_IP_EXCEPTIONS.items():
            lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
            found = 0
            for line in lines:
                if hashlib.sha256(line.encode()).hexdigest() in allowed:
                    found += 1
                    self.assertEqual(hygiene.findings(path, line.encode())[0], [])
                    self.assertEqual(hygiene.findings("other.txt", line.encode())[0], [(1, "private-ip")])
                    self.assertEqual(hygiene.findings(path, (line + " ").encode())[0], [(1, "private-ip")])
            self.assertEqual(found, len(allowed))

    def test_temporary_name_and_binary_boundary(self):
        self.assertEqual(hygiene.findings("temp.TMP", b"\0")[0], [(1, "temporary-file")])
        self.assertEqual(hygiene.findings("notes.md", b"mention .tmp"), ([], True))
        self.assertEqual(hygiene.findings("asset.bin", b"\0"), ([], False))
        self.assertEqual(hygiene.findings("legacy.txt", b"\xff"), ([], False))


class TemporaryRepositoryCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="repository-hygiene-test-")
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        self.env = os.environ.copy()
        for key in (
            "GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX",
            "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        ):
            self.env.pop(key, None)
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        self.git("init", "--quiet")

    def git(self, *args):
        result = subprocess.run(["git", *args], cwd=self.repo, env=self.env, capture_output=True, check=True)
        return result.stdout

    def write(self, name, text):
        file = self.repo / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8")

    def check(self, *args):
        return subprocess.run([sys.executable, str(CHECKER), *args], cwd=self.repo, env=self.env, capture_output=True, text=True)

    def commit_fixture(self):
        self.git("-c", "user.name=卫生检查夹具", "-c", "user.email=fixture@example.invalid", "-c",
                 "core.hooksPath=disabled-hooks", "commit", "--quiet", "-m", "夹具基线")

    def install_hook_files(self):
        for source, target in ((CHECKER, "scripts/ops/check_repository_hygiene.py"),
                               (HOOK, ".githooks/pre-commit"), (CONFIG, ".gitleaks.toml")):
            destination = self.repo / target
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    def run_hook(self):
        before = self.git("write-tree")
        result = subprocess.run([sys.executable, str(self.repo / ".githooks/pre-commit")],
                                cwd=self.repo, env=self.env, capture_output=True, text=True)
        self.assertEqual(self.git("write-tree"), before, "钩子不得改变暂存树")
        return result


class IndexTests(TemporaryRepositoryCase):
    def test_initial_index_full_blob_and_partial_staging(self):
        path = "space name.txt"
        self.write(path, user_path())
        self.git("add", "--", path)
        self.write(path, "干净工作树")
        before = self.git("write-tree")
        result = self.check("--staged")
        self.assertEqual(result.returncode, 1)
        self.assertIn("user-home-path", result.stdout)
        self.assertIn(path, result.stdout)
        self.assertNotIn(user_path(), result.stdout + result.stderr)
        self.assertEqual(self.git("write-tree"), before)
        self.git("add", "--", path)
        self.write(path, user_path())
        self.assertEqual(self.check("--staged").returncode, 0)
        self.assertEqual(self.check("--tracked").returncode, 1)

    def test_staged_delete_rename_and_empty_changes(self):
        self.write("old.txt", "旧内容")
        self.git("add", "--", "old.txt")
        self.commit_fixture()
        self.git("mv", "--", "old.txt", "new space.TMP")
        self.assertIn("temporary-file", self.check("--staged").stdout)
        self.commit_fixture()
        self.git("rm", "--", "new space.TMP")
        self.assertEqual(self.check("--staged").returncode, 0)
        self.commit_fixture()
        self.assertEqual(self.check("--staged").returncode, 0)

    def test_added_unchanged_lines_are_still_checked(self):
        self.write("old.txt", user_path() + "\n原始行\n")
        self.git("add", "old.txt")
        self.commit_fixture()
        self.write("old.txt", user_path() + "\n新行\n")
        self.git("add", "old.txt")
        self.assertEqual(self.check("--staged").returncode, 1)

    def test_newline_name_uses_nul_git_interfaces(self):
        path = "odd\nname.txt"
        self.write(path, private_ip())
        self.git("add", "--", path)
        result = self.check("--staged")
        self.assertEqual(result.returncode, 1)
        self.assertIn(json.dumps(path), result.stdout)
        self.assertNotIn(private_ip(), result.stdout + result.stderr)

    def test_explicit_candidates_missing_files_and_git_errors(self):
        self.write("candidate.txt", private_ip())
        self.assertEqual(self.check("--tracked").returncode, 0)
        self.assertEqual(self.check("--files", "candidate.txt").returncode, 1)
        self.assertEqual(self.check("--files", "../outside").returncode, 2)
        self.git("add", "candidate.txt")
        (self.repo / "candidate.txt").unlink()
        self.assertIn("worktree-read-failed", self.check("--tracked").stdout)
        self.env["GIT_INDEX_FILE"] = str(self.repo / "broken-index")
        (self.repo / "broken-index").write_bytes(b"broken")
        result = self.check("--staged")
        self.assertEqual(result.returncode, 2)
        self.assertIn("git-read-failed", result.stderr)

    def test_hook_missing_scanner_and_version_mismatch_fail(self):
        self.install_hook_files()
        binary = self.repo / "bin"
        binary.mkdir()
        (binary / "git").symlink_to(shutil.which("git"))
        self.env["PATH"] = str(binary)
        result = self.run_hook()
        self.assertEqual(result.returncode, 2)
        self.assertIn("scanner-missing", result.stderr)
        scanner = binary / "gitleaks"
        scanner.write_text("#!/bin/sh\nprintf '%s\\n' '0.0.0'\n", encoding="utf-8")
        scanner.chmod(0o755)
        result = self.run_hook()
        self.assertEqual(result.returncode, 2)
        self.assertIn("scanner-version", result.stderr)


class GitleaksHookTests(TemporaryRepositoryCase):
    def setUp(self):
        super().setUp()
        scanner = shutil.which("gitleaks")
        if scanner is None:
            self.skipTest("未安装固定 Gitleaks；实际工具验收尚未执行")
        version = subprocess.run([scanner, "version"], capture_output=True, text=True, check=True)
        if version.stdout.strip() != "8.30.1":
            self.skipTest("Gitleaks 版本不是 8.30.1；实际工具验收尚未执行")
        self.install_hook_files()

    def test_hook_scans_staged_secrets_and_never_echoes_token(self):
        token = fake_token()
        self.write("credential.txt", "token = " + token + " # gitleaks:allow\n")
        self.git("add", "credential.txt")
        self.write("credential.txt", "干净工作树\n")
        result = self.run_hook()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("github-pat", result.stdout)
        self.assertNotIn(token, result.stdout + result.stderr)
        self.git("add", "credential.txt")
        self.write("credential.txt", "token = " + token)
        self.assertEqual(self.run_hook().returncode, 0)

    def test_three_checksum_file_exceptions_and_new_credential(self):
        digest = hashlib.sha256(b"synthetic-file-content").hexdigest()
        for path in HASH_FILES:
            self.write(path, json.dumps({"app/api/auth.py": digest}, indent=2) + "\n")
        self.git("add", "--", *HASH_FILES)
        self.assertEqual(self.run_hook().returncode, 0)
        for path in HASH_FILES:
            with self.subTest(path=path):
                self.write(path, json.dumps({"app/api/auth.py": digest, "api_key": digest}, indent=2) + "\n")
                self.git("add", "--", path)
                result = self.run_hook()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("generic-api-key", result.stdout)
                self.assertNotIn(digest, result.stdout + result.stderr)
                self.write(path, json.dumps({"app/api/auth.py": digest}, indent=2) + "\n")
                self.git("add", "--", path)

    def test_checksum_shape_in_other_file_is_not_allowlisted(self):
        digest = hashlib.sha256(b"synthetic-file-content").hexdigest()
        self.write("other.json", json.dumps({"app/api/auth.py": digest}, indent=2))
        self.git("add", "other.json")
        result = self.run_hook()
        self.assertEqual(result.returncode, 1)
        self.assertIn("generic-api-key", result.stdout)

    def test_nested_checksum_paths_are_not_allowlisted(self):
        digest = hashlib.sha256(b"synthetic-file-content").hexdigest()
        for path in HASH_FILES:
            self.write("nested/" + path, json.dumps({"app/api/auth.py": digest}, indent=2))
        self.git("add", "nested")
        result = self.run_hook()
        self.assertEqual(result.returncode, 1)
        self.assertIn("generic-api-key", result.stdout)
        self.assertNotIn(digest, result.stdout + result.stderr)

    def test_relative_directory_scan_uses_exact_paths(self):
        digest = hashlib.sha256(b"synthetic-file-content").hexdigest()
        for path in HASH_FILES:
            self.write(path, json.dumps({"app/api/auth.py": digest}, indent=2))
        report = self.repo / "report.json"
        command = [
            "gitleaks", "dir", ".", "--config", str(CONFIG), "--redact=100",
            "--ignore-gitleaks-allow", "--gitleaks-ignore-path", os.devnull,
            "--no-banner", "--no-color", "--log-level", "error",
            "--report-format", "json", "--report-path", str(report),
        ]
        result = subprocess.run(command, cwd=self.repo, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, "从快照根扫描时精确路径例外应通过")
        nested_path = "nested/" + HASH_FILES[0]
        self.write(nested_path, json.dumps({"app/api/auth.py": digest}, indent=2))
        report.unlink()
        result = subprocess.run(command, cwd=self.repo, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, "嵌套同后缀路径不得获得例外")
        hits = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual({hit["File"] for hit in hits}, {nested_path})
        self.assertEqual({hit["RuleID"] for hit in hits}, {"generic-api-key"})
        self.assertNotIn(digest, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
