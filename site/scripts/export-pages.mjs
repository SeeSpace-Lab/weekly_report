import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const siteRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const outputRoot = join(siteRoot, "out");
const clientRoot = join(siteRoot, "dist", "client");
const repository = process.env.GITHUB_REPOSITORY?.split("/")[1] ?? "weekly_report";
const basePath = (process.env.PAGES_BASE_PATH ?? `/${repository}`).replace(/\/$/, "");
const routes = [
  "/",
  "/departments/orbitinfer",
  "/departments/constellation-simulation",
  "/library",
  "/sources",
];

function pagePath(route) {
  if (route === "/") return join(outputRoot, "index.html");
  return join(outputRoot, route.slice(1), "index.html");
}

function withBasePath(html) {
  return html
    .replaceAll("/assets/", "__PAGES_ASSET_PATH__")
    .replaceAll("/og.png", "__PAGES_OG_PATH__")
    .replaceAll("/favicon.svg", "__PAGES_FAVICON_PATH__")
    .replaceAll('href="/', `href="${basePath}/`)
    .replaceAll('\\"href\\":\\"/', `\\"href\\":\\"${basePath}/`)
    .replaceAll("__PAGES_ASSET_PATH__", `${basePath}/assets/`)
    .replaceAll("__PAGES_OG_PATH__", `${basePath}/og.png`)
    .replaceAll("__PAGES_FAVICON_PATH__", `${basePath}/favicon.svg`);
}

await rm(outputRoot, { recursive: true, force: true });
await mkdir(outputRoot, { recursive: true });
await cp(clientRoot, outputRoot, { recursive: true });

const workerUrl = pathToFileURL(join(siteRoot, "dist", "server", "index.js"));
workerUrl.searchParams.set("pages-export", `${Date.now()}`);
const { default: worker } = await import(workerUrl.href);

for (const route of routes) {
  const response = await worker.fetch(
    new Request(`http://pages.local${route}`, {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
  if (!response.ok) {
    throw new Error(`failed to render ${route}: HTTP ${response.status}`);
  }
  const target = pagePath(route);
  await mkdir(dirname(target), { recursive: true });
  await writeFile(target, withBasePath(await response.text()), "utf8");
}

for (const asset of ["favicon.svg", "file.svg", "globe.svg", "window.svg"]) {
  const target = join(outputRoot, asset);
  try {
    const text = await readFile(target, "utf8");
    await writeFile(target, text, "utf8");
  } catch {
    // Optional starter assets do not affect the report.
  }
}

await writeFile(join(outputRoot, ".nojekyll"), "", "utf8");
await cp(join(outputRoot, "index.html"), join(outputRoot, "404.html"));
console.log(`Exported ${routes.length} routes to ${outputRoot} with base ${basePath}`);
