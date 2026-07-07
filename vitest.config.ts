import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Separate from vite.config.ts: the PWA plugin has no business running
// during tests, and vitest's `test` field isn't recognized by plain Vite's
// defineConfig without importing vitest's own config type.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
    css: true,
  },
});
