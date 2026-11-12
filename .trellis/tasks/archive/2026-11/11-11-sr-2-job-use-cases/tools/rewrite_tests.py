"""把测试中对旧 DocumentJobService 的访问改写为 DocumentJobUseCases 上的具体组件。

只处理三种接收者：`runtime.document_job_service`、fixture 变量 `service`、`self.service`；
依赖替换（task_queue 等赋值）与模块级 patch 另行人工处理。
"""
import pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import plan as P  # noqa: E402

owner, *_ = P.plan()
SPECIAL = {"settings": "read_model.settings", "file_repository": "access.file_repository"}


def target(name):
    if name in SPECIAL:
        return SPECIAL[name]
    if name in owner:
        comp = owner[name]
        new = "get_authorized_job" if name == "_get_job" else (
            name[1:] if comp in P.SHARED and name.startswith("_") else name)
        return f"{comp}.{new}"
    return None


def rewrite(text, receivers):
    def sub(m):
        recv, name = m.group(1), m.group(2)
        t = target(name)
        return f"{recv}.{t}" if t else m.group(0)

    def sub_patch(m):
        recv, name = m.group(1), m.group(2)
        t = target(name)
        if not t:
            return m.group(0)
        comp, new = t.rsplit(".", 1)
        return f'patch.object({recv}.{comp}, "{new}"'
    for recv in receivers:
        r = re.escape(recv)
        text = re.sub(rf'patch\.object\(\s*({r})\s*,\s*"(\w+)"', sub_patch, text)
        text = re.sub(rf"(?<![\w.])({r})\.(\w+)\b", sub, text)
    return text


files = {
    "tests/test_document_job_result_persistence.py": ["runtime.document_job_service"],
    "tests/test_document_job_modes.py": ["runtime.document_job_service"],
    "tests/document_job_list_query_v2_publication_fixtures.py": ["runtime.document_job_service"],
    "tests/test_document_job_download_availability_api.py": [],
    "tests/test_translation_batch_failure_semantics.py": ["runtime.document_job_service"],
    "tests/test_document_job_delivery_state_api.py": ["runtime.document_job_service"],
    "tests/test_document_job_list_query_v2_service.py": ["runtime.document_job_service", "service"],
    "tests/test_document_file_read_session.py": ["service"],
    "tests/test_document_job_incident_publish_light_check.py": ["service"],
    "tests/test_document_job_list_publish_light_check.py": ["service"],
    "tests/test_document_job_download_availability.py": ["self.service"],
}
for path, receivers in files.items():
    p = pathlib.Path(path)
    t = p.read_text()
    n = rewrite(t, receivers)
    if n != t:
        p.write_text(n)
        print("改写", path)
