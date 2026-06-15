/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Phase 0：最小 Vite + React 配置 + Vitest（jsdom）。
// 真正的前端应用（路由、SSE、组件库等）在 Phase 5 搭建。
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test-setup.ts",
  },
});
