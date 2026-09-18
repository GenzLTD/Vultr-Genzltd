#!/usr/bin/env node
/**
 * Bundle @looma/shared-core mini entry for WeChat miniprogram runtime.
 * Output: dist/mini/index.js (single CJS file, no fetch/localStorage)
 */
import * as esbuild from "esbuild";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const pkgRoot = path.join(__dirname, "..");
const outDir = path.join(pkgRoot, "dist/mini");
const outfile = path.join(outDir, "index.js");

fs.mkdirSync(outDir, { recursive: true });

await esbuild.build({
  entryPoints: [path.join(pkgRoot, "src/entries/mini.ts")],
  bundle: true,
  outfile,
  format: "cjs",
  platform: "neutral",
  target: "es2018",
  sourcemap: true,
  minify: false,
  treeShaking: true,
  logLevel: "info",
  banner: {
    js: "/* @looma/shared-core mini bundle — do not edit by hand */",
  },
});

// Minimal package stub for WeChat npm pack (main entry = this bundle)
const miniPkg = {
  name: "@looma/shared-core",
  version: "0.1.0",
  description: "Looma shared-core miniprogram runtime bundle",
  main: "index.js",
  miniprogram: "index.js",
};
fs.writeFileSync(path.join(outDir, "package.json"), JSON.stringify(miniPkg, null, 2));

const js = fs.readFileSync(outfile, "utf8");
const forbidden = ["fetch(", "localStorage", "ReadableStream", "FormData(", "AbortController"];
const hits = forbidden.filter((token) => js.includes(token));
if (hits.length > 0) {
  console.error("❌ Mini bundle contains Web-only APIs:", hits.join(", "));
  process.exit(1);
}

const sizeKb = (fs.statSync(outfile).size / 1024).toFixed(1);
console.log(`✅ Mini bundle OK: ${outfile} (${sizeKb} KB)`);
