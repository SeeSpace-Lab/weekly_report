import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render(path = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`http://localhost${path}`, {
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
}

test("server-renders the research portal", async () => {
  const response = await render("/");
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>观宇芯算研发部周报<\/title>/i);
  assert.match(html, /按部门进入周报/);
  assert.match(html, /星载大模型/);
  assert.match(html, /星座智算/);
  assert.match(html, /2026-W32/);
  assert.match(html, /周一 09:00 更新/);
  assert.match(html, /顶会与重要论文库/);
  assert.match(html, /og:image/);
});

test("server-renders the OrbitInfer department report", async () => {
  const response = await render("/departments/orbitinfer");
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /本周趋势雷达/);
  assert.match(html, /\d+<\/strong><span>精选条目/);
  assert.match(html, /查看一手来源/);
  assert.match(html, /公开只读审核/);
  assert.match(html, /不会写入 GitHub/);
  assert.doesNotMatch(html, /github\.com\/SeeSpace-Lab\/weekly_report\/pull\/13/);
  assert.match(html, /class="oneSentence"/);
  assert.match(html, /<dt>问题<\/dt>/);
  assert.match(html, /class="translatedTitle">/);
  assert.match(html, /C²KV/);
  assert.doesNotMatch(html, /C\\$\\^2\\$KV/);
  assert.doesNotMatch(html, /顶会动态/);
  assert.doesNotMatch(html, /论文库回看/);
  assert.doesNotMatch(html, /Your site is taking shape|Building your site/);
});

test("renders the library, source pool, archive and second department", async () => {
  const [library, sources, archive, department] = await Promise.all([
    render("/library"),
    render("/sources"),
    render("/archive"),
    render("/departments/constellation-simulation"),
  ]);
  for (const response of [library, sources, archive, department]) {
    assert.equal(response.status, 200);
  }
  assert.match(await library.text(), /Mooncake/);
  const sourceHtml = await sources.text();
  assert.match(sourceHtml, /PaperWeekly/);
  assert.doesNotMatch(sourceHtml, /OneFlow/);
  assert.doesNotMatch(sourceHtml, /DataFunTalk/);
  const archiveHtml = await archive.text();
  assert.match(archiveHtml, /历史周报/);
  assert.match(archiveHtml, /2026-W31/);
  assert.match(await department.text(), /L2/);
});

test("ships structured report, library and interaction controls", async () => {
  const [page, departmentDataText, library, sources] = await Promise.all([
    readFile(new URL("../app/components/DepartmentReport.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/department-data.json", import.meta.url), "utf8"),
    readFile(new URL("../app/library-data.json", import.meta.url), "utf8"),
    readFile(new URL("../app/source-data.json", import.meta.url), "utf8"),
  ]);
  const departmentPayload = JSON.parse(departmentDataText);
  const orbitinfer = departmentPayload.departments.find(
    (department) => department.id === "orbitinfer",
  );
  const payload = orbitinfer.currentReport;
  const libraryPayload = JSON.parse(library);
  const sourcePayload = JSON.parse(sources);

  assert.equal(departmentPayload.departments.length, 3);
  assert.equal(orbitinfer.enabled, true);
  assert.equal(payload.issue.isoWeek, "2026-W32");
  assert.equal(payload.issue.itemCount, 8);
  const modelDepartment = departmentPayload.departments.find(
    (department) => department.id === "model_and_application",
  );
  assert.equal(modelDepartment.currentReport.issue.itemCount, 8);
  assert.equal(
    departmentPayload.departments.reduce(
      (total, department) => total + department.currentReport.issue.itemCount,
      0,
    ),
    16,
  );
  const renderedItemCount = payload.sections.reduce(
    (count, section) => count + section.items.length,
    0,
  );
  assert.equal(payload.issue.itemCount, renderedItemCount);
  assert.ok(payload.issue.itemCount > 0);
  assert.ok(payload.sections.length >= 1);
  assert.ok(payload.sections.every((section) => Array.isArray(section.items)));
  assert.ok(
    payload.sections.some((section) =>
      section.items.some((item) => item.deepRead?.problemZh),
    ),
  );
  assert.match(page, /useState/);
  assert.match(page, /setActiveSection/);
  assert.match(page, /setQuery/);
  assert.match(page, /target="_blank"/);
  assert.ok(libraryPayload.papers.length >= 8);
  assert.equal(sourcePayload.accounts.length, 7);
  assert.ok(sourcePayload.accounts.every((account) => account.articles.length > 0));
  assert.equal(orbitinfer.archive[0].issue.isoWeek, "2026-W32");
});

test("exports a GitHub Pages-compatible static snapshot", async () => {
  const [home, orbitinfer, archive, library, sources] = await Promise.all([
    readFile(new URL("../out/index.html", import.meta.url), "utf8"),
    readFile(
      new URL("../out/departments/orbitinfer/index.html", import.meta.url),
      "utf8",
    ),
    readFile(new URL("../out/archive/index.html", import.meta.url), "utf8"),
    readFile(new URL("../out/library/index.html", import.meta.url), "utf8"),
    readFile(new URL("../out/sources/index.html", import.meta.url), "utf8"),
  ]);
  assert.match(home, /\/weekly_report\/assets\//);
  assert.match(home, /href="\/weekly_report\/departments\/orbitinfer"/);
  assert.doesNotMatch(home, /weekly_report\/weekly_report/);
  assert.match(orbitinfer, /本周趋势雷达/);
  assert.match(archive, /历史周报/);
  assert.match(library, /固定顶会覆盖/);
  assert.match(sources, /本周值得关注的进展/);
});
