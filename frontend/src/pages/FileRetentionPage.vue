<!-- File: frontend/src/pages/FileRetentionPage.vue -->
<!-- Purpose: Render the Admin-only file library search, retention plan, quota dry-run, metadata expiry, physical deletion, cleanup-run controls, and cleanup history page. -->
<template>
  <main class="file-retention-page" aria-labelledby="file-retention-title">
    <section class="page-heading">
      <div>
        <p class="page-kicker">Storage</p>
        <h1 id="file-retention-title">文件保留计划</h1>
        <p>查看已过保留期的 document_files，先标记 expired，再按 dry-run 结果手动物理删除本地文件。</p>
      </div>
      <div class="heading-actions">
        <el-button :icon="Refresh" :loading="loading || storageLoading || policyLoading || libraryLoading || quotaPolicyLoading || cleanupHistoryLoading || schedulerDryRunLoading" @click="refreshRetentionPage">刷新</el-button>
        <el-button
          type="warning"
          :icon="Finished"
          :disabled="markableCount === 0"
          :loading="marking"
          @click="markExpired"
        >
          标记 expired
        </el-button>
        <el-button :disabled="selectedFileIds.length === 0" :loading="previewing" @click="previewPhysicalDelete">
          预览物理删除
        </el-button>
        <el-button
          type="danger"
          :disabled="!canOpenDeleteDialog"
          :loading="deleting"
          @click="openPhysicalDeleteDialog"
        >
          执行物理删除
        </el-button>
        <el-button :disabled="selectedFileIds.length === 0" :loading="cleanupPreviewing" @click="previewCleanupRun">
          预览 cleanup run
        </el-button>
        <el-button
          type="danger"
          :disabled="!canOpenCleanupRunDialog"
          :loading="cleanupExecuting"
          @click="openCleanupRunDialog"
        >
          执行 cleanup run
        </el-button>
      </div>
    </section>

    <ApiErrorAlert :error="error" />

    <el-alert
      class="retention-notice"
      type="warning"
      title="metadata-only"
      :closable="false"
      show-icon
    >
      标记 expired 仍是 metadata-only。物理删除和 manual cleanup run 都必须先预览、选择精确文件、填写 reason 并输入确认短语；scheduler dry-run 只生成只读计划和 lock/history 证据。所有这些操作都不会调用 provider，也不会执行 S3 delete。
    </el-alert>

    <section v-loading="libraryLoading" class="retention-table-section" aria-label="文件库搜索">
      <div class="section-header">
        <div>
          <h2 class="section-title">文件库搜索</h2>
          <p class="section-subtitle">只读搜索 document_files 安全摘要；不展示 object_key、bucket、checksum、etag、metadata 或本地路径。</p>
        </div>
        <div class="toolbar">
          <el-tag effect="plain">total={{ librarySearch?.total ?? 0 }}</el-tag>
          <el-tag effect="plain">generated={{ formatDateTime(librarySearch?.generated_at) }}</el-tag>
        </div>
      </div>

      <el-form class="library-filter-form" label-position="top">
        <el-form-item label="搜索">
          <el-input v-model="libraryFilters.q" clearable placeholder="file id / job id / filename / type / status" @keyup.enter="applyLibrarySearch" />
        </el-form-item>
        <el-form-item label="Status">
          <el-select v-model="libraryFilters.status" clearable placeholder="全部状态">
            <el-option label="pending_upload" value="pending_upload" />
            <el-option label="uploaded" value="uploaded" />
            <el-option label="expired" value="expired" />
            <el-option label="deleted" value="deleted" />
          </el-select>
        </el-form-item>
        <el-form-item label="File Type">
          <el-select v-model="libraryFilters.file_type" clearable filterable placeholder="全部类型">
            <el-option v-for="fileType in fileTypeOptions" :key="fileType" :label="fileType" :value="fileType" />
          </el-select>
        </el-form-item>
        <el-form-item label="Storage">
          <el-select v-model="libraryFilters.storage_provider" clearable placeholder="全部存储">
            <el-option label="local_file" value="local_file" />
            <el-option label="local_object" value="local_object" />
            <el-option label="s3" value="s3" />
          </el-select>
        </el-form-item>
        <el-form-item label="Job ID">
          <el-input v-model="libraryFilters.job_id" clearable placeholder="docjob_xxx" @keyup.enter="applyLibrarySearch" />
        </el-form-item>
        <el-form-item label="Sort">
          <el-select v-model="librarySort">
            <el-option label="created desc" value="created_at_desc" />
            <el-option label="created asc" value="created_at_asc" />
            <el-option label="updated desc" value="updated_at_desc" />
            <el-option label="expires desc" value="expires_at_desc" />
            <el-option label="size desc" value="size_bytes_desc" />
            <el-option label="size asc" value="size_bytes_asc" />
          </el-select>
        </el-form-item>
      </el-form>
      <div class="filter-actions">
        <el-button @click="resetLibrarySearch">重置搜索</el-button>
        <el-button type="primary" @click="applyLibrarySearch">搜索</el-button>
      </div>

      <el-table :data="librarySearch?.items || []" empty-text="暂无文件记录" class="retention-table" table-layout="fixed" row-key="file_id">
        <el-table-column prop="file_id" label="File ID" min-width="190">
          <template #default="{ row }"><span class="mono">{{ row.file_id }}</span></template>
        </el-table-column>
        <el-table-column prop="original_filename" label="Filename" min-width="220" show-overflow-tooltip />
        <el-table-column prop="job_id" label="Job" min-width="170">
          <template #default="{ row }">
            <router-link v-if="row.job_id" :to="`/jobs/${row.job_id}`" class="mono">
              {{ row.job_id }}
            </router-link>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="file_type" label="Type" min-width="150" />
        <el-table-column prop="storage_provider" label="Storage" min-width="130" />
        <el-table-column prop="status" label="Status" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTag(row.status)" effect="plain">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="size_bytes" label="Size" width="110">
          <template #default="{ row }">{{ formatBytes(row.size_bytes) }}</template>
        </el-table-column>
        <el-table-column prop="expires_at" label="Expires" min-width="180">
          <template #default="{ row }">{{ formatDateTime(row.expires_at) }}</template>
        </el-table-column>
        <el-table-column prop="created_by" label="Created By" min-width="150">
          <template #default="{ row }"><span class="mono">{{ row.created_by || "-" }}</span></template>
        </el-table-column>
        <el-table-column label="Flags" min-width="190">
          <template #default="{ row }">
            <el-tag v-if="row.expired" size="small" type="warning" effect="plain">expired</el-tag>
            <el-tag v-if="row.physical_delete_candidate" size="small" type="danger" effect="plain">delete candidate</el-tag>
            <span v-if="!row.expired && !row.physical_delete_candidate">-</span>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="libraryPage"
        v-model:page-size="libraryPageSize"
        :total="librarySearch?.total || 0"
        :page-sizes="[25, 50, 100, 200]"
        layout="sizes, prev, pager, next"
        background
        small
        @current-change="loadFileLibrarySearch"
        @size-change="handleLibraryPageSizeChange"
      />
    </section>

    <section v-loading="storageLoading" class="retention-table-section" aria-label="存储使用和容量 readiness">
      <div class="section-header">
        <div>
          <h2 class="section-title">存储使用与容量 readiness</h2>
          <p class="section-subtitle">只基于 document_files metadata 估算；不验证对象存在性，不自动选择文件，不执行删除。</p>
        </div>
        <div class="toolbar">
          <el-tag effect="plain">basis={{ storageUsage?.reclaim.estimation_basis || "metadata_only" }}</el-tag>
          <el-tag effect="plain" :type="storageQuotaStatusTag(storageQuotaStatus)">quota={{ storageQuotaStatus }}</el-tag>
          <el-tag effect="plain">generated={{ formatDateTime(storageUsage?.generated_at) }}</el-tag>
        </div>
      </div>

      <div class="summary-grid">
        <article class="summary-card">
          <span>Active Used</span>
          <strong>{{ formatBytes(storageTotalValue("active_size_bytes")) }}</strong>
          <small>active files: {{ storageTotalValue("active_files") }} / seen: {{ storageTotalValue("files_seen") }}</small>
        </article>
        <article class="summary-card">
          <span>Expired Estimate</span>
          <strong>{{ formatBytes(storageTotalValue("expired_size_bytes")) }}</strong>
          <small>expired files: {{ storageTotalValue("expired_files") }}</small>
        </article>
        <article class="summary-card">
          <span>Reclaim Estimate</span>
          <strong>{{ formatBytes(storageReclaimValue("estimated_reclaimable_size_bytes")) }}</strong>
          <small>estimated files: {{ storageReclaimValue("estimated_reclaimable_files") }} · 仍需 delete-preview 验证</small>
        </article>
        <article class="summary-card">
          <span>Disk Free</span>
          <strong>{{ formatBytes(storageUsage?.artifact_disk_free_bytes ?? null) }}</strong>
          <small>{{ storageUsage?.artifact_storage || "-" }} · writable={{ String(storageUsage?.artifact_root_writable ?? "-") }}</small>
        </article>
      </div>

      <div class="quota-dry-run-panel" aria-label="quota policy dry-run">
        <div class="section-header">
          <div>
            <h3 class="section-title">Quota Policy Dry Run</h3>
            <p class="section-subtitle">只预演拟上传文件的 warning/block 结果；不创建上传授权，不改变真实上传阻断策略。</p>
          </div>
          <div class="toolbar">
            <el-tag v-if="quotaPolicyReport" effect="plain" :type="quotaPolicyStatusTag(quotaPolicyReport.policy.status)">
              policy={{ quotaPolicyReport.policy.status }}
            </el-tag>
            <el-tag v-if="quotaPolicyReport" effect="plain" :type="quotaPolicyReport.would_block ? 'danger' : quotaPolicyReport.would_warn ? 'warning' : 'success'">
              would_block={{ String(quotaPolicyReport.would_block) }}
            </el-tag>
            <el-button :loading="quotaPolicyLoading" @click="runQuotaPolicyDryRun">运行 dry-run</el-button>
          </div>
        </div>

        <el-form class="quota-dry-run-form" label-position="top">
          <el-form-item label="Proposed Size">
            <el-input-number
              v-model="quotaPolicyForm.size_bytes"
              :min="0"
              :step="1024 * 1024"
              :precision="0"
              controls-position="right"
            />
          </el-form-item>
          <el-form-item label="File Type">
            <el-select v-model="quotaPolicyForm.file_type" filterable>
              <el-option v-for="fileType in fileTypeOptions" :key="fileType" :label="fileType" :value="fileType" />
            </el-select>
          </el-form-item>
          <el-form-item label="Filename">
            <el-input v-model="quotaPolicyForm.filename" clearable placeholder="quota-dry-run.pdf" @keyup.enter="runQuotaPolicyDryRun" />
          </el-form-item>
        </el-form>

        <div v-if="quotaPolicyReport" class="quota-result-grid">
          <article class="quota-result-card">
            <span>Current Used</span>
            <strong>{{ formatBytes(quotaPolicyReport.usage.current_used_size_bytes) }}</strong>
            <small>{{ formatRatio(quotaPolicyReport.usage.current_usage_ratio) }} of quota</small>
          </article>
          <article class="quota-result-card">
            <span>Projected Used</span>
            <strong>{{ formatBytes(quotaPolicyReport.usage.projected_used_size_bytes) }}</strong>
            <small>{{ formatRatio(quotaPolicyReport.usage.projected_usage_ratio) }} after proposed upload</small>
          </article>
          <article class="quota-result-card">
            <span>Thresholds</span>
            <strong>{{ formatBytes(quotaPolicyReport.policy.quota_bytes) }}</strong>
            <small>
              warn={{ formatRatio(quotaPolicyReport.policy.warning_threshold_ratio) }} ·
              block={{ formatRatio(quotaPolicyReport.policy.block_threshold_ratio) }}
            </small>
          </article>
          <article class="quota-result-card">
            <span>Upload Max</span>
            <strong>{{ formatBytes(quotaPolicyReport.policy.upload_max_bytes) }}</strong>
            <small>proposed={{ formatBytes(quotaPolicyReport.usage.proposed_upload_size_bytes) }}</small>
          </article>
        </div>

        <div v-if="quotaPolicyReport" class="safety-grid" aria-label="quota dry-run safety flags">
          <el-tag
            v-for="item in quotaPolicySafetyEntries"
            :key="item.label"
            :type="item.type"
            effect="plain"
          >
            {{ item.label }}={{ String(item.value) }}
          </el-tag>
        </div>

        <div v-if="quotaPolicyReport?.reasons.length" class="quota-reason-list">
          <el-tag v-for="reason in quotaPolicyReport.reasons" :key="reason" effect="plain">
            {{ reason }}
          </el-tag>
        </div>
      </div>

      <div class="storage-group-grid">
        <article class="storage-group-card" aria-label="按 storage provider 汇总">
          <h3>By Provider</h3>
          <el-table :data="storageUsage?.by_storage_provider || []" empty-text="暂无 provider 汇总" table-layout="fixed">
            <el-table-column prop="key" label="Provider" min-width="130" />
            <el-table-column prop="file_count" label="Files" width="80" />
            <el-table-column prop="size_bytes" label="Size" min-width="110">
              <template #default="{ row }">{{ formatBytes(row.size_bytes) }}</template>
            </el-table-column>
            <el-table-column prop="expired_size_bytes" label="Expired" min-width="110">
              <template #default="{ row }">{{ formatBytes(row.expired_size_bytes) }}</template>
            </el-table-column>
            <el-table-column prop="estimated_reclaimable_size_bytes" label="Reclaim" min-width="110">
              <template #default="{ row }">{{ formatBytes(row.estimated_reclaimable_size_bytes) }}</template>
            </el-table-column>
          </el-table>
        </article>

        <article class="storage-group-card" aria-label="按 file type 汇总">
          <h3>By File Type</h3>
          <el-table :data="storageUsage?.by_file_type || []" empty-text="暂无 file type 汇总" table-layout="fixed">
            <el-table-column prop="key" label="Type" min-width="150" />
            <el-table-column prop="file_count" label="Files" width="80" />
            <el-table-column prop="size_bytes" label="Size" min-width="110">
              <template #default="{ row }">{{ formatBytes(row.size_bytes) }}</template>
            </el-table-column>
            <el-table-column prop="expired_count" label="Expired" width="90" />
            <el-table-column prop="estimated_reclaimable_count" label="Reclaim" width="90" />
          </el-table>
        </article>

        <article class="storage-group-card" aria-label="按 status 汇总">
          <h3>By Status</h3>
          <el-table :data="storageUsage?.by_status || []" empty-text="暂无 status 汇总" table-layout="fixed">
            <el-table-column prop="key" label="Status" min-width="120" />
            <el-table-column prop="file_count" label="Files" width="80" />
            <el-table-column prop="size_bytes" label="Size" min-width="110">
              <template #default="{ row }">{{ formatBytes(row.size_bytes) }}</template>
            </el-table-column>
            <el-table-column prop="expired_size_bytes" label="Expired" min-width="110">
              <template #default="{ row }">{{ formatBytes(row.expired_size_bytes) }}</template>
            </el-table-column>
            <el-table-column prop="estimated_reclaimable_size_bytes" label="Reclaim" min-width="110">
              <template #default="{ row }">{{ formatBytes(row.estimated_reclaimable_size_bytes) }}</template>
            </el-table-column>
          </el-table>
        </article>
      </div>
    </section>

    <section v-loading="loading" class="summary-grid" aria-label="文件保留计划摘要">
      <article class="summary-card">
        <span>候选文件</span>
        <strong>{{ candidateCount }}</strong>
        <small>已选择：{{ selectedFileIds.length }} · 可标记 uploaded：{{ markableCount }}</small>
      </article>
      <article class="summary-card">
        <span>保留天数</span>
        <strong>{{ plan?.retention_days ?? "-" }}</strong>
        <small>来自后端当前配置</small>
      </article>
      <article class="summary-card">
        <span>文件总数</span>
        <strong>{{ totalValue("files_seen") }}</strong>
        <small>有 expires_at：{{ totalValue("files_with_expires_at") }}</small>
      </article>
      <article class="summary-card">
        <span>生成时间</span>
        <strong class="summary-time">{{ formatDateTime(plan?.generated_at) }}</strong>
        <small>action: {{ plan?.action_mode || "dry_run" }}</small>
      </article>
    </section>

    <section class="retention-table-section" aria-label="保留策略治理">
      <div class="section-header">
        <div>
          <h2 class="section-title">保留策略</h2>
          <p class="section-subtitle">策略发布后只影响后续新文件的 expires_at；历史文件只提供 impact preview，不自动回填。</p>
        </div>
        <div class="toolbar">
          <el-tag effect="plain">fallback={{ policyList?.fallback_retention_days ?? "-" }} days</el-tag>
          <el-button :loading="policyLoading" @click="loadPolicies">刷新策略</el-button>
          <el-button type="primary" @click="openCreatePolicyDialog">新增 draft</el-button>
        </div>
      </div>

      <el-table
        v-loading="policyLoading"
        :data="policyList?.items || []"
        empty-text="暂无保留策略"
        class="retention-table"
        table-layout="fixed"
        row-key="policy_id"
      >
        <el-table-column prop="name" label="Name" min-width="210" />
        <el-table-column prop="scope_type" label="Scope" min-width="150">
          <template #default="{ row }">
            <span>{{ row.scope_type }}</span>
            <span v-if="row.file_type" class="mono">:{{ row.file_type }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="retention_days" label="Days" width="90" />
        <el-table-column prop="status" label="Status" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="policyStatusTag(row.status)" effect="plain">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_default" label="Default" width="110">
          <template #default="{ row }">{{ row.is_default ? "yes" : "no" }}</template>
        </el-table-column>
        <el-table-column prop="matching_file_count" label="Matches" width="110" />
        <el-table-column prop="updated_at" label="Updated" min-width="180">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="Actions" min-width="340" fixed="right">
          <template #default="{ row }">
            <el-button size="small" :disabled="row.status !== 'draft'" @click="openEditPolicyDialog(row)">编辑</el-button>
            <el-button size="small" @click="previewPolicyImpact(row)">影响预览</el-button>
            <el-button size="small" type="success" :disabled="row.status !== 'draft'" @click="publishPolicy(row)">发布</el-button>
            <el-button size="small" :disabled="row.status !== 'published' || row.is_default" @click="setDefaultPolicy(row)">设默认</el-button>
            <el-button size="small" type="warning" :disabled="row.status === 'disabled'" @click="disablePolicy(row)">禁用</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="policyList?.effective.length" class="effective-policy-grid">
        <el-tag
          v-for="item in policyList.effective"
          :key="item.file_type || item.reason"
          effect="plain"
          :type="item.source === 'published_policy' ? 'success' : 'info'"
        >
          {{ item.file_type }}={{ item.retention_days }}d · {{ item.source }}
        </el-tag>
      </div>
    </section>

    <section v-if="policyImpact" class="retention-table-section" aria-label="保留策略影响预览">
      <div class="section-header">
        <div>
          <h2 class="section-title">策略影响预览</h2>
          <p class="section-subtitle">
            {{ policyImpact.policy.name }} · generated {{ formatDateTime(policyImpact.generated_at) }} ·
            不修改历史 expires_at。
          </p>
        </div>
        <div class="toolbar">
          <el-tag type="info" effect="plain">matching={{ policyImpact.totals.matching_files ?? 0 }}</el-tag>
          <el-tag type="warning" effect="plain">would_expire={{ policyImpact.totals.would_be_expired ?? 0 }}</el-tag>
          <el-tag type="danger" effect="plain">would_change={{ policyImpact.totals.would_change_expires_at ?? 0 }}</el-tag>
        </div>
      </div>

      <el-table :data="policyImpact.items" empty-text="暂无影响预览" class="retention-table" table-layout="fixed">
        <el-table-column prop="file_id" label="File ID" min-width="180">
          <template #default="{ row }"><span class="mono">{{ row.file_id }}</span></template>
        </el-table-column>
        <el-table-column prop="file_type" label="Type" min-width="140" />
        <el-table-column prop="status" label="Status" width="110" />
        <el-table-column prop="current_expires_at" label="Current Expires" min-width="180">
          <template #default="{ row }">{{ formatDateTime(row.current_expires_at) }}</template>
        </el-table-column>
        <el-table-column prop="projected_expires_at" label="Projected Expires" min-width="180">
          <template #default="{ row }">{{ formatDateTime(row.projected_expires_at) }}</template>
        </el-table-column>
        <el-table-column prop="would_be_expired" label="Would Expire" width="120">
          <template #default="{ row }">{{ row.would_be_expired ? "yes" : "no" }}</template>
        </el-table-column>
        <el-table-column prop="would_change_expires_at" label="Would Change" width="130">
          <template #default="{ row }">{{ row.would_change_expires_at ? "yes" : "no" }}</template>
        </el-table-column>
      </el-table>
    </section>

    <section class="retention-table-section" aria-label="过期候选文件">
      <div class="section-header">
        <div>
          <h2 class="section-title">过期候选</h2>
          <p class="section-subtitle">根据 `expires_at` 生成，`deleted` 状态文件不会进入候选；物理删除只执行 selected expired local 文件。</p>
        </div>
        <div class="toolbar">
          <el-tag effect="plain" :type="plan?.deletion_supported ? 'danger' : 'info'">
            deletion_supported={{ String(plan?.deletion_supported ?? false) }}
          </el-tag>
          <el-tag effect="plain">selected={{ selectedFileIds.length }}</el-tag>
        </div>
      </div>

      <el-table
        :data="plan?.candidates || []"
        empty-text="暂无过期候选文件"
        class="retention-table"
        table-layout="fixed"
        row-key="file_id"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column prop="file_id" label="File ID" min-width="180">
          <template #default="{ row }">
            <span class="mono">{{ row.file_id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="job_id" label="Job" min-width="170">
          <template #default="{ row }">
            <router-link v-if="row.job_id" :to="`/jobs/${row.job_id}`" class="mono">
              {{ row.job_id }}
            </router-link>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="file_type" label="Type" min-width="140" />
        <el-table-column prop="storage_provider" label="Storage" min-width="140" />
        <el-table-column prop="status" label="Status" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTag(row.status)" effect="plain">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="size_bytes" label="Size" width="110">
          <template #default="{ row }">{{ formatBytes(row.size_bytes) }}</template>
        </el-table-column>
        <el-table-column prop="expires_at" label="Expires" min-width="180">
          <template #default="{ row }">{{ formatDateTime(row.expires_at) }}</template>
        </el-table-column>
        <el-table-column prop="object_key" label="Object Key" min-width="320">
          <template #default="{ row }">
            <span class="mono object-key">{{ row.object_key }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="Reason" min-width="260" />
      </el-table>
    </section>

    <section v-if="deleteReport" class="retention-table-section" aria-label="物理删除预览和执行结果">
      <div class="section-header">
        <div>
          <h2 class="section-title">物理删除结果</h2>
          <p class="section-subtitle">
            {{ deleteReport.action_mode }} · generated {{ formatDateTime(deleteReport.generated_at) }} ·
            required confirmation: <span class="mono">{{ deleteReport.confirmation_phrase }}</span>
          </p>
        </div>
        <div class="toolbar">
          <el-tag type="success" effect="plain">deletable={{ totalDeleteValue("deletable") }}</el-tag>
          <el-tag type="danger" effect="plain">deleted={{ totalDeleteValue("deleted") }}</el-tag>
          <el-tag type="warning" effect="plain">skipped={{ totalDeleteValue("skipped") }}</el-tag>
          <el-tag type="danger" effect="plain">failed={{ totalDeleteValue("failed") }}</el-tag>
        </div>
      </div>

      <el-table :data="deleteReport.items" empty-text="暂无物理删除结果" class="retention-table" table-layout="fixed">
        <el-table-column prop="file_id" label="File ID" min-width="180">
          <template #default="{ row }">
            <span class="mono">{{ row.file_id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="outcome" label="Outcome" min-width="180">
          <template #default="{ row }">
            <el-tag size="small" :type="outcomeTag(row.outcome)" effect="plain">{{ row.outcome }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status_before" label="Before" width="110">
          <template #default="{ row }">{{ row.status_before || "-" }}</template>
        </el-table-column>
        <el-table-column prop="status_after" label="After" width="110">
          <template #default="{ row }">{{ row.status_after || "-" }}</template>
        </el-table-column>
        <el-table-column prop="storage_provider" label="Storage" min-width="130">
          <template #default="{ row }">{{ row.storage_provider || "-" }}</template>
        </el-table-column>
        <el-table-column prop="s3_delete_contract" label="S3 Contract" min-width="190">
          <template #default="{ row }">
            <el-tag
              v-if="row.s3_delete_contract"
              size="small"
              :type="row.s3_delete_contract.target_exact ? 'warning' : 'danger'"
              effect="plain"
            >
              {{ s3ContractLabel(row) }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="deleted" label="Deleted" width="100">
          <template #default="{ row }">{{ row.deleted ? "yes" : "no" }}</template>
        </el-table-column>
        <el-table-column prop="metadata_updated" label="Metadata" width="110">
          <template #default="{ row }">{{ row.metadata_updated ? "updated" : "unchanged" }}</template>
        </el-table-column>
        <el-table-column prop="reason" label="Reason" min-width="280" show-overflow-tooltip />
        <el-table-column prop="object_key" label="Object Key" min-width="320">
          <template #default="{ row }">
            <span class="mono object-key">{{ row.object_key || "-" }}</span>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section v-if="cleanupRunReport" class="retention-table-section" aria-label="cleanup run 预览和执行结果">
      <div class="section-header">
        <div>
          <h2 class="section-title">Cleanup Run 结果</h2>
          <p class="section-subtitle">
            {{ cleanupRunReport.action_mode }} · run <span class="mono">{{ cleanupRunReport.run_id }}</span> ·
            generated {{ formatDateTime(cleanupRunReport.generated_at) }} · max_files={{ cleanupRunReport.max_files }}
          </p>
        </div>
        <div class="toolbar">
          <el-tag type="success" effect="plain">deletable={{ cleanupTotalValue("deletable") }}</el-tag>
          <el-tag type="danger" effect="plain">deleted={{ cleanupTotalValue("deleted") }}</el-tag>
          <el-tag type="warning" effect="plain">skipped={{ cleanupTotalValue("skipped") }}</el-tag>
          <el-tag type="danger" effect="plain">failed={{ cleanupTotalValue("failed") }}</el-tag>
        </div>
      </div>

      <div class="cleanup-run-grid">
        <article class="cleanup-run-card">
          <span>Preview Hash</span>
          <strong class="mono object-key">{{ cleanupRunReport.preview_hash }}</strong>
          <small>execute 必须提交同一个 hash；状态变化后需要重新 preview。</small>
        </article>
        <article class="cleanup-run-card">
          <span>Requested Files</span>
          <strong>{{ cleanupRunReport.requested_file_ids.length }}</strong>
          <small class="mono object-key">{{ cleanupRunReport.requested_file_ids.join(", ") }}</small>
        </article>
        <article class="cleanup-run-card">
          <span>Physical Delete</span>
          <strong>{{ cleanupRunReport.physical_delete.action_mode }}</strong>
          <small>复用 selected-file physical-delete safety contract。</small>
        </article>
        <article class="cleanup-run-card">
          <span>Signed Plan</span>
          <strong class="mono object-key">{{ cleanupRunReport.cleanup_plan?.plan_id || "-" }}</strong>
          <small>expires {{ formatDateTime(cleanupRunReport.cleanup_plan?.expires_at) }} · {{ cleanupRunReport.cleanup_plan?.signature_algorithm || "-" }}</small>
        </article>
      </div>

      <div class="safety-grid" aria-label="cleanup run safety flags">
        <el-tag
          v-for="item in cleanupRunSafetyEntries"
          :key="item.label"
          :type="item.type"
          effect="plain"
        >
          {{ item.label }}={{ String(item.value) }}
        </el-tag>
      </div>

      <el-table :data="cleanupRunReport.physical_delete.items" empty-text="暂无 cleanup run 结果" class="retention-table" table-layout="fixed">
        <el-table-column prop="file_id" label="File ID" min-width="180">
          <template #default="{ row }">
            <span class="mono">{{ row.file_id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="outcome" label="Outcome" min-width="180">
          <template #default="{ row }">
            <el-tag size="small" :type="outcomeTag(row.outcome)" effect="plain">{{ row.outcome }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status_before" label="Before" width="110">
          <template #default="{ row }">{{ row.status_before || "-" }}</template>
        </el-table-column>
        <el-table-column prop="status_after" label="After" width="110">
          <template #default="{ row }">{{ row.status_after || "-" }}</template>
        </el-table-column>
        <el-table-column prop="storage_provider" label="Storage" min-width="130">
          <template #default="{ row }">{{ row.storage_provider || "-" }}</template>
        </el-table-column>
        <el-table-column prop="s3_delete_contract" label="S3 Contract" min-width="190">
          <template #default="{ row }">
            <el-tag
              v-if="row.s3_delete_contract"
              size="small"
              :type="row.s3_delete_contract.target_exact ? 'warning' : 'danger'"
              effect="plain"
            >
              {{ s3ContractLabel(row) }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="deleted" label="Deleted" width="100">
          <template #default="{ row }">{{ row.deleted ? "yes" : "no" }}</template>
        </el-table-column>
        <el-table-column prop="metadata_updated" label="Metadata" width="110">
          <template #default="{ row }">{{ row.metadata_updated ? "updated" : "unchanged" }}</template>
        </el-table-column>
        <el-table-column prop="reason" label="Reason" min-width="280" show-overflow-tooltip />
        <el-table-column prop="object_key" label="Object Key" min-width="320">
          <template #default="{ row }">
            <span class="mono object-key">{{ row.object_key || "-" }}</span>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="retention-table-section scheduler-dry-run-section" aria-label="cleanup scheduler dry-run">
      <div class="section-header">
        <div>
          <h2 class="section-title">Scheduler Dry Run</h2>
          <p class="section-subtitle">手动运行 readonly cleanup runner；只获取并释放 cleanup lock、写入 dry-run history，不启动 scheduler loop，不授权删除。</p>
        </div>
        <div class="toolbar">
          <el-tag v-if="schedulerDryRunReport" effect="plain">run={{ schedulerDryRunReport.run_id }}</el-tag>
          <el-tag v-if="schedulerDryRunReport" effect="plain">generated={{ formatDateTime(schedulerDryRunReport.generated_at) }}</el-tag>
          <el-button type="primary" :icon="Refresh" :loading="schedulerDryRunLoading" @click="runCleanupSchedulerDryRun">
            运行 scheduler dry-run
          </el-button>
        </div>
      </div>

      <el-alert type="info" title="readonly runner" :closable="false" show-icon>
        该按钮不会执行 mark-expired、delete-preview、delete-expired、真实 S3 delete、provider cancellation、alert delivery 或主转换流程；结果不能作为 cleanup execute 授权。
      </el-alert>

      <el-form class="scheduler-dry-run-form" label-position="top">
        <el-form-item label="Owner ID">
          <el-input v-model="schedulerDryRunForm.owner_id" clearable placeholder="留空使用当前 admin user" />
        </el-form-item>
        <el-form-item label="Lock TTL Seconds">
          <el-input-number
            v-model="schedulerDryRunForm.lock_ttl_seconds"
            :min="1"
            :max="900"
            :step="30"
            :precision="0"
            controls-position="right"
          />
        </el-form-item>
      </el-form>

      <div v-if="schedulerDryRunReport" class="scheduler-dry-run-grid">
        <article class="cleanup-run-card">
          <span>Run</span>
          <strong class="mono object-key">{{ schedulerDryRunReport.run_id }}</strong>
          <small>{{ schedulerDryRunReport.action_mode }}</small>
        </article>
        <article class="cleanup-run-card">
          <span>Candidates</span>
          <strong>{{ schedulerRetentionCandidateCount }}</strong>
          <small>metadata-only retention candidates</small>
        </article>
        <article class="cleanup-run-card">
          <span>Reclaim Estimate</span>
          <strong>{{ formatBytes(schedulerEstimatedReclaimBytes) }}</strong>
          <small>仍需 selected-file delete-preview 验证</small>
        </article>
        <article class="cleanup-run-card">
          <span>Lock</span>
          <strong>{{ schedulerDryRunReport.lock.status }} · released={{ String(schedulerDryRunReport.lock.released) }}</strong>
          <small class="mono object-key">{{ schedulerDryRunReport.lock.owner_id }} · token={{ schedulerDryRunReport.lock.fencing_token }}</small>
        </article>
      </div>

      <div v-if="schedulerDryRunReport" class="safety-grid" aria-label="scheduler dry-run safety flags">
        <el-tag
          v-for="item in schedulerDryRunSafetyEntries"
          :key="item.label"
          :type="item.type"
          effect="plain"
        >
          {{ item.label }}={{ String(item.value) }}
        </el-tag>
      </div>
    </section>

    <section class="retention-table-section" aria-label="cleanup run durable history">
      <div class="section-header">
        <div>
          <h2 class="section-title">Cleanup Run History</h2>
          <p class="section-subtitle">持久化 preview/execute 摘要；不展示 object_key、本地路径或文件内容，不启动 scheduler。</p>
        </div>
        <div class="toolbar">
          <el-tag effect="plain">total={{ cleanupRunHistory?.total ?? 0 }}</el-tag>
          <el-button :loading="cleanupHistoryLoading" @click="loadCleanupRunHistory">刷新 history</el-button>
        </div>
      </div>

      <el-table
        v-loading="cleanupHistoryLoading"
        :data="cleanupRunHistory?.items || []"
        empty-text="暂无 cleanup run history"
        class="retention-table"
        table-layout="fixed"
        row-key="run_id"
      >
        <el-table-column prop="run_id" label="Run ID" min-width="190">
          <template #default="{ row }"><span class="mono">{{ row.run_id }}</span></template>
        </el-table-column>
        <el-table-column prop="status" label="Status" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="cleanupHistoryStatusTag(row.status)" effect="plain">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="action_mode" label="Mode" min-width="150" />
        <el-table-column prop="requested_file_ids" label="Files" width="90">
          <template #default="{ row }">{{ row.requested_file_ids.length }}</template>
        </el-table-column>
        <el-table-column prop="totals" label="Totals" min-width="190">
          <template #default="{ row }">
            <span v-if="row.action_mode === 'scheduler_dry_run'">
              candidates={{ row.totals.candidate_files ?? 0 }} · local={{ row.totals.candidate_local_files ?? 0 }}
            </span>
            <span v-else>
              deleted={{ row.totals.deleted ?? 0 }} · skipped={{ row.totals.skipped ?? 0 }} · failed={{ row.totals.failed ?? 0 }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="Updated" min-width="180">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="Actions" width="100">
          <template #default="{ row }">
            <el-button size="small" @click="inspectCleanupRunHistory(row.run_id)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="selectedCleanupRunHistory" class="cleanup-history-detail">
        <article class="cleanup-run-card">
          <span>Preview Hash</span>
          <strong class="mono object-key">{{ selectedCleanupRunHistory.preview_hash }}</strong>
          <small>run <span class="mono">{{ selectedCleanupRunHistory.run_id }}</span></small>
        </article>
        <article class="cleanup-run-card">
          <span>Reason</span>
          <strong>{{ selectedCleanupRunHistory.reason || "-" }}</strong>
          <small>{{ selectedCleanupRunHistory.error_code || selectedCleanupRunHistory.action_mode }}</small>
        </article>
        <article class="cleanup-run-card">
          <span>Requested Files</span>
          <strong>{{ selectedCleanupRunHistory.requested_file_ids.length }}</strong>
          <small class="mono object-key">{{ selectedCleanupRunHistory.requested_file_ids.join(", ") }}</small>
        </article>
        <article class="cleanup-run-card">
          <span>Signed Plan</span>
          <strong class="mono object-key">{{ selectedCleanupRunHistory.cleanup_plan?.plan_id || "-" }}</strong>
          <small>expires {{ formatDateTime(selectedCleanupRunHistory.cleanup_plan?.expires_at) }}</small>
        </article>
      </div>

      <div v-if="selectedCleanupRunHistory" class="safety-grid" aria-label="cleanup run history safety flags">
        <el-tag
          v-for="item in selectedCleanupRunHistorySafetyEntries"
          :key="item.label"
          :type="item.type"
          effect="plain"
        >
          {{ item.label }}={{ String(item.value) }}
        </el-tag>
      </div>
    </section>

    <el-dialog v-model="deleteDialog.visible" title="执行物理删除" width="640px">
      <el-alert class="delete-warning" type="error" title="不可逆操作" :closable="false" show-icon>
        该操作会删除 selected expired local/local_object 文件内容；metadata 行、任务记录、事件和 object_key 会保留。
      </el-alert>
      <el-form label-position="top">
        <el-form-item label="Selected file IDs">
          <el-input :model-value="selectedFileIds.join('\n')" type="textarea" :rows="4" readonly class="mono" />
        </el-form-item>
        <el-form-item label="Reason">
          <el-input v-model="deleteDialog.reason" type="textarea" :rows="2" placeholder="说明为什么执行本次物理删除" />
        </el-form-item>
        <el-form-item label="Confirmation phrase">
          <el-input v-model="deleteDialog.confirmation" :placeholder="deleteReport?.confirmation_phrase || 'DELETE EXPIRED FILES'" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deleteDialog.visible = false">取消</el-button>
        <el-button type="danger" :loading="deleting" @click="executePhysicalDelete">确认物理删除</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="cleanupRunDialog.visible" title="执行 manual cleanup run" width="720px">
      <el-alert class="delete-warning" type="error" title="受控删除合同" :closable="false" show-icon>
        cleanup run 会复用 selected-file physical-delete 合同：不会启动 scheduler，不会调用 provider，不会执行 S3 delete；execute 必须携带本次 preview_hash、signed plan、reason 和确认短语。
      </el-alert>
      <el-form label-position="top">
        <el-form-item label="Selected file IDs">
          <el-input :model-value="cleanupRunReport?.requested_file_ids.join('\n') || ''" type="textarea" :rows="4" readonly class="mono" />
        </el-form-item>
        <el-form-item label="Preview Hash">
          <el-input :model-value="cleanupRunReport?.preview_hash || ''" readonly class="mono" />
        </el-form-item>
        <el-form-item label="Signed Plan">
          <el-input :model-value="cleanupRunReport?.cleanup_plan?.plan_id || ''" readonly class="mono" />
        </el-form-item>
        <el-form-item label="Reason">
          <el-input v-model="cleanupRunDialog.reason" type="textarea" :rows="2" placeholder="说明为什么执行本次 cleanup run" />
        </el-form-item>
        <el-form-item label="Confirmation phrase">
          <el-input v-model="cleanupRunDialog.confirmation" :placeholder="cleanupRunReport?.confirmation_phrase || 'EXECUTE AUTOMATED RETENTION CLEANUP'" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cleanupRunDialog.visible = false">取消</el-button>
        <el-button type="danger" :disabled="!canSubmitCleanupRun" :loading="cleanupExecuting" @click="executeCleanupRun">
          确认 cleanup run
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="policyDialog.visible" :title="policyDialog.policyId ? '编辑保留策略' : '新增保留策略 draft'" width="640px">
      <el-alert class="delete-warning" type="info" title="不会回填历史文件" :closable="false" show-icon>
        创建或编辑 draft 不影响新文件；发布后只影响后续新文件 expires_at，历史文件需要单独 dry-run backfill 任务。
      </el-alert>
      <el-form label-position="top">
        <el-form-item label="Name">
          <el-input v-model="policyDialog.form.name" placeholder="例如 Generated Word 30 days" />
        </el-form-item>
        <el-form-item label="Scope">
          <el-select v-model="policyDialog.form.scope_type">
            <el-option label="global" value="global" />
            <el-option label="file_type" value="file_type" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="policyDialog.form.scope_type === 'file_type'" label="File Type">
          <el-select v-model="policyDialog.form.file_type" filterable>
            <el-option v-for="fileType in fileTypeOptions" :key="fileType" :label="fileType" :value="fileType" />
          </el-select>
        </el-form-item>
        <el-form-item label="Retention Days">
          <el-input-number v-model="policyDialog.form.retention_days" :min="1" :max="3650" />
        </el-form-item>
        <el-form-item label="Description">
          <el-input v-model="policyDialog.form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="policyDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="policySaving" @click="savePolicy">保存 draft</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Finished, Refresh } from "@element-plus/icons-vue";

import { filesApi } from "@/api/files";
import type {
  FileLibrarySearchQuery,
  FileLibrarySearchResponse,
  FileLibrarySort,
  FileQuotaPolicyDryRunResponse,
  FileRetentionCandidateResponse,
  FileRetentionCleanupRunHistoryListResponse,
  FileRetentionCleanupRunHistoryResponse,
  FileRetentionCleanupRunHistoryStatus,
  FileRetentionCleanupRunResponse,
  FileRetentionCleanupSchedulerDryRunResponse,
  FileRetentionDeleteItemResponse,
  FileRetentionDeleteOutcome,
  FileRetentionDeleteResponse,
  FileRetentionPolicyCreateRequest,
  FileRetentionPolicyImpactResponse,
  FileRetentionPolicyResponse,
  FileRetentionPolicyScopeType,
  FileRetentionPlanResponse,
  FileStorageUsageResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { formatBytes, formatDateTime } from "@/utils/format";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

type StatusTag = "success" | "warning" | "info" | "danger";
type UnknownRecord = Record<string, unknown>;

type LibraryFilters = {
  q: string;
  status: string;
  file_type: string;
  storage_provider: string;
  job_id: string;
};

type LibraryFilterKey = "q" | "status" | "file_type" | "storage_provider" | "job_id";

const plan = ref<FileRetentionPlanResponse | null>(null);
const selectedCandidates = ref<FileRetentionCandidateResponse[]>([]);
const deleteReport = ref<FileRetentionDeleteResponse | null>(null);
const cleanupRunReport = ref<FileRetentionCleanupRunResponse | null>(null);
const schedulerDryRunReport = ref<FileRetentionCleanupSchedulerDryRunResponse | null>(null);
const policyList = ref<Awaited<ReturnType<typeof filesApi.listRetentionPolicies>> | null>(null);
const policyImpact = ref<FileRetentionPolicyImpactResponse | null>(null);
const storageUsage = ref<FileStorageUsageResponse | null>(null);
const quotaPolicyReport = ref<FileQuotaPolicyDryRunResponse | null>(null);
const librarySearch = ref<FileLibrarySearchResponse | null>(null);
const cleanupRunHistory = ref<FileRetentionCleanupRunHistoryListResponse | null>(null);
const selectedCleanupRunHistory = ref<FileRetentionCleanupRunHistoryResponse | null>(null);
const loading = ref(false);
const marking = ref(false);
const previewing = ref(false);
const deleting = ref(false);
const cleanupPreviewing = ref(false);
const cleanupExecuting = ref(false);
const schedulerDryRunLoading = ref(false);
const policyLoading = ref(false);
const policySaving = ref(false);
const storageLoading = ref(false);
const quotaPolicyLoading = ref(false);
const libraryLoading = ref(false);
const cleanupHistoryLoading = ref(false);
const error = ref<ApiClientError | null>(null);
const libraryFilters = reactive<LibraryFilters>({
  q: "",
  status: "",
  file_type: "",
  storage_provider: "",
  job_id: "",
});
const librarySort = ref<FileLibrarySort>("created_at_desc");
const libraryPage = ref(1);
const libraryPageSize = ref(50);
const deleteDialog = reactive({
  visible: false,
  reason: "",
  confirmation: "",
});
const cleanupRunDialog = reactive({
  visible: false,
  reason: "",
  confirmation: "",
});
const schedulerDryRunForm = reactive({
  owner_id: "",
  lock_ttl_seconds: 60,
});
const quotaPolicyForm = reactive({
  size_bytes: 10 * 1024 * 1024,
  file_type: "source_pdf",
  filename: "quota-dry-run.pdf",
});
const policyDialog = reactive({
  visible: false,
  policyId: "",
  form: {
    name: "",
    scope_type: "file_type" as FileRetentionPolicyScopeType,
    file_type: "generated_word",
    retention_days: 30,
    description: "",
  },
});

const CLEANUP_RUN_MAX_FILES = 50;

const fileTypeOptions = [
  "source_pdf",
  "mineru_raw_result",
  "document_ir",
  "image_asset",
  "generated_word",
  "ai_call_log",
  "ai_debug_archive",
  "template_docx",
  "template_config",
  "term_file",
];

const schedulerExpectedTrueSafety = new Set([
  "scheduler_manual_dry_run_executed",
  "cleanup_lock_acquired",
  "cleanup_lock_released",
  "history_recorded",
]);
const schedulerUnsafeTrueSafety = new Set([
  "scheduler_loop_executed",
  "metadata_mutated",
  "objects_deleted",
  "mark_expired_executed",
  "physical_delete_executed",
  "provider_calls_executed",
  "s3_delete_executed",
  "audit_events_written",
]);

const candidateCount = computed(() => plan.value?.candidates.length ?? 0);
const markableCount = computed(() => (
  plan.value?.candidates.filter((candidate) => candidate.status === "uploaded").length ?? 0
));
const storageQuotaStatus = computed(() => String(storageUsage.value?.quota.status ?? "not_configured"));
const selectedFileIds = computed(() => selectedCandidates.value.map((candidate) => candidate.file_id));
const deletablePreviewCount = computed(() => (
  deleteReport.value?.items.filter((item) => item.outcome === "deletable").length ?? 0
));
const canOpenDeleteDialog = computed(() => (
  selectedFileIds.value.length > 0
  && deleteReport.value?.action_mode === "delete_preview"
  && fileIdsMatchCurrentSelection(deleteReport.value.requested_file_ids)
  && deletablePreviewCount.value > 0
));
const cleanupDeletablePreviewCount = computed(() => (
  cleanupRunReport.value?.physical_delete.items.filter((item) => item.outcome === "deletable").length ?? 0
));
const canOpenCleanupRunDialog = computed(() => (
  selectedFileIds.value.length > 0
  && cleanupRunReport.value?.action_mode === "cleanup_preview"
  && fileIdsMatchCurrentSelection(cleanupRunReport.value.requested_file_ids)
  && cleanupDeletablePreviewCount.value > 0
));
const canSubmitCleanupRun = computed(() => (
  canOpenCleanupRunDialog.value
  && cleanupRunReport.value !== null
  && cleanupRunDialog.reason.trim().length > 0
  && cleanupRunDialog.confirmation === cleanupRunReport.value.confirmation_phrase
));
const schedulerReadonlyReportRecord = computed(() => asRecord(schedulerDryRunReport.value?.readonly_report));
const schedulerRetentionRecord = computed(() => asRecord(schedulerReadonlyReportRecord.value?.retention));
const schedulerStorageUsageRecord = computed(() => asRecord(schedulerReadonlyReportRecord.value?.storage_usage));
const schedulerRetentionTotals = computed(() => asRecord(schedulerRetentionRecord.value?.totals));
const schedulerStorageReclaim = computed(() => asRecord(schedulerStorageUsageRecord.value?.reclaim));
const schedulerRetentionCandidateCount = computed(() => {
  const candidateCountFromTotals = numberField(schedulerRetentionTotals.value, "candidate_files");
  if (candidateCountFromTotals !== null) {
    return candidateCountFromTotals;
  }
  const candidates = schedulerRetentionRecord.value?.candidates;
  return Array.isArray(candidates) ? candidates.length : 0;
});
const schedulerEstimatedReclaimBytes = computed(() => (
  numberField(schedulerStorageReclaim.value, "estimated_reclaimable_size_bytes") ?? 0
));
const schedulerDryRunSafetyEntries = computed(() => {
  if (!schedulerDryRunReport.value) {
    return [];
  }
  return Object.entries(schedulerDryRunReport.value.safety).map(([label, value]) => ({
    label,
    value,
    type: schedulerDryRunSafetyTag(label, value),
  })) satisfies Array<{ label: string; value: boolean; type: StatusTag }>;
});
const cleanupRunSafetyEntries = computed(() => {
  if (!cleanupRunReport.value) {
    return [];
  }
  const safety = cleanupRunReport.value.safety;
  return [
    { label: "scheduler_loop_executed", value: safety.scheduler_loop_executed, type: safety.scheduler_loop_executed ? "danger" : "success" },
    { label: "provider_calls_executed", value: safety.provider_calls_executed, type: safety.provider_calls_executed ? "danger" : "success" },
    { label: "s3_delete_executed", value: safety.s3_delete_executed, type: safety.s3_delete_executed ? "danger" : "success" },
    { label: "physical_delete_executed", value: safety.physical_delete_executed, type: safety.physical_delete_executed ? "warning" : "info" },
    { label: "physical_delete_contract_reused", value: safety.physical_delete_contract_reused, type: safety.physical_delete_contract_reused ? "success" : "danger" },
    { label: "audit_events_written", value: safety.audit_events_written, type: safety.audit_events_written ? "warning" : "info" },
    { label: "history_recorded", value: safety.history_recorded, type: safety.history_recorded ? "success" : "danger" },
    { label: "signed_plan_created", value: safety.signed_plan_created, type: safety.signed_plan_created ? "success" : "danger" },
    { label: "signed_plan_verified", value: safety.signed_plan_verified, type: safety.signed_plan_verified ? "success" : "info" },
  ] satisfies Array<{ label: string; value: boolean; type: StatusTag }>;
});
const selectedCleanupRunHistorySafetyEntries = computed(() => {
  if (!selectedCleanupRunHistory.value) {
    return [];
  }
  return Object.entries(selectedCleanupRunHistory.value.safety).map(([label, value]) => ({
    label,
    value,
    type: value ? "success" : "info",
  })) satisfies Array<{ label: string; value: boolean; type: StatusTag }>;
});
const quotaPolicySafetyEntries = computed(() => {
  if (!quotaPolicyReport.value) {
    return [];
  }
  const safety = quotaPolicyReport.value.safety;
  return [
    { label: "read_only", value: safety.read_only, type: safety.read_only ? "success" : "danger" },
    { label: "upload_authorization_created", value: safety.upload_authorization_created, type: safety.upload_authorization_created ? "danger" : "success" },
    { label: "upload_content_written", value: safety.upload_content_written, type: safety.upload_content_written ? "danger" : "success" },
    { label: "upload_blocking_executed", value: safety.upload_blocking_executed, type: safety.upload_blocking_executed ? "danger" : "success" },
    { label: "metadata_mutated", value: safety.metadata_mutated, type: safety.metadata_mutated ? "danger" : "success" },
    { label: "audit_events_written", value: safety.audit_events_written, type: safety.audit_events_written ? "warning" : "info" },
    { label: "provider_calls_executed", value: safety.provider_calls_executed, type: safety.provider_calls_executed ? "danger" : "success" },
    { label: "delete_executed", value: safety.delete_executed, type: safety.delete_executed ? "danger" : "success" },
    { label: "conversion_workflow_executed", value: safety.conversion_workflow_executed, type: safety.conversion_workflow_executed ? "danger" : "success" },
  ] satisfies Array<{ label: string; value: boolean; type: StatusTag }>;
});

// 同步刷新 retention plan、policy governance 和 storage usage。
function refreshRetentionPage(): void {
  void loadFileLibrarySearch();
  void loadPlan();
  void loadPolicies();
  void loadStorageUsage();
  void loadCleanupRunHistory();
}

// 按当前筛选读取只读文件库搜索结果。
async function loadFileLibrarySearch(): Promise<void> {
  libraryLoading.value = true;
  error.value = null;
  try {
    librarySearch.value = await filesApi.searchLibrary(buildLibrarySearchQuery());
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    libraryLoading.value = false;
  }
}

// 应用文件库筛选条件并回到第一页。
function applyLibrarySearch(): void {
  libraryPage.value = 1;
  void loadFileLibrarySearch();
}

// 重置文件库筛选条件并重新读取第一页。
function resetLibrarySearch(): void {
  libraryFilters.q = "";
  libraryFilters.status = "";
  libraryFilters.file_type = "";
  libraryFilters.storage_provider = "";
  libraryFilters.job_id = "";
  librarySort.value = "created_at_desc";
  libraryPage.value = 1;
  void loadFileLibrarySearch();
}

// 改变文件库页大小时回到第一页，避免页码越界。
function handleLibraryPageSizeChange(): void {
  libraryPage.value = 1;
  void loadFileLibrarySearch();
}

// 生成后端文件库搜索 query，空字符串不发送。
function buildLibrarySearchQuery(): FileLibrarySearchQuery {
  const params: FileLibrarySearchQuery = {
    page: libraryPage.value,
    page_size: libraryPageSize.value,
    sort: librarySort.value,
  };
  addLibraryTrimmedParam(params, "q", libraryFilters.q);
  addLibraryTrimmedParam(params, "status", libraryFilters.status);
  addLibraryTrimmedParam(params, "file_type", libraryFilters.file_type);
  addLibraryTrimmedParam(params, "storage_provider", libraryFilters.storage_provider);
  addLibraryTrimmedParam(params, "job_id", libraryFilters.job_id);
  return params;
}

// 给文件库查询参数做统一 trim，空字符串不发送。
function addLibraryTrimmedParam(params: FileLibrarySearchQuery, key: LibraryFilterKey, value: string): void {
  const normalized = value.trim();
  if (normalized) {
    Object.assign(params, { [key]: normalized });
  }
}

// 读取当前 retention dry-run 计划，可在执行后保留结果报告用于审计查看。
async function loadPlan(preserveDeleteReport = false, preserveCleanupRunReport = false): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    plan.value = await filesApi.getRetentionPlan();
    selectedCandidates.value = [];
    if (!preserveDeleteReport) {
      deleteReport.value = null;
    }
    if (!preserveCleanupRunReport) {
      cleanupRunReport.value = null;
    }
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

// 读取 document_files storage usage 只读估算。
async function loadStorageUsage(): Promise<void> {
  storageLoading.value = true;
  error.value = null;
  try {
    storageUsage.value = await filesApi.getStorageUsage();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    storageLoading.value = false;
  }
}

// 运行 quota policy dry-run，不创建上传授权、不改变真实上传阻断策略。
async function runQuotaPolicyDryRun(): Promise<void> {
  quotaPolicyLoading.value = true;
  error.value = null;
  try {
    quotaPolicyReport.value = await filesApi.dryRunQuotaPolicy({
      filename: quotaPolicyForm.filename.trim() || null,
      file_type: quotaPolicyForm.file_type,
      size_bytes: quotaPolicyForm.size_bytes,
    });
    ElMessage.success(`quota dry-run 完成：would_block=${String(quotaPolicyReport.value.would_block)}。`);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    quotaPolicyLoading.value = false;
  }
}

// 手动运行 cleanup scheduler dry-run，只生成 readonly report、lock evidence 和 durable history。
async function runCleanupSchedulerDryRun(): Promise<void> {
  schedulerDryRunLoading.value = true;
  error.value = null;
  try {
    const response = await filesApi.runRetentionCleanupSchedulerDryRun({
      owner_id: schedulerDryRunForm.owner_id.trim() || null,
      lock_ttl_seconds: schedulerDryRunForm.lock_ttl_seconds,
    });
    schedulerDryRunReport.value = response;
    await loadCleanupRunHistory();
    selectedCleanupRunHistory.value = await filesApi.getRetentionCleanupRunHistory(response.run_id);
    ElMessage.success(`scheduler dry-run 完成：candidates=${schedulerRetentionCandidateCount.value}。`);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    schedulerDryRunLoading.value = false;
  }
}

// 读取 cleanup run durable history，不执行任何清理动作。
async function loadCleanupRunHistory(): Promise<void> {
  cleanupHistoryLoading.value = true;
  error.value = null;
  try {
    cleanupRunHistory.value = await filesApi.listRetentionCleanupRunHistory({ page: 1, page_size: 25 });
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    cleanupHistoryLoading.value = false;
  }
}

// 读取单条 cleanup run history 详情，便于核对 safety flags。
async function inspectCleanupRunHistory(runId: string): Promise<void> {
  cleanupHistoryLoading.value = true;
  error.value = null;
  try {
    selectedCleanupRunHistory.value = await filesApi.getRetentionCleanupRunHistory(runId);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    cleanupHistoryLoading.value = false;
  }
}

// 读取 retention policy governance 列表。
async function loadPolicies(): Promise<void> {
  policyLoading.value = true;
  error.value = null;
  try {
    policyList.value = await filesApi.listRetentionPolicies();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    policyLoading.value = false;
  }
}

// 将当前过期候选标记为 expired，但不执行物理删除。
async function markExpired(): Promise<void> {
  if (markableCount.value === 0) {
    return;
  }
  try {
    await ElMessageBox.confirm(
      "该操作只会把当前 uploaded 过期候选的 metadata 状态标记为 expired，不会删除任何文件内容。",
      "标记过期文件",
      {
        confirmButtonText: "标记 expired",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
  } catch {
    return;
  }

  marking.value = true;
  error.value = null;
  try {
    const response = await filesApi.markRetentionExpired();
    plan.value = response;
    selectedCandidates.value = [];
    deleteReport.value = null;
    cleanupRunReport.value = null;
    ElMessage.success(`已标记 ${response.marked_file_ids.length} 个文件。`);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    marking.value = false;
  }
}

// 记录表格选择，选择变化会清空已有 dry-run 结果。
function handleSelectionChange(rows: FileRetentionCandidateResponse[]): void {
  selectedCandidates.value = rows;
  deleteReport.value = null;
  cleanupRunReport.value = null;
  cleanupRunDialog.visible = false;
}

// 对当前选择的文件执行物理删除 dry-run。
async function previewPhysicalDelete(): Promise<void> {
  if (selectedFileIds.value.length === 0) {
    return;
  }
  previewing.value = true;
  error.value = null;
  try {
    const response = await filesApi.previewRetentionDelete({ file_ids: selectedFileIds.value });
    deleteReport.value = response;
    ElMessage.success(`已预览 ${response.items.length} 个文件，deletable=${response.totals.deletable ?? 0}。`);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    previewing.value = false;
  }
}

// 对当前选择的文件执行 manual cleanup-run preview，不执行删除、不写审计，并读取 durable history。
async function previewCleanupRun(): Promise<void> {
  if (selectedFileIds.value.length === 0) {
    return;
  }
  cleanupPreviewing.value = true;
  error.value = null;
  try {
    const response = await filesApi.previewRetentionCleanupRun({
      file_ids: selectedFileIds.value,
      max_files: CLEANUP_RUN_MAX_FILES,
    });
    cleanupRunReport.value = response;
    selectedCleanupRunHistory.value = await filesApi.getRetentionCleanupRunHistory(response.run_id);
    await loadCleanupRunHistory();
    ElMessage.success(`cleanup run 已预览 ${response.physical_delete.items.length} 个文件，deletable=${response.physical_delete.totals.deletable ?? 0}。`);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    cleanupPreviewing.value = false;
  }
}

// 打开物理删除确认框，要求用户重新输入 reason 和确认短语。
function openPhysicalDeleteDialog(): void {
  if (!canOpenDeleteDialog.value) {
    ElMessage.warning("请先对当前选择执行物理删除预览。");
    return;
  }
  deleteDialog.reason = "";
  deleteDialog.confirmation = "";
  deleteDialog.visible = true;
}

// 打开 cleanup-run 执行确认框，要求 reason 和后端返回的确认短语。
function openCleanupRunDialog(): void {
  if (!canOpenCleanupRunDialog.value) {
    ElMessage.warning("请先对当前选择执行 cleanup run preview。");
    return;
  }
  cleanupRunDialog.reason = "";
  cleanupRunDialog.confirmation = "";
  cleanupRunDialog.visible = true;
}

// 打开新增策略 dialog，默认创建 file_type draft。
function openCreatePolicyDialog(): void {
  policyDialog.policyId = "";
  policyDialog.form.name = "";
  policyDialog.form.scope_type = "file_type";
  policyDialog.form.file_type = "generated_word";
  policyDialog.form.retention_days = 30;
  policyDialog.form.description = "";
  policyDialog.visible = true;
}

// 打开 draft 策略编辑 dialog。
function openEditPolicyDialog(policy: FileRetentionPolicyResponse): void {
  policyDialog.policyId = policy.policy_id;
  policyDialog.form.name = policy.name;
  policyDialog.form.scope_type = policy.scope_type;
  policyDialog.form.file_type = policy.file_type || "generated_word";
  policyDialog.form.retention_days = policy.retention_days;
  policyDialog.form.description = policy.description || "";
  policyDialog.visible = true;
}

// 保存 draft 策略；发布动作单独要求 reason。
async function savePolicy(): Promise<void> {
  const payload: FileRetentionPolicyCreateRequest = {
    name: policyDialog.form.name,
    scope_type: policyDialog.form.scope_type,
    file_type: policyDialog.form.scope_type === "file_type" ? policyDialog.form.file_type : null,
    retention_days: policyDialog.form.retention_days,
    description: policyDialog.form.description || null,
  };
  policySaving.value = true;
  error.value = null;
  try {
    if (policyDialog.policyId) {
      await filesApi.updateRetentionPolicy(policyDialog.policyId, payload);
    } else {
      await filesApi.createRetentionPolicy(payload);
    }
    policyDialog.visible = false;
    await loadPolicies();
    ElMessage.success("保留策略 draft 已保存。");
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    policySaving.value = false;
  }
}

// 预览策略对历史文件的 expires_at 影响，不执行回填。
async function previewPolicyImpact(policy: FileRetentionPolicyResponse): Promise<void> {
  policyLoading.value = true;
  error.value = null;
  try {
    policyImpact.value = await filesApi.previewRetentionPolicyImpact(policy.policy_id, { mode: "candidate_policy" });
    ElMessage.success(`已预览 ${policyImpact.value.items.length} 个匹配文件。`);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    policyLoading.value = false;
  }
}

// 发布 draft policy，发布后只影响后续新文件。
async function publishPolicy(policy: FileRetentionPolicyResponse): Promise<void> {
  await runPolicyReasonAction(policy, "发布策略", "发布后只影响后续新文件 expires_at，不回填历史文件。", "publish");
}

// 设置同 scope 默认 policy。
async function setDefaultPolicy(policy: FileRetentionPolicyResponse): Promise<void> {
  await runPolicyReasonAction(policy, "设为默认策略", "该操作只切换同 scope 默认策略，不回填历史文件。", "set-default");
}

// 禁用 policy，保留历史记录。
async function disablePolicy(policy: FileRetentionPolicyResponse): Promise<void> {
  await runPolicyReasonAction(policy, "禁用策略", "禁用后该策略不再影响后续新文件，历史记录仍保留。", "disable");
}

// 对需要 reason 的策略治理动作执行确认和 API 调用。
async function runPolicyReasonAction(
  policy: FileRetentionPolicyResponse,
  title: string,
  message: string,
  action: "publish" | "set-default" | "disable",
): Promise<void> {
  let reason = "";
  try {
    const result = await ElMessageBox.prompt(message, title, {
      confirmButtonText: title,
      cancelButtonText: "取消",
      inputPlaceholder: "填写审计 reason",
      inputValidator: (value) => Boolean(value?.trim()) || "reason 不能为空",
      type: "warning",
    });
    reason = result.value;
  } catch {
    return;
  }

  policySaving.value = true;
  error.value = null;
  try {
    if (action === "publish") {
      await filesApi.publishRetentionPolicy(policy.policy_id, { reason });
    } else if (action === "set-default") {
      await filesApi.setDefaultRetentionPolicy(policy.policy_id, { reason });
    } else {
      await filesApi.disableRetentionPolicy(policy.policy_id, { reason });
    }
    await loadPolicies();
    ElMessage.success("保留策略治理动作已完成。");
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    policySaving.value = false;
  }
}

// 执行 selected expired 文件物理删除，并刷新 retention plan。
async function executePhysicalDelete(): Promise<void> {
  if (!canOpenDeleteDialog.value || !deleteReport.value) {
    return;
  }
  deleting.value = true;
  error.value = null;
  try {
    const response = await filesApi.deleteExpiredRetentionFiles({
      file_ids: deleteReport.value.requested_file_ids,
      reason: deleteDialog.reason,
      confirmation: deleteDialog.confirmation,
    });
    deleteReport.value = response;
    cleanupRunReport.value = null;
    deleteDialog.visible = false;
    await loadPlan(true);
    ElMessage.success(`物理删除完成：deleted=${response.totals.deleted ?? 0}，skipped=${response.totals.skipped ?? 0}。`);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    deleting.value = false;
  }
}

// 执行带 preview_hash 的 manual cleanup run，并显示同一 run_id 的 durable history。
async function executeCleanupRun(): Promise<void> {
  if (!canSubmitCleanupRun.value || !cleanupRunReport.value) {
    return;
  }
  cleanupExecuting.value = true;
  error.value = null;
  try {
    const response = await filesApi.executeRetentionCleanupRun({
      run_id: cleanupRunReport.value.run_id,
      file_ids: cleanupRunReport.value.requested_file_ids,
      max_files: cleanupRunReport.value.max_files,
      preview_hash: cleanupRunReport.value.preview_hash,
      plan_id: cleanupRunReport.value.cleanup_plan?.plan_id ?? null,
      plan_signature: cleanupRunReport.value.cleanup_plan?.signature ?? null,
      reason: cleanupRunDialog.reason,
      confirmation: cleanupRunDialog.confirmation,
    });
    cleanupRunReport.value = response;
    cleanupRunDialog.visible = false;
    deleteReport.value = null;
    await loadPlan(false, true);
    await loadCleanupRunHistory();
    selectedCleanupRunHistory.value = await filesApi.getRetentionCleanupRunHistory(response.run_id);
    ElMessage.success(`cleanup run 完成：deleted=${response.physical_delete.totals.deleted ?? 0}，skipped=${response.physical_delete.totals.skipped ?? 0}。`);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    cleanupExecuting.value = false;
  }
}

// 读取 totals 中的数值，缺失时展示 0。
function totalValue(key: string): number {
  return plan.value?.totals[key] ?? 0;
}

// 读取物理删除 report totals 中的数值，缺失时展示 0。
function totalDeleteValue(key: string): number {
  return deleteReport.value?.totals[key] ?? 0;
}

// 读取 cleanup-run physical_delete totals 中的数值，缺失时展示 0。
function cleanupTotalValue(key: string): number {
  return cleanupRunReport.value?.physical_delete.totals[key] ?? 0;
}

// 读取 storage usage totals 中的数值，缺失时展示 0。
function storageTotalValue(key: string): number {
  return storageUsage.value?.totals[key] ?? 0;
}

// 读取 storage usage reclaim 中的数字字段，非数字字段按 0 处理。
function storageReclaimValue(key: string): number {
  const value = storageUsage.value?.reclaim[key];
  return typeof value === "number" ? value : 0;
}

// 将 ratio 小数转换为百分比展示；未配置 quota 时展示短横线。
function formatRatio(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${(value * 100).toFixed(1)}%`;
}

// 仅把普通对象视为可读记录，避免从 unknown report 里误读数组或 null。
function asRecord(value: unknown): UnknownRecord | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return null;
  }
  return value as UnknownRecord;
}

// 从 unknown record 中读取数值字段，非数字字段按缺失处理。
function numberField(record: UnknownRecord | null, key: string): number | null {
  const value = record?.[key];
  return typeof value === "number" ? value : null;
}

// 将 scheduler dry-run safety flag 映射为标签样式，突出任何意外副作用。
function schedulerDryRunSafetyTag(label: string, value: boolean): StatusTag {
  if (value && schedulerUnsafeTrueSafety.has(label)) {
    return "danger";
  }
  if (!value && schedulerExpectedTrueSafety.has(label)) {
    return "danger";
  }
  if (value) {
    return "success";
  }
  return "info";
}

// 判断当前选择是否仍匹配某次 preview 请求的精确 file_id 顺序。
function fileIdsMatchCurrentSelection(requestedFileIds: string[]): boolean {
  return selectedFileIds.value.join("\n") === requestedFileIds.join("\n");
}

// 将 metadata 状态映射为表格标签样式。
function statusTag(status: string): StatusTag {
  if (status === "uploaded") {
    return "warning";
  }
  if (status === "expired") {
    return "info";
  }
  if (status === "deleted") {
    return "danger";
  }
  return "success";
}

// 将 policy 状态映射为标签样式。
function policyStatusTag(status: string): StatusTag {
  if (status === "draft") {
    return "warning";
  }
  if (status === "published") {
    return "success";
  }
  if (status === "disabled") {
    return "info";
  }
  return "info";
}

// 将 advisory quota 状态映射为标签样式。
function storageQuotaStatusTag(status: string): StatusTag {
  if (status === "exceeded") {
    return "danger";
  }
  if (status === "warning") {
    return "warning";
  }
  if (status === "ok") {
    return "success";
  }
  return "info";
}

// 将 quota policy dry-run 状态映射为标签样式。
function quotaPolicyStatusTag(status: string): StatusTag {
  if (status === "dry_run" || status === "ready") {
    return "success";
  }
  if (status === "invalid") {
    return "danger";
  }
  if (status === "not_configured") {
    return "warning";
  }
  return "info";
}

// 将 cleanup run history 状态映射为标签样式。
function cleanupHistoryStatusTag(status: FileRetentionCleanupRunHistoryStatus): StatusTag {
  if (status === "executed") {
    return "success";
  }
  if (status === "failed") {
    return "danger";
  }
  if (status === "dry_run") {
    return "info";
  }
  return "warning";
}

// 将物理删除 outcome 映射为结果标签样式。
function outcomeTag(outcome: FileRetentionDeleteOutcome): StatusTag {
  if (outcome === "deleted" || outcome === "already_missing" || outcome === "deletable") {
    return "success";
  }
  if (outcome === "failed") {
    return "danger";
  }
  if (outcome === "skipped_unsupported_storage") {
    return "warning";
  }
  return "info";
}

// 展示 S3 fake deletion contract 的关键安全结论，避免误解为真实删除。
function s3ContractLabel(row: FileRetentionDeleteItemResponse): string {
  const contract = row.s3_delete_contract;
  if (!contract) {
    return "-";
  }
  const target = contract.target_exact ? "exact" : "inexact";
  const realDelete = contract.safety.real_s3_delete_executed ? "real-delete" : "no-real-delete";
  return `${contract.adapter_mode}/${target}/${realDelete}`;
}

onMounted(() => {
  void loadFileLibrarySearch();
  void loadPlan();
  void loadPolicies();
  void loadStorageUsage();
  void loadCleanupRunHistory();
});
</script>

<style scoped lang="scss">
.file-retention-page {
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

.heading-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.retention-notice {
  margin-bottom: 0;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-card {
  display: grid;
  gap: 6px;
  min-height: 112px;
  padding: 16px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
}

.summary-card span,
.summary-card strong,
.summary-card small {
  display: block;
}

.summary-card span {
  color: #667085;
  font-size: 13px;
}

.summary-card strong {
  color: #111827;
  font-size: 24px;
  line-height: 1.2;
}

.summary-card small {
  color: #667085;
  font-size: 13px;
  line-height: 1.5;
}

.summary-time {
  font-size: 16px !important;
  line-height: 1.4 !important;
}

.retention-table-section {
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.library-filter-form {
  display: grid;
  grid-template-columns: 1.8fr repeat(5, minmax(130px, 1fr));
  gap: 12px;
}

.filter-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.effective-policy-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
}

.storage-group-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.quota-dry-run-panel {
  display: grid;
  gap: 12px;
  padding: 14px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #f8fafc;
}

.quota-dry-run-form {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(180px, 1fr) minmax(220px, 2fr);
  gap: 12px;
}

.quota-result-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.quota-result-card {
  display: grid;
  gap: 6px;
  min-width: 0;
  padding: 12px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
}

.quota-result-card span,
.quota-result-card small {
  color: #667085;
  font-size: 12px;
}

.quota-result-card strong {
  overflow-wrap: anywhere;
  color: #111827;
  font-size: 18px;
  line-height: 1.3;
}

.quota-reason-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.scheduler-dry-run-section {
  background: #fbfdff;
}

.scheduler-dry-run-form {
  display: grid;
  grid-template-columns: minmax(220px, 2fr) minmax(180px, 1fr);
  gap: 12px;
}

.scheduler-dry-run-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.cleanup-run-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.cleanup-history-detail {
  display: grid;
  grid-template-columns: minmax(0, 2fr) repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.cleanup-run-card {
  display: grid;
  gap: 6px;
  min-width: 0;
  padding: 12px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #f8fafc;
}

.cleanup-run-card span,
.cleanup-run-card small {
  color: #667085;
  font-size: 12px;
}

.cleanup-run-card strong {
  overflow-wrap: anywhere;
  color: #111827;
  font-size: 14px;
  line-height: 1.5;
}

.safety-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.storage-group-card {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.storage-group-card h3 {
  margin: 0;
  color: #111827;
  font-size: 14px;
}

.section-title {
  margin: 0;
  color: #111827;
  font-size: 18px;
}

.section-subtitle {
  margin: 6px 0 0;
  color: #667085;
  font-size: 13px;
}

.retention-table {
  width: 100%;
}

.mono {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 12px;
}

.object-key {
  overflow-wrap: anywhere;
}

.delete-warning {
  margin-bottom: 14px;
}

@media (max-width: 920px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .storage-group-grid {
    grid-template-columns: 1fr;
  }

  .quota-dry-run-form,
  .quota-result-grid,
  .scheduler-dry-run-form,
  .scheduler-dry-run-grid {
    grid-template-columns: 1fr;
  }

  .cleanup-run-grid,
  .cleanup-history-detail {
    grid-template-columns: 1fr;
  }

  .library-filter-form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .page-heading,
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .library-filter-form {
    grid-template-columns: 1fr;
  }

  .heading-actions {
    align-items: flex-start;
    flex-direction: column;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
