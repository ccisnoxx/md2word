# RND-504 独立实际实现复核

2026-10-23。Trellis检查 `/root/rnd504_check` 与独立只读 `critical_reviewer` `/root/rnd504_implementation_review` 分别完成。当前实现审查与已完成的修订3/4 architect规划审查分开，不能互相替代。

## 最终结论

独立主审确认的3项P2均经主会话独立反例核实并局部修复；同一审查者最终delta复核三项closed，未确认新的合同问题或未关闭新增阻断。任务停review，尚未人工验收，不改done，不提交/push/archive。

最终候选research/candidate-files.json SHA-256：`04ac039011f8cda8dab591bb660ed2c03f38189bbb1d9e3a620eba6f50782d08`。38个路径逐项匹配mismatch=0；冻结三件套hash与授权一致。候选内容清单不包含任务bookkeeping，根工作区仅任务/manifest镜像，不复制业务。

## 三项确认问题、修复与证据

| 项目 | 修复前触发/影响 | 修复与独立复审 |
|---|---|---|
| IR1 / P2 | 文件列表对每个preview成员重新读取并解码整套证据，N页呈N²；审查者1/3/10页=12/30/156次读取，主会话独立3页=30。 | verified_current_preview_files成为实质owner，一次list观测+完整Record匹配；单件/Token各自新观测，无cache。独立10页反例13次（source/manifest/PDF各1，page10），3/10页测试另核PNG解码3/10及完整观测一次；失效/损坏/未知整组、partial/旧件/跨scope/stale Record拒绝保留。closed。 |
| IR2 / P2 | 新预览PDF写入PermissionError原文进入旧execution的str(exc)，owner detail和日志含内部路径。主会话独立probe得failed/uploading/oss_failed、receipt保留但path_leaked=true。 | 新预览source/Artifact/job窄I/O将已识别OS/SQLite/PyMySQL/S3异常转固定安全存储错误；不包Provider/整_run、不捕BaseException，继续oss_failed/独立retry显式失败。独立同probe路径不泄漏且原失败/receipt保留；实际异常类型内存验证明确NoSuchKey、ValueError、BaseException分类保持。17个initial/4个独立故障子例验证公开detail/quality/manifest/event/audit无canary，closed。 |
| IR3 / P2 | 完整旧终态只有同当前key才能补证；旧current=initial无法通过强制UUID的内部retry补证。主会话真实成功清阶段后available=true，新UUID仍改failed/blocked且Provider1次。 | 新key判断前用绑定current/revision的完整有效观测补证旧终态，与alias/claim同锁一次revision提交。独立probe available=true、同run/current initial、Provider仍1、revision仅+1。file/SQLite succeeded/failed/unavailable覆盖，缺阶段running仍failclosed。属于已批准design§6兼容合同，无现网旧数据存在推断/DDL/回填，closed。 |

修复前定位与主会话反例参数见research/implementation-review-round1.json。最终实现位置：service._list_files_for_job、preview.verified_current_preview_files/_preview_storage_io、preview_state.claim_preview；精确文件与当前SHA由candidate-files清单绑定，不把旧行号当作现存缺陷。

## Trellis检查与验证归属

第一次Trellis check读取全部context和当前tracked/untracked候选，10个定向selector通过13.119s，无自修。独立主审另执行7个最小合同与3个反例，不宣称复跑全套。最后四文件delta由同一Trellis checker复验AST/引用/中文/原28测试与新增7测试，写文件0，diffcheck通过，lint/typecheck无配置N/A。

实施代理最终完整应用35项41.451s通过，日志research/rnd504-review-delta-app-final.log；首轮7selector两处fixture前置错误已修，失败中间日志仍保留，没有计通过。独立审查者读取该最终日志并复跑三个原反例，全部达到预期。

主会话post-review release203项通过、OpenAPI/current与前端合同通过；既有113项仍6个已HEAD复现失败，与原失败列表完全一致。独立代理没有将主会话结果记作自己执行。具体命令/日志/限制见implementation-validation.md。

## 保留边界

唯一主DOCX/receipt/generation、三adapter同job锁、原终态CAS、CON-104 classification/actions、TR-406、RND-502/503认证、公式贡献及并发blocked、独立file_id键、pending/expiry/Token/完整TTL均保留。无新增公开API/DDL/DocumentIR/前端/发布行为。

真实engine/validator/fonts/批准隔离、真实InnoDB/部署FS/S3、Word视觉/线上Golden未验。生产disabled，production_ready=false；跨域非原子、S3非即时撤销与迟到对象回收限制保持，不以离线测试替代。
