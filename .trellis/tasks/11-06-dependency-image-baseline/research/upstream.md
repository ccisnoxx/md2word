# 官方资料与取舍依据

检索日期 2026-11-06。仅研究，没有下载包或镜像；没有复制上游代码。工具文档的最新版不能代替已安装版本行为。

- [uv compile](https://docs.astral.sh/uv/pip/compile/)：可消费 requirements 和 constraints 输出完整标准锁。首次无既有锁时仍须显式约束目标版本，否则不带 upgrade 也可能选新版。[目标环境解析](https://docs.astral.sh/uv/concepts/resolution/)说明跨平台解析不能等同目标安装验收。
- [uv/pip 差异](https://docs.astral.sh/uv/pip/compatibility/)及[上游 changelog](https://github.com/astral-sh/uv/blob/main/CHANGELOG.md)、[PR #21235](https://github.com/astral-sh/uv/pull/21235)：binary policy 与生成 hash 的联动有演进，不能假设旧版编译 hash 只含 wheel；安装端独立 wheel-only。本机 0.11.19 实际 help 支持 constraints、hash、no-build、python-platform/version；对应 release 页面未取到足够变更正文，不宣称该版无已知问题。
- [pip 安全安装](https://pip.pypa.io/en/stable/topics/secure-installs/)：全闭包精确版本和 hash 校验配合 wheel-only，避免隐含源码构建链；版本相等或 freeze 不等于制品/来源验证。
- [pip-tools 文档](https://pip-tools.pypa.io/en/stable/)及[发布记录](https://github.com/pypa/pip-tools/releases)：可提供同类锁，存在 pip 26 系列兼容修复历史；未安装且无必要额外引入，作为备选而非第二条常驻流程。
- [PyMySQL 安装说明](https://pymysql.readthedocs.io/en/latest/user/installation.html)：sha256_password/caching_sha2_password 的认证能力需要 rsa extra。远端额外三项 cryptography/cffi/pycparser 与此相符，但不证明当前账号实际采用该机制；建议显式保留能力，避免锁定时丢包。
- [Docker 固定镜像](https://docs.docker.com/build/building/best-practices/)：tag 可变，digest 固定内容。这里只采用镜像身份原则，不采用文中的 CI 建议。[BuildKit 配置](https://docs.docker.com/build/buildkit/configure/)与[配置语义](https://docs.docker.com/build/buildkit/toml-configuration/)要求区分 builder 与 daemon 来源。
- [Requests 官方安全公告](https://github.com/psf/requests/security/advisories/GHSA-9hjg-9r4m-mvj7)：特定 URL/netrc 问题影响 <2.32.4，2.32.4 修复。本机/目标观察都是 2.34.2，但 requirements 宽范围容许旧版；后续锁不得默默降到受影响版本。此项不是全包安全审计。
- [python-docx 历史](https://github.com/python-openxml/python-docx/blob/master/HISTORY.rst)：存在 lxml pin 影响 Python 安装的历史，支持按真实版本组合验证；不能据此推断当前组合不兼容。

安装来源候选仅为官方 PyPI/官方 Docker Hub 或已核实等价制品；没有用星数、流行度或本机可用性代替兼容与来源证据。锁生成器若需要重新取得，另核对固定版本官方制品及许可证元数据。
