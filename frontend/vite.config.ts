import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API proxy target. Defaults to :8000 (the normal local dev backend).
// The QA harness overrides it so the Playwright run talks to its own
// hermetic backend on :8010 — a QA run must not depend on whatever
// happens to be listening on the developer's default port.
//
// The host is EXPLICITLY 127.0.0.1, never "localhost". On Windows,
// `localhost` resolves to ::1 first, and uvicorn binds IPv4 only, so the
// proxy's IPv6 connect is refused and every /api request comes back as a
// bare 500 "Internal Server Error" with nothing in the backend log.
const apiTarget =
  process.env.REPOSCOPE_QA_BACKEND_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": apiTarget },
  },
});
