"use client"

import { Tag } from "@/components/biz/Tag"
import { useOpportunityRequirement } from "@/hooks/useRequirement"
import { formatFen, formatRelative } from "@/lib/format"
import { COMPLEXITIES, PLATFORMS } from "@/lib/requirement-card"

const PLATFORM_NAME = Object.fromEntries(PLATFORMS)
const COMPLEXITY_NAME = Object.fromEntries(COMPLEXITIES)

/** 商机侧栏：出方案时 AI 拆出并保存的需求清单（还没出过方案时不显示）；版式与「竞争对手」一致 */
export function RequirementSummary({ oppId }: { oppId: string }) {
  const { data } = useOpportunityRequirement(oppId)
  if (!data) return null
  const r = data.data
  const modules = r.modules ?? []
  return (
    <section aria-label="需求清单">
      <div className="mb-1.5 flex h-7 items-center gap-2">
        <h3 className="text-zinc-500">需求清单</h3>
        <Tag color={data.confirmed ? "green" : "yellow"}>{data.confirmed ? "已确认" : "待和客户确认"}</Tag>
        {data.price_low != null && data.price_high != null ? (
          <span className="ml-auto text-xs text-zinc-500 tabular-nums">
            粗估 {formatFen(data.price_low)}–{formatFen(data.price_high)}
          </span>
        ) : null}
      </div>
      <div className="space-y-2 text-sm">
        <div className="text-zinc-600">
          {(r.platforms ?? []).map((p) => PLATFORM_NAME[p] ?? p).join("、")}
          {r.team_size === 1 ? " · 个人全栈" : ""} · {modules.length} 个功能模块
        </div>
        <div className="flex flex-wrap gap-1">
          {modules.map((m) => (
            <span
              key={`${m.key}-${m.name}`}
              className="inline-flex h-6 items-center gap-1 rounded bg-zinc-100 px-1.5 text-xs text-zinc-700"
            >
              {m.name}
              <span className="text-zinc-400">
                {COMPLEXITY_NAME[m.complexity] ?? ""}
                {m.must === false ? " · 二期" : ""}
              </span>
            </span>
          ))}
        </div>
        {!data.confirmed && data.questions.length > 0 ? (
          <ol className="list-decimal space-y-0.5 pl-5 text-xs leading-5 text-zinc-500">
            {data.questions.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ol>
        ) : null}
        <div className="text-xs text-zinc-400">
          {data.updated_by ? `${data.updated_by} · ` : ""}
          {formatRelative(data.updated_at)}
          {data.confirmed ? "" : " · 点「出方案」继续确认"}
        </div>
      </div>
    </section>
  )
}
