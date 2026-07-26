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

test("server-renders the OrbitInfer weekly report", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>OrbitInfer Weekly Intelligence<\/title>/i);
  assert.match(html, /星载大模型/);
  assert.match(html, /本周趋势雷达/);
  assert.match(html, /2026-W30/);
  assert.match(html, /20<\/strong><span>精选条目/);
  assert.match(html, /og:image/);
  assert.match(html, /查看一手来源/);
  assert.doesNotMatch(html, /Your site is taking shape|Building your site/);
});

test("ships structured report data and interaction controls", async () => {
  const [page, report] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/report-data.json", import.meta.url), "utf8"),
  ]);
  const payload = JSON.parse(report);

  assert.equal(payload.issue.isoWeek, "2026-W30");
  assert.equal(payload.issue.itemCount, 20);
  assert.ok(payload.sections.length >= 5);
  assert.ok(payload.sections.every((section) => Array.isArray(section.items)));
  assert.match(page, /useState/);
  assert.match(page, /setActiveSection/);
  assert.match(page, /setQuery/);
  assert.match(page, /target="_blank"/);
});
