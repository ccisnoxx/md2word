# 交付与验证记录

- [PR #59](https://github.com/ccisnoxx/md2word/pull/59) 已合入 `main`，交付提交 `1b981e97`，合并提交 `f8342714`。交付限[页映射合同](../../../../../docs/contracts/pdf-ir-word-page-mapping-contract.md)和[兼容回归](../../../../../tests/test_preview_page_mapping.py)。
- AC1、AC4 通过合同差异复核。B1 回退仍待验证，合同记录了所需候选构建及恢复证据。
- AC2、AC3 采用实施阶段结果。`.venv/bin/python -m unittest tests.test_preview_page_mapping` 共 5 个定向用例通过，耗时 1.341 秒，覆盖两版读取、零基页码、多页估算及内外层校验边界。归档阶段复用该结果。
- 历史 PR #8 暂缓。B1 演练和部署均未执行。
