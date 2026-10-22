# 原始 HEAD 回归失败复现

日期：2026-10-22。为区分整合回归与既有测试问题，主会话通过 git archive 将初始 HEAD `596a2de7ed29edb7fdb378d91c17bda09b7f1066` 解包到独立临时目录，使用项目同一 `.venv/bin/python` 运行10个未分类失败 selector。当前工作区没有被回退或切换；临时快照不含本次CON102/103/104整合及TR406代码。

- 命令：项目虚拟环境Python `-m unittest` 加 `original-head-regression-selectors.json` 中的10个完整selector，cwd为临时checkout，`PYTHONDONTWRITEBYTECODE=1`。
- 实际结果：Ran 10 tests in 1.310s，FAILED (failures=5, errors=5)，子进程退出1；外层采集脚本退出0不表示测试成功。
- 5个MinerU callback测试均在创建响应读取job_id时KeyError，与整合前宽回归相同。
- sqlite/MySQL callback流程均因测试renderer缺失table/image/heading的内容完整性证据而failed，原断言期待succeeded。不得放宽真实完整性校验来通过。
- non-parsing callback返回404而旧断言期望400；两项模板用例实际default@2而旧断言期望default@1。
- 日志：`original-head-regression.log`；精确selector：`original-head-regression-selectors.json`。所有10项均在原始HEAD实测复现，现可归类为既有基线失败；本任务不扩展修复未触及旧callback/模板fixture。
- dependency-con103104-integration.md中另外3条列表/incident/action的旧观测已由接受基线接线修正并单独通过；不混作当前失败。
- 此证据不代替当前TR406候选的定向/adapter/API回归，也不意味着候选不会引入新失败。最终需与当前结果对照。
