"""sr-2 拆分规划：从 service.py 计算每个方法的归属组件、组件依赖与跨组件调用。

只读分析；generate.py 复用这里的 COMPONENT_OF 结果生成代码。
"""
import ast, collections, pathlib, sys

SERVICE = pathlib.Path("app/domains/document_jobs/service.py")
DEPS = ["settings", "job_repository", "event_repository", "file_repository", "task_queue", "template_read_service",
        "term_version_service", "job_resource_snapshot_service", "document_job_translation_batch_repository",
        "file_upload_service", "word_preview_service", "audit_service"]
PUBLIC_GROUPS = {
    "submission": ["create_job", "clone_job", "retry_job", "retry_word_preview"],
    "lifecycle_commands": ["archive_job", "unarchive_job", "preview_delete_job", "delete_job", "cancel_job"],
    "publication": ["list_document_publications", "request_new_generation", "get_generation_request",
                    "get_publication_file_for_download", "get_publication_file_for_authorized_download",
                    "check_publication_download_current", "record_publication_download_audit", "publish_document"],
    "quality_review": ["get_document_quality", "get_document_review", "list_document_review_blocks",
                       "get_document_review_block", "get_document_review_history", "get_document_quality_tables",
                       "get_document_preview", "get_document_quality_pages", "submit_document_review_with_source",
                       "get_table_evidence", "submit_document_review", "list_document_reviews"],
    "table_references": ["list_table_references", "read_table_reference_content"],
    "translation_qa": ["get_translation_qa", "update_translation_qa"],
    "downloads": ["get_result_file_for_download", "get_file_for_download", "get_result_file_for_authorized_download",
                  "get_file_for_authorized_download", "record_download_authorized"],
    "queries": ["list_jobs", "list_events", "list_translation_batches", "get_translation_batch_snapshot",
                "list_visible_jobs", "document_job_search_values", "list_files", "_document_job_search_values"],
}
SHARED = {
    "access": ["_ensure_job_not_deleted", "_get_job", "_ensure_visible", "_is_visible", "_effective_job",
               "_file_retry_count", "_file_belongs_to_job", "_is_current_downloadable_job_file",
               "_file_matches_current_retry_count", "_ensure_file_not_expired", "_get_completed_result_file",
               "_get_downloadable_completed_result_file", "_list_files_for_job", "_review_api_file",
               "_ensure_file_reader_available", "_get_source_file_for_clone", "_normalize_optional_text", "get_job"],
    "read_model": ["_new_generation_source_file", "_new_generation_resource_snapshot", "_build_job_read_observation",
                   "_build_retry_action", "_build_new_generation_action", "_download_policy_for_view",
                   "_available_action", "_build_result_read_view", "_build_publish_action", "_cancel_disabled_reason",
                   "_archive_disabled_reason", "_unarchive_disabled_reason", "_clone_disabled_reason",
                   "_delete_disabled_reason", "_is_retryable_failure", "_retry_disabled_reason",
                   "build_available_actions", "build_job_read_view", "build_incident_classification_view",
                   "build_download_policy"],
    "review_writer": ["_submit_document_review"],
    "dispatcher": ["_mark_enqueue_failed", "_enqueue_created_job", "_mark_created_job_queued"],
    "events": ["record_event"],
    "request_snapshot": ["_resolve_clone_config", "_build_clone_snapshot", "_read_snapshot_record", "_read_snapshot_string",
                         "_build_retry_request_snapshot", "_build_resource_snapshot", "_ensure_resource_selection_allowed",
                         "_split_template_version_id", "_preserve_retry_template_and_profile", "_resolve_document_job_mode",
                         "_ensure_direct_translation_selection_absent", "_ensure_document_language_allowed",
                         "_legacy_translation_term_version_id", "_resolve_template_version_id", "_resolve_term_version_id",
                         "_resolve_debug_full_text_enabled", "_ensure_debug_full_text_allowed", "_build_request_snapshot"],
}
DEAD = ["_matches_document_job_query", "_matches_status_filter", "_matches_translation_qa_status",
        "_count_translation_qa_statuses", "_matches_created_range", "_document_job_sort_key",
        "_snapshot_resource_id", "_snapshot_resource_version"]


def service_source():
    """service.py 删除后从 HEAD 读取原文件，保证规划结果可复现。"""
    if SERVICE.exists():
        return SERVICE.read_text()
    import subprocess
    return subprocess.run(["git", "show", f"HEAD:{SERVICE}"], capture_output=True, text=True, check=True).stdout


def load():
    tree = ast.parse(service_source())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "DocumentJobService")
    methods = {f.name: f for f in cls.body if isinstance(f, ast.FunctionDef) and f.name != "__init__"}
    return tree, cls, methods


def self_refs(func):
    return {n.attr for n in ast.walk(func)
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "self"}


def plan():
    tree, cls, methods = load()
    owner = {}
    for g, ms in {**PUBLIC_GROUPS, **SHARED}.items():
        for m in ms:
            assert m not in owner, m
            owner[m] = g
    callers = collections.defaultdict(set)
    for name, f in methods.items():
        for r in self_refs(f):
            if r in methods:
                callers[r].add(name)
    # 其余私有方法：跟随唯一调用组件（迭代直到稳定）
    changed = True
    while changed:
        changed = False
        for m in methods:
            if m in owner or m in DEAD:
                continue
            groups = {owner[c] for c in callers[m] if c in owner}
            if callers[m] and all(c in owner for c in callers[m]) and len(groups) == 1:
                owner[m] = groups.pop(); changed = True
    unresolved = [m for m in methods if m not in owner and m not in DEAD]
    comp_deps = collections.defaultdict(set); comp_uses = collections.defaultdict(set); other = collections.defaultdict(set)
    for m, g in owner.items():
        for r in self_refs(methods[m]):
            if r in DEPS:
                comp_deps[g].add(r)
            elif r in methods:
                if owner.get(r) != g:
                    comp_uses[g].add(owner.get(r))
            else:
                other[g].add(r)
    return owner, unresolved, comp_deps, comp_uses, other, methods


if __name__ == "__main__":
    owner, unresolved, comp_deps, comp_uses, other, methods = plan()
    print("未归属:", unresolved)
    for g in [*PUBLIC_GROUPS, *SHARED]:
        ms = [m for m, o in owner.items() if o == g]
        lines = sum(methods[m].end_lineno - methods[m].lineno + 1 for m in ms)
        print(f"{g:20s} 方法{len(ms):3d} 行{lines:5d} deps={sorted(comp_deps[g])} uses={sorted(comp_uses[g])} other={sorted(other[g])}")
    # 依赖被哪些组件使用
    by_dep = collections.defaultdict(list)
    for g, ds in comp_deps.items():
        for d in ds: by_dep[d].append(g)
    for d in DEPS: print(f"  {d}: {sorted(by_dep[d])}")
