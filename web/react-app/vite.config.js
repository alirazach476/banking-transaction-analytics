import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The built app is served by the API at /app/, so asset URLs are relative to that base.
const API = "http://localhost:8000";
export default defineConfig({
  plugins: [react()],
  base: "/app/",
  server: { proxy: { "/kpis": API, "/decline-reasons": API, "/reconciliation": API, "/score": API, "/models": API } },
  test: { environment: "node" },
});
