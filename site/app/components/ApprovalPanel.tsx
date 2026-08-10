type ApprovalPanelProps = {
  departmentId: string;
  status: string;
  isoWeek: string;
};

const REVIEW_PULL_REQUEST =
  "https://github.com/SeeSpace-Lab/weekly_report/pull/13";

export default function ApprovalPanel({
  departmentId,
  status,
  isoWeek,
}: ApprovalPanelProps) {
  if (status === "approved" || status === "published") {
    return (
      <aside className="approvalPanel approvalDone">
        <div>
          <span>APPROVAL GATE</span>
          <strong>{isoWeek} 已审核通过</strong>
          <p>该快照已经通过 GitHub Pull Request 审核。</p>
        </div>
      </aside>
    );
  }

  return (
    <aside className="approvalPanel">
      <div>
        <span>REMOTE REVIEW</span>
        <strong>{isoWeek} GitHub 远程审核</strong>
        <p>
          本页面是只读草稿。代码和周报只能从独立开发分支提交，并通过面向
          main 的 Pull Request 审核；页面不会直接推送受保护分支或发布
          GitHub Pages。
        </p>
      </div>
      <div className="approvalAction">
        <a
          className="approvalLinkButton"
          href={REVIEW_PULL_REQUEST}
          target="_blank"
          rel="noreferrer"
        >
          前往 GitHub PR 审核并合并 main
        </a>
      </div>
    </aside>
  );
}
