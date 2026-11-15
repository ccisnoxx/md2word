# 隔离候选 Worker 和 MinerU 实物验收

2026-11-15 在独立 Colima context `colima-md2word-rollout5` 运行候选镜像，实际容器 `rollout5-worker-acceptance` 的 image ID 为 `sha256:6127850d19531ef99844ffb99090dfbb09dab1f0e997d1673de1381987618f1f`，平台为 Linux/amd64。验收用例在容器内启动绑定随机 loopback 端口的 Uvicorn 和正式 `scripts/dev/run_document_worker.py`。Worker 启动和消费都使用实际角色 `md2word`（UID 1000），各用例使用隔离 Redis 队列、文件元数据和本地对象目录。MySQL 锁实测在同一隔离环境另行运行。

实际消费容器四项取证工具分别是 `/usr/bin/pdfinfo`、`/usr/bin/pdftotext`、`/usr/bin/pdftocairo` 和 `/usr/bin/pdftohtml`。四个可执行文件的 `LC_ALL=C -v` 均报告 `25.03.0`。同源实物测试完成几何核定，确认此版本可取字框和绘制证据。macOS 上的现成工具只用于另一个宿主机对照，版本 `26.06.0`。

## 真实 P7 上游与同源缓存对照

重新上传 `gs-008` 的公开 P7 PDF，以真实 MinerU 且强制轮询，Worker 使用实际返回的 ZIP。上传登记与回包登记的实际读取长度和摘要都正确，对账同代源文件、原解析代、`batch_id` 和 `data_id` 成功。正式选择唯一 v2 和对应同文档布局。记录如下。

| 项目 | 真实结果 |
| --- | --- |
| 原批次及 data ID | `be62607d…`、`docjob_a46d…` |
| 上传 PDF | `file_adfb0b13f01c`，112080 字节，SHA-256 `24f724cf0e795f6afeb6fec5c72ff8f144085c59d57fbf0a5c9efbf1808b1eb3` |
| 实际 ZIP | `file_dbb6f10731f7`，解析代 0，231586 字节，SHA-256 `5de05d59fdacea166361bde14625ff8045350b0aefc894a923ff181a030fe033` |
| 所选 v2 | `94021190-eac6-4cfb-8f36-027a0037221d_content_list_v2.json`，SHA-256 `7ebf782c6b11c4ebff391697f1a0f1e500031115d4075cd4596cc4d66e9efff0` |
| 同文档布局 | SHA-256 `159a58f70d60cf53a083722ff32ed4192852f348b6ad57c0c3d58dfcc2cdd193` |
| 包内对应原件 | 112172 字节，SHA-256 `69e9aaba32caeaabb31a76e5c419d2e9c497c5d7e275bd34524bb0e40784625b` |
| 实际 Word 和表报告 | Word SHA-256 `6c103bf107eacdf8a9fb8f1e6aa0f2a58b4f37f92f4a9f75a6b6bad55d76e39a`，表报告摘要 `fb6cb783605dbf8f9eb62e1ee9df0572a96e50ed9b4a4403cd9716ff20d62088` |
| 门禁 | 实际新鲜回包原 18 个跨列 finding 全部以 `source_pair_unverified` 保留，0 个修正。审批 `409 review_quality_blocked`，发布 `409 publication_quality_blocked`。同包核定入口还要求包内原件同源。 |

同一候选从保留的完整历史 `gs-008` 回包重新转换时，原 PDF 与包内对应原件字节相同，实际 Word 仍是 `±5 µV` 只在 TYP、`±100 µV` 只在 MAX。历史回包原 23 个跨列 finding 中 9 个通过认证，其余 14 个为 `row_ambiguous` 且阻断。真实新鲜回包与历史同源缓存是两次独立输入。新鲜回包缺少通过逐字节配对的正例，按验收标准继续维持关闭。

## 新鲜 LOW/HIGH 上游回包

合成 LOW/HIGH 的源 PDF 在同一候选容器通过正式上传、本次解析提交、轮询和 ZIP 登记独立跑完。验收使用新鲜批次 `a0e10b67…` 和 data ID `docjob_d3e7…`。此前宿主真实提交的恢复验证未计入本次同代结果。

| 项目 | 真实结果 |
| --- | --- |
| 上传 PDF | 1503 字节，SHA-256 `bf90bdcb7a4a23beaa5496f371190a85461966d1c35b4b452ec983b62c974b6d` |
| 实际 ZIP | `file_32ecd877f286`，解析代 0，21630 字节，SHA-256 `a61757b0fb85ba190f5e706f3c5289fc25ae734f5e1328b1a39698dcc07dacb8` |
| 所选 v2 与布局 | v2 SHA-256 `6fcd9dc59637bd489fa048a1da0d4c8d4bf35e8f0f9d5f42a8290a7ad5d6f8c1`，布局 SHA-256 `191d9147a9178efaf8f03a1270324ccc056cf425f0ab8c44456eed2258c8a98c` |
| 包内对应原件 | SHA-256 `c5ee429ffb598c06136bd481f4e916fa75a0434cadf93e05457299f260ca07a3`，与上传 PDF 不同 |
| 实际 Word 和表报告 | Word SHA-256 `eb00f045aa97c52211e11d366784fe11e743e85602c32798eae1bf7cdd804666`，表报告摘要 `593a3ccdbe181025e7541d7e0aae8f407871546119604531c9f3922894826eac` |

此真实回包没有数值跨列候选，0 修正、0 值列未决，整体质量为 `pending`。没有同源可自动修复的实证。另一方面，原不嵌字体的 LOW/HIGH 合成原包在宿主 Poppler 26.06.0 已通过两条自动修正，放到候选 Poppler 25.03.0 后，观察的 `Mode` 词框缺少可确认的绘制字形，表头不确定，3 项全部以 `header_ambiguous` 保留。未做任何放宽。

## 单公司开关和回滚演练

隔离夹具保留同一划线几何、行条件和数值，重建 PDF 并嵌入 DejaVu Sans，使候选 Poppler 可确认文字和绘制。PDF SHA-256 为 `07a8f8eb81e699060176f982216fb5c08d3e6d8f64285e85d962296ca7ace5cc`，配套 ZIP SHA-256 为 `290ed4d9ef35fd2001ba32dbd2f6a12cd79d507048f73c8e557012cfbcd98a68`。此套受控原包用于复现同源正例以及灰度回滚。套用到现成版式的新字体仅是验收输入，候选镜像和认证逻辑相同。

初次用 file 元数据实证开与关的区分，名单内经 Word 实物认证锁定两个格，名单外仍为普通转换，名单外新同包动作返回 409。file 后端没有正式资源版本仓储，名单内动作返回 `503 new_generation_resources_unavailable`。随后用独立 MySQL schema、实际资源版本、相同 Redis 队列和相同本地对象存储演练完整生命周期。

| 步骤 | 实际审批、发布或 Word 结果 |
| --- | --- |
| 关闭基线 | 0 个自动修正，原跨列质量阻断保留。 |
| 启用该公司 | `7.2e-4 s` 只归 HIGH，`43 ms` 只归 LOW。最后一行 `48 ms` 仍跨 LOW–HIGH，`row_ambiguous` 待核定。审批 `409 review_quality_blocked`，发布 `409 publication_quality_blocked`。 |
| 名单外对照 | 0 个自动修正，原跨列质量阻断保留。以名单外管理员提交新同包核定，实际返回 `409 table_value_column_review_disabled`。 |
| 名单内接纳 | 管理员从未决记录生成最后一行的 HIGH 核定。暂未启动新的消费，正式接口返回 202，冻结原包及第 1 执行代。 |
| 关闭并清空名单 | API 和 Worker 以原镜像、存储和队列重启。新同包申请返回 `409 table_value_column_review_disabled`，已接纳原 UUID 原样重提返回 200，接纳代仍为 1。新普通任务 0 修正且仍阻断。 |
| 已接纳第 1 代完成 | 正式 Worker 继续原包，原 raw 身份和上一代 Word 的实读 SHA-256 不变。新 Word SHA-256 为 `494bc94cd166581d2d394d633a0d559aebe06101b4d21d518722c11ad2a002d7`。实际 3 格都只占单列，第三个 `48 ms` 只在 HIGH，LOW 空出，0 项未决。正式批准返回 200。 |

此轮容器演练的对象存储是隔离本地对象目录，预览执行未启用，未测完成态生产预览及正式发布 201。发布的独立并发门禁及正向发布 HTTP 另见本任务 MySQL 专项。

## 复核入口

真实公开样本回包、逐格摘要和灰度记录复制到本机受限临时目录 `/tmp/md2word-rollout5.roi2be/evidence/`。复核脚本位于主工作树下的忽略目录 `tests/tmp/rollout5-worker-1ddydx7T/`，其中 `accept.py` 用独立对象目录、HTTP 和正式 Worker 取证，`canary.py` 用同一隔离存储走灰度和回滚，`docker_live.py` 只按键名注入本地凭据并关闭回调。测试凭据和真实包均未写入 Git。
