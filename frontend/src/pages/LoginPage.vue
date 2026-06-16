<!-- frontend/src/pages/LoginPage.vue: Internal account login page for operators and admins. -->
<template>
  <main class="login-page" aria-labelledby="login-title">
    <section class="login-shell">
      <div class="login-copy">
        <div class="brand-row">
          <span class="brand-mark" aria-hidden="true">
            <el-icon><DocumentChecked /></el-icon>
          </span>
          <span class="brand-name">md2word Workbench</span>
        </div>
        <p class="login-eyebrow">内部文档转换入口</p>
        <h1 id="login-title">把 PDF 转换任务交给稳定队列。</h1>
        <p class="login-lede">集中处理上传、转换进度和 Word 结果，适合内部运营与交付团队日常使用。</p>

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
        </div>

        <div class="signal-grid" aria-label="工作台能力状态">
          <div class="signal-item">
            <span>队列</span>
            <strong>实时</strong>
          </div>
          <div class="signal-item">
            <span>结果</span>
            <strong>可下载</strong>
          </div>
          <div class="signal-item">
            <span>审计</span>
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
          type="warning"
          :closable="false"
          show-icon
          :title="authNotice"
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
  if (reason === "token_expired") {
    return "登录已过期，请重新登录。";
  }
  if (reason === "invalid_token") {
    return "登录状态无效，请重新登录。";
  }
  return "";
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
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/jobs";
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
  --login-bg: #f7f5ff;
  --login-bg-secondary: #ecfeff;
  --login-text: #16163a;
  --login-muted: #5a6680;
  --login-panel: rgba(255, 255, 255, 0.78);
  --login-panel-strong: rgba(255, 255, 255, 0.9);
  --login-border: rgba(99, 102, 241, 0.16);
  --login-shadow: 0 28px 80px rgba(39, 39, 90, 0.18);
  --login-accent: #4f46e5;
  --login-accent-strong: #312e81;
  --login-emerald: #0f9f75;
  --login-amber: #b7791f;
  --login-input-bg: rgba(255, 255, 255, 0.82);
  --login-input-text: #16163a;
  --login-input-placeholder: #7a849a;

  position: relative;
  overflow: hidden;
  display: grid;
  min-height: 100svh;
  place-items: center;
  padding: 48px 24px;
  background:
    linear-gradient(120deg, rgba(79, 70, 229, 0.12), rgba(15, 159, 117, 0.1) 45%, transparent 70%),
    linear-gradient(150deg, var(--login-bg), var(--login-bg-secondary));
  color: var(--login-text);
  color-scheme: light;
}

.login-page::before,
.login-page::after {
  position: absolute;
  z-index: 0;
  content: "";
  pointer-events: none;
}

.login-page::before {
  inset: -12% -8% auto auto;
  width: 58vw;
  height: 58vw;
  max-width: 720px;
  max-height: 720px;
  background:
    linear-gradient(135deg, rgba(79, 70, 229, 0.22), rgba(15, 159, 117, 0.08)),
    linear-gradient(45deg, transparent 0 42%, rgba(255, 255, 255, 0.34) 42% 46%, transparent 46% 100%);
  clip-path: polygon(18% 0, 100% 8%, 86% 72%, 38% 100%, 0 48%);
  filter: blur(2px);
  opacity: 0.88;
  transform: translate3d(0, 0, 0);
  animation: panel-drift 900ms ease-out both;
}

.login-page::after {
  inset: 0;
  background-image:
    linear-gradient(rgba(79, 70, 229, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(79, 70, 229, 0.08) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: linear-gradient(120deg, transparent 0%, #000 26%, transparent 82%);
  opacity: 0.42;
}

.login-shell {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 420px);
  gap: clamp(28px, 6vw, 72px);
  width: min(1080px, 100%);
  align-items: center;
}

.login-copy {
  animation: fade-up 420ms ease-out both;
}

.brand-row {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 28px;
  padding: 8px 12px 8px 8px;
  border: 1px solid var(--login-border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.54);
  box-shadow: 0 12px 30px rgba(49, 46, 129, 0.08);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.brand-mark {
  display: inline-grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--login-accent), var(--login-emerald));
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
  color: var(--login-emerald);
  font-size: 13px;
  font-weight: 700;
}

.login-copy h1 {
  max-width: 620px;
  margin: 0 0 18px;
  color: var(--login-text);
  font-size: clamp(34px, 5vw, 58px);
  font-weight: 760;
  line-height: 1.08;
}

.login-lede {
  max-width: 560px;
  margin: 0 0 28px;
  color: var(--login-muted);
  font-size: 17px;
  line-height: 1.75;
}

.workflow-panel {
  display: grid;
  grid-template-columns: minmax(180px, 240px) minmax(0, 1fr);
  gap: 20px;
  width: min(640px, 100%);
  margin-bottom: 18px;
  padding: 18px;
  border: 1px solid var(--login-border);
  border-radius: 8px;
  background: var(--login-panel);
  box-shadow: 0 18px 50px rgba(49, 46, 129, 0.1);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  animation: fade-up 420ms ease-out 80ms both;
}

.document-preview {
  display: grid;
  grid-template-columns: 1fr 44px 1fr;
  gap: 8px;
  align-items: center;
  min-height: 122px;
}

.doc-card {
  display: grid;
  min-height: 104px;
  place-items: center;
  border: 1px solid var(--login-border);
  border-radius: 8px;
  background: var(--login-panel-strong);
  color: var(--login-accent-strong);
  font-size: 16px;
  font-weight: 800;
  box-shadow: 0 12px 28px rgba(49, 46, 129, 0.12);
  transform-origin: center;
  animation: doc-enter 460ms ease-out both;
}

.doc-card-source {
  animation-delay: 160ms;
}

.doc-card-target {
  color: var(--login-emerald);
  animation-delay: 360ms;
}

.convert-line {
  position: relative;
  display: block;
  height: 2px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(79, 70, 229, 0.16);
}

.convert-line::after {
  position: absolute;
  inset: 0;
  content: "";
  border-radius: inherit;
  background: linear-gradient(90deg, var(--login-accent), var(--login-emerald));
  transform: translateX(-100%);
  animation: line-fill 600ms ease-out 520ms both;
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
  animation: fade-up 420ms ease-out 140ms both;
}

.signal-item {
  min-height: 78px;
  padding: 14px;
  border: 1px solid var(--login-border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.56);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
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
  border: 1px solid var(--login-border);
  border-radius: 8px;
  background: var(--login-panel);
  box-shadow: var(--login-shadow);
  backdrop-filter: blur(22px);
  -webkit-backdrop-filter: blur(22px);
  animation: card-in 480ms ease-out 100ms both;
}

.login-card::before {
  position: absolute;
  inset: 0 0 auto;
  height: 4px;
  content: "";
  background: linear-gradient(90deg, var(--login-accent), var(--login-emerald), var(--login-amber));
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
    border-radius: 8px;
    background: var(--login-input-bg);
    box-shadow: 0 0 0 1px var(--login-border) inset;
    transition:
      box-shadow 180ms ease-out,
      background-color 180ms ease-out;
  }

  :deep(.el-input__wrapper.is-focus) {
    box-shadow:
      0 0 0 1px var(--login-accent) inset,
      0 0 0 3px rgba(79, 70, 229, 0.14);
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
  border-radius: 8px;
}

.login-button {
  width: 100%;
  min-height: 44px;
  margin-top: 8px;
  border: 0;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--login-accent), var(--login-emerald));
  box-shadow: 0 14px 32px rgba(15, 159, 117, 0.2);
  font-weight: 750;
  transition:
    box-shadow 180ms ease-out,
    filter 180ms ease-out,
    transform 180ms ease-out;
}

.login-button:hover,
.login-button:focus-visible {
  background: linear-gradient(135deg, var(--login-accent), var(--login-emerald));
  filter: saturate(1.08);
  box-shadow: 0 18px 40px rgba(15, 159, 117, 0.28);
  transform: translateY(-1px);
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

@keyframes panel-drift {
  from {
    opacity: 0;
    transform: translate3d(28px, -18px, 0) rotate(2deg);
  }

  to {
    opacity: 0.88;
    transform: translate3d(0, 0, 0) rotate(0deg);
  }
}

@media (prefers-color-scheme: dark) {
  .login-page {
    --login-bg: #050711;
    --login-bg-secondary: #0b1020;
    --login-text: #f7f8ff;
    --login-muted: #a9b4c7;
    --login-panel: rgba(10, 16, 32, 0.74);
    --login-panel-strong: rgba(15, 23, 42, 0.88);
    --login-border: rgba(148, 163, 184, 0.2);
    --login-shadow: 0 30px 90px rgba(0, 0, 0, 0.42);
    --login-accent: #818cf8;
    --login-accent-strong: #c7d2fe;
    --login-emerald: #34d399;
    --login-amber: #f5c451;
    --login-input-bg: rgba(15, 23, 42, 0.84);
    --login-input-text: #f8fafc;
    --login-input-placeholder: #8fa0b8;

    background:
      linear-gradient(120deg, rgba(129, 140, 248, 0.2), rgba(52, 211, 153, 0.12) 44%, transparent 70%),
      linear-gradient(150deg, var(--login-bg), var(--login-bg-secondary));
    color-scheme: dark;
  }

  .brand-row,
  .signal-item {
    background: rgba(15, 23, 42, 0.58);
  }

  .doc-card {
    box-shadow: 0 18px 42px rgba(0, 0, 0, 0.26);
  }

  .login-page::after {
    background-image:
      linear-gradient(rgba(148, 163, 184, 0.1) 1px, transparent 1px),
      linear-gradient(90deg, rgba(148, 163, 184, 0.1) 1px, transparent 1px);
    opacity: 0.32;
  }

  .login-form {
    :deep(.el-input__wrapper.is-focus) {
      box-shadow:
        0 0 0 1px var(--login-accent) inset,
        0 0 0 3px rgba(129, 140, 248, 0.22);
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
