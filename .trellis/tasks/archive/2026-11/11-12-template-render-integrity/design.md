# 模板与渲染资源完整性设计

## 资源绑定与物化

`DocumentJobRecord` 的持久化来源是 `request_snapshot["resources"]`。渲染入口解析已保存的 `JobResourceSnapshot`，核对 `template_version_id` 和创建时固定的 draft 授权，复用 `JobResourceSnapshotService` 的资源版本查询。在该服务内提供渲染所需的 DOCX、YAML 和规则物化，原完整 `materialize` 继续验证其翻译资源调用者所需的 Profile/Term Set。direct 不触发翻译资源加载。

绑定资源版本校验 ID、状态、记录 snapshot hash 与 canonical payload 的一致性。模板记录一次解析其 DOCX/YAML 路径和预期 SHA-256。已声明的资源从任务副本单次读取得到实际 SHA-256，副本缺失才读取源并验证，按身份定位任务路径。不同模板、术语版本、部门规则显式重绑时使用不同的任务资源身份，同一绑定可重放。未绑定 YAML 的旧版本保持现有无配置语义，声明了路径的版本不可回退到全局默认或空配置。

并发 Worker 对同一绑定写入相同的认证字节，使用同目录独立临时文件、flush、fsync 和原子 replace，校验最终实物后才返回。发现已有副本内容不符就报错。中断遗留一个合法文件时可继续补齐其他文件；任何资源失败都不能进入 Renderer。规则从已绑定版本 payload 和部门生成，使用相同的原子物化合同。旧的显式页眉覆盖若有相对 logo_path，保留原配置目录解析语义，用同次渲染使用的资产字节复用现有私有身份与证明，不把默认 Logo 转入配置。

`WordRenderExecution` 选择资源一次并把任务路径交给 Renderer。Renderer 已从实际字节建立 RenderPlan 资源身份和图片输入哈希，新增核对沿用这些事实并确认其与任务期望一致。publication provenance 消费同次已认证的资源与实际渲染身份，保持其现有私有格式及 draft/历史不可证明状态。现有 new-generation 检查复用同一校验，清理直接调用私有方法或重读共享源的重复校验。缺少/为空的历史资源快照继续走原模板解析和全局规则；格式非法或内容不匹配的快照失败。Worker 用现有分类和摘要发布受控错误码。

## DOCX 部件与符合性

让联合预检与生成符合性复用一个小型 OOXML 关系读取器。预检验证 ZIP 可完整读取、内容类型、正文和 section、XML 和内部目标。关系相对其所属 part 解析，识别外部关系但不联网，拒绝越过包根或无法解析的内部目标。处理文档到页眉/页脚以及页眉/页脚到媒体的关系，并检验 XML 实际引用的 ID。现有 `PackageIndex` 继续拥有块级位置索引，不另建块级证据体系。关系解析按 ECMA-376 Part 2 和当前 python-docx Section 继承行为核对。

符合性比较渲染清正文后仍应保留的模板 section 装饰与输出中各 section 的有效引用。按 header/footer 和 default/first/even 解析继承，不依赖 part 文件名、rId 或 ZIP 顺序。检验可达装饰部件的内容与媒体 SHA-256，检验首页、奇偶页设置。覆盖对页眉、页脚各自生效，允许已覆盖一侧改变，仍检查输出引用完整性。内置空白文档显式返回 `no_template`，无装饰的合法自定义模板按实际引用校验。基线先固定默认模板和现有 Section 行为，避免为了检查引入排版调整。

## 联合预检与配置

`TemplateReadService` 调用同一模板包验证器。用 Renderer 共用的 `TemplateConfigPackage` 字节解析和字段校验，避免把管理端要求全部分组齐全的编辑格式强加给已支持的稀疏 YAML。按 DOCX 实际属性检查 YAML 与继承默认值组合后的正文区域，按 Word 样式类型校验表格及显式段落样式，覆盖语言配置叠加。沿用现有 `unknown_word_style` 合同，将表格样式检查并入验证器。相对 Logo 路径遵循既有目录边界。现有 seed 声明的可选 Logo 文件并未随仓库分发，启用标题覆盖时须保持已有的无图片分支。存在的 override 资产才需验证可读取与有效，默认模板 Logo 始终从 DOCX 检查。

校验在创建目录、写 manifest、写资源记录和修改默认指针之前进行。版式 draft 复用现有版本目录暂存和失败清理。publish 校验待发布记录及文件身份，保留成功同版本验证任务与既有发布操作。bootstrap 在登记或设置默认指针前预检本次待处理 seed 集合，保留 create-only、同版本受管副本识别、旧默认优先与已有 draft 的行为。预检错误使用固定代码与字段或逻辑部件位置，不带文件绝对路径和用户配置原文。

字段注册以 editor schema 派生的完整字段集核对，登记目标与适用分支。页脚的 `alignment` 验证使用非左右文字模式，`show_page_number` 在左右文字模式验证实际 PAGE field，字体在有文本时验证。页眉标题属性在 override 且有标题时验证，已有 Logo 高度只在显式覆盖且存在资产时验证。表格缩字用会触发约束的单元格测试。若字段确实无消费者，依任务要求在现有编辑合同中标为只读或补齐实测的消费路径，以保持默认输出。

## 质量与治理

`WordRenderResult` 携带同次报告，`build_renderer_evidence` 持久化可选的 `template_conformance` 嵌套版本。质量门和历史读取在有字段时验证 schema、产物身份和阻断结论。历史缺字段保持可读。事件沿用现有摘要白名单，仅投影固定码、布尔和计数，私有证据保留必要哈希，Datasheet 度量区分通过、阻断、未采集。保持现有 API 与 OpenAPI。

用同一个 manifest 解析入口选择仓库内置当前默认资源，保留 DB 默认指针、显式版本和既有定制 manifest 语义。生产路径、测试和本地质量工具中代表“当前内置默认”的硬编码改用 manifest，显式历史或版本固定回归仍可引用对应文件。release check 在现有入口内增加四个可定位检查项。旧 YAML 的说明放在 manifest 和模板维护文档，保持已发布字节、路径和哈希。

## 参考

- [ECMA-376，Part 2 Open Packaging Conventions](https://ecma-international.org/publications-and-standards/standards/ecma-376/)
- [python-docx 页眉页脚的 Section 继承](https://python-docx.readthedocs.io/en/stable/user/hdrftr.html)
