<!-- frontend/src/pages/LoginPage.vue: Internal account login page for operators and admins. -->
<template>
  <main class="login-page" aria-labelledby="login-title">
    <div class="login-actions" aria-label="显示设置">
      <AppThemeToggle />
    </div>
    <section class="login-shell">
      <div class="login-copy">
        <div class="brand-row">
          <span class="brand-mark" aria-hidden="true">
            <el-icon><DocumentChecked /></el-icon>
          </span>
          <span class="brand-name">md2word 工作台</span>
        </div>
        <p class="login-eyebrow">内部文档转换入口</p>
        <h1 id="login-title">md2word 内部工作台</h1>
        <p class="login-lede">面向内部运营与交付团队的文档处理工作台，覆盖 PDF 上传、DOCX 交付、翻译 QA 和审计证据。</p>

        <div class="workflow-panel" aria-label="PDF 到 Word 的处理流程">
          <div class="document-preview" aria-hidden="true">
            <span class="doc-card doc-card-source">PDF</span>
            <span class="convert-line"></span>
            <span class="doc-card doc-card-target">DOCX</span>
          </div>

          <ol class="flow-list">
            <li>
              <span>01</span>
              <strong>上传</strong>
              <em>文件进入队列</em>
            </li>
            <li>
              <span>02</span>
              <strong>转换</strong>
              <em>任务进度同步</em>
            </li>
            <li>
              <span>03</span>
              <strong>交付</strong>
              <em>结果可追溯</em>
            </li>
          </ol>
          <div class="assurance-strip" aria-label="工作台治理线索">
            <span>队列</span>
            <span>QA 闸口</span>
            <span>审计链路</span>
            <span>配置</span>
          </div>
        </div>

        <div class="signal-grid" aria-label="工作台能力状态">
          <div class="signal-item">
            <span>转换队列</span>
            <strong>实时</strong>
          </div>
          <div class="signal-item">
            <span>QA 证据</span>
            <strong>可追溯</strong>
          </div>
          <div class="signal-item">
            <span>审计链路</span>
            <strong>留痕</strong>
          </div>
        </div>
      </div>

      <el-card class="login-card card-flat" shadow="never">
        <div class="login-card-header">
          <span>安全访问</span>
          <h2>账号登录</h2>
          <p>使用内部账号进入转换工作台。</p>
        </div>
        <ApiErrorAlert :error="error" />
        <el-alert
          v-if="authNotice"
          class="auth-notice"
          :type="authNotice.type"
          :closable="false"
          show-icon
          :title="authNotice.title"
        />
        <el-form
          ref="formRef"
          class="login-form"
          :model="form"
          :rules="rules"
          label-position="top"
          @keyup.enter="submit"
        >
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model.trim="form.username"
              autocomplete="username"
              autofocus
              placeholder="请输入用户名"
              :prefix-icon="User"
              size="large"
            />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              autocomplete="current-password"
              placeholder="请输入密码"
              :prefix-icon="Lock"
              show-password
              size="large"
            />
          </el-form-item>
          <el-button
            class="login-button"
            type="primary"
            :icon="ArrowRight"
            :loading="submitting"
            size="large"
            @click="submit"
          >
            登录工作台
          </el-button>
        </el-form>
        <p class="security-note">
          <el-icon><Lock /></el-icon>
          <span>登录信息仅用于内部身份校验。</span>
        </p>
      </el-card>
    </section>
  </main>
</template>

<script setup lang="ts">
import { ArrowRight, DocumentChecked, Lock, User } from "@element-plus/icons-vue";
import { computed, reactive, ref } from "vue";
import type { FormInstance, FormRules } from "element-plus";
import { useRoute, useRouter } from "vue-router";

import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import AppThemeToggle from "@/components/AppThemeToggle.vue";
import { getDefaultProtectedRoute } from "@/navigation/appShell";
import { useAuthStore } from "@/stores/auth";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const formRef = ref<FormInstance>();
const submitting = ref(false);
const error = ref<ApiClientError | null>(null);

const form = reactive({
  username: "",
  password: "",
});

const rules: FormRules<typeof form> = {
  username: [{ required: true, message: "请输入用户名。", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码。", trigger: "blur" }],
};

const authNotice = computed(() => {
  const reason = route.query.auth;
  if (reason === "password_changed") {
    return {
      type: "success" as const,
      title: "密码已修改，请使用新密码重新登录。",
    };
  }
  if (reason === "token_expired") {
    return {
      type: "warning" as const,
      title: "登录已过期，请重新登录。",
    };
  }
  if (reason === "invalid_token") {
    return {
      type: "warning" as const,
      title: "登录状态无效，请重新登录。",
    };
  }
  return null;
});

async function submit(): Promise<void> {
  if (submitting.value) {
    return;
  }
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }

  submitting.value = true;
  error.value = null;
  try {
    await auth.login({ username: form.username, password: form.password });
    const redirect = typeof route.query.redirect === "string"
      ? route.query.redirect
      : getDefaultProtectedRoute({
          role: auth.user?.role ?? null,
          roles: auth.user?.roles ?? [],
          permissions: auth.user?.permissions ?? [],
        });
    await router.push(redirect);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped lang="scss">
.login-page {
  --login-bg: var(--app-color-bg);
  --login-bg-secondary: var(--app-color-surface-muted);
  --login-text: var(--app-color-text);
  --login-muted: var(--app-color-text-muted);
  --login-panel: var(--app-color-surface);
  --login-panel-strong: var(--app-color-surface-muted);
  --login-border: var(--app-color-border);
  --login-shadow: var(--app-shadow-panel);
  --login-accent: var(--app-color-primary);
  --login-accent-strong: var(--app-color-primary-hover);
  --login-sky: var(--app-color-accent-cyan);
  --login-emerald: var(--app-color-accent-emerald);
  --login-amber: var(--app-color-warning);
  --login-input-bg: var(--app-color-surface);
  --login-input-text: var(--app-color-text);
  --login-input-placeholder: var(--app-color-text-faint);

  position: relative;
  overflow: hidden;
  display: grid;
  min-height: 100svh;
  place-items: center;
  padding: 48px 24px;
  background:
    var(--app-gradient-ambient),
    linear-gradient(var(--app-color-grid-line) 1px, transparent 1px),
    linear-gradient(90deg, var(--app-color-grid-line) 1px, transparent 1px),
    var(--app-gradient-page);
  background-size:
    auto,
    48px 48px,
    48px 48px,
    auto;
  color: var(--login-text);
  color-scheme: var(--app-color-scheme);
}

.login-page::before,
.login-page::after {
  position: absolute;
  z-index: 0;
  content: "";
  pointer-events: none;
}

.login-page::before {
  display: none;
}

.login-actions {
  position: absolute;
  top: 18px;
  right: 18px;
  z-index: 2;
}

.login-page::after {
  inset: 0;
  background:
    linear-gradient(90deg, transparent 0%, var(--app-color-ambient-primary) 48%, transparent 48%),
    linear-gradient(180deg, transparent 0%, var(--app-color-ambient-amber) 64%, transparent 64%);
  background-size:
    260px 100%,
    100% 180px;
  mask-image: linear-gradient(180deg, #000 0%, transparent 78%);
  opacity: 0.28;
}

.login-shell {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 410px);
  gap: clamp(24px, 5vw, 56px);
  width: min(1080px, 100%);
  align-items: center;
}

.login-copy {
  animation: fade-up var(--app-motion-base) var(--app-ease-out) both;
}

.brand-row {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 22px;
  padding: 8px 12px 8px 8px;
  border: 1px solid var(--login-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-glass-strong);
  box-shadow: var(--app-shadow-subtle);
  backdrop-filter: var(--app-backdrop-panel);
  -webkit-backdrop-filter: var(--app-backdrop-panel);
}

.brand-mark {
  display: inline-grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: var(--app-radius-md);
  background: linear-gradient(135deg, var(--login-accent), var(--login-sky) 58%, var(--login-emerald));
  color: #ffffff;
  font-size: 18px;
}

.brand-name {
  color: var(--login-text);
  font-size: 14px;
  font-weight: 700;
}

.login-eyebrow,
.login-card-header span {
  margin: 0 0 12px;
  color: var(--login-accent-strong);
  font-size: 13px;
  font-weight: 700;
}

.login-copy h1 {
  max-width: 620px;
  margin: 0 0 14px;
  color: var(--login-text);
  font-size: clamp(32px, 4vw, 44px);
  font-weight: 760;
  line-height: 1.14;
}

.login-lede {
  max-width: 560px;
  margin: 0 0 24px;
  color: var(--login-muted);
  font-size: 15px;
  line-height: 1.75;
}

.workflow-panel {
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: minmax(180px, 240px) minmax(0, 1fr);
  gap: 20px;
  width: min(640px, 100%);
  margin-bottom: 16px;
  padding: 18px;
  border: 1px solid var(--app-color-primary-border);
  border-radius: var(--app-radius-md);
  background:
    linear-gradient(var(--app-color-grid-line) 1px, transparent 1px),
    linear-gradient(90deg, var(--app-color-grid-line) 1px, transparent 1px),
    var(--app-gradient-glass);
  background-size:
    24px 24px,
    24px 24px,
    auto;
  box-shadow: var(--app-shadow-panel);
  backdrop-filter: var(--app-backdrop-panel);
  -webkit-backdrop-filter: var(--app-backdrop-panel);
  animation: fade-up var(--app-motion-base) var(--app-ease-out) 60ms both;
}

.workflow-panel::before {
  position: absolute;
  inset: 0 0 auto;
  height: 3px;
  content: "";
  background: linear-gradient(90deg, var(--login-accent), var(--login-sky) 62%, var(--login-emerald));
}

.document-preview {
  display: grid;
  grid-template-columns: 1fr 44px 1fr;
  gap: 8px;
  align-items: center;
  min-height: 122px;
}

.doc-card {
  position: relative;
  display: grid;
  min-height: 104px;
  place-items: center;
  border: 1px solid var(--app-color-primary-border);
  border-radius: var(--app-radius-sm);
  background: linear-gradient(180deg, var(--app-color-glass-strong), var(--login-panel-strong));
  color: var(--login-accent-strong);
  font-size: 16px;
  font-weight: 800;
  box-shadow: var(--app-shadow-subtle);
  transform-origin: center;
  animation: doc-enter var(--app-motion-slow) var(--app-ease-out) both;
}

.doc-card::before {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 24px;
  height: 18px;
  border-top: 2px solid currentColor;
  border-bottom: 2px solid currentColor;
  content: "";
  opacity: 0.22;
}

.doc-card-source {
  animation-delay: 160ms;
}

.doc-card-target {
  border-color: var(--app-color-accent-cyan-border);
  color: var(--login-emerald);
  animation-delay: 220ms;
}

.convert-line {
  position: relative;
  display: block;
  height: 2px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--app-color-primary-border);
}

.convert-line::after {
  position: absolute;
  inset: 0;
  content: "";
  border-radius: inherit;
  background: linear-gradient(90deg, var(--login-accent), var(--login-sky), var(--login-emerald));
  transform: translateX(-100%);
  animation: line-fill var(--app-motion-slow) var(--app-ease-out) 220ms both;
}

.assurance-strip {
  display: flex;
  flex-wrap: wrap;
  grid-column: 1 / -1;
  gap: 8px;
}

.assurance-strip span {
  min-height: 26px;
  padding: 6px 10px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-pill);
  background: var(--app-color-glass);
  color: var(--login-accent-strong);
  font-size: 11px;
  font-weight: 800;
}

.assurance-strip span:nth-child(2) {
  color: var(--login-emerald);
}

.assurance-strip span:nth-child(3) {
  color: var(--login-amber);
}

.flow-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.flow-list li {
  display: grid;
  grid-template-columns: 38px minmax(48px, 64px) minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  min-height: 34px;
}

.flow-list span {
  color: var(--login-accent);
  font-size: 12px;
  font-weight: 800;
}

.flow-list strong {
  color: var(--login-text);
  font-size: 14px;
}

.flow-list em {
  overflow-wrap: anywhere;
  color: var(--login-muted);
  font-size: 13px;
  font-style: normal;
}

.signal-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  width: min(520px, 100%);
  animation: fade-up var(--app-motion-base) var(--app-ease-out) 120ms both;
}

.signal-item {
  position: relative;
  overflow: hidden;
  min-height: 78px;
  padding: 14px;
  border: 1px solid var(--login-border);
  border-radius: var(--app-radius-md);
  background: linear-gradient(180deg, var(--app-color-glass-strong), var(--login-panel-strong));
}

.signal-item::before {
  position: absolute;
  inset: 0 0 auto;
  height: 3px;
  content: "";
  background: linear-gradient(90deg, var(--login-accent), var(--login-sky), var(--login-emerald));
}

.signal-item span {
  display: block;
  margin-bottom: 8px;
  color: var(--login-muted);
  font-size: 12px;
}

.signal-item strong {
  color: var(--login-text);
  font-size: 18px;
  font-weight: 760;
}

.login-card {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--app-color-primary-border);
  border-radius: var(--app-radius-md);
  background: var(--app-gradient-glass);
  box-shadow: var(--login-shadow);
  backdrop-filter: var(--app-backdrop-panel);
  -webkit-backdrop-filter: var(--app-backdrop-panel);
  animation: card-in var(--app-motion-slow) var(--app-ease-out) 80ms both;
}

.login-card::before {
  position: absolute;
  inset: 0 0 auto;
  height: 4px;
  content: "";
  background: linear-gradient(90deg, var(--login-accent), var(--login-sky) 62%, var(--login-emerald));
}

.login-card-header {
  margin-bottom: 22px;
}

.login-card-header h2 {
  margin: 0 0 8px;
  color: var(--login-text);
  font-size: 24px;
  font-weight: 760;
}

.login-card-header p {
  margin: 0;
  color: var(--login-muted);
  font-size: 14px;
  line-height: 1.6;
}

.auth-notice {
  margin-bottom: 12px;
}

.login-form {
  :deep(.el-form-item__label) {
    color: var(--login-text);
    font-weight: 650;
  }

  :deep(.el-input__wrapper) {
    border-radius: var(--app-radius-md);
    background: var(--login-input-bg);
    box-shadow: 0 0 0 1px var(--login-border) inset;
    transition:
      box-shadow var(--app-motion-base) ease-out,
      background-color var(--app-motion-base) ease-out;
  }

  :deep(.el-input__wrapper.is-focus) {
    box-shadow:
      0 0 0 1px var(--login-accent) inset,
      var(--app-shadow-focus);
  }

  :deep(.el-input__inner) {
    color: var(--login-input-text);
  }

  :deep(.el-input__inner::placeholder) {
    color: var(--login-input-placeholder);
  }

  :deep(.el-input__prefix),
  :deep(.el-input__password) {
    color: var(--login-muted);
  }
}

.login-card :deep(.el-card__body) {
  padding: 30px;
}

.login-card :deep(.el-alert) {
  border-radius: var(--app-radius-md);
}

.login-button {
  width: 100%;
  min-height: 44px;
  margin-top: 8px;
  border: 1px solid var(--login-accent);
  border-radius: var(--app-radius-md);
  background: linear-gradient(135deg, var(--login-accent), var(--login-sky) 58%, var(--login-emerald));
  box-shadow: 0 12px 24px color-mix(in srgb, var(--login-accent) 24%, transparent);
  font-weight: 750;
  transition:
    box-shadow var(--app-motion-base) ease-out,
    background-color var(--app-motion-base) ease-out,
    border-color var(--app-motion-base) ease-out;
}

.login-button:hover,
.login-button:focus-visible {
  border-color: var(--login-accent-strong);
  background: var(--login-accent-strong);
  box-shadow: var(--app-shadow-focus);
}

.security-note {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 18px 0 0;
  color: var(--login-muted);
  font-size: 13px;
  line-height: 1.5;
}

.security-note .el-icon {
  flex: 0 0 auto;
  color: var(--login-emerald);
}

@keyframes fade-up {
  from {
    opacity: 0;
    transform: translateY(14px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes card-in {
  from {
    opacity: 0;
    transform: translateY(18px) scale(0.985);
  }

  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes doc-enter {
  from {
    opacity: 0;
    transform: translateY(10px) rotate(-1deg);
  }

  to {
    opacity: 1;
    transform: translateY(0) rotate(0deg);
  }
}

@keyframes line-fill {
  to {
    transform: translateX(0);
  }
}

@media (prefers-color-scheme: dark) {
  .login-page {
    color-scheme: var(--app-color-scheme);
    background:
      var(--app-gradient-ambient),
      linear-gradient(var(--app-color-grid-line) 1px, transparent 1px),
      linear-gradient(90deg, var(--app-color-grid-line) 1px, transparent 1px),
      var(--app-gradient-page);
    background-size:
      auto,
      48px 48px,
      48px 48px,
      auto;
  }

  .brand-row,
  .assurance-strip span,
  .signal-item {
    background: var(--login-panel);
  }

  .workflow-panel,
  .doc-card {
    background: linear-gradient(180deg, var(--login-panel), var(--login-panel-strong));
    box-shadow: var(--app-shadow-subtle);
  }

  .login-page::after {
    background-image:
      linear-gradient(var(--app-color-grid-line) 1px, transparent 1px),
      linear-gradient(90deg, var(--app-color-grid-line) 1px, transparent 1px);
    opacity: 0.22;
  }

  .login-form {
    :deep(.el-input__wrapper.is-focus) {
      box-shadow:
        0 0 0 1px var(--login-accent) inset,
        var(--app-shadow-focus);
    }
  }
}

@media (max-width: 920px) {
  .login-page {
    place-items: start center;
    padding: 28px 18px;
  }

  .login-shell {
    grid-template-columns: 1fr;
  }

  .login-copy h1 {
    max-width: 680px;
  }
}

@media (max-width: 760px) {
  .workflow-panel {
    grid-template-columns: 1fr;
  }

  .document-preview {
    min-height: 104px;
  }

  .doc-card {
    min-height: 92px;
  }
}

@media (max-width: 560px) {
  .login-page {
    padding: 18px 12px;
  }

  .login-shell {
    gap: 22px;
  }

  .login-card {
    order: -1;
  }

  .brand-row {
    margin-bottom: 20px;
  }

  .login-copy h1 {
    font-size: 32px;
  }

  .login-lede {
    margin-bottom: 20px;
    font-size: 15px;
  }

  .workflow-panel {
    padding: 14px;
  }

  .flow-list li {
    grid-template-columns: 34px 52px minmax(0, 1fr);
  }

  .signal-grid {
    grid-template-columns: 1fr;
  }

  .signal-item {
    min-height: 64px;
  }

  .login-card :deep(.el-card__body) {
    padding: 24px 18px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .login-page::before,
  .login-copy,
  .workflow-panel,
  .signal-grid,
  .doc-card,
  .convert-line::after,
  .login-card {
    animation: none;
  }

  .login-button {
    transition: none;
  }

  .login-button:hover,
  .login-button:focus-visible {
    transform: none;
  }
}
</style>
