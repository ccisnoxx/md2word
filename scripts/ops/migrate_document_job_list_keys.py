"""大 key 拆列的独立入口；沿用当前列表迁移的配置、事务和恢复协议。"""
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ops.migrate_document_job_list_query import (
    main,
    migrate_document_job_list_query as migrate_document_job_list_keys,
)


if __name__ == "__main__":
    raise SystemExit(main())
