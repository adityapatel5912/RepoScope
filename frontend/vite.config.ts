import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API proxy target. Defaults to :8000 (the normal local dev backend).
// The QA harness overrides it so the Playwright run talks to its own
// hermetic backend on :8010 — a QA run must not depend on whatever
// happens to be listening on the developer's default port.
const apiTarget =
  process.env.REPOSCOPE_QA_BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": apiTarget },
  },
});
