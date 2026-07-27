import { readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const siteRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const dataPath = join(siteRoot, "app", "department-data.json");
const data = JSON.parse(await readFile(dataPath, "utf8"));

let approvedCount = 0;
for (const department of data.departments) {
  department.archive = department.archive
    .filter((report) =>
      ["approved", "published"].includes(report.issue.status),
    )
    .map((report) => {
      if (report.issue.status === "approved") {
        report.issue.status = "published";
        approvedCount += 1;
      }
      return report;
    });
  department.currentReport = department.archive[0] ?? null;
}

if (!approvedCount && !data.departments.some(
  (department) => department.currentReport?.issue.status === "published",
)) {
  throw new Error("Refusing public preparation: no approved report exists");
}

await writeFile(dataPath, JSON.stringify(data, null, 2), "utf8");
