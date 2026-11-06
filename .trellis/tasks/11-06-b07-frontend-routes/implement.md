# 实施与验证

1. 在修改源码前执行 frontend/npm ci 和 npm run build，记录基线入口 chunk；相同安装、模式、环境构建候选。
2. 路由动态导入并添加反馈及定向测试；任务详情拆分由 trellis-implement 执行，修改范围互斥。
3. 迁移 JobDetail 既有测试，新增有必要的生命周期/权限/组件装配回归。
4. 运行 npx vitest run src/stores/auth.test.ts src/navigation/appShell.test.ts src/router/index.test.ts src/pages/jobRequestRaces.test.ts src/pages/documentJobReviewHints.test.ts 及本批次新增 JobDetail 测试；npm run build。
5. trellis-check 独立复核状态 owner、换代、权限及样式作用域；检查最终 diff 和文件范围，记录结果。

不运行完整 test:unit/test:smoke、unittest discover、check_release 或在线门禁。既有无关失败单列。不开启 CI，不提交/推送，不 archive/add_session，不改其他任务状态或主工作区。

## 基线构建证据

命令：`cd frontend && npm ci --cache .npm-cache`；`cd frontend && npm run build`，均通过。

```json
{
  "commit": "79f20cef9ca0bb1a59af635e2408e130c4935e2d",
  "node": "v24.16.0",
  "npm": "11.13.0",
  "lock_sha256": "3ea1b357164f5393bd84b0f6445e3d53981094935414b1be835d802ab6a0f5e9",
  "entry_js": {
    "name": "index-21WnaXcf.js",
    "bytes": 1862769,
    "gzip_bytes": 567206
  },
  "entry_css": {
    "name": "index-D9EK3zHm.css",
    "bytes": 573076,
    "gzip_bytes": 78126
  }
}
```

源码尚未修改时构建，同一次依赖安装供候选使用。已知第三方 PURE 注释和 500 kB chunk 警告保留。

gzip 使用 Node zlib 默认压缩级别，与 Vite 输出口径一致；基线 dist 临时保留于 node_modules/.cache/b07-baseline-dist。

## 本地执行结果

- `cd frontend && npx vitest run src/stores/auth.test.ts src/navigation/appShell.test.ts src/router/index.test.ts`：27/27 通过。
- `cd frontend && npx vitest run src/pages/jobRequestRaces.test.ts src/pages/documentJobReviewHints.test.ts src/features/job-detail/jobDetailLifecycle.test.ts`：76/76 通过（34 + 39 + 3），原断言保留；共 103 项。
- `cd frontend && npx vue-tsc --noEmit`：通过。
- `cd frontend && npm run build`：基线与最终候选均通过；未改变 package.json、package-lock.json、API client，复用同一 npm ci 安装、Node v24.16.0、npm 11.13.0、Vite production 配置。
- `git diff --check`：通过；最终范围只含授权页面/路由/feature/相关测试/本任务文档。

| 产物 | 基线 bytes | 候选 bytes | 基线 gzip bytes | 候选 gzip bytes |
|---|---:|---:|---:|---:|
| 入口 JS | 1862769 | 1155188 | 567206 | 382044 |
| 入口 CSS | 573076 | 413929 | 78126 | 56463 |

入口 JS 减少 37.99%，gzip 减少 32.64%。基线为 `index-21WnaXcf.js`，候选为 `index-D5z_TDdM.js`。JobDetail 独立 chunk 为 88961 bytes（gzip 24322）；后台 OpsDashboard/FileRetention/AiProviderConfig/UserManagement 等为独立按需 chunk。此数据不等于真实网络或用户体验耗时改善。

### 定向浏览器证据

命令（frontend）：`node node_modules/.cache/b07-browser.mjs baseline` 和 `node node_modules/.cache/b07-browser.mjs candidate`。使用本机 Chrome 156.0.8078.74、worktree 内独立临时 profile、本地静态服务和全量拦截的 mock API；没有真实后端或生产调用。不是完整 Playwright smoke。

32 组样本覆盖 375/768/1024/1440px、五个详情页签、深色、克隆弹窗、真实选择 published 模板、关闭后焦点返回。Node assert.deepEqual 比较两份 JSON：页面文案、选定区域几何/样式/scrollHeight/clientHeight、关闭焦点完全一致；没有页面级横向溢出或脚本异常。候选网络请求不含后台页面 chunk；主动阻断 JobDetail chunk 后，首次深链接能显示中文加载失败提示。

脚本调试时原生 radio/input 被 Element Plus 装饰层覆盖导致定位超时，已改为点击可见标签/控件外壳，关闭使用可见取消按钮；产品代码未因此修改。首次几何对比捕获 12px 入场动画延迟，改为等待有限动画结束后，32 组全部一致。脚本、尺寸与样本 JSON 保留在 node_modules/.cache/b07-* 供本地复核，临时浏览器 profile 已删除。

### 独立复核与边界

Trellis check 子代理只读复核最终算法、状态归属、模板、scoped CSS/Teleport、迁移断言和最小导出，未发现新增缺陷；现有 specs 继续适用，无需修改。未运行完整 unit/smoke、Python discover、聚合发布门禁、生产或真实 Provider/MinerU。无关测试没有运行，不宣称其通过。

取消、归档、重试等动作完成后直接回写 job 的既有行为原样保留，未扩展为动作跨路由竞态修复；读请求仍以轮次/disposed 失效，不中止底层网络。第三方 PURE 注释及入口仍超过 500 kB 的已知构建警告保留。未提交、推送、发布、archive/add_session；这些是本地实现与验证结果，不代表设计方已验收。
