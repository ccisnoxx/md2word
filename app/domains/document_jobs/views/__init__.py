"""document_jobs 应用层读模型：用例的输出契约，HTTP 层直接复用为 response_model。

本包不得导入 schemas（HTTP 请求模型与仅由路由组装的响应包装）；依赖方向固定为 schemas → views。
"""
