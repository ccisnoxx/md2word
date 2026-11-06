# B10 执行与验证记录

## 实际执行

工作目录始终为 `/Users/sc/PycharmProjects/md2word-wt/b10-measurement`，Python 统一设置 `PYTHONDONTWRITEBYTECODE=1`。无 commit、push、发布、归档、add_session、依赖安装或 Spec 修改；没有运行应用测试、前端测试、unittest discover、check_release 或在线门禁。

1. **120 档探测：首次失败，修复夹具后通过。** 两次实际命令相同：
   ```bash
   PYTHONDONTWRITEBYTECODE=1 /Users/sc/PycharmProjects/md2word/.venv/bin/python .trellis/tasks/11-06-b10-measurement/measure.py --sizes 120 --output smoke
   ```
   首次尝试通过普通任务 patch 写发布指针，被真实仓储的不可变字段约束拒绝（ValueError）。修正任务内播种脚本，使用真实模型和仓储内部 `_write_job` / `_insert_publication` 构造发布元数据；未放宽应用约束。随后四路径 smoke 通过，保留 smoke.json/csv；这份数据采用初轮测量方法，不用于最终预算判断。
2. **首轮完整测量：主动中断，非成功结果。** 命令与最终命令相同：
   ```bash
   PYTHONDONTWRITEBYTECODE=1 /Users/sc/PycharmProjects/md2word/.venv/bin/python .trellis/tasks/11-06-b10-measurement/measure.py --output results
   ```
   发现脚本把 query_only PRAGMA 和 authorizer 加到了计时连接中，会对短连接路径增加测量开销；仅中断本任务进程（session 8737，退出码130），finally清理临时数据库。完整完成的120/1000档另存 guarded-baseline.json/csv，JSON标明 interrupted_method_correction；10,000档未完成，不充作正式结果。
3. **正式完整测量：通过。** 将只读保护限制在独立计数阶段，正常计时和内存使用真实 backend.connect 后，重新执行上条命令，session 73205 退出0。results.json/csv包含3档×4路径、每格5次计时，共60个原始样本；前后数据库SHA一致，脚本SHA与当前measure.py一致。正文读取全零、临时SQLite及sidecar已清理。
4. **最终证据核对：通过。**
   ```bash
   PYTHONDONTWRITEBYTECODE=1 /Users/sc/PycharmProjects/md2word/.venv/bin/python .trellis/tasks/11-06-b10-measurement/verify_results.py
   ```
   核对12格覆盖、5次样本与P95、中位数、CSV中位数/返回行字段、任务/文件/事件比例、只读SHA、保护与清理公式、任务解码、零正文/事件SQL和临时库清理，输出verification.json。它不宣称核对了所有CSV字段，也不替代应用回归测试。
5. **语法、空白与最终范围：通过。** 对两个新增脚本做AST解析；`git diff --check`通过，另检查新增任务文件的行尾空白和结尾换行（Git默认diff不覆盖未跟踪文件）。`git status --short --untracked-files=all`确认仅本任务目录新增，无跟踪文件改动、无临时数据库或pycache。

## 独立只读审查

Trellis检查代理只读复核脚本、真实调用链、已完成初步结果和静态分析，未运行测量或应用测试、未修改文件。确认34条列表SQL含BEGIN、返回行/模型解码/保护JSON解码/推导扫描分开、N×P扫描关系成立、tracemalloc与计数独立；没有发现需修复的严重缺陷。计时额外防写开销已按审查修订。

后续只读复核verify_results.py指出“JSON/CSV一致”描述过宽（实际仅比中位数和返回行），已将说明限定到真实验证字段。最终12格由主会话执行verify_results.py核对。当前未配置/安装Python lint/type工具；没有为测量安装依赖或扩展检查范围。

## 路径偏差与处理

证据核对脚本首次创建时误落到仓库根目录 `verify_results.py`，一次语法检查因预期任务路径不存在而报FileNotFoundError。发现后立即将本次新增文件移入本任务目录，没有覆盖或修改任何既存文件；再次AST解析通过。此为执行路径偏差，保留记录，不声称全过程从未出现目录外新增；最终工作区仅任务目录新增。

## 未验证边界

未运行真实MySQL、file后端、HTTP序列化、并发、生产、Provider、MinerU、真实对象存储或冷缓存测量。扫描是SQLite执行计划推导，不是MySQL引擎rows_examined；峰值Python分配不是完整进程RSS。详见report.md和static-analysis.md。

## 文档与收尾

新增脚本注释、docstring、日志及错误说明使用中文；协议字段和Python标识符保持原文。规划与任务状态只写本目录，不创建全局Trellis开发者身份/current-task，不归档、不生成Trellis记账提交。AC状态是本次报告状态，不代表Claude验收。
