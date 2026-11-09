"""窗口专用辅助：文件系统保真核对及隔离恢复库的真实角色矩阵。"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
from datetime import timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

from common import OpsError, connection_factory, mysql_environment, safe_main, target_arguments


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
        separators=(",", ":")).encode("ascii")).hexdigest()


def write_private_json(path, value):
    """敏感路径及账号只进入当前执行者私有目录，完整写入后独占发布。"""
    path = Path(path).absolute()
    parent = path.parent.lstat()
    if (not stat.S_ISDIR(parent.st_mode) or stat.S_IMODE(parent.st_mode) != 0o700
            or parent.st_uid != os.geteuid()):
        raise OpsError("private_owned_output_directory_required")
    fd, temporary = tempfile.mkstemp(prefix=".window-helper-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=True, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path, follow_symlinks=False)
    finally:
        os.unlink(temporary)


def _read_xattrs(path):
    # Linux 的 POSIX access/default ACL 就在 system.posix_acl_* 中；不可在别的平台
    # 将缺少 ACL API 误报成空 ACL。目标主机为 Linux，离线夹具只替换此平台边界。
    if sys.platform != "linux" or not hasattr(os, "listxattr"):
        raise OpsError("linux_nofollow_acl_xattr_required")
    return {name: base64.b64encode(os.getxattr(path, name, follow_symlinks=False)).decode("ascii")
            for name in sorted(os.listxattr(path, follow_symlinks=False))}


def filesystem_manifest(root):
    """不跟随符号链接；完整 hash 文件并保留恢复时可比较的全部请求元数据。"""
    root = Path(root).absolute()
    entries, hardlinks = {}, {}
    kinds = {stat.S_IFREG: "file", stat.S_IFDIR: "directory", stat.S_IFLNK: "symlink",
             stat.S_IFIFO: "fifo", stat.S_IFCHR: "character", stat.S_IFBLK: "block",
             stat.S_IFSOCK: "socket"}

    def capture(path, relative):
        before = path.lstat()
        kind = kinds.get(stat.S_IFMT(before.st_mode))
        if kind is None:
            raise OpsError("unsupported_filesystem_entry")
        attrs = _read_xattrs(path)
        entry = dict(type=kind, size=before.st_size, mode=stat.S_IMODE(before.st_mode),
            uid=before.st_uid, gid=before.st_gid, mtime_ns=before.st_mtime_ns,
            symlink_target=os.readlink(path) if kind == "symlink" else None,
            xattrs=attrs, acl={key: value for key, value in attrs.items()
                             if key.startswith("system.posix_acl_")})
        if kind == "file":
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as stream:
                opened = os.fstat(stream.fileno())
                if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                    raise OpsError("filesystem_changed_during_capture")
                digest = hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
                entry["sha256"] = digest.hexdigest()
            identity = before.st_dev, before.st_ino
            entry["hardlink_to"] = hardlinks.setdefault(identity, relative)
        elif kind in {"character", "block"}:
            entry["rdev"] = before.st_rdev
        entries[relative] = entry
        if kind == "directory":
            fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                if (os.fstat(fd).st_dev, os.fstat(fd).st_ino) != (before.st_dev, before.st_ino):
                    raise OpsError("filesystem_changed_during_capture")
                for name in sorted(os.listdir(fd)):
                    # T0 停写之外仍核对目录身份；链接条目仅读取链接本身。
                    capture(path / name, name if relative == "." else relative + "/" + name)
            finally:
                os.close(fd)
        after = path.lstat()
        keys = ("st_dev", "st_ino", "st_mode", "st_size", "st_uid", "st_gid",
                "st_mtime_ns", "st_ctime_ns", "st_nlink")
        if any(getattr(before, key) != getattr(after, key) for key in keys):
            raise OpsError("filesystem_changed_during_capture")

    capture(root, ".")
    return {"format": "md2word-filesystem-manifest-v1", "entries": entries,
            "entries_sha256": _digest(entries)}


def compare_filesystems(before, after):
    """核对同源恢复；目录 size 只诊断分配布局，其余捕获字段逐项严格相等。"""
    for manifest in (before, after):
        if (manifest.get("format") != "md2word-filesystem-manifest-v1"
                or not isinstance(manifest.get("entries"), dict)
                or "." not in manifest["entries"]
                or _digest(manifest["entries"]) != manifest.get("entries_sha256")):
            raise OpsError("complete_filesystem_manifest_required")
    left, right = before["entries"], after["entries"]
    added, removed = len(right.keys() - left.keys()), len(left.keys() - right.keys())
    changed = 0
    for key in left.keys() & right.keys():
        left_entry, right_entry = left[key], right[key]
        if left_entry["type"] == right_entry["type"] == "directory":
            # tar 无法重建目录的磁盘分配大小；保留原 manifest，不据此判内容丢失。
            left_entry = {name: value for name, value in left_entry.items() if name != "size"}
            right_entry = {name: value for name, value in right_entry.items() if name != "size"}
        changed += left_entry != right_entry
    return dict(exit_code=int(bool(added or removed or changed)), equal=not (added or removed or changed),
                before_entries=len(left), after_entries=len(right), added=added, removed=removed,
                changed=changed)


def load_matrix_records(connect):
    """仅在已绑定隔离身份的同一只读快照读取真实记录，不调用应用 bootstrap。"""
    from app.domains.document_jobs.models import DocumentJobRecord
    from app.domains.users.models import InternalUserRecord

    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT")
            cursor.execute("SELECT user_id, payload FROM internal_users "
                           "WHERE status = %s AND role IN (%s, %s) ORDER BY BINARY user_id",
                           ("active", "admin", "operator"))
            users = []
            for row in cursor.fetchall():
                user = InternalUserRecord.model_validate_json(row["payload"])
                if user.id != row["user_id"] or user.status != "active" or user.role not in {"admin", "operator"}:
                    raise OpsError("actual_active_user_identity_mismatch")
                users.append(user)
            cursor.execute("SELECT job_id, payload FROM document_jobs ORDER BY BINARY job_id")
            jobs = []
            for row in cursor.fetchall():
                raw = json.loads(row["payload"])
                if "created_at" not in raw:
                    raise OpsError("persisted_job_created_at_required")
                job = DocumentJobRecord.model_validate(raw)
                if job.id != row["job_id"]:
                    raise OpsError("actual_job_identity_mismatch")
                jobs.append(job)
        return users, jobs
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def build_case_matrix(users, jobs):
    """逐用户覆盖基本查询，其余维度按角色/租户/公司选代表，避免窗口内笛卡尔积。"""
    from typing import get_args
    from app.domains.document_jobs.list_query import document_job_search_values
    from app.domains.document_jobs.models import DocumentJobTranslationQaStatus
    from app.domains.document_jobs.schemas import DocumentJobIncidentSort
    from app.domains.document_jobs.service import DOCUMENT_JOB_LIST_SORTS

    if not {"admin", "operator"}.issubset(user.role for user in users):
        raise OpsError("actual_admin_and_operator_required")
    if any(user.status != "active" or user.role not in {"admin", "operator"} for user in users):
        raise OpsError("actual_active_users_required")
    cases, seen = [], set()
    summary = dict(users=len(users), admin_users=sum(user.role == "admin" for user in users),
        operator_users=sum(user.role == "operator" for user in users), jobs=len(jobs),
        users_without_visible_jobs=0, representatives_without_unicode_samples=0,
        representatives_without_aware_date_samples=0, representative_naive_date_observations=0,
        default_page_upper_bound=0)
    # 上界只使用已知权限字段；实际请求仍由原 router/service 完整核验权限和有效复核。
    visible_by_user = {user.id: [job for job in jobs if job.deleted_at is None and job.archived_at is None
        and job.tenant_id == user.tenant_id and job.company_id == user.company_id
        and (user.role == "admin" or job.created_by == user.id)] for user in users}
    representatives = {}
    for user in users:
        scope = user.role, user.tenant_id, user.company_id
        previous = representatives.get(scope)
        if previous is None or len(visible_by_user[user.id]) > len(visible_by_user[previous]):
            representatives[scope] = user.id
    representative_ids = set(representatives.values())
    summary["extra_dimension_representatives"] = len(representative_ids)

    def add(user, endpoint, label, **params):
        identity = _digest([user.id, endpoint, params])
        if identity not in seen:
            cases.append(dict(user_id=user.id, expected_role=user.role, endpoint=endpoint,
                              label=label, params=params))
            seen.add(identity)

    for user in users:
        visible = visible_by_user[user.id]
        pages = max(1, (len(visible) + 19) // 20)
        summary["default_page_upper_bound"] += pages * 2
        summary["users_without_visible_jobs"] += int(not visible)
        search_values = sorted({value for job in visible for value in document_job_search_values(job)})
        missing_query = "__md2word_no_match_" + _digest(search_values)
        if any(missing_query.casefold() in value.casefold() for value in search_values):
            raise OpsError("no_match_query_collision")
        for endpoint in ("jobs", "incidents"):
            add(user, endpoint, "default")
            # 默认请求本身已经覆盖第一页，不重复一次成本较高的完整旧版查询。
            for page in range(2, pages + 1):
                add(user, endpoint, "all_default_pages", page=page, page_size=20)
            add(user, endpoint, "out_of_range_empty_page", page=pages + 1, page_size=20)
            add(user, endpoint, "no_match", q=missing_query)
        if user.id not in representative_ids:
            continue
        unicode_values = [value for value in search_values if not value.isascii()]
        unicode_query = unicode_values[0] if unicode_values else "未匹配搜索验证Ω"
        summary["representatives_without_unicode_samples"] += int(not unicode_values)
        for endpoint in ("jobs", "incidents"):
            add(user, endpoint, "unicode", q=unicode_query)
            if visible:
                add(user, endpoint, "actual_job_id", q=visible[0].id)
            for status in sorted({job.status for job in visible}):
                add(user, endpoint, "actual_status", status_filter=status)
            sorts = DOCUMENT_JOB_LIST_SORTS if endpoint == "jobs" else get_args(DocumentJobIncidentSort)
            for sort in sorted(sorts):
                if sort != ("created_at_desc" if endpoint == "jobs" else "priority"):
                    add(user, endpoint, "sort", sort=sort)
        for qa in (*get_args(DocumentJobTranslationQaStatus), "all"):
            add(user, "jobs", "translation_qa", translation_qa_status=qa)
        add(user, "jobs", "include_archived", include_archived=True)
        dates = [job.created_at.astimezone(timezone.utc) for job in visible
                 if job.created_at.tzinfo is not None and job.created_at.utcoffset() is not None]
        summary["representative_naive_date_observations"] += len(visible) - len(dates)
        summary["representatives_without_aware_date_samples"] += int(not dates)
        if dates:
            start, end = min(dates).isoformat(), max(dates).isoformat()
            for params in (dict(created_from=start), dict(created_to=end),
                    dict(created_from=start, created_to=end),
                    dict(created_from=start, created_to=start), dict(created_from=end, created_to=end)):
                add(user, "jobs", "inclusive_date_boundary", **params)
    summary.update(cases=len(cases), jobs_cases=sum(case["endpoint"] == "jobs" for case in cases),
                   incidents_cases=sum(case["endpoint"] == "incidents" for case in cases),
                   dimension_cases=dict(sorted(Counter(case["label"] for case in cases).items())))
    return cases, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("filesystem-capture", help="捕获本地文件系统，不跟随链接")
    capture.add_argument("--root", type=Path, required=True)
    capture.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("filesystem-compare", help="严格比较同源恢复的 manifest")
    check.add_argument("before", type=Path)
    check.add_argument("after", type=Path)
    matrix = commands.add_parser("query-cases", help="仅从隔离恢复库生成真实角色的查询矩阵")
    target_arguments(matrix)
    matrix.add_argument("--deny-server-uuid", required=True)
    matrix.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "filesystem-capture":
        if args.root.is_dir() and args.output.absolute().is_relative_to(args.root.absolute()):
            raise OpsError("output_must_be_outside_captured_root")
        manifest = filesystem_manifest(args.root)
        write_private_json(args.output, manifest)
        report = dict(exit_code=0, entries=len(manifest["entries"]),
            files=sum(entry["type"] == "file" for entry in manifest["entries"].values()),
            entries_sha256=manifest["entries_sha256"])
    elif args.command == "filesystem-compare":
        report = compare_filesystems(json.loads(args.before.read_text()), json.loads(args.after.read_text()))
    else:
        if args.expect_server_uuid == args.deny_server_uuid or not args.deny_server_uuid:
            raise OpsError("production_instance_forbidden")
        connect = connection_factory(mysql_environment(), args.expect_database,
                                     args.expect_server_uuid, readonly=True)
        cases, summary = build_case_matrix(*load_matrix_records(connect))
        write_private_json(args.output, cases)
        report = dict(exit_code=0, **summary)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(safe_main(main))
