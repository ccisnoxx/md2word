# 上游依据与方案取舍

查阅日期 2026-11-06；只采用 MinerU/Requests 官方资料。无上游源码复制，无新依赖。

1. [MinerU API v4](https://mineru.net/doc/docs/index_en/) 定义 full_zip_url 为结果 ZIP，并提供 cdn-mineru.openxlab.org.cn 示例。所查页面没有 redirect 条款；未找到承诺不等于生产必然跳转，也不支持“可无代价禁止所有跳转”的结论。
2. [Requests API](https://requests.readthedocs.io/en/stable/api/) 公开 Session.send(PreparedRequest, **kwargs)。[官方 Session 源码](https://requests.readthedocs.io/en/latest/_modules/requests/sessions/) 的初始请求和 resolve_redirects 都走 self.send，默认跳转上限 30。因此在公开发送边界统一检查可复用其跳转逻辑；这是设计推论，仍需离线定向测试。
3. [Requests 高级用法](https://requests.readthedocs.io/en/stable/user/advanced/) 说明 Session cookie/连接复用、上下文关闭、PreparedRequest/环境设置、流式响应释放。方案仍从 Session.get 发起，避免自行构造低层 send kwargs 漏掉代理/CA。
4. [官方 issue #5677](https://github.com/psf/requests/issues/5677) 记录过 Session.send/代理环境差异。它是避免绕过 request 流程的历史线索，不是当前 2.34.2 仍有同一缺陷的证明；当前行为以本机源码为准。
5. [官方更新记录](https://requests.readthedocs.io/en/latest/community/updates/) 记录了 2.32.x HTTPAdapter TLS/连接接口变化。本方案不覆盖这些内部接口，也不需要自建 HTTPAdapter 类型。
6. [GHSA-9hjg-9r4m-mvj7](https://github.com/psf/requests/security/advisories/GHSA-9hjg-9r4m-mvj7) 说明小于 2.32.4 的特定 URL/netrc 凭据问题在 2.32.4 修复。本机 2.34.2 高于修复版本，但 requirements 下界容许旧版，生产未知。B03 不宣称解决所有环境凭据或依赖风险，不擅自设 trust_env=False 影响代理/CA；版本治理仍是 B02，未来部署结论需要实际版本证据。

## 本机交叉核对

- .venv/lib/python3.11/site-packages/requests/__version__.py:8：2.34.2。
- .venv/lib/python3.11/site-packages/requests/sessions.py:292：resolve_redirects 调用 self.send。
- .venv/lib/python3.11/site-packages/requests/sessions.py:651：request 合并环境设置后调用 self.send。
- .venv/lib/python3.11/site-packages/requests/sessions.py:752：send 选 adapter 并发送，再处理跳转。
- .venv/lib/python3.11/site-packages/requests/models.py:104：默认上限 30。
- .venv/lib/python3.11/site-packages/requests/models.py:485：prepare_url 规范化 URL。

以上是源码阅读，没有执行请求；未将官方示例自动扩充为允许名单，也未读取真实凭据。
