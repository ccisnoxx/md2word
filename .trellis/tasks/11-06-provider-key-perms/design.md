# 设计

缺陷 owner 是 AiProviderConfigService._write_record / _restrict_permissions。采用标准库以排他创建和 0600 模式打开同目录临时文件，在写入密钥与原子替换前完成权限设置和确认。替换保留同一 inode 权限，不在替换后执行可能失败的 chmod，以免权限失败已覆盖原记录。保留 UTF-8、ensure_ascii=False、indent=2 与末尾换行。

根据 AC-3 验收反馈，使用 `tempfile.mkstemp(dir=父目录, prefix=目标文件名 + ".", suffix=".tmp")` 排他创建唯一随机临时文件，权限为 0600，不跟随已有符号链接。历史固定名及其他随机名残留不阻塞保存，也不自动删除；只清理本次创建的临时文件。通过 `fchmod` 设置及 `fstat` 确认权限后才写入密钥，无法确认时失败关闭。原有 OSError 写入错误经路由向上传播并成为 HTTP 500，审计仅在成功后执行；本次沿用该未预期错误语义，不新增 API 错误码或路由处理。定向测试证明失败不进入成功审计。

范围为服务、独立权限测试和必要 API 定向测试；现有 runtime-configuration Spec 的 0600 描述只针对 MinerU，不将本次变更扩到 MinerU。操作系统权限与标准库 tempfile/os 为既有本地模式，无新增依赖。新增注释、文档与异常使用中文。
