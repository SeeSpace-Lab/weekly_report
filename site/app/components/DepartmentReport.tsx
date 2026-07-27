"use client";

import { useState } from "react";
import ApprovalPanel from "./ApprovalPanel";

type DeepRead = {
  titleZh: string;
  oneSentenceZh: string;
  problemZh: string;
  methodZh: string;
  resultZh: string;
  contributions: string[];
  evidence: string[];
  limitations: string[];
  confidence: number;
  modelVersion: string;
};

export type ReportItem = {
  position: number;
  role: string;
  itemType: string;
  title: string;
  url: string | null;
  reason: string;
  summary: string | null;
  implication: string | null;
  readMinutes: number;
  publishedAt: string | null;
  updatedAt: string | null;
  status: string | null;
  deepRead?: DeepRead | null;
};

export type Report = {
  issue: {
    id: string;
    departmentId: string;
    title: string;
    isoWeek: string;
    windowStart: string;
    windowEnd: string;
    status: string;
    targetReadMinutes: number;
    estimatedReadMinutes: number;
    itemCount: number;
  };
  trends: string[];
  sections: Array<{ id: string; items: ReportItem[] }>;
};

const defaultSectionNames: Record<string, string> = {
  must_read: "本周必读",
  inference_and_scheduling: "推理引擎与调度",
  kv_storage_moe_quantization: "KV Cache · MoE · 量化",
  power_reliability_edge_distributed: "功耗 · 可靠性 · 边缘",
  frameworks_benchmarks_datasets: "框架 · Benchmark · 数据集",
};

const roleNames: Record<string, string> = {
  must_read: "MUST READ",
  deep_read: "DEEP READ",
  quick_scan: "QUICK SCAN",
  library_review: "LIBRARY",
};

function readableDate(value: string | null) {
  if (!value) return "日期待确认";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

function plainSummary(value: string | null) {
  if (!value) return "该条目的结构化摘要尚待补充。";
  return value
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/[#*_`>\[\]\r\n]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

type DepartmentPresentation = {
  id: string;
  name: string;
  page: {
    brand_mark?: string;
    eyebrow?: string;
    headline?: string[];
    description?: string;
  };
  sectionLabels: Record<string, string>;
};

export default function DepartmentReport({
  department,
  report,
}: {
  department: DepartmentPresentation;
  report: Report;
}) {
  const [activeSection, setActiveSection] = useState("all");
  const [query, setQuery] = useState("");
  const sectionNames = {
    ...defaultSectionNames,
    ...department.sectionLabels,
  };
  const weeklySections = report.sections.filter(
    (section) =>
      !["venue_updates", "library_review"].includes(section.id),
  );
  const normalized = query.trim().toLocaleLowerCase();
  const sections = weeklySections
    .filter(
      (section) => activeSection === "all" || section.id === activeSection,
    )
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => {
        if (!normalized) return true;
        return `${item.title} ${item.reason} ${item.summary ?? ""} ${
          item.deepRead?.titleZh ?? ""
        } ${item.deepRead?.oneSentenceZh ?? ""}`
          .toLocaleLowerCase()
          .includes(normalized);
      }),
    }))
    .filter((section) => section.items.length > 0);
  const itemCount = weeklySections.reduce(
    (total, section) => total + section.items.length,
    0,
  );
  const headline = department.page.headline ?? [department.name];
  const brandMark =
    department.page.brand_mark ?? department.name.slice(0, 2);

  return (
    <main>
      <header className="topbar">
        <a className="brand" href="/" aria-label="返回研发部周报总览">
          <span className="brandMark">{brandMark}</span>
          <span>
            <b>{department.name}</b>
            <small>
              {department.page.eyebrow ?? "WEEKLY INTELLIGENCE"}
            </small>
          </span>
        </a>
        <nav className="portalNav" aria-label="研发部周报导航">
          <a href="/">总览</a>
          <a href="/archive">历史周报</a>
          <a href="/library">论文库</a>
          <a href="/sources">公众号</a>
        </nav>
        <div className="issueStatus">
          <span className="pulse" />
          {report.issue.status === "published"
            ? "已发布"
            : report.issue.status === "approved"
              ? "审核通过 · 待公开发布"
              : "研究员审核中"}
        </div>
      </header>

      <section className="hero" id="top">
        <div className="eyebrow">
          <span>{report.issue.isoWeek}</span>
          <span>RESEARCH RADAR / 01</span>
        </div>
        <h1>
          {headline.map((line, index) => (
            <span key={line}>
              {index === headline.length - 1 ? <em>{line}</em> : line}
              {index < headline.length - 1 && <br />}
            </span>
          ))}
          周报
        </h1>
        <p className="heroLead">
          {department.page.description ?? department.name}
        </p>
        <div className="metrics" aria-label="本期统计">
          <div>
            <strong>{itemCount}</strong>
            <span>精选条目</span>
          </div>
          <div>
            <strong>{report.issue.estimatedReadMinutes}</strong>
            <span>预计分钟</span>
          </div>
          <div>
            <strong>{report.trends.length}</strong>
            <span>趋势信号</span>
          </div>
          <div>
            <strong>{readableDate(report.issue.windowEnd).replace("年", ".")}</strong>
            <span>数据截至</span>
          </div>
        </div>
      </section>

      <ApprovalPanel
        departmentId={department.id}
        status={report.issue.status}
        isoWeek={report.issue.isoWeek}
      />

      <section className="trendPanel" aria-labelledby="trend-title">
        <div className="sectionIndex">01</div>
        <div>
          <p className="kicker">SIGNAL MAP</p>
          <h2 id="trend-title">本周趋势雷达</h2>
        </div>
        <ol>
          {report.trends.map((trend, index) => (
            <li key={trend}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              {trend}
            </li>
          ))}
        </ol>
      </section>

      <section className="contentShell">
        <div className="filterBar">
          <div className="sectionTabs" aria-label="按板块筛选">
            <button
              className={activeSection === "all" ? "active" : ""}
              onClick={() => setActiveSection("all")}
            >
              全部
            </button>
            {weeklySections.map((section) => (
              <button
                key={section.id}
                className={activeSection === section.id ? "active" : ""}
                onClick={() => setActiveSection(section.id)}
              >
                {sectionNames[section.id] ?? section.id}
              </button>
            ))}
          </div>
          <label className="searchBox">
            <span>SEARCH</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="检索论文、框架或方向"
              aria-label="检索周报内容"
            />
          </label>
        </div>

        {sections.length ? (
          sections.map((section, sectionIndex) => (
            <section className="reportSection" key={section.id}>
              <div className="sectionHeading">
                <span>{String(sectionIndex + 2).padStart(2, "0")}</span>
                <div>
                  <p className="kicker">CURATED INTELLIGENCE</p>
                  <h2>{sectionNames[section.id] ?? section.id}</h2>
                </div>
                <small>{section.items.length} ITEMS</small>
              </div>
              <div className="cardGrid">
                {section.items.map((item) => {
                  const summary = plainSummary(item.summary);
                  const deepRead = item.deepRead;
                  return (
                    <article className="intelCard" key={`${section.id}-${item.position}`}>
                      <div className="cardMeta">
                        <span className={`role role-${item.role}`}>
                          {roleNames[item.role] ?? item.role}
                        </span>
                        <span>{item.readMinutes} MIN</span>
                        <span>{readableDate(item.updatedAt)}</span>
                      </div>
                      <h3>
                        <a href={item.url ?? "#"} target="_blank" rel="noreferrer">
                          {item.title}
                        </a>
                      </h3>
                      {deepRead?.titleZh && deepRead.titleZh !== item.title && (
                        <p className="translatedTitle">{deepRead.titleZh}</p>
                      )}
                      {item.status && <p className="statusTag">{item.status}</p>}
                      {deepRead ? (
                        <div className="deepRead">
                          <p className="oneSentence">{deepRead.oneSentenceZh}</p>
                          <dl>
                            <div>
                              <dt>问题</dt>
                              <dd>{deepRead.problemZh}</dd>
                            </div>
                            <div>
                              <dt>方法</dt>
                              <dd>{deepRead.methodZh}</dd>
                            </div>
                            <div>
                              <dt>结果</dt>
                              <dd>{deepRead.resultZh}</dd>
                            </div>
                          </dl>
                          {!!deepRead.evidence.length && (
                            <details className="evidencePanel">
                              <summary>证据与局限</summary>
                              <ul>
                                {deepRead.evidence.map((evidence) => (
                                  <li key={evidence}>{evidence}</li>
                                ))}
                              </ul>
                              {!!deepRead.limitations.length && (
                                <p>
                                  <b>局限：</b>
                                  {deepRead.limitations.join("；")}
                                </p>
                              )}
                            </details>
                          )}
                        </div>
                      ) : (
                        <p className="summary">
                          {summary.length > 560 ? `${summary.slice(0, 560)}…` : summary}
                        </p>
                      )}
                      <div className="implication">
                        <span>部门意义</span>
                        <p>{item.implication}</p>
                      </div>
                      <a className="sourceLink" href={item.url ?? "#"} target="_blank" rel="noreferrer">
                        查看一手来源 <span aria-hidden="true">↗</span>
                      </a>
                    </article>
                  );
                })}
              </div>
            </section>
          ))
        ) : (
          <div className="emptyState">
            <p>没有匹配当前筛选条件的条目。</p>
            <button onClick={() => { setQuery(""); setActiveSection("all"); }}>
              清除筛选
            </button>
          </div>
        )}
      </section>

      <footer>
        <div>
          <span className="brandMark">{brandMark}</span>
          <p>{department.name} · 自动化研究情报系统</p>
        </div>
        <p>
          自动生成，发布前需经研究员核验。时间窗口：
          {readableDate(report.issue.windowStart)} — {readableDate(report.issue.windowEnd)}
        </p>
      </footer>
    </main>
  );
}
