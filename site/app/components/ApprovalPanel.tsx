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
          <strong>{isoWeek} 自动质量门禁已通过</strong>
          <p>该周报已完成篇数、阅读时间、中文细读和一手来源校验，可由 main 发布。</p>
        </div>
      </aside>
    );
  }

  return (
    <aside className="approvalPanel">
      <div>
        <span>AUTOMATED RELEASE</span>
        <strong>{isoWeek} 等待自动质量门禁</strong>
        <p>
          周报只有通过篇数、阅读时间、中文细读、一手来源和测试门禁后，才会直接
          提交并推送到 main；未通过时自动任务停止，不会发布不完整周报。
        </p>
      </div>
    </aside>
  );
}
