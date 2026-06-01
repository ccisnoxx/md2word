<!-- frontend/src/pages/LoginPage.vue: Internal account login page for operators and admins. -->
<template>
  <main class="login-page">
    <section class="login-panel">
      <div class="login-copy">
        <h1>内部文档转换工作台</h1>
        <p>使用内部账号登录后上传 PDF、查看转换进度并下载 Word 结果。</p>
      </div>

      <el-card class="login-card card-flat" shadow="never">
        <h2>账号登录</h2>
        <ApiErrorAlert :error="error" />
        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @keyup.enter="submit">
          <el-form-item label="用户名" prop="username">
            <el-input v-model.trim="form.username" autocomplete="username" autofocus />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input v-model="form.password" type="password" autocomplete="current-password" show-password />
          </el-form-item>
          <el-button class="login-button" type="primary" :loading="submitting" @click="submit">登录</el-button>
        </el-form>
      </el-card>
    </section>
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
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
  display: grid;
  min-height: 100vh;
  place-items: center;
  padding: 24px;
  background:
    linear-gradient(135deg, rgba(37, 99, 235, 0.08), rgba(5, 150, 105, 0.08)),
    #f5f7fb;
}

.login-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 380px;
  gap: 40px;
  width: min(920px, 100%);
  align-items: center;
}

.login-copy h1 {
  margin: 0 0 12px;
  color: #111827;
  font-size: 34px;
  line-height: 1.15;
}

.login-copy p {
  margin: 0;
  color: #475467;
  font-size: 16px;
  line-height: 1.7;
}

.login-card {
  border: 1px solid #d9e2ec;
}

.login-card h2 {
  margin: 0 0 18px;
  font-size: 20px;
}

.login-button {
  width: 100%;
  margin-top: 6px;
}

@media (max-width: 760px) {
  .login-panel {
    grid-template-columns: 1fr;
    gap: 24px;
  }

  .login-copy h1 {
    font-size: 28px;
  }
}
</style>
