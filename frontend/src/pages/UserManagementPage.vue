<!-- File: frontend/src/pages/UserManagementPage.vue -->
<!-- Purpose: Render the Admin-only internal user management workbench. -->
<template>
  <main class="user-management-page app-page" aria-labelledby="user-management-title">
    <section class="page-heading app-page-header app-page-shell">
      <div>
        <p class="page-kicker">Users</p>
        <h1 id="user-management-title" class="page-title">用户管理</h1>
        <p class="page-description">管理内部账号、角色、启停状态和密码重置。</p>
      </div>
      <div class="heading-actions">
        <el-button :icon="Refresh" :loading="loading" @click="loadUsers">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreateDialog">新建用户</el-button>
      </div>
    </section>

    <ApiErrorAlert class="app-page-shell" :error="error" />

    <section class="filter-section app-filter-panel app-page-shell" aria-label="用户筛选">
      <el-form class="filter-form" label-position="top">
        <el-form-item label="搜索">
          <el-input v-model="filters.keyword" clearable placeholder="用户名 / 显示名 / 用户 ID" @keyup.enter="applyFilters" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="filters.role" clearable placeholder="全部角色">
            <el-option label="管理员" value="admin" />
            <el-option label="操作员" value="operator" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部状态">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="disabled" />
          </el-select>
        </el-form-item>
      </el-form>
      <div class="filter-actions">
        <el-button @click="resetFilters">重置</el-button>
        <el-button type="primary" :icon="Search" @click="applyFilters">查询</el-button>
      </div>
    </section>

    <section class="user-table-section app-filter-panel app-table-card app-page-shell" aria-label="内部用户列表">
      <div class="section-header">
        <div>
          <h2 class="section-title">内部用户</h2>
          <p class="section-subtitle">
            共 {{ total }} 个账号<span v-if="loadedAt"> · 更新于 {{ formatDateTime(loadedAt) }}</span>
          </p>
        </div>
      </div>

      <el-table v-loading="loading" :data="users" empty-text="暂无用户" table-layout="fixed" class="user-table">
        <el-table-column label="用户名" min-width="180">
          <template #default="{ row }">
            <div class="identity-cell">
              <strong>{{ row.username }}</strong>
              <span class="mono muted">{{ row.id }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="display_name" label="显示名" min-width="160">
          <template #default="{ row }">{{ row.display_name || "-" }}</template>
        </el-table-column>
        <el-table-column prop="role" label="角色" min-width="120">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" :type="row.role === 'admin' ? 'danger' : 'info'">
              {{ roleLabel(row.role) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" min-width="110">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" :type="row.status === 'active' ? 'success' : 'warning'">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" min-width="180">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" fixed="right" width="260">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button size="small" :icon="Edit" @click="openEditDialog(row)">编辑</el-button>
              <el-button size="small" :icon="Key" @click="openResetPasswordDialog(row)">重置密码</el-button>
              <el-button
                size="small"
                :type="row.status === 'active' ? 'warning' : 'success'"
                plain
                @click="toggleUserStatus(row)"
              >
                {{ row.status === "active" ? "停用" : "启用" }}
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="createDialogVisible" title="新建用户" width="min(560px, 96vw)">
      <el-form label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="createForm.username" autocomplete="off" />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="createForm.display_name" autocomplete="off" />
        </el-form-item>
        <el-form-item label="角色">
          <el-segmented v-model="createForm.role" :options="roleOptions" />
        </el-form-item>
        <el-form-item label="状态">
          <el-segmented v-model="createForm.status" :options="statusOptions" />
        </el-form-item>
        <el-form-item label="初始密码">
          <el-input v-model="createForm.initial_password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="createForm.confirm_password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editDialogVisible" title="编辑用户" width="min(520px, 96vw)">
      <el-form v-if="selectedUser" label-position="top">
        <el-form-item label="用户名">
          <el-input :model-value="selectedUser.username" disabled />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="editForm.display_name" autocomplete="off" />
        </el-form-item>
        <el-form-item label="角色">
          <el-segmented v-model="editForm.role" :options="roleOptions" />
        </el-form-item>
        <el-form-item label="状态">
          <el-segmented v-model="editForm.status" :options="statusOptions" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetPasswordDialogVisible" title="重置密码" width="min(520px, 96vw)">
      <el-alert
        v-if="selectedUser"
        type="warning"
        show-icon
        :closable="false"
        :title="`将重置 ${selectedUser.username} 的登录密码，旧 token 会立即失效。`"
      />
      <el-form class="dialog-form" label-position="top">
        <el-form-item label="临时密码">
          <el-input v-model="resetPasswordForm.new_password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="resetPasswordForm.confirm_password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetPasswordDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitResetPassword">确认重置</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { Edit, Key, Plus, Refresh, Search } from "@element-plus/icons-vue";

import { internalUsersApi } from "@/api/users";
import type {
  InternalUserCreateRequest,
  InternalUserResponse,
  InternalUserRole,
  InternalUserStatus,
  InternalUserUpdateRequest,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { formatDateTime } from "@/utils/format";

type UserFilters = {
  keyword: string;
  role: InternalUserRole | "";
  status: InternalUserStatus | "";
};

type CreateForm = InternalUserCreateRequest & {
  confirm_password: string;
};

type EditForm = Required<Pick<InternalUserUpdateRequest, "display_name" | "role" | "status">>;

type ResetPasswordForm = {
  new_password: string;
  confirm_password: string;
};

const roleOptions = [
  { label: "管理员", value: "admin" },
  { label: "操作员", value: "operator" },
];
const statusOptions = [
  { label: "启用", value: "active" },
  { label: "停用", value: "disabled" },
];

const filters = reactive<UserFilters>({
  keyword: "",
  role: "",
  status: "",
});
const users = ref<InternalUserResponse[]>([]);
const total = ref(0);
const loadedAt = ref<string | null>(null);
const loading = ref(false);
const saving = ref(false);
const error = ref<ApiClientError | null>(null);
const createDialogVisible = ref(false);
const editDialogVisible = ref(false);
const resetPasswordDialogVisible = ref(false);
const selectedUser = ref<InternalUserResponse | null>(null);

const createForm = reactive<CreateForm>({
  username: "",
  display_name: "",
  role: "operator",
  status: "active",
  initial_password: "",
  confirm_password: "",
});
const editForm = reactive<EditForm>({
  display_name: "",
  role: "operator",
  status: "active",
});
const resetPasswordForm = reactive<ResetPasswordForm>({
  new_password: "",
  confirm_password: "",
});

async function loadUsers(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const response = await internalUsersApi.list({
      keyword: filters.keyword.trim() || undefined,
      role: filters.role,
      status: filters.status,
    });
    users.value = response.items;
    total.value = response.total;
    loadedAt.value = new Date().toISOString();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

function applyFilters(): void {
  void loadUsers();
}

function resetFilters(): void {
  filters.keyword = "";
  filters.role = "";
  filters.status = "";
  void loadUsers();
}

function openCreateDialog(): void {
  createForm.username = "";
  createForm.display_name = "";
  createForm.role = "operator";
  createForm.status = "active";
  createForm.initial_password = "";
  createForm.confirm_password = "";
  createDialogVisible.value = true;
}

async function submitCreate(): Promise<void> {
  if (createForm.initial_password !== createForm.confirm_password) {
    ElMessage.error("两次输入的新密码不一致。");
    return;
  }
  saving.value = true;
  try {
    await internalUsersApi.create({
      username: createForm.username,
      display_name: createForm.display_name || null,
      role: createForm.role,
      status: createForm.status,
      initial_password: createForm.initial_password,
    });
    ElMessage.success("用户已创建。");
    createDialogVisible.value = false;
    await loadUsers();
  } catch (caught) {
    ElMessage.error(normalizeApiError(caught).message);
  } finally {
    saving.value = false;
  }
}

function openEditDialog(user: InternalUserResponse): void {
  selectedUser.value = user;
  editForm.display_name = user.display_name || "";
  editForm.role = user.role;
  editForm.status = user.status;
  editDialogVisible.value = true;
}

async function submitEdit(): Promise<void> {
  if (!selectedUser.value) {
    return;
  }
  saving.value = true;
  try {
    await internalUsersApi.update(selectedUser.value.id, {
      display_name: editForm.display_name || null,
      role: editForm.role,
      status: editForm.status,
    });
    ElMessage.success("用户信息已保存。");
    editDialogVisible.value = false;
    await loadUsers();
  } catch (caught) {
    ElMessage.error(normalizeApiError(caught).message);
  } finally {
    saving.value = false;
  }
}

async function toggleUserStatus(user: InternalUserResponse): Promise<void> {
  saving.value = true;
  try {
    await internalUsersApi.update(user.id, {
      status: user.status === "active" ? "disabled" : "active",
    });
    ElMessage.success(user.status === "active" ? "用户已停用。" : "用户已启用。");
    await loadUsers();
  } catch (caught) {
    ElMessage.error(normalizeApiError(caught).message);
  } finally {
    saving.value = false;
  }
}

function openResetPasswordDialog(user: InternalUserResponse): void {
  selectedUser.value = user;
  resetPasswordForm.new_password = "";
  resetPasswordForm.confirm_password = "";
  resetPasswordDialogVisible.value = true;
}

async function submitResetPassword(): Promise<void> {
  if (!selectedUser.value) {
    return;
  }
  if (resetPasswordForm.new_password !== resetPasswordForm.confirm_password) {
    ElMessage.error("两次输入的新密码不一致。");
    return;
  }
  saving.value = true;
  try {
    await internalUsersApi.resetPassword(selectedUser.value.id, {
      new_password: resetPasswordForm.new_password,
    });
    ElMessage.success("密码已重置。");
    resetPasswordDialogVisible.value = false;
    await loadUsers();
  } catch (caught) {
    ElMessage.error(normalizeApiError(caught).message);
  } finally {
    saving.value = false;
  }
}

function roleLabel(role: InternalUserRole): string {
  return role === "admin" ? "管理员" : "操作员";
}

function statusLabel(status: InternalUserStatus): string {
  return status === "active" ? "启用" : "停用";
}

onMounted(() => {
  void loadUsers();
});
</script>

<style scoped lang="scss">
.user-management-page {
  display: grid;
  align-content: start;
  grid-auto-rows: max-content;
  gap: var(--app-space-4);
}

.page-heading,
.section-header,
.heading-actions,
.filter-actions,
.row-actions {
  display: flex;
  align-items: center;
}

.page-heading,
.section-header {
  justify-content: space-between;
  gap: var(--app-space-4);
}

.heading-actions,
.filter-actions,
.row-actions {
  justify-content: flex-end;
  gap: var(--app-space-2);
}

.filter-form {
  display: grid;
  grid-template-columns: minmax(240px, 2fr) minmax(160px, 1fr) minmax(160px, 1fr);
  gap: var(--app-space-3);
}

.user-table-section {
  overflow-x: auto;
}

.user-table {
  min-width: 920px;
}

.identity-cell {
  display: grid;
  gap: 3px;
}

.mono {
  font-family: var(--app-font-mono);
}

.muted {
  color: var(--app-color-text-muted);
}

.dialog-form {
  margin-top: var(--app-space-4);
}

@media (max-width: 780px) {
  .page-heading,
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .heading-actions,
  .filter-actions {
    justify-content: flex-start;
    width: 100%;
  }

  .filter-form {
    grid-template-columns: 1fr;
  }
}
</style>
