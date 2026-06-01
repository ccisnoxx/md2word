// frontend/src/env.d.ts: Declare Vite environment variables used by the frontend app.
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_API_PROXY_TARGET?: string;
  readonly VITE_ENABLE_EN2ZH?: string;
  readonly VITE_MAX_UPLOAD_BYTES?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
