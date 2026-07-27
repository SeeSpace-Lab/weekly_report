import { notFound } from "next/navigation";

import departmentData from "../../department-data.json";
import DepartmentReport, {
  type Report,
} from "../../components/DepartmentReport";

type DepartmentEntry = {
  id: string;
  slug: string;
  name: string;
  enabled: boolean;
  status: string;
  mission: string;
  page: {
    brand_mark?: string;
    eyebrow?: string;
    headline?: string[];
    description?: string;
  };
  coreTopics: Array<{ id: string; label: string }>;
  adjacentTopics: string[];
  activationRequirements: string[];
  sectionLabels: Record<string, string>;
  currentReport: Report | null;
};

const departments =
  departmentData.departments as unknown as DepartmentEntry[];

export default async function DepartmentPage({
  params,
}: {
  params: Promise<{ department: string }>;
}) {
  const { department: slug } = await params;
  const department = departments.find((entry) => entry.slug === slug);
  if (!department) notFound();

  if (department.enabled && department.currentReport) {
    return (
      <DepartmentReport
        department={department}
        report={department.currentReport}
      />
    );
  }

  const headline = department.page.headline ?? [department.name];
  const requirements = department.activationRequirements.length
    ? department.activationRequirements
    : [
        "确认部门使命、核心主题和排除边界",
        "选择论文、代码、数据集和公众号来源",
        "指定内容负责人和发布审核团队",
      ];

  return (
    <main className="placeholderPage">
      <header className="topbar">
        <a className="brand" href="/">
          <span className="brandMark">
            {department.page.brand_mark ?? department.name.slice(0, 2)}
          </span>
          <span>
            <b>{department.name}</b>
            <small>
              {department.page.eyebrow ?? "DEPARTMENT WEEKLY"}
            </small>
          </span>
        </a>
        <nav className="portalNav">
          <a href="/">总览</a>
          <a href="/archive">历史周报</a>
          <a href="/library">论文库</a>
          <a href="/sources">公众号</a>
        </nav>
        <div className="issueStatus">
          <span className="pulse mutedPulse" />
          {department.status === "scope_pending"
            ? "范围待确认"
            : "尚未生成周报"}
        </div>
      </header>

      <section className="placeholderHero">
        <p className="kicker">
          {department.page.eyebrow ?? "DEPARTMENT SCOPE"}
        </p>
        <h1>
          {headline.map((line, index) => (
            <span key={line}>
              {index === headline.length - 1 ? <em>{line}</em> : line}
              {index < headline.length - 1 && <br />}
            </span>
          ))}
        </h1>
        <p>{department.page.description ?? department.mission}</p>
      </section>

      <section className="scopeChecklist">
        <div>
          <span>SCOPE</span>
          <h2>当前范围</h2>
          <ul>
            <li>{department.mission}</li>
            {department.coreTopics.map((topic) => (
              <li key={topic.id}>{topic.label}</li>
            ))}
          </ul>
        </div>
        <div>
          <span>ACTIVATION</span>
          <h2>启用前需要</h2>
          <ul>
            {requirements.map((requirement) => (
              <li key={requirement}>{requirement}</li>
            ))}
          </ul>
        </div>
      </section>
    </main>
  );
}
