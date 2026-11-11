// 保留策略治理 owner：策略列表、影响预览、draft 编辑对话框与需要 reason 的治理动作。
import { reactive, ref, type Ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { filesApi } from "@/api/files";
import type {
  FileRetentionPolicyCreateRequest,
  FileRetentionPolicyImpactResponse,
  FileRetentionPolicyResponse,
  FileRetentionPolicyScopeType,
} from "@/api/types";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

export function useRetentionPolicy(
  error: Ref<ApiClientError | null>,
) {
  const policyList = ref<Awaited<ReturnType<typeof filesApi.listRetentionPolicies>> | null>(null);
  const policyImpact = ref<FileRetentionPolicyImpactResponse | null>(null);
  const policyLoading = ref(false);
  const policySaving = ref(false);

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

  return {
    policyList,
    policyImpact,
    policyLoading,
    policySaving,
    policyDialog,
    loadPolicies,
    openCreatePolicyDialog,
    openEditPolicyDialog,
    savePolicy,
    previewPolicyImpact,
    publishPolicy,
    setDefaultPolicy,
    disablePolicy,
    runPolicyReasonAction,
  };
}

export type RetentionPolicy = ReturnType<typeof useRetentionPolicy>;
