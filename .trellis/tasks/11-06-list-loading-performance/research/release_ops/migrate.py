"""同脚本挂入旧/新完整镜像，调用该镜像自己的迁移 owner，不改写版本。"""
from __future__ import annotations

import argparse
import json

from common import connection_factory, mysql_environment, safe_main, target_arguments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target_arguments(parser)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("dry-run", "apply", "verify"):
        modes.add_argument("--" + mode, action="store_const", dest="mode", const=mode)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--after-job-id", default="")
    parser.add_argument("--after-file-id", default="")
    args = parser.parse_args()
    values = mysql_environment()
    connect = connection_factory(values, args.expect_database, args.expect_server_uuid,
                                 readonly=args.mode != "apply")
    from app.core.config import Settings
    from scripts.ops.migrate_document_job_list_query import migrate_document_job_list_query
    settings = Settings(_env_file=None, jobs_repository_backend="mysql",
                        **{"jobs_mysql_" + key: value for key, value in values.items()})
    # 旧镜像 owner 生成 job/file 2/1，新镜像 owner 生成 3/2；不复制投影实现。
    report = migrate_document_job_list_query(
        settings, mode=args.mode, batch_size=args.batch_size,
        after_job_id=args.after_job_id, after_file_id=args.after_file_id,
        mysql_connect_factory=connect,
    )
    print(json.dumps(report, ensure_ascii=False))
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(safe_main(main))
