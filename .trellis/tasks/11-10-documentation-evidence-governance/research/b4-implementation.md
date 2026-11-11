# B4 实施与文档检查

日期：2026-11-10。B3整批独立复核通过后，主会话授权按design revision 1实施B4；候选完成后交最终独立复核。

## 交付范围

- 52份资料追加四个治理字段与顶部单段导语：47份提示词索引/独立资料、合并阅读版1份、父任务模板4份，全部active。此状态仅表示辅助/模板仍维护，不代表产品功能完成。
- 所有owner和last_verified_commit为null；未确认人类owner，未把模板/文档编辑或当前HEAD冒充代码核验。verification_scope以相对路径指向准备证据。
- 原指令、任务AC/依赖、分支/slug、模板复选框、合并版标题/分隔符/副本/链接逐字保留；未执行任何文件内命令或授权语句。未修改前三批、Manifest数据或主会话任务文件。
- 新增b4-preparation.md与本报告。准备记录说明全文读取/共同正文复用、45项参数槽位对照、合并关系、52份原内容身份及旧差异。

## 文档检查结果

| 检查 | 实际结果 |
|---|---|
| B4一次性文档检查 | validate_docs.py --batch B4通过；selected=52，active=52，errors=[]，既有断链=[]。 |
| 结构和原字段 | 全52份原无frontmatter；新增YAML无重复键，四字段类型/语义合规；两个docs YAML所有原业务对象仍与实施前相同。 |
| 精确原文与指令保持 | 从52份候选仅去掉新增frontmatter及顶部单段导语后，与实施前副本UTF-8字节完全一致；代码围栏载荷亦一致，没有修改AC/依赖/状态约定或模板占位。 |
| 合并版关系 | 原47嵌入段已对账：45任务+初始化段与独立原文一致；索引仅有既有46链接重定位及状态图缩进差异。原合并正文未改，不生成第二套执行状态或嵌入治理字段。 |
| 参数槽位与旧差异 | 45标题/阶段/建议分支/slug匹配Manifest；44依赖集合匹配，TR-406原差异精确登记并保留。未把检查断言暴露的旧差异当作产品失败或自动修正。 |
| 格式和卫生 | git diff --check对52路径通过；显式卫生--files对52资料+b4-preparation.md共53份通过，内容跳过0、规则命中0；本报告单文件另查通过，无行尾空白。 |
| 前三批 | B1含治理说明/B2/B3共83份候选均仍匹配各已过批次报告SHA-256，仅复核身份，没有重跑原产品或文档检查。 |
| 直接依据 | 准备记录所列5份文档依据身份仍匹配；实现/历史核验复用B2明确范围，不扩成重新验收。 |
| 原dirty与暂存区 | 原245条中178条身份不变；累计67条变化均为授权维护文档，范围外原dirty变化0。index条目摘要仍为`1552991ae88d79c5b5fbc5c839b62cc3ea57eb7f7c800c455dea435c64344e31`。 |

没有应用测试、lint/typecheck、build、CI、OpenAPI导出、check_release/发布聚合器、Docker、生产访问或依赖安装。没有执行提示词中的init_developer、task create/start/archive、切分支/pull、commit/push/add_session。没有业务Python修改，代码注释/docstring/运行输出未变；新增说明和研究材料使用中文。

## 保留的旧差异与限制

- TR-406提示词写TR-403/CON-102；现行Manifest还包括CON-103/CON-104。二者原文均保留，顶部导语明确实际依赖门以Manifest为准。
- 初始化“首次全部todo”、父计划空复选框、14个建议分组slug与各提示词未来代码路径均为模板使用线索，不重置现有8 done/37 todo，不证明当前功能/路径存在或授权动作。
- 本批未重新认证提示词内最低验证命令、未来目标、产品API/数据库/Provider/Word行为或人工签字。可用性与当前任务授权须在实际使用提示词时另行核对。
- B3已登记的两条receipt归档旧断链保留；B4自身没有新增或既有本地Markdown断链。

## 52份候选内容身份

| 相对路径 | SHA-256 |
|---|---|
| `docs/implementation/codex-prompts/00-parent-task-bootstrap.md` | `c377f5c95ee2e8e6dacaa6acd335bd0ad5ed27225d2358e1dc12e24c3a86552e` |
| `docs/implementation/codex-prompts/BAS-001.md` | `a87cfb1f111ccea636fa296377f7e901e5e70d85c17613170734b388d3a8dabb` |
| `docs/implementation/codex-prompts/CON-101.md` | `5fa11a03e492b0d76ecc1fa20c148e55e198f1a5af6a515e37a9099929f5ebe1` |
| `docs/implementation/codex-prompts/CON-102.md` | `6a8231760747535612536b2d51afa7e64b966c87d412b0db2496ff6fedf4a94c` |
| `docs/implementation/codex-prompts/CON-103.md` | `3e0d04352f9ade232bdac9c4d65714afb07c75084f5facd3958f9d3377466578` |
| `docs/implementation/codex-prompts/CON-104.md` | `05bc7db28df60dae7c93fa7a8dd5adae3f73446b7432b432ed884d69b1494ed4` |
| `docs/implementation/codex-prompts/DOC-001.md` | `5d133020928ca82d86115e7049914c460edc39c5344b7732870655733a9498e6` |
| `docs/implementation/codex-prompts/IR-201.md` | `844e00730e15a03d4735345bbd9af09d32ebfba16a442c5829537c47c08aca54` |
| `docs/implementation/codex-prompts/IR-202.md` | `562249f303eb22dc1ab340ed508d545331efd54bedafdeb900e1c7f065d8a7ef` |
| `docs/implementation/codex-prompts/IR-203.md` | `563b4bff9badcb3df399542923232e5b377837a925482e27d5642f9087d1ec76` |
| `docs/implementation/codex-prompts/IR-204.md` | `c9147a7ee5ecc93e62376f28268cd7eeee93646227f0d615c1c7466bdc8a2275` |
| `docs/implementation/codex-prompts/IR-205.md` | `d2ad8682cfda7e1639722b45aefb8d92276ca093be871290a617b23af129c6bc` |
| `docs/implementation/codex-prompts/IR-206.md` | `f5b18b5cac22d884014e0ed4090c5954e0f38ce3605763282bd433846bdd97e3` |
| `docs/implementation/codex-prompts/IR-207.md` | `a6c5c4dac99aa7a4a6b87a7492bb0b3d0ee9793fd5495312ec2001074567013d` |
| `docs/implementation/codex-prompts/QA-601.md` | `946bf567af23a0124ff3874549f74ccfd96e4b319b5bcac47e216227e192d82c` |
| `docs/implementation/codex-prompts/QA-602.md` | `7231cb251e007906b935ca0ce6c406cffff94a038ae9aebdbd1dfe3dc0d0f329` |
| `docs/implementation/codex-prompts/QA-603.md` | `5b31a7f37fa7d3a0ec75395acae3df0b7205da15d2634fb43c4e6a8b5c0fe26a` |
| `docs/implementation/codex-prompts/QA-604.md` | `334b5949e494d367efbb2740ddaee81cf5526bc4f2c700b42ed7e1a5c83b839c` |
| `docs/implementation/codex-prompts/QA-605.md` | `1ffcd115ee741adfd79fd498b4dfa779b7d3207e69c14a3e874bc3ea0f6123a9` |
| `docs/implementation/codex-prompts/QA-606.md` | `3764adb9ae64b6938e468b31437fb10b91cae54a0708cc2c6ea04ed91699cf06` |
| `docs/implementation/codex-prompts/QA-607.md` | `c33a48439647bbdabfb484378ef6503059f1ad6a49d7dd1053642c1cecfacc18` |
| `docs/implementation/codex-prompts/README.md` | `dafe328762d405d8341844a41bbbd0ece4737de5843237a5af3f047c9b8eae02` |
| `docs/implementation/codex-prompts/REL-701.md` | `32917a95af1d67d7196a7cc6367e66889aceaffec77dd67d5d28818fc206507d` |
| `docs/implementation/codex-prompts/REL-702.md` | `5db4a86a2021c09b6d64e90f16c748523d1e76247315680554703b8bb6cd11d4` |
| `docs/implementation/codex-prompts/REL-703.md` | `e0db631506e3557de2c405bd3d538c63820caea0f1187a568b507db51d880cc4` |
| `docs/implementation/codex-prompts/REL-704.md` | `91d69c1595d32f7e09885c7e73ac7d67a3641d759d6ffe413e097669abb93b96` |
| `docs/implementation/codex-prompts/RND-501.md` | `1b3f6f6e4f363bdf93f8a51c3c155bf399bc92f01a280686c0999016fd432bdf` |
| `docs/implementation/codex-prompts/RND-502.md` | `a6b9311c2b83537e33a823738b07169ee7bdd3cf7ce5eb4e160a15c81394655c` |
| `docs/implementation/codex-prompts/RND-503.md` | `4bef973d63e5a1071b1dc828a3a87bedcaef13d4aefbe9ccdeaf5f6a54fed34e` |
| `docs/implementation/codex-prompts/RND-504.md` | `113522484578e16faf5675665d7c3a2eee2891df53f2e8c49e0d09f309d0332e` |
| `docs/implementation/codex-prompts/RND-505.md` | `ad1fcf894607d0d20dcc5f724f63df03c81d51c8e5cc5a4b005deea746ab1fd4` |
| `docs/implementation/codex-prompts/RND-506.md` | `4ec027a65f2f05d2b793e4e7660e612b8ffbdafa80eba9b814e3991ecd6145d9` |
| `docs/implementation/codex-prompts/TAB-301.md` | `ab3a971e3bfda6213384d4f555ab2a10b5237eed372266627b94ced472ab31d9` |
| `docs/implementation/codex-prompts/TAB-302.md` | `6b3abad0af82efc7ec2e9d069dedc7a2fd0722af0cf7e12c78efa589d91e2328` |
| `docs/implementation/codex-prompts/TAB-303.md` | `add85125be96b50d029e9b1ad2682d94b1e92a796b8a4595c3301a66b17dcbed` |
| `docs/implementation/codex-prompts/TAB-304.md` | `76afb79588b847cb4435b4862c84a9bf49e365fd3d1c71d105ee7b0d5c15434e` |
| `docs/implementation/codex-prompts/TAB-305.md` | `2c73d7d6d1d67aad0418cc4bed99e9ecec548df21782642bf6a164f46fbc552c` |
| `docs/implementation/codex-prompts/TAB-306.md` | `8d98ef4ea50a54f5299c80814d237afe1bc7da5d129432246bbc21b336f3eacb` |
| `docs/implementation/codex-prompts/TAB-307.md` | `10c4a650ba037e0a8d4f79111abf2f47ff384545e09143bf8efd77d581f176e3` |
| `docs/implementation/codex-prompts/TAB-308.md` | `d3066a809bce6f66a8d75060b11faa84ea41823e00cf8f843f8ad713fb9bfb68` |
| `docs/implementation/codex-prompts/TR-401.md` | `c04507e0dc59a4aa2d090fb3e8d69c148e209795e60f912174687d981079206a` |
| `docs/implementation/codex-prompts/TR-402.md` | `9f25464ae3987832d905f5a047c2c4f3891d8ad76bdfce8de3c42ec9d000f2ea` |
| `docs/implementation/codex-prompts/TR-403.md` | `9e516ee28b795924fd8e04b30405b47242a15be7a9d3c168fc0d633d955a07c0` |
| `docs/implementation/codex-prompts/TR-404.md` | `9f0eb250707850e8a7a8598e34fdb0fc6f5aac028a6fd5bf0e32029869c7c097` |
| `docs/implementation/codex-prompts/TR-405.md` | `6c1c2b6e1bfba8bcadb71dd48a4f27d9841674c3db2eb4bde527ad0498a0b915` |
| `docs/implementation/codex-prompts/TR-406.md` | `f9f4356729437be04dd00accf430b62802dccd7bedb045a975c86ffe761bd933` |
| `docs/implementation/codex-prompts/TR-407.md` | `950b3825b9fb00b520d2547e2b8334b22436ff6701f3ec0aaad54902ae8eb36a` |
| `docs/implementation/codex-task-prompts-all-in-one.md` | `236673f581b1c384b0e90f72b7a93ee70a0cb95bdd750a2e4082c7821f4e70a5` |
| `trellis-bootstrap/design.md` | `bd7a04c7297933233007a749d491f34c0b8ffdeb2a3139d47805414c1b794c45` |
| `trellis-bootstrap/implement.md` | `633387708c2471fd25868787d3e3651abc29771015a045d7738dda42bc9a4f5e` |
| `trellis-bootstrap/prd.md` | `d8eef595cd6156d815edd8f3a1b1b465d999abeb236b7aadf4bd47a877f57409` |
| `trellis-bootstrap/task-map.md` | `54cd4a981123424b4238da2a24295c95a89f586f0148af4a8f4bf213fb2c08f3` |

## 交接

B4候选已完成定向文档检查；交主会话进行最终全范围独立复核，本报告不代替该结论。不继续实现任何提示词中的产品任务，也不执行提交、归档或会话记账。
