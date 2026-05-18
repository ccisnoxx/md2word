---
doc_type: learning
track: pitfall
date: 2026-05-18
slug: mineru-callback-stage-validation-pitfall
component: app/api/v1/routers/mineru_callbacks.py, app/services/jobs/stage.py
severity: medium
tags: [mineru, callback, fastapi, backgroundtasks, stage]
---

# MinerU callback 状态校验不要只放在后台 stage

## 1. 问题

MinerU callback 入站后，如果把“任务状态是否允许处理 callback”的校验只放到后台 `process_callback` stage 里，`BackgroundTasks` 会把异常一路冒泡到请求处理链，导致本该返回 `400` 的请求变成后台执行异常。

## 2. 症状

- 回调接口看起来已经返回成功入队，但后台实际抛错。
- 测试里会出现 `BackgroundTasks` 触发的异常栈，而不是预期的 4xx。
- 任务状态已经不允许处理 callback 时，错误位置不直观，排查成本高。

## 3. 没用的做法

- 只在 `process_callback` 里校验任务状态。
- 让后台 stage 负责所有请求级前置条件。

## 4. 解法

- 在 router 里先做同步校验，直接返回 `400`。
- `process_callback` 只保留防御式兜底，遇到非法状态就跳过，不再抛异常。

## 5. 为什么有效

请求级错误应尽量在同步链路暴露，这样响应语义清晰，`BackgroundTasks` 也不会把本该是客户端错误的问题转成后台异常。

## 6. 预防

- 任何“入队前就能判断”的条件，都先放到 router / dependency。
- 后台 stage 只处理真正的异步副作用。
- 新增 callback / webhook 时，优先把 4xx 语义放在请求路径上。
