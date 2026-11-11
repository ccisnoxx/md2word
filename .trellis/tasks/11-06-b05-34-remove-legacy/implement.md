# 实施与验证
1. 记录静态引用和指定定向测试基线。
2. 分工删除 runtime、jobs/装配、仓储/健康/运维；各自拥有文件，不覆盖其他改动。
3. 同步混合测试夹具与相关 Spec；汇总删除清单。
4. 使用 ${PROJECT_ROOT}/.venv/bin/python 与 PYTHONDONTWRITEBYTECODE=1，执行 AC-2～AC-5 定向检查；不 discover/全前端/发布门禁。临时目录自动清理，编译缓存位于 Codex 缓存。
5. 静态 AST/grep、最终 diff 和独立复核。保留基线失败，不扩大历史测试修复。
