import { fileURLToPath, URL } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  base: "/llm/",
  server: {
    port: 5173,
    proxy: {
      "/dashboard": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
