import { defineConfig } from "vite";
import { resolve } from "path";

export default defineConfig({
  build: {
    // Compile directly into the Django static directory
    outDir: resolve(__dirname, "../src/djpress_tiptap/static/djpress_tiptap"),
    // Clear out the target folder before building fresh assets
    emptyOutDir: true,
    // Build as a standalone library configuration
    // SM Note: To keep deployment simple, this configuration targets a self-invoking format (iife) and outputs a
    // fixed filename. This eliminates the need to parse dynamic asset manifests inside Python templates.
    lib: {
      entry: resolve(__dirname, "src/main.js"),
      formats: ["es"],
      name: "DjTipTapEditor",
      fileName: () => "djtiptap.bundle.js",
      cssFileName: "djtiptap",
    },
    // Minify the shipped bundle; Vite leaves this off by default for lib builds
    minify: "oxc",
    // No source maps in the published package - see note in README/CLAUDE.md
    sourcemap: false,
    rollupOptions: {
      output: {
        // For ES-format lib builds, Vite's oxc minifier only mangles names and
        // skips whitespace collapsing (it assumes a downstream bundler will
        // finish the job). We ship this bundle as-is, so force full minification.
        minify: true,
      },
    },
  },
});
