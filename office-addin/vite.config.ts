import react from "@vitejs/plugin-react";
import { getHttpsServerOptions } from "office-addin-dev-certs";
import { defineConfig } from "vite";

// Office requires HTTPS for task panes. `pnpm dev-certs` installs a local CA and a certificate
// whose names include 127.0.0.1 (an IP entry) and localhost; the dev server uses it and listens on
// 127.0.0.1 only, the address the manifest and the API's CORS_ORIGINS name.
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
