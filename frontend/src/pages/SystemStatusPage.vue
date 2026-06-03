<!-- frontend/src/pages/SystemStatusPage.vue: Admin-only entry page for the read-only system status area. -->
<template>
  <main class="system-status-page" aria-labelledby="system-status-title">
    <section class="page-heading">
      <div>
        <p class="page-kicker">System Status</p>
        <h1 id="system-status-title">系统状态</h1>
        <p>只读查看后端、worker、存储和资源默认值状态；完整指标面板将在后续子任务接入。</p>
      </div>
      <el-tag type="info" effect="plain">admin only</el-tag>
    </section>

    <el-card class="card-flat status-entry" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">状态入口已接入</h2>
          <p class="section-subtitle">
            本页当前只负责信息架构入口和权限边界，不会修改运行时配置，也不会触发任务处理流程。
          </p>
        </div>
      </div>

      <div class="status-grid" aria-label="后续状态模块">
        <article v-for="item in statusAreas" :key="item.title" class="status-card">
          <strong>{{ item.title }}</strong>
          <small>{{ item.description }}</small>
        </article>
      </div>
    </el-card>
  </main>
</template>

<script setup lang="ts">
type StatusArea = {
  title: string;
  description: string;
};

const statusAreas: StatusArea[] = [
  { title: "Readiness", description: "后续展示 /api/v1/health/ready 的部署就绪与阻断项。" },
  { title: "Worker", description: "后续展示 worker mode、stage dispatcher 和 stage message 队列状态。" },
  { title: "Storage", description: "后续展示 metadata store、artifact storage 和本地可写性。" },
  { title: "Resources", description: "后续展示默认模板、术语规则集和翻译配置版本。" },
];
</script>

<style scoped lang="scss">
.system-status-page {
  display: grid;
  gap: 18px;
}

.page-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 0 2px;
}

.page-kicker {
  margin: 0 0 4px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.page-heading h1 {
  margin: 0;
  color: #111827;
  font-size: 28px;
  line-height: 1.2;
}

.page-heading p:last-child {
  margin: 8px 0 0;
  color: #667085;
}

.status-entry {
  border: 1px solid #d9e2ec;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.status-card {
  min-height: 112px;
  padding: 16px;
  border: 1px solid #e4e7ec;
  border-radius: 8px;
  background: #f8fafc;
}

.status-card strong,
.status-card small {
  display: block;
}

.status-card strong {
  margin-bottom: 8px;
  color: #111827;
  font-size: 15px;
}

.status-card small {
  color: #667085;
  font-size: 13px;
  line-height: 1.5;
}

@media (max-width: 920px) {
  .status-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .status-grid {
    grid-template-columns: 1fr;
  }
}
</style>
