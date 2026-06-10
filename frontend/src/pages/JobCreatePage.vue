<!-- File: frontend/src/pages/JobCreatePage.vue -->
<!-- Purpose: Render the focused document job creation page. -->
<template>
  <main class="job-create-page" aria-labelledby="job-create-title">
    <section class="create-shell">
      <div class="create-header">
        <div>
          <p class="create-kicker">Document Jobs</p>
          <h1 id="job-create-title">创建转换任务</h1>
          <p>上传单个 PDF，并使用当前发布配置创建 Word 转换任务。</p>
        </div>
        <el-button :icon="ArrowLeft" @click="goBack">返回任务列表</el-button>
      </div>

      <PdfUploadPanel class="create-upload-panel" @created="handleCreated" />
    </section>
  </main>
</template>

<script setup lang="ts">
import { ArrowLeft } from "@element-plus/icons-vue";
import { useRouter } from "vue-router";

import PdfUploadPanel from "@/components/PdfUploadPanel.vue";

const router = useRouter();

function goBack(): void {
  void router.push("/jobs");
}

function handleCreated(jobId: string): void {
  void router.push(`/jobs/${jobId}`);
}
</script>

<style scoped lang="scss">
.job-create-page {
  min-height: calc(100vh - 114px);
}

.create-shell {
  display: grid;
  gap: 18px;
  width: min(860px, 100%);
  margin: 0 auto;
}

.create-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 0 4px;
}

.create-kicker {
  margin: 0 0 8px;
  color: #0f766e;
  font-size: 13px;
  font-weight: 760;
}

.create-header h1 {
  margin: 0;
  color: #111827;
  font-size: 28px;
  font-weight: 760;
  line-height: 1.2;
}

.create-header p:last-child {
  margin: 8px 0 0;
  color: #667085;
  font-size: 14px;
  line-height: 1.6;
}

.create-upload-panel {
  min-width: 0;
}

@media (prefers-color-scheme: dark) {
  .create-kicker {
    color: #34d399;
  }

  .create-header h1 {
    color: #f8fafc;
  }

  .create-header p:last-child {
    color: #aab6ca;
  }
}

@media (max-width: 720px) {
  .create-header {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
