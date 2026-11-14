# RND-505 页映射合同与兼容回归

## 目标

给当前主干的 PDF → DocumentIR → Word 预览页映射补齐维护合同与兼容回归，明确旧产物的读取行为和页定位的可信度。

## 背景

基线为 `main@e902143b`。[历史 PR #9](https://github.com/ccisnoxx/md2word/pull/9) 提供早期合同与测试场景。当前主干已有映射生成、读取和消费链路，后续交付以当前实现为依据。

## 需求与验收标准

- [x] **AC1 合同。** 文档说明 `word-preview/v1` manifest 的可选 `page_mapping` 字段、`pdf-ir-word-page-map/v1` schema、`source-order-nearest/v1` 和 `source-order-nearest/v2` 算法版本、身份绑定、置信度、失败边界及审核内容和页面质量中的用途。
- [x] **AC2 兼容读取。** 定向用例覆盖两版有效映射、旧 manifest 缺映射字段、独立的内层 hash 错误和身份绑定错误。内层失败降级为映射不可用，已认证的预览仍可用，旧产物和状态原样保留。外层 manifest 完整性失败维持现有错误行为。
- [x] **AC3 页定位。** 定向用例保留零基页码 `0`，断言有真实正文目标的单页定位为高置信，多页只提供低置信起始页且 `page_range=null`。
- [x] **AC4 回退边界。** 合同将 B1 标为待验证，写明将来认定兼容回退所需的证据。当前任务的离线回归仅证明当前读者的兼容行为。

验收依据见[交付与验证记录](./verification.md)。

## 范围边界

后续交付限页映射合同与直接相关的回归测试。生产实现、API、配置、数据迁移、历史产物回填、B1 实现或演练均在范围外。PR #8 暂缓。

规划阶段仅建任务与整理规划。保留 `en2zh-runtime-evidence.md` 原样，不操作其他 worktree 或历史 PR。
