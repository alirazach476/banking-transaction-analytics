import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The built app is served by the API at /app/ (with a fallback to index.html for client-side routes).
const API = "http://localhost:8000";
export default defineConfig({
  plugins: [react()],
  base: "/app/",
  server: { proxy: { "/v1": API, "/kpis": API, "/decline-reasons": API, "/reconciliation": API, "/score": API, "/models": API } },
  build: {
    rollupOptions: { output: { manualChunks: { echarts: ["echarts/core", "echarts/charts", "echarts/components", "echarts/renderers"], maplibre: ["maplibre-gl"], react: ["react", "react-dom", "react-router-dom", "@tanstack/react-query", "@tanstack/react-table"] } } },
    chunkSizeWarningLimit: 900,
  },
  test: { environment: "node" },
});
