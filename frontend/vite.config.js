import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import fs from "node:fs";
import { fileURLToPath } from "node:url";
const mobileTls =
  process.env.PUNTOCOM_MOBILE_TLS === "1"
    ? {
        key: fs.readFileSync(
          fileURLToPath(new URL("../.local/celular-key.pem", import.meta.url)),
        ),
        cert: fs.readFileSync(
          fileURLToPath(new URL("../.local/celular-cert.pem", import.meta.url)),
        ),
      }
    : undefined;
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          materialize: ["@materializecss/materialize"],
          charts: ["chart.js/auto"],
        },
      },
    },
  },
  server: { proxy: { "/api": "http://127.0.0.1:5001" } },
  preview: { https: mobileTls, proxy: { "/api": "http://127.0.0.1:5001" } },
});
