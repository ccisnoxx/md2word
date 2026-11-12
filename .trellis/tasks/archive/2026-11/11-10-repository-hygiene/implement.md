# 实施与最小验证计划

## 实施前门槛

- [x] 用户在最终规划摘要之后明确批准本方案，包括当前树清理、开发工具依赖和本仓库钩子激活。
- [x] 保持 `planning`，直至上述批准；再执行 `task.py start`。
- [x] 复核 Git dirty/staged 基线、当前任务与并发工作树；历史重写、提交、推送、真实凭证轮换和生产操作不在该批准中。
- [x] 按 Trellis 模式派发 `trellis-implement`，提示词以 `Active task: .trellis/tasks/11-10-repository-hygiene` 开头，并说明中文总结、文件所有权和保留他人修改。

## 执行顺序

1. [x] 复核并删除精确网络脚本，更新 `.gitignore`；3 个 SDK/module 文件只解除跟踪，保留本机字节。确认共享 `.idea` / `.run` / AI / Trellis 配置未误删。
2. [x] 按位置清单规范化任务、文档和日志的路径；仅清理再次确认失效的 `worktree_path`，不改其他任务状态。检查外部项目路径、生成证据和运行字段，避免机械替换。
3. [x] 修改两个沙盒脚本的参数默认行为和模板示例，更新必要的中文帮助/注释；新增直接验证缺失参数、环境配置和 CLI 优先级的回归。
4. [x] 实现标准库卫生检查器和 `.githooks/pre-commit`，增加明确部署例外及 `.gitleaks.toml` 的校验和窄范围例外；不复制原始凭证到测试。
5. [x] 编写 `docs/dev/repository-hygiene.md`，给出工具版本/制品验证、运行命令、安装、激活与回退。更新相关 Spec 的必要执行合同，避免重复规则 owner。
6. [x] 执行下列一次合并后的最小验证；由 `trellis-check` 复核暂存内容、allowlist、失败可见性和敏感值输出。若仍有具体未解决的安全边界风险，追加独立只读复核。
7. [x] 在本仓库激活钩子并验证实际设置；不借用 `git commit` 验证。报告准确变更、工具启用状态、扫描结果与未验证范围，等待独立提交授权。

## 最小验证矩阵

| 对象 | 检查与证据 | 不扩大的边界 |
|---|---|---|
| 路径/规则 | `python3 -m unittest tests.test_repository_hygiene`（新增）：临时文件、各平台用户路径、RFC1918 候选验证、变量占位符、精确例外和不回显。 | 不测试无关应用层。 |
| 真实 index | 新模块用独立临时 Git 仓库覆盖违规 staged / 干净 working tree，以及干净 staged / 违规 working tree、初始提交、删除、重命名和空格文件名；钩子退出状态与 `git write-tree` 前后不变。 | 根仓库不创建测试提交、不 stash、不覆盖现有 index。 |
| 沙盒脚本 | 使用既有 `tests.test_conversion_sandbox_dev_tools.ConversionSandboxAuditTests` 和 `Md2wordMainMigrationTests`，及新增配置分支测试；只使用临时目录。 | 不启动 MinerU、服务或移动真实沙盒。 |
| secrets 规则 | 固定 Gitleaks 对临时 repo 的伪造 token 应失败，校验和清单例外应通过；在同一例外文件新增 credential 字段仍失败。 | 不使用或测试历史真实 token 的有效性。 |
| 当前树 | `check_repository_hygiene.py --tracked`，并对新增候选文件执行相同规则；完整 Git 跟踪快照和本任务新增候选文本进行脱敏 Gitleaks 扫描，避免 `export-ignore` 漏扫。 | 例外必须可审查；不扫描 ignored 私有配置。 |
| 历史 | 复用本轮默认规则的本地 refs 扫描与关键定位；本轮没有改写历史，不为收尾重复运行。 | 不将历史噪声标作无条件通过，不把未 fetch 的远端当作已查。 |
| 材料与 diff | 受影响 JSON/JSONL 可解析、`task.py validate`、精确变更空白检查和最终 status/diff。 | 文档整理不触发全仓测试、构建、CI 或聚合发布门禁。 |

新增测试模块的确切命名在实施时落地；沙盒现有类中的新增测试随所属类运行，其他历史用例不为了“全绿”扩大维护。成功结果在相关输入不变时复用。

## 本轮规划验证

本轮仅核对三件套、研究证据、上下文引用、JSON/JSONL 解析、文档空白和变更范围；不把这些检查写成上述实施验收已经通过。实际结果记入 `planning-validation.md`。

## 历史及凭证后续

凭证所有者确认/吊销和历史清理方案仍是外部后续。它们不阻止用户审阅本方案，也不因批准当前树修复而自动获得授权。安全交付状态需要明确保留历史凭证未确认这一项。
