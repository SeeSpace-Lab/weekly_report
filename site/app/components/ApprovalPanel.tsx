type ApprovalPanelProps = {
  departmentId: string;
  status: string;
  isoWeek: string;
};

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
        <strong>{isoWeek} 公开只读审核</strong>
        <p>
          本页面仅用于负责人远程查看本期草稿，不会写入 GitHub、创建 Pull
          Request、修改审核状态或触发正式发布。审核意见请反馈给周报维护人。
        </p>
      </div>
      <div className="approvalAction">
        <span className="approvalLinkButton" aria-label="只读审核快照">
          只读审核快照
        </span>
      </div>
    </aside>
  );
}
