#!/bin/sh
# 由 env -i 启动；仅使用固定工具、目标解释器和只读离线制品。
set -eu
cd /src
python -m venv /work/venv
B02_UV=/tools/uv
B02_PYTHON=/work/venv/bin/python
B02_WHEELS=/wheels
B02_CONSTRAINTS=/inputs/constraints.txt
B02_LOCK=/work/runtime-lock.txt
B02_REPORT=/work/install-report.json
B02_CACHE=/work/cache
export B02_UV B02_PYTHON B02_WHEELS B02_CONSTRAINTS B02_LOCK B02_REPORT B02_CACHE
"$B02_PYTHON" /inputs/collect_environment.py > /work/before.json
"$B02_UV" --version
"$B02_UV" --no-config --cache-dir "$B02_CACHE" pip compile requirements.txt \
  --constraints "$B02_CONSTRAINTS" --python "$B02_PYTHON" \
  --no-index --find-links "$B02_WHEELS" --no-build --generate-hashes \
  --output-file "$B02_LOCK"
"$B02_PYTHON" -m pip --isolated install --no-index --find-links "$B02_WHEELS" \
  --require-hashes --only-binary=:all: --report "$B02_REPORT" -r "$B02_LOCK"
"$B02_PYTHON" -m pip check
"$B02_PYTHON" /inputs/collect_environment.py > /work/after.json
