---
doc_type: learning
track: knowledge
date: 2026-05-18
slug: mineru-callback-router-should-stay-light
component: app/api/v1/routers/mineru_callbacks.py
tags: [mineru, callback, fastapi, api-design, guards]
---

# MinerU callback router 应该只做轻量编排

## 1. 背景

MinerU callback 的职责边界很清晰：鉴权、归一化、任务匹配、入队。真正的状态推进和持久化，应该放在后台 stage 里。

## 2. 指导原则

- router 只做同步前置校验和编排。
- stage 负责异步副作用和状态写入。
- `data_id` 优先于 `batch_id`，能减少错误匹配。

## 3. 为什么重要

如果 router 里混入太多业务逻辑，callback 入口会变成“半个 service”，后续再加结果恢复或后处理时，很容易把边界弄乱。

## 4. 何时适用

- Webhook / callback / 外部回调入口。
- 需要 token、checksum、allowlist 这类请求级护栏的 API。
- 需要把“是否接受请求”和“如何处理请求”拆开的场景。

## 5. 示例

这次实现里，router 负责 `verify_*` 和 `enqueue_callback()`；`process_callback` 只负责把 `done + full_zip_url` 收口到 `parsed`，把 `failed` 收口到 `failed`。
