/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_JOB_SERVICE_URL?: string;
  readonly VITE_CANDIDATE_SERVICE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
