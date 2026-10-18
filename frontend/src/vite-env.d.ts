/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Public origin of the API including the version prefix, e.g. https://api.example.com/api/v1. */
  readonly VITE_API_URL?: string;
}
