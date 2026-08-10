import departmentData from "./department-data.json";
import libraryData from "./library-data.json";
import sourceData from "./source-data.json";
import type { Report } from "./components/DepartmentReport";

type DepartmentEntry = {
  id: string;
  slug: string;
  name: string;
  enabled: boolean;
  status: string;
  mission: string;
  page: {
    headline?: string[];
    description?: string;
  };
  currentReport: Report | null;
};

const departments =
  departmentData.departments as unknown as DepartmentEntry[];
const primaryDepartment =
  departments.find((department) => department.enabled && department.currentReport) ??
  departments[0];
const reportData = primaryDepartment?.currentReport ?? null;

export default function PortalHome() {
  const collectedSources = sourceData.accounts.filter(
    (account) => account.inWindow > 0,
  );
  const weeklyItemCount = departments.reduce((departmentTotal, department) => {
    const report = department.currentReport;
    if (!report) return departmentTotal;
    return (
      departmentTotal +
      report.sections
        .filter(
          (section) =>
            !["venue_updates", "library_review"].includes(section.id),
        )
        .reduce((total, section) => total + section.items.length, 0)
    );
  }, 0);
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
          {reportData?.issue.status === "approved" ||
          reportData?.issue.status === "published"
            ? "本期已审核"
            : "私域审核"}
        </div>
      </header>

      <section className="portalHero">
        <p className="kicker">GUANYU AI · R&amp;D WEEKLY</p>
        <h1>观宇芯算<br /><em>研发部周报</em></h1>
        <div className="portalTimeline">
          <strong>{reportData?.issue.isoWeek ?? "尚未生成"}</strong>
          <span>
            {reportData
              ? `${date(reportData.issue.windowStart)}—${date(reportData.issue.windowEnd)}`
              : "等待首期周报"}
          </span>
          <span>周一 09:00 更新</span>
          <span>
            {reportData?.issue.status === "published"
              ? "已发布"
              : reportData?.issue.status === "approved"
                ? "审核通过 · 待公开发布"
                : "内部审核中"}
          </span>
        </div>
        <div className="portalMetrics">
          <div><strong>{departments.length}</strong><span>部门入口</span></div>
          <div><strong>{weeklyItemCount}</strong><span>本周精选</span></div>
          <div><strong>{libraryData.papers.length}</strong><span>固定论文库</span></div>
          <div><strong>{collectedSources.length}</strong><span>本周公众号</span></div>
        </div>
      </section>

      <section className="departmentDirectory">
        <div className="directoryIntro">
          <p className="kicker">DEPARTMENT RADAR</p>
          <h2>按部门进入周报</h2>
          <p>不同部门拥有独立的研究边界、选稿权重和周报板块，共享论文、框架、Benchmark 与公众号证据库。</p>
        </div>
        <div className="departmentCards">
          {departments.map((department, index) => {
            const report = department.currentReport;
            const headline =
              department.page.headline ?? [department.name];
            const status = !department.enabled
              ? "范围待确认"
              : report?.issue.status === "published"
                ? "本周已发布"
                : report?.issue.status === "approved"
                  ? "本周审核通过"
                  : report
                    ? "本周已生成 · 审核中"
                    : "已启用 · 等待首期周报";
            return (
              <a
                className={`departmentCard ${
                  department.enabled
                    ? "activeDepartment"
                    : "pendingDepartment"
                }`}
                href={`/departments/${department.slug}`}
                key={department.id}
              >
                <div className="departmentNumber">
                  {String(index + 1).padStart(2, "0")}
                </div>
                <span className="statusTag">{status}</span>
                <h3>
                  {headline.map((line, lineIndex) => (
                    <span key={line}>
                      {line}
                      {lineIndex < headline.length - 1 && <br />}
                    </span>
                  ))}
                </h3>
                <p>{department.page.description ?? department.mission}</p>
                <dl>
                  <div>
                    <dt>周期</dt>
                    <dd>{report?.issue.isoWeek ?? "尚未生成"}</dd>
                  </div>
                  <div>
                    <dt>阅读</dt>
                    <dd>
                      {report
                        ? `${report.issue.estimatedReadMinutes} 分钟`
                        : "等待配置"}
                    </dd>
                  </div>
                </dl>
                <span className="enterLink">
                  {department.enabled ? "进入部门周报" : "查看范围占位"} ↗
                </span>
              </a>
            );
          })}
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
