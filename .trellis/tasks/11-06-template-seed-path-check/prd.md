# bundled seed 同版本受管路径身份修复

用户已授权本 worktree 内创建简短任务文档并直接实施；禁止提交、推送、发布、外部服务访问、仓库外写入、归档和会话记账。

问题：生产已发布 default@2 使用同哈希 DOCX 的受管路径，启动时因与 bundled 路径不同误判冲突。

## 验收

- AC-1：published 记录使用 var/config/templates/default/v2/ 内路径且哈希相同，bootstrap 成功且不改记录。
- AC-2：哈希不同、其他版本/模板目录、任意其他路径、draft、自身 snapshot_hash 不匹配仍抛原冲突异常。
- AC-3：tests.test_template_seed_history 全部原用例通过，不删减原断言；若存在同版本受管路径必须冲突的断言则停止。
- AC-4：测试配置调用真实 build_runtime() 成功，不连接外部服务。

仅修改 read_service.py 的 bundled 校验、定向测试及必要身份 Spec。11-01 PRD 要求身份/完整性冲突失败，未规定同版本受管副本必须冲突；本次细化身份规则，不改变持久化记录、资源内容或默认指针合同。若发现明确相反合同则停止。
