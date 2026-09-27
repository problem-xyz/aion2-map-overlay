import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vitest/config";

export default defineConfig({
  // Vitest replaces vite.config.ts rather than merging with it, so the "@" alias defined there
  // does not exist under test unless it is repeated here. Without it any module reaching for
  // "@/..." fails during transform -- before vi.mock is ever consulted, so a test cannot work
  // around it. Keep this in step with vite.config.ts.
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  test: {
    environment: "jsdom",
    globals: false,
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["src/test/setup.ts"],
  },
});
