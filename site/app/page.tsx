import reportData from "./report-data.json";
import libraryData from "./library-data.json";
import sourceData from "./source-data.json";

export default function PortalHome() {
  const collectedSources = sourceData.accounts.filter(
    (account) => account.articles.length > 0,
  );
  const weeklyItemCount = reportData.sections
    .filter((section) => !["venue_updates", "library_review"].includes(section.id))
    .reduce((total, section) => total + section.items.length, 0);
  const date = (value: string) => value.slice(0, 10).replaceAll("-", ".");

  return (
    <main className="portalPage">
      <header className="topbar">
        <a className="brand" href="/" aria-label="观宇芯算研发部周报">
          <span className="brandMark">GY</span>
          <span>
            <b>观宇芯算研发部周报</b>
            <small>RESEARCH INTELLIGENCE PORTAL</small>
          </span>
        </a>
        <nav className="portalNav" aria-label="研发部周报导航">
          <a href="/archive">历史周报</a>
          <a href="/library">论文库</a>
          <a href="/sources">公众号</a>
        </nav>
        <div className="issueStatus">
          <span className="pulse" />
          私域审核
        </div>
      </header>

      <section className="portalHero">
        <p className="kicker">GUANYU AI · R&amp;D WEEKLY</p>
        <h1>观宇芯算<br /><em>研发部周报</em></h1>
        <div className="portalTimeline">
          <strong>{reportData.issue.isoWeek}</strong>
          <span>{date(reportData.issue.windowStart)}—{date(reportData.issue.windowEnd)}</span>
          <span>周一 09:00 更新</span>
          <span>{reportData.issue.status === "approved" ? "审核通过" : "内部审核中"}</span>
        </div>
        <div className="portalMetrics">
          <div><strong>2</strong><span>部门入口</span></div>
          <div><strong>{weeklyItemCount}</strong><span>本周精选</span></div>
          <div><strong>{libraryData.papers.length}</strong><span>固定论文库</span></div>
          <div><strong>{collectedSources.length}</strong><span>已采集公众号</span></div>
        </div>
      </section>

      <section className="departmentDirectory">
        <div className="directoryIntro">
          <p className="kicker">DEPARTMENT RADAR</p>
          <h2>按部门进入周报</h2>
          <p>不同部门拥有独立的研究边界、选稿权重和周报板块，共享论文、框架、Benchmark 与公众号证据库。</p>
        </div>
        <div className="departmentCards">
          <a className="departmentCard activeDepartment" href="/departments/orbitinfer">
            <div className="departmentNumber">01</div>
            <span className="statusTag">本周已生成 · 审核中</span>
            <h3>星载大模型<br />推理引擎</h3>
            <p>动态功率预算、推理调度、KV Cache、MoE Runtime、量化、可靠性与边缘分布式推理。</p>
            <dl>
              <div><dt>周期</dt><dd>{reportData.issue.isoWeek}</dd></div>
              <div><dt>阅读</dt><dd>{reportData.issue.estimatedReadMinutes} 分钟</dd></div>
            </dl>
            <span className="enterLink">进入部门周报 ↗</span>
          </a>
          <a className="departmentCard pendingDepartment" href="/departments/constellation-simulation">
            <div className="departmentNumber">02</div>
            <span className="statusTag">接口已保留 · 范围待确认</span>
            <h3>星座智算<br />仿真平台</h3>
            <p>先建立部门入口和数据契约；在获取项目资料后，再确定固定来源、关键词、顶会与选稿策略。</p>
            <dl>
              <div><dt>状态</dt><dd>未启动采集</dd></div>
              <div><dt>内容</dt><dd>不与其他部门混用</dd></div>
            </dl>
            <span className="enterLink">查看范围占位 ↗</span>
          </a>
        </div>
      </section>

      <section className="portalResources">
        <a href="/library">
          <span>KNOWLEDGE BASE / 01</span>
          <h2>顶会与重要论文库</h2>
          <p>近两年顶会论文、领域奠基工作、版本变化与 PaperWeekly 等中文解读附件。</p>
        </a>
        <a href="/sources">
          <span>SOURCE RADAR / 02</span>
          <h2>公众号订阅池</h2>
          <p>仅展示已经取得文章的 AI 与大模型来源，持续追踪最新解读与技术信号。</p>
        </a>
      </section>
    </main>
  );
}
