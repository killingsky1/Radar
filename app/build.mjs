// Construit le site dans dist/ : app.jsx -> app.js (un seul fichier, compatible Safari iPhone).
import * as esbuild from "esbuild";
import { copyFile, mkdir } from "node:fs/promises";

await mkdir("dist", { recursive: true });
await esbuild.build({
  entryPoints: ["app.jsx"],
  bundle: true,
  minify: true,
  format: "esm",
  target: ["safari15"],
  jsx: "automatic",
  outfile: "dist/app.js",
  define: { "process.env.NODE_ENV": '"production"' },
});
for (const f of ["index.html", "manifest.json"]) await copyFile(f, `dist/${f}`);
console.log("Site construit dans dist/");
