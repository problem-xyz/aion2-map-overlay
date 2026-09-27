import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";

// Everything is bundled into a single index.html (scripts and styles inlined): that way the page
// opens from a file (file://) inside QWebEngineView without trouble.
export default defineConfig({
  plugins: [react(), viteSingleFile()],
  base: "./",
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  // Read by the dev mock only (src/dev/scenarios.ts), to find the tiles the app cut locally
  define: {
    __MOCK_USERDATA__: JSON.stringify(
      "/@fs/" + fileURLToPath(new URL("../userdata", import.meta.url)).replaceAll("\\", "/"),
    ),
  },
  // fs.allow: in dev the editor has to reach map tiles in ../maps through /@fs/
  server: { port: 5173, strictPort: true, fs: { allow: [".."] } },
  // assetsInlineLimit: so the images referenced by leaflet.css land inside that single file too
  build: { outDir: "dist", emptyOutDir: true, target: "chrome110", assetsInlineLimit: 200000 },
});
