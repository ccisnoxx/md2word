# Attention

本文件是 CodeStable 技能启动必读的项目注意事项入口。所有 CodeStable 子技能开始工作前必须读取它。

## 项目碎片知识

<!-- cs-note managed: 用 cs-note 维护，新条目按下面分节追加 -->

### 编译与构建

### 运行与本地起服务

- 真实 MinerU 转 DOCX 转换、LLM 翻译联调优先使用 `/Users/sc/miniconda3/envs/md2word/bin/python`；这个 conda 环境已包含 `openai`、`python-docx`、`PyYAML`、`beautifulsoup4`、`loguru` 等运行依赖。当前主模式约定是 `translation_mode=direct`（默认直出）和 `translation_mode=en2zh`（英文 PDF 翻译成中文 Word）。
- 线上 Golden Sample 复跑不能假设部署容器内已有 `tests/fixtures/golden_samples/`；需要先准备脚本、manifest 和 PDF，或走专门的线上复跑方案。

### 测试

- 本项目测试和后端验证默认使用 `/Users/sc/miniconda3/envs/md2word/bin/python`；不要用 macOS 本机 `python3` 跑 `unittest`，该解释器缺少项目依赖（例如 `PyYAML`）。

### 命令与脚本陷阱

### 路径与目录约定

- 部署文档里的 `md2word-api.962850.xyz` 与现场 hostdzire nginx `server_name` 曾出现不一致；真实环境联调或更新公开入口文档前先核对现场配置。

### 环境变量与凭证

- LLM 翻译配置默认从仓库根目录 `.env` 读取，当前由 `config.py` 加载到运行时；优先使用 `OPENAI_BASE_URL`、`OPENAI_API_KEY`、`OPENAI_MODEL` 和翻译分批相关配置。

### 其他
