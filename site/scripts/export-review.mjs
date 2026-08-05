import { execFileSync } from "node:child_process";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const siteRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const repositoryRoot = dirname(siteRoot);
const branch = execFileSync("git", ["branch", "--show-current"], {
  cwd: repositoryRoot,
  encoding: "utf8",
}).trim();

if (!branch || branch === "main" || branch === "develop") {
  throw new Error("Public review snapshots require an independent development branch");
}

const repository = process.env.GITHUB_REPOSITORY ?? "SeeSpace-Lab/weekly_report";
process.env.PAGES_OUTPUT_DIR = "review";
process.env.PAGES_BASE_PATH = `/${repository}/${branch}/site/review`;
process.env.PAGES_STATIC_FILE_LINKS = "true";

await import(`./export-pages.mjs?review=${Date.now()}`);
console.log(
  `Public review URL: https://raw.githack.com/${repository}/${branch}/site/review/index.html`,
);
