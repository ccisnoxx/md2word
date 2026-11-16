# 分支整合验证

## 冷启动独有提交

原分支末端 c663210d 与整合提交 3545509e 已进入 GitHub main。PR #77 的合并提交为 2303a287。6 个独有提交中，MinerU v4 语言映射与主分支既有补丁等价。对比确认应用、Compose 和既有定向测试与主分支一致。新增的隔离 Compose 验收脚本通过 dev/prod 工厂参数、健康探针和 Worker 依赖静态核对，缺 factory 的负例按预期拒绝。归档中原空库、故障阻断和重启证据对应原候选 37440385。本轮未重新拉起 Compose 拓扑。

## 参数表独有提交

原分支末端 525904a0 有 21 个独有提交。合并保留人工核定、同源 PDF 取证、实物认证、锁内重验和审批发布门禁。开关与名单仍采用关闭、空集合的默认值。OpenAPI 导出结果为 180 个路径及 398 个 schema，快照一致。

用原始提交生成并经整合候选重读的证据包括主分支 v1/v2、原分支 v1 核定和未核定、早期 shared_limits 报告及反序 TYP/MIN 核定，共 6 组。报告和渲染定位逐值匹配。反序核定的 Word 经过预览实物、锚点与绑定 IR 复验。独立复核从原分支 SQLite 专项夹具读取 v1 同包账本，原执行摘要保持，旧冻结记录经转换和实物认证完成。新账本将冻结规则纳入摘要。

最终候选两组定向 unittest 共 127 项，125 项通过、2 项跳过。表格与渲染组 67 项全部通过，任务、权限、审批、发布、预览和回调组 60 项中 58 项通过。包含本机实际 Poppler 取证和 DOCX 错列拒绝。67 个变更 Python 文件语法检查通过。

更广的交付状态及回调对照中，候选剩余 4 个失败和 15 个错误均在原 main 的相同子用例复现。直接覆盖这次审批 CAS 的两个既有夹具错误已修正。两份外部受控 PDF 样本对应的用例缺少本地输入。真实 MySQL 8.4、生产部署和真实 MinerU 请求均未执行。

## 2026-11-16 最终合并与清理核对

| GitHub PR | 合并提交 | 已核对的分支清理结果 |
| --- | --- | --- |
| [#77 冷启动验收与归档](https://github.com/ccisnoxx/md2word/pull/77) | `2303a287762bebba17e4e6503fbe5484506b9928` | 确认 `main` 包含原分支末端 `c663210d`，本地和 GitHub 上的 `codex/production-cold-start-bootstrap` 均已删除。 |
| [#78 参数值列同源取证与核定](https://github.com/ccisnoxx/md2word/pull/78) | `230dd1cb72c48814b4e79d558ace435d995afaca` | 确认 `main` 包含原分支末端 `525904a0`，本地和 GitHub 上的 `claude/parameter-column-binding-check-cb3979` 均已删除。 |

- 确认 `codex/mineru-v4-language-mapping` 的末端 `f44a1d71` 已通过 [PR #74](https://github.com/ccisnoxx/md2word/pull/74) 的合并提交 `f2a60afc` 进入 `main`。分支无关联工作区，已安全删除本地分支，GitHub 上也已无该分支。
- 原 Claude 分离 HEAD 工作区的 HEAD 日志包含 21 个不同提交，均已进入 `main`。删除前确认没有未提交改动或未跟踪文件。被 Git 忽略的内容为可重建的 Python 缓存、Trellis 更新检查标记及与主工作区逐字节相同的 Claude 本地配置。原工作区目录及 Git 登记均已移除，主工作区的配置副本仍在。
- 冷启动、参数表及历史证据复验使用的临时工作区均已移除。最终只登记了主工作区，没有残留工作区目录或待清理登记。
- 补记前，经 `git ls-remote --heads origin` 确认 GitHub 仅有 `main`，本地也仅有 `main`。本地 `main`、`origin/main` 和 GitHub 的 `main` 均指向 `230dd1cb72c48814b4e79d558ace435d995afaca`，提交领先和落后均为 0。当时主工作区没有已暂存、未暂存或未跟踪的文件。
