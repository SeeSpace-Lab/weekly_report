"use client";

import { useMemo, useState } from "react";
import libraryData from "../library-data.json";

const topicNames: Record<string, string> = {
  inference_runtime: "推理 Runtime",
  inference_scheduling: "推理调度",
  kv_cache: "KV Cache",
  distributed_inference: "分布式推理",
  storage_and_migration: "存储与迁移",
};

export default function PaperLibraryPage() {
  const [query, setQuery] = useState("");
  const [topic, setTopic] = useState("all");
  const topics = Array.from(new Set(libraryData.papers.map((paper) => paper.topic)));
  const papers = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    return libraryData.papers.filter((paper) => {
      if (topic !== "all" && paper.topic !== topic) return false;
      if (!normalized) return true;
      return `${paper.title} ${paper.titleZh} ${paper.venue} ${paper.oneSentenceZh}`
        .toLocaleLowerCase()
        .includes(normalized);
    });
  }, [query, topic]);

  return (
    <main className="libraryPage">
      <header className="topbar">
        <a className="brand" href="/">
          <span className="brandMark">KB</span>
          <span><b>顶会与重要论文库</b><small>ORBITINFER KNOWLEDGE BASE</small></span>
        </a>
        <nav className="portalNav">
          <a href="/">总览</a>
          <a href="/">部门周报</a>
          <a href="/archive">历史周报</a>
          <a href="/sources">公众号</a>
        </nav>
        <div className="issueStatus"><span className="pulse" />固定库 v{libraryData.version}</div>
      </header>

      <section className="libraryHero">
        <p className="kicker">ROLLING RESEARCH KNOWLEDGE BASE</p>
        <h1>追踪关键工作的演进<br /><em>建立可复用的研究坐标</em></h1>
        <p>持续收录近两年相关顶会论文、重要版本与少量奠基工作，并关联中文解读和开源实现。</p>
      </section>

      <section className="libraryControls">
        <div className="sectionTabs">
          <button className={topic === "all" ? "active" : ""} onClick={() => setTopic("all")}>全部</button>
          {topics.map((value) => (
            <button key={value} className={topic === value ? "active" : ""} onClick={() => setTopic(value)}>
              {topicNames[value] ?? value}
            </button>
          ))}
        </div>
        <label className="searchBox">
          <span>SEARCH</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="论文、会议或方向" />
        </label>
      </section>

      <section className="venueCoverage">
        <div>
          <p className="kicker">VENUE COVERAGE</p>
          <h2>固定顶会覆盖</h2>
        </div>
        <div className="venueChips">
          {libraryData.venues.map((venue) => (
            <span className={venue.coverage === "fixed" ? "fixedVenue" : ""} key={venue.id}>
              {venue.name}
            </span>
          ))}
        </div>
      </section>

      <section className="paperLibraryGrid">
        {papers.map((paper, index) => (
          <article className="libraryCard" key={paper.id}>
            <div className="libraryMeta">
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{paper.venue}</strong>
              <span>{topicNames[paper.topic] ?? paper.topic}</span>
            </div>
            <h2><a href={paper.url} target="_blank" rel="noreferrer">{paper.titleZh}</a></h2>
            <p className="originalTitle">{paper.title}</p>
            <p className="oneSentence">{paper.oneSentenceZh}</p>
            <div className="implication">
              <span>为什么进入固定库</span>
              <p>{paper.whyItMattersZh}</p>
            </div>
            <div className="librarySignals">
              <span>{paper.status}</span>
              {paper.famousException && <span>著名论文例外</span>}
              {paper.versionCount > 1 && <span>{paper.versionCount} 个版本</span>}
            </div>
            {paper.interpretations.length > 0 && (
              <div className="interpretations">
                <b>中文解读附件</b>
                {paper.interpretations.map((item) => (
                  <a key={item.url} href={item.url ?? "#"} target="_blank" rel="noreferrer">{item.title} ↗</a>
                ))}
              </div>
            )}
            <div className="libraryLinks">
              <a href={paper.url} target="_blank" rel="noreferrer">正式论文 ↗</a>
              {paper.codeUrl && <a href={paper.codeUrl} target="_blank" rel="noreferrer">开源代码 ↗</a>}
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}
