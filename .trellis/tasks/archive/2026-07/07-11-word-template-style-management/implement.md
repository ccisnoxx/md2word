# 实施清单

## Phase A：合同与红灯基线

- [x] 增加真实 seed 无修改 round-trip、schema/renderer 字段一致性和 operator 使用 draft 的失败测试。
- [x] 记录当前目标测试 `400 != 201` 作为修复基线。
- [x] 建立 `layout_config_schema.py` 严格完整模型和有序编辑 schema。
- [x] 为 seed YAML 显式补齐与 renderer 当前默认一致的 `table_style.header_fill`。
- [x] 把页面宽高建模为只读并无损保留，移除猜测性 schema version 默认。

## Phase B：后端安全与持久化

- [x] 演进 GET/POST schemas 和 router，支持指定版本读取、base/hash/active CAS 与结构化错误。
- [x] 将 layout config 读取、版本列表和写操作统一收口到 admin 管理边界。
- [x] 分离 published production resolver 与 admin draft verification resolver，封堵 create/clone/retry draft 注入。
- [x] 新增 MySQL `resource_version_sequences` 和原子整数分配接口。
- [x] 实现 staging 目录、fsync、原子 rename、create-only DB 记录和失败清理。
- [x] 让 DB default pointer 成为版本唯一来源，停止 set-default 改写 manifest 版本指针。
- [x] 实现 manifest seed 的幂等 published/default bootstrap。
- [x] 严格校验版本文件存在、YAML schema 和 payload hash；禁止版本化配置静默 fallback。
- [x] 补充 draft/publish/default/rollback、并发、失败注入和真实 DOCX 属性测试。

## Phase C：前端产品化

- [x] 更新 templates API/types，采用有序 schema 和 dirty changes payload。
- [x] 移除前端分组/字段范围第二真相，保留控件类型映射。
- [x] 完善版本选择、active/baseline 状态、保存后 draft 基线和请求竞态防护。
- [x] 完善字段级 422、409 冲突、403/503 和未保存保护。
- [x] 显式过滤配置中心 admin 卡片，保持侧栏和路由 guard 一致。
- [x] 增加近似 A4/文本/表格/页眉页脚预览及非权威提示。
- [x] 增加“创建验证任务”和“查看版本”后续动作，不复制模板版本发布状态机。
- [ ] 验证 `375/768/1024/1440px`、深色主题、单滚动根和键盘可达性。

## Phase D：文档、验证与审计

- [x] 更新 `docs/api/templates.md`、OpenAPI 和相关 Trellis backend/frontend spec。
- [x] 运行目标后端测试和 templates/document job/renderer 相关测试。
- [ ] 运行 `npm --prefix frontend run test:unit` 与 `npm --prefix frontend run build`。
- [ ] 运行核心 Playwright smoke，覆盖 admin/operator、保存 draft、近似预览和响应式。
- [x] 运行 `.venv/bin/python scripts/ops/check_release.py`。
- [x] 扫描最终 diff：无第二真相、无 silent fallback、无 draft 越权、无半提交和无未说明行为变化。

前端生产构建、Vitest 和 Playwright 因当前 worktree 复用主项目只读 `node_modules`，Vite 无法写 `.vite-temp` 而被沙箱阻止。替代检查已完成：Vue `vue-tsc --noEmit`、三份 smoke TypeScript 编译、release frontend contract/smoke mock 检查。

## 关键验证命令

```bash
.venv/bin/python -m unittest \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_template_layout_config_admin_creates_draft_version_without_mutating_source_yaml

.venv/bin/python -m unittest tests.test_fastapi_jobs_backend tests.test_document_ir_word_renderer_layout
npm --prefix frontend run test:unit
npm --prefix frontend run build
npm --prefix frontend run test:smoke -- --workers=1
.venv/bin/python scripts/ops/check_release.py
```

## 风险与回滚点

- API 保存合同由 full config 改为 changes patch，后端和前端必须协调发布。
- DB 默认指针权威化前必须完成 seed bootstrap 和已有 default 数据检查。
- schema strict 化可能暴露历史 YAML 问题；不得用 `extra=ignore` 或默认值掩盖，应明确迁移。
- 文件/DB 故障测试未通过前不得开放保存入口。
- 生产异常优先把默认指针切回已验证 published 版本，不删除失败版本。
