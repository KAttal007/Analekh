import react from "@vitejs/plugin-react";
import { getHttpsServerOptions } from "office-addin-dev-certs";
import { defineConfig } from "vite";

export default defineConfig(async ({ command }) => ({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 3000,
    strictPort: true,
    https: command === "serve" ? await getHttpsServerOptions() : undefined,
  },
  build: { rollupOptions: { input: "taskpane.html" } },
}));
