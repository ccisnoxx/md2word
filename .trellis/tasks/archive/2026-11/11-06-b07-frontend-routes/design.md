# 设计

## 路由
所有页面使用 Vue Router 原生动态导入，保留 history、路径、元数据和守卫。导入失败使用明确中文错误反馈，保留失败导航的拒绝语义，不自动刷新或猜测权限。

## 任务详情
沿现有 API 和 Vue composable 模式拆出请求生命周期 owner、动作/配置交互和只读展示职责。一个页面实例只创建一次任务数据状态和轮询；动作引用同一 job，不复制可变任务状态。保留请求轮次、routeEpoch、disposed、复核来源绑定及换代失效语义。面板按自然区域分离，维持 DOM、类名、顺序、弹层及样式作用域。

## 测试与回退
现有 AST 页面测试迁移到实际 composable/组件，保留断言语义。路由使用内存 history 验证守卫及异步加载失败；不增加依赖。路由和页面可分别回退，未改变持久数据。

## 最终职责
- `useJobDetailData`：唯一 job、各读取结果、请求轮次、routeEpoch、disposed、复核来源绑定、轮询及可见性监听。
- `useJobDetailActions`：下载、取消/归档/删除、重试/克隆配置与导航；使用同一个 job ref。
- `useJobDetailResources/ReviewHints/Batches/Diagnostics`：只读展示投影。
- 10 个区域组件：页头、处置、发布、复核、概览、诊断、上下文、文件、事件、动作弹窗；样式随 DOM owner 移动。
- `JobDetailPage.vue` 为 264 行装配；现有模式/动作/权限合同与 API client 未改。
