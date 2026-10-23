# B1 最终源码构建与本地兼容验证

2026-10-23，当前记录取代首轮及中间构建，未部署，deployed=false。B0仅开发差异基线，不能作为已有新产物后的回退。B1必须携带当前完整reader，仅源码生成常量grouped/v1→single-only/v1，无运行时feature flag或用户参数。

实际执行 `.venv/bin/python -B tests/tmp/rnd503/run_b1_build.py` exit0；实际模块路径、来源清单和源码字节均先断言，结束重算294来源无变化。隔离根：`/var/folders/m5/j06tv2sn1hn93d6f33j559jm0000gn/T/rnd503-b1-build-1wrv0wpc`。

| 身份 | SHA-256 |
|---|---|
| 正常来源清单 | `1b87278761248cb80c53eaf37c14b567dd0069baead6c3319ff4223998434bf3` |
| B1来源清单 | `a5cfd2bd25437d26ddb9b208af52f12b9c08fbb46966e9f7a12b100dfb90e6d7` |
| 正常image_evidence.py | `3adce3b48164897de9d483be40df4487b36098aab204bbe408300729a9dc4dcb` |
| 实际B1模块 | `5f8d75857937b338f1445bdce3d86a18296df8d5a0c46c1462215ca3e52e825a` |

两份294项清单唯一差异为该生成策略文件，真实清单保存在b1-build-manifest.json。任务副本与tests/tmp/rnd503/b1/build-manifest.json字节相同；b1/image_evidence.b1.py与实际加载字节/hash一致。

最终原始日志：tests/tmp/rnd503/post-review/closure-b1.log、b1/child.log，7 tests/OK13.280s，55 subTests（原45+新增全报告字段缺失10）。覆盖三恢复入口、跨代明确指针、冻结输入/原路径删除、损坏不重新选件、真旧无marker、旧公式与依赖摘要。

实际B1 reader读取17份已存在产物：新正常图对/单图3、修复前正常3、新mixed-column/mixed-geometry/大缩进模板3、旧单位及省略属性形态7、修复前真实B1单图1。legacy-indent-units的dxa/pct/auto/nil/omit-type/omit-width/omit-both每份均保留真实模板字节、原IR和报告；修复前reader及最终正常reader也都已先重验这些文件。不是重生成旧件后冒称兼容。

实际B1默认新生成single-only文件后，最终正常reader读取通过；正常reader也读取修复前真实B1旧件通过，共2个方向断言。报告不重写旧hash，缺image_geometries按原span.geometry；B1需含当前reader以读取带可选差异的当前产物。未演练线上部署、真实队列切换或跨主机回退；不得删历史文件/审计、覆盖发布件或卸载reader回B0。

首轮历史证据在tests/tmp/rnd503/post-review/before-b1与before-visual，当前最终清单不再沿用旧指纹。完整当前产物hash见artifact-hashes.json；独立critical最终核对记于post-implementation-review.md。
