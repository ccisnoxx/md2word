# 最小设计

保留 is_bundled_seed 分类。已有记录的 template_id、version、docx_sha256、非 DRAFT 和 payload 自身 snapshot_hash 校验不变。仅把 docx_path 精确比较改为：按 root_dir 解析相对路径并 resolve 后，等于 seed 路径或位于 settings.templates_storage_dir/<id>/v<version> 内。

复用现有 _resolve_manifest_path；不增加 helper、读文件 fallback、记录更新、默认指针分支或依赖。缺失/非法路径仍按冲突处理，目录边界用 Path 语义比较，不使用字符串前缀。

新增测试保留原 14 个用例及断言，覆盖生产相对路径、绝对/规范化路径及拒绝矩阵，比较记录、默认指针和写入轨迹。启动验证使用真实 build_runtime 和本地测试仓储/替身，禁止真实 DB/Provider/MinerU。

临时夹具置于本任务目录下，运行后清理；PYTHONDONTWRITEBYTECODE=1。无数据迁移，回退仅撤销本次代码改动。
