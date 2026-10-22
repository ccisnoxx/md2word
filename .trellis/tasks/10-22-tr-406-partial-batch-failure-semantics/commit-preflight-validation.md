# 两笔业务提交的预提交与合成检查

日期：2026-10-22。用户已批准commit-plan.md并授权执行，范围限两笔业务提交；不push、不归档、不记录会话。

## 依赖提交

- 实际依赖提交：`0946326b0f457ef4b4f60895f17feb915d657c14`，父提交596a2de7ed29edb7fdb378d91c17bda09b7f1066。
- 提交树：7fb0acfa499e95cb87809157426b306490e3907b，60路径，等同已重建、实跑验证及独立check/critical reviewer复核的冻结中间树。
- 验证为132项后端、150项前端、build、OpenAPI164/323、release通过；独立check另实跑132项，风险复核未发现重建引入的P1/P2/P3。详见dependency-intermediate-validation.md/json。

## TR-406 提交与验收候选

第二笔为包含本文件和本任务记录的业务提交，subject为`fix(translation): enforce terminal batch failure semantics (TR-406)`，parent为上述依赖提交。实际提交哈希通过Git历史查询，不向本提交的内容写入自引用哈希。

- 产品允许清单71路径已在本轮开始逐文件保存SHA-256和字节副本；第二笔的产品blob使用该冻结候选，主工作区71文件也逐字节相符。
- 验收产品参考树：9a56f1f6e1c85bec9feef8e61058f1dec2cb7321。此树基于原HEAD，仅放入71产品路径和以HEAD其他区块为底的TR-406 manifest区块。
- 第二笔预提交树与该参考树的差量必须全部位于本任务目录；其相对第一笔的差量只能是计划30个TR-406路径、本任务记录和manifest的TR-406区块。
- 本任务记录仅补人工验收、提交授权、中间树验证及本轮执行证据；业务源码、测试、API、设计及Spec的71路径保持验收字节。
- 最终候选既有126项核心/兼容、API/状态/下载门、前端152项/build/smoke、OpenAPI164/324、release和样本证据仍适用，不因只拆分Git树重复无变化测试。

## 原改动保护与索引

原始332个非本任务dirty文件逐字节保留；父任务6项既存删除仍缺失且保持原staged binary patch。原workspace journal/index、CON-104 prompt/backlog及14个未跟踪archive目录未进入提交。

manifest提交blob以HEAD为底，只移植TR-406区块；其他原有变更继续留在工作树。两笔均使用独立index构建，只将已提交允许路径索引同步至新HEAD，不整体提交或覆盖原index。

第二笔完成后再核对最终Git tree、71路径hash、manifest选择性blob、原staged patch、原dirty字节及剩余status；实际两笔哈希和最终保护结果由本轮执行输出及交付答复报告。

raw完整tree diff有两处验收候选已有EOF空行诊断，按字节一致要求保留；关闭blank-at-eof这一诊断后的diff --check通过，无其他空白诊断。没有修改Git配置。未运行生产迁移或真实Provider、VPS、数据库/S3外调。
