/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    // ANALEKH_API points the dev server at another API (e.g. a second instance on :8001).
    proxy: {
      "/api": {
        target: process.env.ANALEKH_API ?? "http://127.0.0.1:8000",
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
  // ECharts and AG Grid are split into their own lazily loaded chunks (see src/router.tsx).
  build: { chunkSizeWarningLimit: 1300 },
  test: { environment: "jsdom", globals: false },
});
