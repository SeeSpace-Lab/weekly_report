"use client";

import { useMemo, useState } from "react";
import departmentData from "../department-data.json";
import type { Report } from "../components/DepartmentReport";

type DepartmentArchive = {
  id: string;
  slug: string;
  name: string;
  archive: Report[];
};

const departments = (
  departmentData.departments as unknown as DepartmentArchive[]
).filter((department) => department.archive.length > 0);

const sectionNames: Record<string, string> = {
  must_read: "本周必读",
  inference_and_scheduling: "推理引擎与调度",
  kv_storage_moe_quantization: "KV Cache · MoE · 量化",
  power_reliability_edge_distributed: "功耗 · 可靠性 · 边缘",
  frameworks_benchmarks_datasets: "框架 · Benchmark · 数据集",
};

function readableDate(value: string) {
  return value.slice(0, 10).replaceAll("-", ".");
}

export default function ArchivePage() {
  const [selectedDepartment, setSelectedDepartment] = useState(
    departments[0]?.slug ?? "",
  );
  const department =
    departments.find((entry) => entry.slug === selectedDepartment) ??
    departments[0];
  const [selectedWeek, setSelectedWeek] = useState(
    department?.archive[0]?.issue.isoWeek ?? "",
  );
  const report = useMemo(
    () =>
      department?.archive.find(
        (issue) => issue.issue.isoWeek === selectedWeek,
      ) ?? department?.archive[0],
    [department, selectedWeek],
  );

  if (!department || !report) {
    return <main className="emptyState">尚无历史周报。</main>;
  }

  const sections = report.sections.filter(
    (section) => !["venue_updates", "library_review"].includes(section.id),
  );
  const itemCount = sections.reduce(
    (total, section) => total + section.items.length,
    0,
  );

  return (
    <main className="archivePage">
      <header className="topbar">
        <a className="brand" href="/">
          <span className="brandMark">AR</span>
          <span><b>历史周报</b><small>WEEKLY ARCHIVE</small></span>
        </a>
        <nav className="portalNav">
          <a href="/">总览</a>
          <a href={`/departments/${department.slug}`}>最新周报</a>
          <a href="/library">论文库</a>
          <a href="/sources">公众号</a>
        </nav>
        <div className="issueStatus"><span className="pulse" />{department.archive.length} 期存档</div>
      </header>

      <section className="archiveHero">
        <div>
          <p className="kicker">{department.name} · WEEKLY ARCHIVE</p>
          <h1>历史周报</h1>
          <p>{readableDate(report.issue.windowStart)}—{readableDate(report.issue.windowEnd)} · {itemCount} 项精选</p>
        </div>
        <label>
          <span>选择部门与周次</span>
          <select
            value={department.slug}
            onChange={(event) => {
              const next = departments.find(
                (entry) => entry.slug === event.target.value,
              );
              setSelectedDepartment(event.target.value);
              setSelectedWeek(next?.archive[0]?.issue.isoWeek ?? "");
            }}
          >
            {departments.map((entry) => (
              <option key={entry.id} value={entry.slug}>
                {entry.name}
              </option>
            ))}
          </select>
          <select value={selectedWeek} onChange={(event) => setSelectedWeek(event.target.value)}>
            {department.archive.map((issue) => (
              <option key={issue.issue.id} value={issue.issue.isoWeek}>
                {issue.issue.isoWeek} · {issue.issue.status}
              </option>
            ))}
          </select>
        </label>
      </section>

      <section className="archiveContent">
        {sections.map((section) => (
          <section className="archiveSection" key={section.id}>
            <div className="sectionHeading">
              <div>
                <p className="kicker">CURATED INTELLIGENCE</p>
                <h2>{sectionNames[section.id] ?? section.id}</h2>
              </div>
              <small>{section.items.length} ITEMS</small>
            </div>
            <div className="archiveGrid">
              {section.items.map((item) => (
                <article className="archiveCard" key={`${section.id}-${item.position}`}>
                  <div className="cardMeta">
                    <span>{item.itemType}</span>
                    <span>{item.readMinutes} MIN</span>
                  </div>
                  <h3><a href={item.url ?? "#"} target="_blank" rel="noreferrer">{item.title}</a></h3>
                  {item.deepRead?.titleZh && <p className="translatedTitle">{item.deepRead.titleZh}</p>}
                  <p className="oneSentence">
                    {item.deepRead?.oneSentenceZh ?? item.summary ?? "摘要待补充。"}
                  </p>
                  <a className="sourceLink" href={item.url ?? "#"} target="_blank" rel="noreferrer">
                    查看一手来源 <span>↗</span>
                  </a>
                </article>
              ))}
            </div>
          </section>
        ))}
      </section>
    </main>
  );
}
