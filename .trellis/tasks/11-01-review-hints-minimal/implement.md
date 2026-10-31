# 实施与校验

## 实施轮执行边界（已完成）

- [x] 核对最新 main 并建立独立 worktree，外置 before.json 记录原八工作区/索引/全部未提交内容。
- [x] 用户明确批准上一轮最终范围并授权创建任务、规划、实施及仅两个新增模块；本规划不扩围。
- [x] PRD 收敛、design/implement 与上下文清单可审阅。
- [x] 运行 task.py start 激活本任务，原工作区任务与配置保持。
- [x] 后端 Trellis implement 代理只负责 review_content.py 和新 Python 回归。
- [x] 前端 Trellis implement 代理只负责四份前端源码和新 Vitest 回归。
- [x] 主会话补必要 Spec，独立 Trellis check 仅只读复核，不自行跑检查或修复。
- [x] 主会话仅执行两份新增直接回归；先诊断实际失败，只有相关输入变化才重跑受影响模块。
- [x] 核对精确14路径、索引为空、无额外提交、原八工作区与远程引用保持。

## 实施轮唯一应用检查（已完成，本提交轮不重跑）

以下命令仅记录实施轮已完成的检查，本提交轮不重跑。后端使用已安装项目 venv，不建立新环境：

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/sc/PycharmProjects/md2word/.venv/bin/python -m unittest tests.test_document_job_review_hints -v
```

前端使用既有 node_modules 中 Vitest，若新 worktree 没有依赖目录，仅在新 worktree 建 ignored node_modules 目录，按包链接已安装依赖；不链接共享 .vite/.cache，缓存保留新 worktree，不安装或改动共享依赖：

```bash
node ./node_modules/vitest/vitest.mjs run src/pages/documentJobReviewHints.test.ts --config vite.config.ts --reporter verbose --maxWorkers=1 --no-file-parallelism --no-cache
```

工作目录为当前 worktree/frontend；仅此单模块，不调用 test:unit 聚合脚本。不运行旧 tests、lint、typecheck、build、smoke、CI、数据库或线上验收。记录真实 argv、cwd、日志、退出码及源码/依赖指纹。

## AC 对应回归

- 后端：真实 uncertain/rebound 事实到公开块flags；普通/未知/派生块；保留既有flags且不修改输入、状态或来源合同。
- 前端：GET及筛选参数；源页0/20/null、多span与固定建议；info与warning区分；允许/禁止下载及publish eligible/enabled分离。
- 前端：初次与追加分页、snapshot冲突、not_ready/unavailable/错误；任务切换、同任务新代/IR/结果与旧响应/finally不得覆盖新源。
- 不以源码字符串断言替代行为验证，不复制生产算法到测试。权限/selector/renderer未改，既有保护保持，新增模块不扩大成旧门禁。

## 实施轮结束状态

实施结束时任务保持 in_progress、未归档，源码、测试、Spec与六份记录未暂存。本提交轮仅保存这一批为一个本地提交；不执行 task.py archive 或 add_session，避免自动记账提交。结果不冒充浏览器视觉、真实DB、部署或Word外观验收。

## 最终实现与验证证据

- 后端新增模块首次9/9通过，退出码0；真实测试耗时0.009秒。准确argv/cwd/env、源码/依赖SHA及stdout/stderr记录在工作区外 evidence/backend-regression-attempt-1.*。
- 前端新增模块首次39/39通过，1个Test File、退出码0，Vitest总耗时1.32秒；只导入SFC做正常编译，没有运行独立build/typecheck。准确执行记录在 evidence/frontend-regression-attempt-1.*。
- 两模块各运行一次，均无失败；源码和依赖指纹保持，通过结果直接复用。不执行旧测试、lint/typecheck/build、smoke、CI、数据库或线上校验。
- 独立只读复核先确认1项P2源IR绑定遗漏，前端在首次执行前修复并补直接反例；增量复核确认问题消除，无剩余确定缺陷。原API已公开的源IR字段在前端按既有可选字段约定补齐，缺字段失败关闭并与显式null区分，未改旧fixtures。
- 后端只新增8行读投影；前端只消费现有DTO与GET，未修改producer/renderer/router/schema/仓储、正式状态或动作授权。
- 新增/触及的Python注释、模块文档以及前端建议/错误说明使用中文；机器码、字段名和协议值保留原文。
- 实施结束时任务保持in_progress、不归档/add_session，未产生提交，本批14个路径未暂存。本提交轮已获得一笔本地提交授权。最终原八工作区/索引/未提交内容及远程引用核对以外置preservation-result.json为准。
- 未验证浏览器视觉、真实MySQL、部署或Word外观；48个直接用例不作为这些验收证据。

## 本地提交计划（本轮新增授权）

- 仅暂存五源码、两新增回归、一Spec、六任务记录，共14个路径，并创建一个本地提交；不包含历史测试维护或文档同步。
- 本轮开始时HEAD为44fd4ad8、暂存区为空；已记录其他八工作区/索引/未提交内容、远程heads/tags及仓库配置基线，提交钩子无可执行脚本。
- 源码、回归、Spec及相关依赖与已复核/成功版本相同；本轮不再测试、不配置CI。
- 本记录随本次唯一提交纳入；精确SHA见Git历史和工作区外 evidence/local-commit-20261101/commit-result.json，避免回填自身SHA增加提交。
- 提交后仅核对精确路径、单一父提交、干净工作区与其他工作区保留情况；不推送、合并、删分支、归档或add_session。
