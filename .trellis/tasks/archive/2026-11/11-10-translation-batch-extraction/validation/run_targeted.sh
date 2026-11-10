#!/bin/zsh
# 逐模块运行本任务的定向测试，并把每个用例的结果归一成可比较的清单。
# 用法：run_targeted.sh <标签>，例如 baseline / stage1 / stage2。
set -u
label="$1"
# 任务目录归档后位置会变，因此结果目录取脚本所在目录，仓库根目录由 git 定位。
here="${0:A:h}"
root="$(git -C "$here" rev-parse --show-toplevel)" || exit 2
out="$here/$label"
mkdir -p "$out"
cd "$root" || exit 2
targets=(
  tests.test_translation_batch_failure_semantics
  tests.test_translation_integrity_execution
  tests.test_document_job_execution_stages
  tests.test_degraded_page_display
  tests.test_document_job_delivery_state_api
  tests.test_document_job_modes
  tests.test_database_job_repository
  tests.test_translation_table_context
  tests.test_document_job_list_query_v2_writers
  tests.test_document_job_incident_publish_light_check
  tests.test_document_job_list_publish_light_check
  tests.test_document_job_list_query_v2_service
  tests.test_fastapi_jobs_backend
)
: > "$out/summary.txt"
for module in "${targets[@]}"; do
  start=$(date +%s)
  PYTHONDONTWRITEBYTECODE=1 "$root/.venv/bin/python" -m unittest -v "$module" > "$out/$module.log" 2>&1
  code=$?
  echo "$module exit=$code seconds=$(( $(date +%s) - start )) $(grep -E '^(Ran |OK|FAILED)' "$out/$module.log" | tr '\n' ' ')" >> "$out/summary.txt"
done
"$root/.venv/bin/python" "$here/summarize.py" "$out"
cat "$out/summary.txt"
