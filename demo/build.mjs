// Builds demo/index.html: one self-contained file (Leaflet, fonts, CSS and JS inlined).
//
//   node build.mjs                                   # rule planner only
//   node build.mjs --api=https://<agent>.workers.dev # page talks to the Claude agent

import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const read = (p) => readFileSync(p, "utf8");
const src = (f) => read(join(here, "src", f));

const apiArg = process.argv.find((a) => a.startsWith("--api="));
const apiBase = (apiArg ? apiArg.slice(6) : process.env.TT_API_BASE || "").trim();
if (apiBase && !/^https:\/\/[^\s"'<>]+$/.test(apiBase)) {
  console.error("--api must be an https:// URL");
  process.exit(1);
}

const leafletDir = dirname(require.resolve("leaflet/dist/leaflet.js"));
const overpassDir = dirname(require.resolve("@fontsource/overpass/package.json"));
const fontDir = join(overpassDir, "files");
const bundledLicenses = [
  ["Leaflet", join(leafletDir, "..", "LICENSE")],
  ["Overpass", join(overpassDir, "LICENSE")],
].map(([name, path]) => `${name}\n${read(path).trimEnd()}`).join("\n\n");
const font = (weight) => {
  const data = readFileSync(join(fontDir, `overpass-latin-${weight}-normal.woff2`)).toString("base64");
  return `@font-face{font-family:"Overpass";font-style:normal;font-weight:${weight};font-display:swap;src:url(data:font/woff2;base64,${data}) format("woff2");}`;
};

const stripImports = (code) => code.replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];?[ \t]*$/gm, "");
const stripExports = (code) => code.replace(/^export\s+(?=(?:const|let|function|class|async)\b)/gm, "");
const safeScript = (code) => code.replace(/<\/script/gi, "<\\/script");

const appJs = [
  "// core.js", stripExports(src("core.js")),
  "// charts.js", stripExports(stripImports(src("charts.js"))),
  "// app.js", stripImports(src("app.js")),
].join("\n");

const html = read(join(here, "src", "template.html"))
  .replace("/*API_BASE*/", () => apiBase)
  .replace("/*LEAFLET_CSS*/", () => read(join(leafletDir, "leaflet.css")))
  .replace("/*FONTS_CSS*/", () => [400, 600, 800].map(font).join("\n"))
  .replace("/*APP_CSS*/", () => src("styles.css"))
  .replace("/*LEAFLET_JS*/", () => safeScript(read(join(leafletDir, "leaflet.js"))))
  .replace("/*APP_JS*/", () => safeScript(appJs))
  .replace("</head>", () => `<script type="text/plain" id="third-party-licenses">\n${safeScript(bundledLicenses)}\n</script>\n</head>`);

writeFileSync(join(here, "index.html"), html);
console.log(`Wrote index.html (${Math.round(html.length / 1024)} KB)${apiBase ? ` for agent ${apiBase}` : ", rule planner only"}`);
