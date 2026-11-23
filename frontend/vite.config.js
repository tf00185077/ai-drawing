import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendTarget = "http://127.0.0.1:8001";

export default defineConfig({
  cacheDir: process.env.AI_DRAWING_VITE_CACHE || "node_modules/.vite",
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.js"],
  },
  server: {
    proxy: {
      "/api": {
        target: backendTarget,
        changeOrigin: true,
      },
      // Leave /gallery and /gallery/ (including queries) to the SPA.
      "^/gallery/(?![?]|$)": {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
});
