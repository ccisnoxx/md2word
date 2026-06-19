// frontend/src/main.ts: Bootstrap Vue, Pinia, router, and Element Plus.
import { createApp } from "vue";
import ElementPlus from "element-plus";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import "element-plus/dist/index.css";

import App from "@/App.vue";
import router from "@/router";
import { pinia } from "@/stores";
import "@/styles/main.scss";
import { applyThemeMode, getStoredThemeMode } from "@/utils/theme";

const app = createApp(App);

applyThemeMode(getStoredThemeMode());

app.use(pinia);
app.use(router);
app.use(ElementPlus, { locale: zhCn });

app.mount("#app");
