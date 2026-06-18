<!-- File: frontend/src/pages/JobCreatePage.vue -->
<!-- Purpose: Render the focused document job creation page. -->
<template>
  <main class="job-create-page app-page" aria-labelledby="job-create-title">
    <section class="create-shell app-page-shell app-page-shell--narrow">
      <div class="create-header app-page-header">
        <div>
          <p class="create-kicker page-kicker">Document Jobs</p>
          <h1 id="job-create-title" class="page-title">创建转换任务</h1>
          <p class="page-description">上传单个 PDF，并使用当前发布配置创建 Word 转换任务。</p>
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
  padding-top: var(--app-space-2);
}

.create-shell {
  display: grid;
  gap: 18px;
}

.create-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.create-upload-panel {
  min-width: 0;
}

@media (max-width: 720px) {
  .create-header {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
