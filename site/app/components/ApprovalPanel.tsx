"use client";

import { useState } from "react";

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
  const [state, setState] = useState<
    "idle" | "confirm" | "working" | "done" | "error"
  >(status === "approved" || status === "published" ? "done" : "idle");
  const [message, setMessage] = useState("");

  async function approve() {
    setState("working");
    setMessage("");
    try {
      const response = await fetch(
        "http://127.0.0.1:8010/api/review/approve?" +
          new URLSearchParams({ department: departmentId }),
        {
        method: "POST",
        },
      );
      const payload = (await response.json()) as {
        error?: string;
        blockers?: string[];
      };
      if (!response.ok) {
        throw new Error(
          payload.error ||
            payload.blockers?.join("；") ||
            `审核请求失败（HTTP ${response.status}）`,
        );
      }
      setState("done");
      setMessage("审核快照已同步，GitHub Pages 发布流程已经启动。");
      window.setTimeout(() => window.location.reload(), 1800);
    } catch (error) {
      setState("error");
      setMessage(error instanceof Error ? error.message : "审核同步失败");
    }
  }

  if (state === "done") {
    return (
      <aside className="approvalPanel approvalDone">
        <div>
          <span>APPROVAL GATE</span>
          <strong>{isoWeek} 已审核通过</strong>
          <p>
            审核快照已同步至 GitHub，Pages 正在自动构建并发布公开版本。
          </p>
        </div>
      </aside>
    );
  }

  return (
    <aside className="approvalPanel">
      <div>
        <span>APPROVAL GATE</span>
        <strong>{isoWeek} 私域审核</strong>
        <p>
          确认后将锁定本期内容、移除审核中标识，并把已批准快照同步到
          GitHub，随后自动触发 Pages 公开发布。
        </p>
      </div>
      <div className="approvalAction">
        {state === "confirm" ? (
          <>
            <p>请再次确认：当前页面内容可以作为本期公开版本。</p>
            <div>
              <button onClick={approve}>确认、同步并发布</button>
              <button
                className="secondaryButton"
                onClick={() => setState("idle")}
              >
                取消
              </button>
            </div>
          </>
        ) : (
          <button
            disabled={state === "working"}
            onClick={() => setState("confirm")}
          >
            {state === "working" ? "正在审核并同步…" : "确认本期周报"}
          </button>
        )}
        {message && (
          <p className={state === "error" ? "approvalError" : ""}>{message}</p>
        )}
      </div>
    </aside>
  );
}
