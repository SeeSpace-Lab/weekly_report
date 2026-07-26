import { readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const siteRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const appRoot = join(siteRoot, "app");
const reportPath = join(appRoot, "report-data.json");
const archivePath = join(appRoot, "archive-data.json");

const report = JSON.parse(await readFile(reportPath, "utf8"));
if (report.issue.status !== "approved") {
  throw new Error(
    `Refusing public preparation: issue status is ${report.issue.status}`,
  );
}
report.issue.status = "published";

const archive = JSON.parse(await readFile(archivePath, "utf8"));
archive.issues = archive.issues
  .filter(
    (issue) =>
      issue.issue.status === "approved" ||
      issue.issue.status === "published" ||
      issue.issue.id === report.issue.id,
  )
  .map((issue) => {
    if (issue.issue.id === report.issue.id) {
      issue.issue.status = "published";
    }
    return issue;
  });

await writeFile(reportPath, JSON.stringify(report, null, 2), "utf8");
await writeFile(archivePath, JSON.stringify(archive, null, 2), "utf8");
