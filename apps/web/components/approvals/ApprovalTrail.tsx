import { Chip } from "@/components/biz/Chip"
import { Tag } from "@/components/biz/Tag"
import { formatRelative } from "@/lib/format"
import { APPROVAL_STATUS_META, labelOf } from "@/lib/labels"
import type { ApprovalBrief } from "@/types/api"

/** 审批流转：什么时候提交、为什么要审批、现在谁在处理 / 谁什么时候通过或驳回、意见 */
export function ApprovalTrail({ approvals }: { approvals: ApprovalBrief[] }) {
  return (
    <ol className="divide-y divide-zinc-100 rounded-lg border border-zinc-200">
      {approvals.map((a) => {
        const m = labelOf(APPROVAL_STATUS_META, a.status)
        const who = a.status === "pending" ? a.handler : a.approver
        return (
          <li key={a.id} className="space-y-1.5 px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <Tag color={m.color}>{m.label}</Tag>
              {who ? <Chip name={who.name} /> : null}
              <span className="text-xs text-zinc-500">
                {a.status === "pending" ? (who ? "正在处理" : "等待主管处理") : formatRelative(a.decided_at)}
              </span>
              <span className="flex-1" />
              {a.submitted_at ? (
                <span className="text-xs text-zinc-400">{formatRelative(a.submitted_at)}提交</span>
              ) : null}
            </div>
            <div className="whitespace-pre-line text-zinc-700">触发原因：{a.reason}</div>
            {a.comment ? <div className="whitespace-pre-line text-zinc-500">审批意见：{a.comment}</div> : null}
          </li>
        )
      })}
    </ol>
  )
}
