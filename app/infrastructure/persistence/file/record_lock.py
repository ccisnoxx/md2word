"""稳定旁路锁文件承载跨进程元数据互斥，不锁会被 replace 的 JSON inode。"""

import fcntl
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator


@contextmanager
def record_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
