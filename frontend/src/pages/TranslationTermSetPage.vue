<!-- File: frontend/src/pages/TranslationTermSetPage.vue -->
<!-- Purpose: Provide the Admin Translation Term Set CSV import, export, default switching, and rollback page. -->
<template>
  <main class="translation-term-set-page app-page" aria-labelledby="translation-term-set-title">
    <section class="page-heading app-page-header app-page-shell app-page-shell--wide">
      <div>
        <p class="page-kicker">翻译术语集</p>
        <h1 id="translation-term-set-title" class="page-title">翻译术语集</h1>
        <p class="page-description">通过 CSV 管理草稿，查看版本并执行发布、设默认和回滚。</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
    </section>

    <ApiErrorAlert class="app-page-shell app-page-shell--wide" :error="error" />
    <el-alert
      v-if="errorActionHint"
      class="context-alert app-page-shell app-page-shell--wide"
      type="info"
      :title="errorActionHint"
      :closable="false"
      show-icon
    />
    <el-alert
      v-if="proposalGovernanceContext"
      class="context-alert governance-context-alert app-page-shell app-page-shell--wide"
      type="info"
      :closable="false"
      show-icon
    >
      <template #title>
        <span>建议治理上下文</span>
      </template>
      <div class="context-summary">
        <el-tag effect="plain">建议 ID：{{ proposalGovernanceContext.proposalId }}</el-tag>
        <el-tag effect="plain">术语集：{{ proposalGovernanceContext.setId || "-" }}</el-tag>
        <el-tag effect="plain">观察版本：{{ proposalGovernanceContext.observedVersion || "-" }}</el-tag>
        <el-button link type="primary" @click="returnToProposalReview">返回建议审核页</el-button>
      </div>
    </el-alert>

    <el-alert
      class="app-page-shell app-page-shell--wide"
      v-if="unavailable"
      type="warning"
      title="当前部署未启用 MySQL resource service，翻译术语集管理不可用。"
      :closable="false"
      show-icon
    />

    <section v-else class="term-set-grid app-page-shell app-page-shell--wide">
      <el-card class="app-panel-card app-table-card" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">术语集</h2>
            <p class="section-subtitle">选择术语集查看草稿和已发布版本。</p>
          </div>
        </div>
        <el-table :data="sets" :loading="loading" empty-text="暂无翻译术语集" @row-click="selectSet">
          <el-table-column prop="set_id" label="术语集 ID" min-width="210" show-overflow-tooltip />
          <el-table-column prop="language_pair" label="语言方向" width="110" />
          <el-table-column prop="default_version" label="默认版本" width="150" show-overflow-tooltip />
          <el-table-column prop="version_count" label="版本数" width="90" />
        </el-table>
      </el-card>

      <el-card class="app-panel-card" shadow="never">
        <div class="section-header term-set-draft-header">
          <div>
            <h2 class="section-title">草稿摘要</h2>
            <p class="section-subtitle">CSV 导入是本阶段唯一草稿修改入口。</p>
          </div>
          <el-tag v-if="draft?.snapshot_hash" class="draft-hash-tag mono" effect="plain" :title="draft.snapshot_hash">
            {{ draft.snapshot_hash }}
          </el-tag>
        </div>
        <el-empty v-if="!selectedSetId" description="请选择术语集" :image-size="90" />
        <template v-else>
          <dl class="summary-list">
            <div><dt>基线版本</dt><dd>{{ draft?.base_version || "-" }}</dd></div>
            <div><dt>术语数</dt><dd>{{ draft?.term_count ?? "-" }}</dd></div>
            <div><dt>校验状态</dt><dd>{{ draft?.validation.valid ? "有效" : "无效" }}</dd></div>
          </dl>
          <RoleGate>
            <div class="action-row app-action-row">
              <el-button type="primary" :disabled="!selectedSetId" @click="openImportDialog">导入 CSV</el-button>
              <el-button type="success" :disabled="!selectedSetId" @click="openPublishDialog">发布草稿</el-button>
              <el-button :disabled="!selectedSetId" @click="exportVersion(null)">导出默认 CSV</el-button>
            </div>
          </RoleGate>
        </template>
      </el-card>
    </section>

    <el-card v-if="!unavailable && lastImportReport" class="app-panel-card app-table-card app-page-shell app-page-shell--wide" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">最近一次 CSV 导入</h2>
          <p class="section-subtitle">{{ importReportSummary }}</p>
        </div>
        <el-tag effect="plain">dedupe={{ lastImportReport.dedupe }}</el-tag>
      </div>
      <el-table
        :data="lastImportReport.duplicates"
        empty-text="本次导入没有重复项"
        class="import-report-table"
      >
        <el-table-column prop="row_number" label="重复行" width="100" />
        <el-table-column prop="kept_row_number" label="保留行" width="100" />
        <el-table-column prop="source_term" label="源术语" min-width="180" show-overflow-tooltip />
        <el-table-column prop="normalized_source_term" label="规范化术语" min-width="180" show-overflow-tooltip />
      </el-table>
    </el-card>

    <el-card v-if="!unavailable" class="app-panel-card app-table-card app-page-shell app-page-shell--wide" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">草稿校验</h2>
          <p class="section-subtitle">错误会阻断发布，告警作为发布前提示。</p>
        </div>
      </div>
      <el-table :data="validationFindings" :loading="loading" empty-text="暂无草稿校验结果">
        <el-table-column prop="level" label="级别" width="100">
          <template #default="{ row }">
            <el-tag :type="row.level === 'error' ? 'danger' : 'warning'" effect="plain">
              {{ validationLevelLabel(row.level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="code" label="代码" width="220" show-overflow-tooltip />
        <el-table-column prop="normalized_source_term" label="规范化术语" width="220" show-overflow-tooltip />
        <el-table-column prop="message" label="说明" min-width="260" show-overflow-tooltip />
      </el-table>
    </el-card>

    <el-card v-if="!unavailable" class="app-panel-card app-table-card app-page-shell app-page-shell--wide" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">差异 / 发布前检查</h2>
          <p class="section-subtitle">默认版本与草稿的只读治理预览，不会发布或修改草稿。</p>
        </div>
        <el-tag v-if="diff" effect="plain">{{ diff.base_version }} -> {{ diff.target_version }}</el-tag>
      </div>

      <div class="governance-summary-grid app-governance-grid" aria-label="Translation Term Set diff summary">
        <article class="summary-metric app-governance-metric">
          <span>新增</span>
          <strong>{{ diff?.summary.added ?? "-" }}</strong>
        </article>
        <article class="summary-metric app-governance-metric">
          <span>移除</span>
          <strong>{{ diff?.summary.removed ?? "-" }}</strong>
        </article>
        <article class="summary-metric app-governance-metric">
          <span>变更</span>
          <strong>{{ diff?.summary.changed ?? "-" }}</strong>
        </article>
        <article class="summary-metric app-governance-metric">
          <span>未变</span>
          <strong>{{ diff?.summary.unchanged ?? "-" }}</strong>
        </article>
      </div>

      <el-alert
        v-if="preflight?.publish_blocked"
        class="context-alert"
        type="error"
        title="发布前检查阻断发布"
        :closable="false"
        show-icon
      >
        <ul class="blocking-list">
          <li v-for="reason in preflight.blocking_reasons" :key="reason">{{ reason }}</li>
        </ul>
      </el-alert>
      <el-alert
        v-else-if="preflight"
        class="context-alert"
        type="success"
        title="发布前检查未发现阻断项"
        :closable="false"
        show-icon
      />

      <el-table :data="visibleDiffItems" :loading="loading" empty-text="暂无草稿差异">
        <el-table-column label="类型" width="110">
          <template #default="{ row }">
            <el-tag :type="diffKindTag(row.kind)" effect="plain">{{ diffKindLabel(row.kind) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source_term" label="源术语" min-width="160" show-overflow-tooltip />
        <el-table-column prop="normalized_source_term" label="规范化术语" min-width="170" show-overflow-tooltip />
        <el-table-column label="变更字段" min-width="220">
          <template #default="{ row }">
            <span v-if="!row.changed_fields.length" class="muted">-</span>
            <span v-else class="tag-stack">
              <el-tag v-for="field in row.changed_fields" :key="field" size="small" effect="plain">{{ field }}</el-tag>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="变更前" min-width="260">
          <template #default="{ row }">
            <pre class="diff-payload app-technical-block">{{ formatDiffPayload(row.before) }}</pre>
          </template>
        </el-table-column>
        <el-table-column label="变更后" min-width="260">
          <template #default="{ row }">
            <pre class="diff-payload app-technical-block">{{ formatDiffPayload(row.after) }}</pre>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="!unavailable" class="app-panel-card app-table-card app-page-shell app-page-shell--wide" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">待审核建议兼容性</h2>
          <p class="section-subtitle">只读预览待审核建议与当前草稿的兼容性。</p>
        </div>
      </div>

      <div class="governance-summary-grid app-governance-grid" aria-label="Translation Term Proposal compatibility summary">
        <article class="summary-metric app-governance-metric">
          <span>总数</span>
          <strong>{{ proposalCompatibility?.summary.total ?? "-" }}</strong>
        </article>
        <article class="summary-metric app-governance-metric">
          <span>兼容</span>
          <strong>{{ proposalCompatibility?.summary.compatible ?? "-" }}</strong>
        </article>
        <article class="summary-metric app-governance-metric">
          <span>告警</span>
          <strong>{{ proposalCompatibility?.summary.warning ?? "-" }}</strong>
        </article>
        <article class="summary-metric app-governance-metric">
          <span>冲突</span>
          <strong>{{ proposalCompatibility?.summary.conflict ?? "-" }}</strong>
        </article>
      </div>

      <el-alert
        v-if="proposalCompatibilityNotice"
        class="context-alert"
        type="warning"
        :title="proposalCompatibilityNotice"
        :closable="false"
        show-icon
      />
      <el-table
        :data="proposalCompatibility?.items || []"
        :loading="loading"
        empty-text="暂无待审核翻译术语建议"
        :row-class-name="proposalCompatibilityRowClassName"
      >
        <el-table-column prop="proposal_id" label="建议 ID" min-width="160">
          <template #default="{ row }">
            <router-link :to="{ name: 'term-proposals', query: { tab: 'translation-review', proposal_id: row.proposal_id } }" class="mono">
              {{ row.proposal_id }}
            </router-link>
          </template>
        </el-table-column>
        <el-table-column label="兼容性" width="140">
          <template #default="{ row }">
            <el-tag :type="compatibilityTag(row.compatibility)" effect="plain">{{ compatibilityLabel(row.compatibility) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="observed_version" label="观察版本" min-width="150" show-overflow-tooltip />
        <el-table-column prop="change_count" label="变更数" width="100" />
        <el-table-column label="冲突" min-width="220">
          <template #default="{ row }">{{ findingCodes(row.conflicts) }}</template>
        </el-table-column>
        <el-table-column label="告警" min-width="220">
          <template #default="{ row }">{{ findingCodes(row.warnings) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="!unavailable" class="app-panel-card app-table-card app-page-shell app-page-shell--wide" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">已发布版本</h2>
          <p class="section-subtitle">回滚只切默认指针，不生成新版本。</p>
        </div>
      </div>
      <el-table :data="detail?.versions || []" :loading="loading" empty-text="暂无已发布版本">
        <el-table-column prop="version" label="版本" width="170" show-overflow-tooltip />
        <el-table-column label="默认" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="success" effect="plain">默认</el-tag>
            <span v-else class="muted">否</span>
          </template>
        </el-table-column>
        <el-table-column prop="term_count" label="术语数" width="90" />
        <el-table-column prop="snapshot_hash" label="快照哈希" min-width="210" show-overflow-tooltip />
        <el-table-column label="发布时间" width="190">
          <template #default="{ row }">{{ formatDateTime(row.published_at) }}</template>
        </el-table-column>
        <el-table-column prop="published_by" label="发布人" width="120" />
        <el-table-column prop="release_note" label="发布说明" min-width="180" show-overflow-tooltip />
        <el-table-column v-if="isAdmin" label="管理操作" width="260" fixed="right">
          <template #default="{ row }">
            <RoleGate>
              <el-button link type="primary" @click="exportVersion(row.version)">导出</el-button>
              <el-button link type="warning" :disabled="row.is_default" @click="setDefault(row.version)">设默认</el-button>
              <el-button link type="danger" :disabled="row.is_default" @click="rollback(row.version)">回滚</el-button>
            </RoleGate>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="!unavailable" class="app-panel-card app-table-card app-page-shell app-page-shell--wide" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">草稿词条</h2>
          <p class="section-subtitle">逐行维护当前草稿；发布后才会影响后续新任务的默认术语版本。</p>
        </div>
        <RoleGate>
          <el-button type="primary" :icon="Plus" :disabled="!selectedSetId" @click="openAddTermDialog">新增术语</el-button>
        </RoleGate>
      </div>
      <el-table :data="draft?.entries || []" :loading="loading" empty-text="暂无草稿词条">
        <el-table-column prop="source_term" label="源术语" min-width="180" show-overflow-tooltip />
        <el-table-column label="推荐译法" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ recommendedTranslationText(row) }}</template>
        </el-table-column>
        <el-table-column label="禁用译法" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ listText(row.forbidden_translations) }}</template>
        </el-table-column>
        <el-table-column label="同义词" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ listText(row.synonyms) }}</template>
        </el-table-column>
        <el-table-column prop="language_pair" label="语言对" width="110" />
        <el-table-column prop="project" label="项目" width="130" show-overflow-tooltip />
        <el-table-column prop="content_type" label="内容类型" width="130" show-overflow-tooltip />
        <el-table-column label="标签" width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ listText(row.tags) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="termStatusTag(row.status)" effect="plain">{{ termStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column prop="maintainer" label="维护人" width="130" show-overflow-tooltip />
        <el-table-column prop="case_sensitive" label="区分大小写" width="110">
          <template #default="{ row }">{{ row.case_sensitive ? "区分" : "忽略" }}</template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="90" />
        <el-table-column prop="domain" label="领域" width="140" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="140" show-overflow-tooltip />
        <el-table-column prop="note" label="备注" min-width="160" show-overflow-tooltip />
        <el-table-column v-if="isAdmin" label="管理操作" width="240" fixed="right">
          <template #default="{ row }">
            <RoleGate>
              <div class="table-actions app-action-row">
                <el-button link type="primary" :icon="Edit" @click="openEditTermDialog(row)">编辑</el-button>
                <el-button
                  link
                  type="warning"
                  :icon="CircleClose"
                  :disabled="row.status === 'deprecated' || row.status === 'disabled'"
                  @click="disableDraftEntry(row)"
                >
                  废弃
                </el-button>
                <el-button link type="danger" :icon="Delete" @click="deleteDraftEntry(row)">删除</el-button>
              </div>
            </RoleGate>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="importDialog.visible" title="导入翻译术语 CSV" width="720px">
      <el-form ref="importFormRef" :model="importDialog.form" :rules="importRules" label-width="90px">
        <el-form-item label="重复处理" prop="dedupe">
          <el-segmented v-model="importDialog.form.dedupe" :options="dedupeOptions" />
          <p class="form-help">{{ dedupeHint }}</p>
        </el-form-item>
        <el-form-item label="CSV" prop="csv_text">
          <el-input
            v-model="importDialog.form.csv_text"
            type="textarea"
            :rows="12"
            class="mono"
            placeholder="language_pair,source_term,target_term,version"
          />
        </el-form-item>
      </el-form>
      <el-alert
        v-if="lastImportReport"
        class="dialog-alert"
        type="success"
        :title="importReportSummary"
        :closable="false"
        show-icon
      />
      <template #footer>
        <el-button @click="importDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="importCsv">导入到草稿</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="entryDialog.visible" :title="entryDialogTitle" width="720px">
      <el-form ref="entryFormRef" :model="entryDialog.form" :rules="entryRules" label-width="120px">
        <div class="entry-form-grid">
          <el-form-item label="源术语" prop="source_term">
            <el-input
              v-model="entryDialog.form.source_term"
              class="mono"
              :readonly="entryDialog.mode === 'edit'"
              :disabled="entryDialog.mode === 'edit'"
            />
          </el-form-item>
          <el-form-item label="推荐译法主值" prop="target_term">
            <el-input v-model="entryDialog.form.target_term" class="mono" />
          </el-form-item>
          <el-form-item label="推荐译法">
            <el-input v-model="entryDialog.form.recommended_translations" placeholder="多个译法用 ; 分隔" />
          </el-form-item>
          <el-form-item label="禁用译法">
            <el-input v-model="entryDialog.form.forbidden_translations" placeholder="多个译法用 ; 分隔" />
          </el-form-item>
          <el-form-item label="同义词">
            <el-input v-model="entryDialog.form.synonyms" placeholder="多个同义词用 ; 分隔" />
          </el-form-item>
          <el-form-item label="区分大小写">
            <el-switch v-model="entryDialog.form.case_sensitive" />
          </el-form-item>
          <el-form-item label="状态" prop="status">
            <el-segmented v-model="entryDialog.form.status" :options="termStatusOptions" />
          </el-form-item>
          <el-form-item label="优先级">
            <el-input-number v-model="entryDialog.form.priority" :min="-1000" :max="1000" controls-position="right" />
          </el-form-item>
          <el-form-item label="项目">
            <el-input v-model="entryDialog.form.project" />
          </el-form-item>
          <el-form-item label="内容类型">
            <el-input v-model="entryDialog.form.content_type" />
          </el-form-item>
          <el-form-item label="标签">
            <el-input v-model="entryDialog.form.tags" placeholder="多个标签用 ; 分隔" />
          </el-form-item>
          <el-form-item label="维护人">
            <el-input v-model="entryDialog.form.maintainer" />
          </el-form-item>
          <el-form-item label="领域">
            <el-input v-model="entryDialog.form.domain" />
          </el-form-item>
          <el-form-item label="分类">
            <el-input v-model="entryDialog.form.category" />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="entryDialog.form.note" type="textarea" :rows="3" />
          </el-form-item>
        </div>
      </el-form>
      <el-alert
        v-if="draft?.snapshot_hash"
        class="dialog-alert"
        type="info"
        :title="`基于当前草稿快照：${draft.snapshot_hash}`"
        :closable="false"
        show-icon
      />
      <template #footer>
        <el-button @click="entryDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="entrySaving" @click="submitDraftEntry">保存到草稿</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="publishDialog.visible" title="发布翻译术语集草稿" width="540px">
      <el-form ref="publishFormRef" :model="publishDialog.form" :rules="publishRules" label-width="100px">
        <el-form-item label="发布说明" prop="release_note">
          <el-input v-model="publishDialog.form.release_note" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="publishDialog.form.make_default" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="publishDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="publishing" @click="publishDraft">发布</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="exportDialog.visible" title="导出翻译术语 CSV" width="760px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="术语集 ID">{{ exportDialog.manifest?.set_id || "-" }}</el-descriptions-item>
        <el-descriptions-item label="版本">{{ exportDialog.manifest?.version || "-" }}</el-descriptions-item>
        <el-descriptions-item label="语言对">{{ exportDialog.manifest?.language_pair || "-" }}</el-descriptions-item>
        <el-descriptions-item label="导出人">{{ exportDialog.manifest?.exported_by || "-" }}</el-descriptions-item>
      </el-descriptions>
      <el-input v-model="exportDialog.csv_text" type="textarea" :rows="14" class="mono export-text" readonly />
      <template #footer>
        <el-button @click="copyExport">复制 CSV</el-button>
        <el-button type="primary" @click="downloadExport">下载 CSV</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus";
import { CircleClose, Delete, Edit, Plus, Refresh } from "@element-plus/icons-vue";
import { useRoute, useRouter } from "vue-router";

import { translationTermSetsApi } from "@/api/translationTermSets";
import type {
  TranslationTermEntryResponse,
  TranslationTermProposalCompatibilityFindingResponse,
  TranslationTermProposalCompatibilityItemResponse,
  TranslationTermProposalCompatibilityResponse,
  TranslationTermSetDraftChangeRequest,
  TranslationTermSetDetailResponse,
  TranslationTermSetDiffEntryPayload,
  TranslationTermSetDiffEntryResponse,
  TranslationTermSetDiffResponse,
  TranslationTermSetDraftResponse,
  TranslationTermSetExportManifestResponse,
  TranslationTermSetImportReportResponse,
  TranslationTermSetListItemResponse,
  TranslationTermSetPreflightResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import RoleGate from "@/components/RoleGate.vue";
import { useAuthStore } from "@/stores/auth";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { formatDateTime } from "@/utils/format";

type FindingRow = {
  level: "error" | "warning";
  code: string;
  message: string;
  normalized_source_term: string | null;
};

type DedupeMode = "reject" | "keep_first";
type DiffKind = TranslationTermSetDiffEntryResponse["kind"];
type Compatibility = TranslationTermProposalCompatibilityItemResponse["compatibility"];
type TagType = "success" | "warning" | "info" | "danger";
type EntryDialogMode = "add" | "edit";
type TermStatus = "editing" | "publishable" | "deprecated";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const isAdmin = computed(() => auth.user?.role === "admin");
const sets = ref<TranslationTermSetListItemResponse[]>([]);
const selectedSetId = ref("");
const detail = ref<TranslationTermSetDetailResponse | null>(null);
const draft = ref<TranslationTermSetDraftResponse | null>(null);
const diff = ref<TranslationTermSetDiffResponse | null>(null);
const preflight = ref<TranslationTermSetPreflightResponse | null>(null);
const proposalCompatibility = ref<TranslationTermProposalCompatibilityResponse | null>(null);
const loading = ref(false);
const unavailable = ref(false);
const importing = ref(false);
const publishing = ref(false);
const entrySaving = ref(false);
const error = ref<ApiClientError | null>(null);
const lastImportReport = ref<TranslationTermSetImportReportResponse | null>(null);
const importFormRef = ref<FormInstance>();
const publishFormRef = ref<FormInstance>();
const entryFormRef = ref<FormInstance>();

const dedupeOptions = [
  { label: "reject", value: "reject" },
  { label: "keep_first", value: "keep_first" },
];

const termStatusOptions = [
  { label: "编辑中", value: "editing" },
  { label: "可发布", value: "publishable" },
  { label: "已废弃", value: "deprecated" },
];

const importDialog = reactive({
  visible: false,
  form: {
    csv_text: "",
    dedupe: "reject" as DedupeMode,
  },
});

const publishDialog = reactive({
  visible: false,
  form: {
    make_default: true,
    release_note: "",
  },
});

const entryDialog = reactive({
  visible: false,
  mode: "add" as EntryDialogMode,
  form: {
    source_term: "",
    target_term: "",
    recommended_translations: "",
    forbidden_translations: "",
    synonyms: "",
    case_sensitive: false,
    status: "publishable" as TermStatus,
    priority: 0,
    project: "",
    content_type: "",
    tags: "",
    maintainer: "",
    domain: "",
    category: "",
    note: "",
  },
});

const exportDialog = reactive({
  visible: false,
  manifest: null as TranslationTermSetExportManifestResponse | null,
  csv_text: "",
});

const importRules: FormRules = {
  csv_text: [{ required: true, message: "请粘贴 CSV 内容", trigger: "blur" }],
};

const publishRules: FormRules = {
  release_note: [{ required: true, message: "请填写发布说明", trigger: "blur" }],
};

const entryRules: FormRules = {
  source_term: [{ required: true, message: "请填写源术语", trigger: "blur" }],
  target_term: [{ required: true, message: "请填写推荐译法主值", trigger: "blur" }],
  status: [{ required: true, message: "请选择状态", trigger: "change" }],
};

const dedupeHints: Record<DedupeMode, string> = {
  reject: "默认策略。只要 CSV 存在重复规范化术语，后端会拒绝导入，草稿不会保存。",
  keep_first: "治理导入策略。保留第一条重复术语，丢弃后续重复行，并在导入报告中列出被丢弃的行。",
};

const dedupeHint = computed(() => dedupeHints[importDialog.form.dedupe]);
const entryDialogTitle = computed(() => (entryDialog.mode === "add" ? "新增草稿术语" : "编辑草稿术语"));

const proposalGovernanceContext = computed(() => {
  const proposalId = queryString("proposal_id");
  if (!proposalId) {
    return null;
  }
  return {
    proposalId,
    setId: queryString("set_id"),
    observedVersion: queryString("observed_version"),
    returnTab: queryString("return_tab") || "translation-review",
  };
});

const importReportSummary = computed(() => {
  const report = lastImportReport.value;
  if (!report) {
    return "";
  }
  return `总行数 ${report.total_rows}，导入 ${report.imported_rows} 行，重复 ${report.duplicate_rows} 行。`;
});

const validationFindings = computed<FindingRow[]>(() => {
  const report = draft.value?.validation;
  if (!report) {
    return [];
  }
  return [
    ...report.errors.map((item) => ({ ...item, level: "error" as const })),
    ...report.warnings.map((item) => ({ ...item, level: "warning" as const })),
  ];
});

const visibleDiffItems = computed(() => (
  diff.value?.items.filter((item) => item.kind !== "unchanged") ?? []
));

const targetProposalCompatibility = computed(() => {
  const proposalId = proposalGovernanceContext.value?.proposalId;
  if (!proposalId) {
    return null;
  }
  return proposalCompatibility.value?.items.find((item) => item.proposal_id === proposalId) || null;
});

const proposalCompatibilityNotice = computed(() => {
  const proposalId = proposalGovernanceContext.value?.proposalId;
  if (!proposalId || loading.value || targetProposalCompatibility.value) {
    return "";
  }
  return `建议 ${proposalId} 当前不在待审核兼容性列表中；可能已审核、已发布、已拒绝，或当前术语集不匹配。`;
});

// 根据 Translation Term Set 页面语境给 Admin 提供下一步处理建议。
const errorActionHint = computed(() => {
  const currentError = error.value;
  if (!currentError) {
    return "";
  }
  if (currentError.status === 503) {
    return "当前部署未启用 MySQL resource service，本页面不会保存任何翻译术语集变更。";
  }
  if (currentError.status === 404) {
    return "目标术语集或版本不存在。请刷新术语集列表后确认版本仍可用。";
  }
  if (currentError.status === 409 && currentError.code === "draft_snapshot_conflict") {
    return "草稿已被其他修改更新，本页面已刷新当前术语集。请重新确认后再保存。";
  }
  if (currentError.status === 400 && /CSV|重复|dedupe|language_pair|字段/.test(currentError.message)) {
    return "CSV 未导入，草稿未保存。请按错误信息修正 CSV，或在确认可丢弃重复行后改用“保留第一条”。";
  }
  if (currentError.status === 400 && /draft|术语|source_term|target_term|changes|新增|目标|状态/.test(currentError.message)) {
    return "草稿行级修改未保存。请按错误信息修正表单后重试。";
  }
  if (currentError.status === 400) {
    return "操作未执行。请确认目标版本是已发布状态，且请求参数符合当前 API 合同。";
  }
  return "";
});

// 记录页面级 API 错误，并在 503 时切到不可用状态。
function setPageError(caught: unknown): void {
  const normalized = normalizeApiError(caught);
  if (normalized.status === 503) {
    unavailable.value = true;
  }
  error.value = normalized;
}

function queryString(key: string): string {
  const value = route.query[key];
  if (Array.isArray(value)) {
    return typeof value[0] === "string" ? value[0] : "";
  }
  return typeof value === "string" ? value : "";
}

// 加载 set 列表和当前选中 set 的详情。
async function loadAll(): Promise<void> {
  loading.value = true;
  error.value = null;
  unavailable.value = false;
  try {
    const response = await translationTermSetsApi.list();
    sets.value = response.items;
    selectedSetId.value = queryString("set_id") || selectedSetId.value || sets.value[0]?.set_id || "";
    if (selectedSetId.value) {
      await loadSelectedSet();
    }
  } catch (caught) {
    setPageError(caught);
  } finally {
    loading.value = false;
  }
}

// 切换当前管理的 Translation Term Set，并清空旧 set 的导入报告。
async function selectSet(row: TranslationTermSetListItemResponse): Promise<void> {
  selectedSetId.value = row.set_id;
  lastImportReport.value = null;
  error.value = null;
  try {
    await loadSelectedSet();
  } catch (caught) {
    setPageError(caught);
  }
}

// 加载当前 set 的详情和 draft 预览。
async function loadSelectedSet(): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  const [
    detailResponse,
    draftResponse,
    diffResponse,
    preflightResponse,
    proposalCompatibilityResponse,
  ] = await Promise.all([
    translationTermSetsApi.get(selectedSetId.value),
    translationTermSetsApi.getDraft(selectedSetId.value),
    translationTermSetsApi.getDiff(selectedSetId.value),
    translationTermSetsApi.getPreflight(selectedSetId.value),
    translationTermSetsApi.getProposalCompatibility(selectedSetId.value),
  ]);
  detail.value = detailResponse;
  draft.value = draftResponse;
  diff.value = diffResponse;
  preflight.value = preflightResponse;
  proposalCompatibility.value = proposalCompatibilityResponse;
}

// 打开 CSV 导入对话框，并重置导入策略为安全的 reject。
function openImportDialog(): void {
  importDialog.form.csv_text = "";
  importDialog.form.dedupe = "reject";
  lastImportReport.value = null;
  importDialog.visible = true;
}

// 将 CSV 导入草稿；失败时保留后端错误并提示草稿未保存。
async function importCsv(): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  const valid = await importFormRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  importing.value = true;
  error.value = null;
  try {
    const response = await translationTermSetsApi.importCsv(selectedSetId.value, {
      csv_text: importDialog.form.csv_text,
      target: "draft",
      dedupe: importDialog.form.dedupe,
    });
    lastImportReport.value = response.import_report;
    ElMessage.success("CSV 已导入草稿。");
    await loadAll();
  } catch (caught) {
    setPageError(caught);
  } finally {
    importing.value = false;
  }
}

function optionalText(value: string): string | null {
  const normalized = value.trim();
  return normalized || null;
}

function splitListText(value: string): string[] {
  return Array.from(new Set(value.split(";").map((item) => item.trim()).filter(Boolean)));
}

function joinListText(values: string[] | null | undefined): string {
  return values?.join("; ") || "";
}

function listText(values: string[] | null | undefined): string {
  return values?.length ? values.join("; ") : "-";
}

function recommendedTranslationText(row: TranslationTermEntryResponse): string {
  return row.recommended_translations?.length ? listText(row.recommended_translations) : row.target_term;
}

function normalizeTermStatus(status: string): TermStatus {
  if (status === "editing" || status === "deprecated") {
    return status;
  }
  return status === "disabled" ? "deprecated" : "publishable";
}

function termStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    editing: "编辑中",
    publishable: "可发布",
    deprecated: "已废弃",
    active: "可发布",
    disabled: "已废弃",
  };
  return labels[status] || status;
}

function termStatusTag(status: string): TagType {
  if (status === "publishable" || status === "active") {
    return "success";
  }
  if (status === "editing") {
    return "warning";
  }
  return "info";
}

function resetEntryForm(): void {
  entryDialog.form.source_term = "";
  entryDialog.form.target_term = "";
  entryDialog.form.recommended_translations = "";
  entryDialog.form.forbidden_translations = "";
  entryDialog.form.synonyms = "";
  entryDialog.form.case_sensitive = false;
  entryDialog.form.status = "publishable";
  entryDialog.form.priority = 0;
  entryDialog.form.project = "";
  entryDialog.form.content_type = "";
  entryDialog.form.tags = "";
  entryDialog.form.maintainer = "";
  entryDialog.form.domain = "";
  entryDialog.form.category = "";
  entryDialog.form.note = "";
}

function openAddTermDialog(): void {
  resetEntryForm();
  entryDialog.mode = "add";
  entryDialog.visible = true;
}

function openEditTermDialog(row: TranslationTermEntryResponse): void {
  entryDialog.mode = "edit";
  entryDialog.form.source_term = row.source_term;
  entryDialog.form.target_term = row.target_term;
  entryDialog.form.recommended_translations = joinListText(row.recommended_translations);
  entryDialog.form.forbidden_translations = joinListText(row.forbidden_translations);
  entryDialog.form.synonyms = joinListText(row.synonyms);
  entryDialog.form.case_sensitive = row.case_sensitive;
  entryDialog.form.status = normalizeTermStatus(row.status);
  entryDialog.form.priority = row.priority;
  entryDialog.form.project = row.project || "";
  entryDialog.form.content_type = row.content_type || "";
  entryDialog.form.tags = joinListText(row.tags);
  entryDialog.form.maintainer = row.maintainer || "";
  entryDialog.form.domain = row.domain || "";
  entryDialog.form.category = row.category || "";
  entryDialog.form.note = row.note || "";
  entryDialog.visible = true;
}

async function applyDraftEntryChanges(changes: TranslationTermSetDraftChangeRequest[], reason: string): Promise<void> {
  if (!selectedSetId.value || !draft.value?.snapshot_hash) {
    return;
  }
  await translationTermSetsApi.applyDraftChanges(selectedSetId.value, {
    expected_snapshot_hash: draft.value.snapshot_hash,
    reason,
    changes,
  });
  await loadSelectedSet();
}

async function handleDraftChangeError(caught: unknown): Promise<void> {
  const normalized = normalizeApiError(caught);
  if (normalized.status === 503) {
    unavailable.value = true;
  }
  error.value = normalized;
  if (normalized.status === 409 && normalized.code === "draft_snapshot_conflict") {
    ElMessage.warning("草稿已被其他修改更新，已刷新当前术语集。");
    try {
      await loadSelectedSet();
    } catch (refreshError) {
      setPageError(refreshError);
    }
  }
}

async function submitDraftEntry(): Promise<void> {
  const valid = await entryFormRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  entrySaving.value = true;
  error.value = null;
  const change: TranslationTermSetDraftChangeRequest = {
    action: entryDialog.mode === "add" ? "add" : "update",
    source_term: entryDialog.form.source_term,
    target_term: entryDialog.form.target_term,
    recommended_translations: splitListText(entryDialog.form.recommended_translations),
    forbidden_translations: splitListText(entryDialog.form.forbidden_translations),
    synonyms: splitListText(entryDialog.form.synonyms),
    case_sensitive: entryDialog.form.case_sensitive,
    status: entryDialog.form.status,
    priority: entryDialog.form.priority,
    project: optionalText(entryDialog.form.project),
    content_type: optionalText(entryDialog.form.content_type),
    tags: splitListText(entryDialog.form.tags),
    maintainer: optionalText(entryDialog.form.maintainer),
    domain: optionalText(entryDialog.form.domain),
    category: optionalText(entryDialog.form.category),
    note: entryDialog.form.note.trim(),
  };
  try {
    await applyDraftEntryChanges([change], `${change.action} ${change.source_term}`);
    ElMessage.success("草稿术语已保存。");
    entryDialog.visible = false;
  } catch (caught) {
    await handleDraftChangeError(caught);
  } finally {
    entrySaving.value = false;
  }
}

async function disableDraftEntry(row: TranslationTermEntryResponse): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `将 ${row.source_term} 标记为已废弃。术语仍保留在草稿中，但不会进入治理包发布。`,
      "废弃草稿术语",
      {
        confirmButtonText: "废弃",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
  } catch {
    return;
  }
  error.value = null;
  try {
    await applyDraftEntryChanges(
      [
        {
          action: "update",
          source_term: row.source_term,
          status: "deprecated",
        },
      ],
      `deprecate ${row.source_term}`,
    );
    ElMessage.success("草稿术语已标记为废弃。");
  } catch (caught) {
    await handleDraftChangeError(caught);
  }
}

async function deleteDraftEntry(row: TranslationTermEntryResponse): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `从当前草稿移除 ${row.source_term}。此操作不会删除任何已发布历史，只有发布草稿后才会影响后续新任务。`,
      "删除草稿术语",
      {
        confirmButtonText: "删除",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
  } catch {
    return;
  }
  error.value = null;
  try {
    await applyDraftEntryChanges(
      [
        {
          action: "delete",
          source_term: row.source_term,
        },
      ],
      `delete ${row.source_term}`,
    );
    ElMessage.success("草稿术语已删除。");
  } catch (caught) {
    await handleDraftChangeError(caught);
  }
}

// 打开发布草稿对话框，要求填写发布说明。
function openPublishDialog(): void {
  publishDialog.form.release_note = "";
  publishDialog.form.make_default = true;
  publishDialog.visible = true;
}

// 发布当前草稿，并按开关决定是否设为默认版本。
async function publishDraft(): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  const valid = await publishFormRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  publishing.value = true;
  error.value = null;
  try {
    await translationTermSetsApi.publish(selectedSetId.value, {
      make_default: publishDialog.form.make_default,
      release_note: publishDialog.form.release_note,
    });
    ElMessage.success("翻译术语集草稿已发布。");
    publishDialog.visible = false;
    await loadAll();
  } catch (caught) {
    setPageError(caught);
  } finally {
    publishing.value = false;
  }
}

// 导出默认版本或指定 published version 的 CSV。
async function exportVersion(version: string | null): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  error.value = null;
  try {
    const response = await translationTermSetsApi.exportCsv(selectedSetId.value, version);
    exportDialog.manifest = response.manifest;
    exportDialog.csv_text = response.csv_text;
    exportDialog.visible = true;
  } catch (caught) {
    setPageError(caught);
  }
}

// 将导出的 CSV 正文复制到剪贴板。
async function copyExport(): Promise<void> {
  if (!exportDialog.csv_text) {
    return;
  }
  await navigator.clipboard.writeText(exportDialog.csv_text);
  ElMessage.success("CSV 已复制。");
}

// 在浏览器侧下载导出的 CSV，不触发后端文件删除或文件管理。
function downloadExport(): void {
  if (!exportDialog.csv_text || !exportDialog.manifest) {
    return;
  }
  const blob = new Blob([exportDialog.csv_text], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${exportDialog.manifest.set_id}-${exportDialog.manifest.version}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

// 将 diff payload 压缩为页面内可扫描 JSON。
function formatDiffPayload(payload: TranslationTermSetDiffEntryPayload | null): string {
  return payload ? JSON.stringify(payload, null, 2) : "-";
}

// 将 diff kind 映射为表格标签样式。
function diffKindTag(kind: DiffKind): TagType {
  if (kind === "added") {
    return "success";
  }
  if (kind === "removed") {
    return "danger";
  }
  if (kind === "changed") {
    return "warning";
  }
  return "info";
}

function diffKindLabel(kind: DiffKind): string {
  const labels: Record<DiffKind, string> = {
    added: "新增",
    removed: "移除",
    changed: "变更",
    unchanged: "未变",
  };
  return labels[kind] || kind;
}

function validationLevelLabel(level: string): string {
  const labels: Record<string, string> = {
    error: "错误",
    warning: "告警",
  };
  return labels[level] || level;
}

// 将 proposal compatibility 映射为表格标签样式。
function compatibilityTag(compatibility: Compatibility): TagType {
  if (compatibility === "compatible") {
    return "success";
  }
  if (compatibility === "warning") {
    return "warning";
  }
  return "danger";
}

function compatibilityLabel(compatibility: Compatibility): string {
  const labels: Record<Compatibility, string> = {
    compatible: "兼容",
    warning: "有告警",
    conflict: "有冲突",
  };
  return labels[compatibility] || compatibility;
}

// 汇总 finding codes，避免在列表中渲染大段冲突 payload。
function findingCodes(findings: TranslationTermProposalCompatibilityFindingResponse[]): string {
  return findings.length ? findings.map((item) => item.code).join(", ") : "-";
}

// 高亮从 proposal 审核页跳转而来的 compatibility 行，找不到时由页面提示说明。
function proposalCompatibilityRowClassName({ row }: { row: TranslationTermProposalCompatibilityItemResponse }): string {
  return row.proposal_id === proposalGovernanceContext.value?.proposalId ? "is-selected-row" : "";
}

// 返回 Translation proposal 审核页，保持 proposal_id deep-link。
function returnToProposalReview(): void {
  const context = proposalGovernanceContext.value;
  if (!context) {
    return;
  }
  void router.push({
    name: "term-proposals",
    query: {
      tab: context.returnTab,
      proposal_id: context.proposalId,
    },
  });
}

// 切换默认指针；只影响后续默认绑定，不改已有 job 快照。
async function setDefault(version: string): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  try {
    await ElMessageBox.confirm(
      "将该已发布版本切换为默认翻译术语集版本。此操作只影响后续使用默认配置的新任务；已创建任务的资源快照不会改变。",
      `设默认 ${version}`,
      {
        confirmButtonText: "设默认",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
  } catch {
    return;
  }
  error.value = null;
  try {
    await translationTermSetsApi.setDefault(selectedSetId.value, version);
    ElMessage.success("默认翻译术语集已切换。");
    await loadAll();
  } catch (caught) {
    setPageError(caught);
  }
}

// 回滚只切默认指针，不生成新版本、不删除历史版本、不改已有 job 快照。
async function rollback(version: string): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  try {
    await ElMessageBox.confirm(
      "回滚只会把默认版本指针切回该已发布版本，不会生成新版本，不会删除或修改历史版本，也不会改变已创建任务的资源快照。",
      `回滚 ${version}`,
      {
        confirmButtonText: "回滚",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
  } catch {
    return;
  }
  error.value = null;
  try {
    await translationTermSetsApi.rollback(selectedSetId.value, { version });
    ElMessage.success("已完成回滚。");
    await loadAll();
  } catch (caught) {
    setPageError(caught);
  }
}

watch(() => route.fullPath, () => {
  void loadAll();
}, { immediate: true });
</script>

<style scoped lang="scss">
.translation-term-set-page {
  display: grid;
  align-content: start;
  grid-auto-rows: max-content;
  gap: var(--app-space-4);
}

.term-set-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(340px, 0.9fr);
  gap: var(--app-space-4);
}

.summary-list {
  display: grid;
  gap: var(--app-space-2);
  margin: 0 0 var(--app-space-4);
}

.summary-list div {
  display: grid;
  grid-template-columns: 140px minmax(0, 1fr);
  gap: var(--app-space-2);
}

.summary-list dt {
  color: var(--app-color-text-muted);
}

.summary-list dd {
  min-width: 0;
  margin: 0;
  color: var(--app-color-text);
  overflow-wrap: anywhere;
}

.term-set-draft-header {
  align-items: flex-start;
  flex-wrap: wrap;
}

.term-set-draft-header > div {
  flex: 1 1 260px;
  min-width: 0;
}

.draft-hash-tag {
  flex: 0 1 min(100%, 280px);
  max-width: 100%;
}

.draft-hash-tag :deep(.el-tag__content) {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.context-alert {
  margin-bottom: 4px;
}

.context-summary {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2);
  align-items: center;
}

.governance-context-alert {
  border-left: 4px solid var(--app-color-primary);
}

.governance-summary-grid {
  margin-bottom: var(--app-space-4);
}

.summary-metric {
  min-width: 0;
}

.summary-metric span {
  display: block;
  font-size: 12px;
}

.summary-metric strong {
  display: block;
  margin-top: 4px;
}

.blocking-list {
  margin: 0;
  padding-left: 18px;
}

.tag-stack {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.table-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.diff-payload {
  max-height: 140px;
  margin: 0;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.form-help {
  flex-basis: 100%;
  margin: 6px 0 0;
  color: var(--app-color-text-muted);
  font-size: 13px;
  line-height: 1.5;
}

.import-report-table {
  width: 100%;
}

.dialog-alert {
  margin-top: 12px;
}

.export-text {
  margin-top: 14px;
}

.entry-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 16px;
}

.entry-form-grid :deep(.el-form-item:nth-child(8)) {
  grid-column: 1 / -1;
}

:deep(.el-table__row.is-selected-row td) {
  background: var(--app-color-primary-soft);
}

@media (max-width: 1040px) {
  .term-set-grid {
    grid-template-columns: 1fr;
  }

  .governance-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .entry-form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
