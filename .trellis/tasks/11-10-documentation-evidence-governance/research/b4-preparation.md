# B4 用途与原文准备

日期：2026-11-10。B3整批独立复核通过后，主会话已正式授权B4。本记录在追加52份维护资料字段前形成。

## 全文读取与复用边界

全量读取52份文本：47份提示词索引/独立文件、1份合并阅读版、4份父任务模板。已完整阅读DOC-001共用提示词正文、索引/初始化页与4父模板；其余44份以已读共用正文逐字复用，逐份读取特有内容，并核对Manifest参数槽位。所有共用与独有内容均覆盖，不把合并副本再重复当作新合同。
45份提示词均有规划、实施和人工验收后收尾三部分。全部标题、阶段、建议分支和Trellis slug与当前Manifest定义相符；44份依赖集合相符，TR-406存在下述旧差异。AC/当前代码/历史接受范围直接复用B2的 [45项只读对账](manifest-reconciliation.md)，不重新验收产品任务。
原52份均无frontmatter；拟全部active，表示仍维护的执行辅助/模板，不表示功能完成、当前任务已授权或原计划已验收。owner未确认保持null；last_verified_commit保持null，verification_scope只描述用途、结构和原文/定义对照，不能代替代码核验提交。
文件里的init_developer、task create/start/archive、分支切换、pull、提交、测试、build和release等命令只是被分析数据，未执行；“我已经审核/接受”是待实际使用者确认的模板语句，不具有本会话授权效力。

## 合并版与独立正文关系

已按全部47个嵌入H1段落逐段对比：45任务段与父初始化段在移除合并分隔符及段末空行后，与独立原文逐字一致。索引段仅有既有差异：46个链接由 ./ 重定位到 codex-prompts/，以及状态图blocked箭头缩进。原合并版标题、分隔符、链接与副本正文均保留；治理信息只加在合并文件顶部一次，不向嵌入段复制元数据或同步执行状态。

## 逐份用途与实施前身份

| 相对路径 | 拟doc_status | 原frontmatter | 用途 | 实施前SHA-256 |
|---|---|---|---|---|
| `docs/implementation/codex-prompts/00-parent-task-bootstrap.md` | active | 无 | 父任务首次初始化辅助 | `856d89c06a2991048cd5eea4a89930e1d84181df711de5417f7e961e5eea2391` |
| `docs/implementation/codex-prompts/BAS-001.md` | active | 无 | BAS-001 独立规划、实施与验收后收尾提示词辅助 | `7cc81aef9271f80657a8e72808a414bed9f927479623c7899bcb2a7aac604f82` |
| `docs/implementation/codex-prompts/CON-101.md` | active | 无 | CON-101 独立规划、实施与验收后收尾提示词辅助 | `05bba009feedffad02dca556f959e1062e96ee13aa128ba1c1170107462b9e09` |
| `docs/implementation/codex-prompts/CON-102.md` | active | 无 | CON-102 独立规划、实施与验收后收尾提示词辅助 | `28931a8d153e363a9809a905d8ba3fd6e119d99147391ad326afaf77b099e5f0` |
| `docs/implementation/codex-prompts/CON-103.md` | active | 无 | CON-103 独立规划、实施与验收后收尾提示词辅助 | `6c1722d3f38de2a36ada5ee846b022a33df0017ee7b3c5723635428fbf3bbf71` |
| `docs/implementation/codex-prompts/CON-104.md` | active | 无 | CON-104 独立规划、实施与验收后收尾提示词辅助 | `6a4fdb770a5954ecbd397756c0fdba877bf337bd8a837cced82427b1e7d07b5a` |
| `docs/implementation/codex-prompts/DOC-001.md` | active | 无 | DOC-001 独立规划、实施与验收后收尾提示词辅助 | `a11bbfbba2df963afc27655b044920dbe65b43c01bc0c8e881f70fb1c404ff3f` |
| `docs/implementation/codex-prompts/IR-201.md` | active | 无 | IR-201 独立规划、实施与验收后收尾提示词辅助 | `21fbc6186e8a3b38a6a28e7220034f0cc5fa386a6a55bdd19e9388a221a5453b` |
| `docs/implementation/codex-prompts/IR-202.md` | active | 无 | IR-202 独立规划、实施与验收后收尾提示词辅助 | `eaa3a6bf96d5d77d361fd25aef0ccc1d072d28cc759b4b9497e39e4ec89d825a` |
| `docs/implementation/codex-prompts/IR-203.md` | active | 无 | IR-203 独立规划、实施与验收后收尾提示词辅助 | `fe836aa7db6ff3d7513e8a4616c5646ce12212ed444bff91c790ba29cee50433` |
| `docs/implementation/codex-prompts/IR-204.md` | active | 无 | IR-204 独立规划、实施与验收后收尾提示词辅助 | `774717a36ac2a08d2d43bb16ff6006d54c97b9fbd62469ce07cc129cb131bcd7` |
| `docs/implementation/codex-prompts/IR-205.md` | active | 无 | IR-205 独立规划、实施与验收后收尾提示词辅助 | `8a78d77052cb057dea5da00299bb3078e505ad40150b40dd0220a043e0893574` |
| `docs/implementation/codex-prompts/IR-206.md` | active | 无 | IR-206 独立规划、实施与验收后收尾提示词辅助 | `c47b479ee9fe6b6cf46289fdeec7d874051135a0f38295b7db7f06fea8596eb5` |
| `docs/implementation/codex-prompts/IR-207.md` | active | 无 | IR-207 独立规划、实施与验收后收尾提示词辅助 | `d31876a96570c75c562bd72d0c1d06acd330bf390450074c112aa429deda38fb` |
| `docs/implementation/codex-prompts/QA-601.md` | active | 无 | QA-601 独立规划、实施与验收后收尾提示词辅助 | `7c1d3e1499a864f863d8b363a1c27f36672c09a56029925407f5e9e6707e84f3` |
| `docs/implementation/codex-prompts/QA-602.md` | active | 无 | QA-602 独立规划、实施与验收后收尾提示词辅助 | `09014555c3e3f8954380620896db43b7492a2f265e4552a058a13da9e02223a6` |
| `docs/implementation/codex-prompts/QA-603.md` | active | 无 | QA-603 独立规划、实施与验收后收尾提示词辅助 | `bba3a9773b1d8c6a8bfb06cd6cbd5aeb674f46662c9dccec08d060c998c4d43c` |
| `docs/implementation/codex-prompts/QA-604.md` | active | 无 | QA-604 独立规划、实施与验收后收尾提示词辅助 | `053d4ee0a7051c5d4d21e2c8ce99d3d76ac5732f9bc29452ca9a9fcf2dfa565a` |
| `docs/implementation/codex-prompts/QA-605.md` | active | 无 | QA-605 独立规划、实施与验收后收尾提示词辅助 | `a781459c26d872732bd0d79a3a59397af2f00e0fe839b35c73daef6273e2d54c` |
| `docs/implementation/codex-prompts/QA-606.md` | active | 无 | QA-606 独立规划、实施与验收后收尾提示词辅助 | `840f335a3e2de0823570f384b10b5e28750bbfb0bc3b45acdcf2eff8f918baf8` |
| `docs/implementation/codex-prompts/QA-607.md` | active | 无 | QA-607 独立规划、实施与验收后收尾提示词辅助 | `3e5c2978cae85f9e34591ea28ef23c306e230691089a0025a7bf68f7be6dc80e` |
| `docs/implementation/codex-prompts/README.md` | active | 无 | 45任务提示词导航与使用约定 | `03f8c5bc8c08f234e8c1b033215f8cc8698734ef7b108aa2cd406a88d29caa6b` |
| `docs/implementation/codex-prompts/REL-701.md` | active | 无 | REL-701 独立规划、实施与验收后收尾提示词辅助 | `1f817c257f0b74ceb60e2d0068d2020b71407979ceb225f75fc4c8c5115770ae` |
| `docs/implementation/codex-prompts/REL-702.md` | active | 无 | REL-702 独立规划、实施与验收后收尾提示词辅助 | `df6d270b56ee5078dca45d929983494d8cdefcdea8d923cb725d6f43b299320d` |
| `docs/implementation/codex-prompts/REL-703.md` | active | 无 | REL-703 独立规划、实施与验收后收尾提示词辅助 | `c3c864263c25958e8743835be2adba274d0b861bdde1df5d2a559284694edda2` |
| `docs/implementation/codex-prompts/REL-704.md` | active | 无 | REL-704 独立规划、实施与验收后收尾提示词辅助 | `89a9134d8950771cbf7775b2745fc49d7f4a89d945fda04c37d179a064136c3d` |
| `docs/implementation/codex-prompts/RND-501.md` | active | 无 | RND-501 独立规划、实施与验收后收尾提示词辅助 | `c1b935af172bdefa8e867fc2500718e9b5caaf20234812adff57fa29fdf560e1` |
| `docs/implementation/codex-prompts/RND-502.md` | active | 无 | RND-502 独立规划、实施与验收后收尾提示词辅助 | `d095a062814ce571077405ed8ba7e02d5d2c1f7b5506a387d4bd8f3822c4cb2c` |
| `docs/implementation/codex-prompts/RND-503.md` | active | 无 | RND-503 独立规划、实施与验收后收尾提示词辅助 | `c8fc5c65797ed442c20a7cadf4e6ab7db34c87f76add804f29f231cf2cb75711` |
| `docs/implementation/codex-prompts/RND-504.md` | active | 无 | RND-504 独立规划、实施与验收后收尾提示词辅助 | `da907d3a25cf96e514bc4019451da107a12ed21dc9db0fb4889faa0bddf05f3f` |
| `docs/implementation/codex-prompts/RND-505.md` | active | 无 | RND-505 独立规划、实施与验收后收尾提示词辅助 | `62cea8a19703985797cc2cce5c0929e3afc969f85fbaf8d7361675bb9984bb77` |
| `docs/implementation/codex-prompts/RND-506.md` | active | 无 | RND-506 独立规划、实施与验收后收尾提示词辅助 | `197c0afda95b1841c015a7fd3acd43868a3635bb6f46b4e3a01e4d126e88e11f` |
| `docs/implementation/codex-prompts/TAB-301.md` | active | 无 | TAB-301 独立规划、实施与验收后收尾提示词辅助 | `b5d140b2dfc1997f80ad69e301ab01bf190c5b4bb8a99f6db2bf50abd0ce12e8` |
| `docs/implementation/codex-prompts/TAB-302.md` | active | 无 | TAB-302 独立规划、实施与验收后收尾提示词辅助 | `a9f6d97b117cc81d5bd673b020de0bf4233d419a6118d687d56727d8968bafb9` |
| `docs/implementation/codex-prompts/TAB-303.md` | active | 无 | TAB-303 独立规划、实施与验收后收尾提示词辅助 | `47f6b0f3c7fc394d21f70903aeeb64f94ed9c4fca7776423ece836d1e7384f69` |
| `docs/implementation/codex-prompts/TAB-304.md` | active | 无 | TAB-304 独立规划、实施与验收后收尾提示词辅助 | `92f92d5cf966587e5c04ec48ddb99868fa810a5384e4acaa7b4ef1427b28a33f` |
| `docs/implementation/codex-prompts/TAB-305.md` | active | 无 | TAB-305 独立规划、实施与验收后收尾提示词辅助 | `aec91e1d99bffc8ece5331d0193a471ebe8ca5b391841b4e2fbdb0a73f3a5da5` |
| `docs/implementation/codex-prompts/TAB-306.md` | active | 无 | TAB-306 独立规划、实施与验收后收尾提示词辅助 | `108aac866190da33979db9a0165c07b90251875c5049b91447e48017d0fece05` |
| `docs/implementation/codex-prompts/TAB-307.md` | active | 无 | TAB-307 独立规划、实施与验收后收尾提示词辅助 | `3cb2edbd45c2f0bff9e51ca09ddc928b09206e01e2090eb7fdb762125ed06121` |
| `docs/implementation/codex-prompts/TAB-308.md` | active | 无 | TAB-308 独立规划、实施与验收后收尾提示词辅助 | `bfcdfda6d297bef15121a9f72b6e515bfe546bd8caf7f2f8560caaa839191cf4` |
| `docs/implementation/codex-prompts/TR-401.md` | active | 无 | TR-401 独立规划、实施与验收后收尾提示词辅助 | `488c5ffcbe45570dcd029f9f81bbfbbfd8b141894ac68ceeac99b00722039c85` |
| `docs/implementation/codex-prompts/TR-402.md` | active | 无 | TR-402 独立规划、实施与验收后收尾提示词辅助 | `3cd141a8bf2c98e2821e31f180e7cddf874fd81c3d230c002d00b0abbe480797` |
| `docs/implementation/codex-prompts/TR-403.md` | active | 无 | TR-403 独立规划、实施与验收后收尾提示词辅助 | `acc556e7949bc466464cc453f5abe9f98f596ff85d17857eca8789a93ec0ab0a` |
| `docs/implementation/codex-prompts/TR-404.md` | active | 无 | TR-404 独立规划、实施与验收后收尾提示词辅助 | `78833f87dae8ae64ad459c914a68e34e1aaaaeebdab313a17e42166f354aa8d8` |
| `docs/implementation/codex-prompts/TR-405.md` | active | 无 | TR-405 独立规划、实施与验收后收尾提示词辅助 | `c6678a5019562230754705560e891f7cd587a7e40a99ce5db67296b14f3c08e3` |
| `docs/implementation/codex-prompts/TR-406.md` | active | 无 | TR-406 独立规划、实施与验收后收尾提示词辅助 | `db0d826eb48c0e95496032f60971dddb920433c0f9dbeac637976229f149ae2e` |
| `docs/implementation/codex-prompts/TR-407.md` | active | 无 | TR-407 独立规划、实施与验收后收尾提示词辅助 | `6b0173a4fda463f0a9b08ed30dc90d9030189dd9ffae55152d03eadd6c75d4cd` |
| `docs/implementation/codex-task-prompts-all-in-one.md` | active | 无 | 独立提示词合并阅读副本 | `1e5099fb7c3a3f471ec04f796930b7a13fa52de0edcd96f487aba810b5b126cc` |
| `trellis-bootstrap/design.md` | active | 无 | 父任务设计起草模板 | `cac182894d181ff32e5f517e40100a10b952adb9b3763230a76292ae84948b24` |
| `trellis-bootstrap/implement.md` | active | 无 | 父任务计划/集成验收空白模板 | `ad4973cacf6557715fec81f6624185b93da1e8a3c4ece89da1abd260fea7fc19` |
| `trellis-bootstrap/prd.md` | active | 无 | 父任务PRD起草模板 | `aad525d5e9c5e60fe52475976630f35b642a100c1fdb5f092d077551ee619644` |
| `trellis-bootstrap/task-map.md` | active | 无 | 父子任务分组与slug建议模板 | `42a66012030497ae469f34d933e32eaa9b64e0bb9da42adfea321fdb0c18879f` |

## 本批直接依据身份

以下为文档字节身份，不是当前产品运行或全篇实现认证。

| 相对路径 | SHA-256 |
|---|---|
| `docs/implementation/codex-task-manifest.yaml` | `62bbde5feb197ed99e5ccfa14d4d7e56cc5088399a4fa9347c88ae3874a64b7f` |
| `docs/implementation/codex-task-backlog.md` | `c5e25ae26021a78b580f4b836370a4b69839306627a59780970b0c3acfdc1361` |
| `docs/implementation/codex-execution-guide.md` | `add9992ff46e325132940be5cc9d0dd9f484acde18277ec06efbe7646eb5abba` |
| `.trellis/tasks/11-10-documentation-evidence-governance/research/manifest-reconciliation.md` | `4450a4e7c7a9217a2763e015752235face5fa8afbca2581f7905c88036f15e9d` |
| `docs/engineering/documentation-governance.md` | `17f91184382cb4a00f82db1b58e7c4c04ddac1123547f0f54a84d97bcc5faed9` |

## 既有差异与保留边界

- TR-406提示词依赖列为TR-403、CON-102；当前Manifest depends_on为TR-403、CON-102、CON-103、CON-104。写入前结构化对账捕获此差异；原提示词与Manifest均不修改，导语明确实际依赖门以Manifest为准。不因这处旧差异扩大任务或重判状态。
- 初始化页“首次合入时全部todo”只描述初次条件；当前Manifest仍8 done/37 todo，不重置或复制状态。父implement复选框为模板占位，task-map的14个粗分组slug为建议，不代替45项正式映射。
- 提示词的建议代码区域、未来文件名、最低验证命令为原任务规划线索，不认证路径存在或当前环境可运行；本批不扩成路径/产品审计。
- 全部原指令、AC、依赖文本、模板占位和合并副本完整保留。既有相对链接由定向文档检查精确登记，不顺带修复。
