"use client"

import { Clock, GraduationCap, LayoutDashboard, Plus, Sparkles, Target, Trophy, Wallet } from "lucide-react"
import { useEffect, useState } from "react"

import { QueryError } from "@/components/biz/QueryStatus"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"
import { StatCard } from "@/components/biz/StatCard"
import { pendingCardHint, pendingCardHref } from "@/lib/approvals"
import { ActivityFeed } from "@/components/dashboard/ActivityFeed"
import { FunnelChart } from "@/components/dashboard/FunnelChart"
import { PipelineOverview } from "@/components/dashboard/PipelineOverview"
import { TodoCard } from "@/components/dashboard/TodoCard"
import { useSession } from "@/components/shell/SessionProvider"
import { useDashboard } from "@/hooks/useDashboard"
import { usePermissions } from "@/hooks/usePermissions"
import { formatFen, formatPercent } from "@/lib/format"
import { todoSummary } from "@/lib/tasks"
import { defaultScope } from "@/lib/views"

function greeting(now: Date = new Date()): string {
  const h = now.getHours()
  if (h < 11) return "上午好"
  if (h < 13) return "中午好"
  if (h < 18) return "下午好"
  return "晚上好"
}

/** 问候语按浏览器本地时间算；服务端（容器是 UTC）先渲染「你好」，避免两边文字不一致报 hydration 错误 */
function useGreeting(): string {
  const [g, setG] = useState("你好")
  useEffect(() => setG(greeting()), [])
  return g
}

/** 本月成交卡片的说明：设了目标显示完成率，否则说明口径 */
function targetHint(won: number | undefined, target: number | null | undefined): string {
  if (!target || won === undefined) return "按本月新签合同"
  return `目标 ${formatFen(target)} · 完成 ${formatPercent(won / target, 0)}`
}

/** 工作台：StatCard ×4、FunnelChart、待办（TodoCard）、ActivityFeed、PipelineOverview */
export default function DashboardPage() {
  const { role, user, isLead, solo } = useSession()
  const hello = useGreeting()
  const { canAiWrite } = usePermissions()
  const view = defaultScope(role)
  const query = useDashboard(view)
  const d = query.data
  // 个人模式：只有自己，不叫「团队」
  const prefix = role === "admin" ? "全公司" : isLead && !solo ? "团队" : ""
  const loading = query.isPending
  const summary = todoSummary(d?.tasks_today, d?.tasks_overdue)
  // 主管 / 管理员看到的是团队（全公司）的任务，不是自己的
  const todo = summary && prefix ? `${prefix}${summary}` : summary

  const cards = [
    // 与合同页「本月成交」同一口径：本月新签合同金额
    {
      label: `${prefix}本月成交`,
      value: formatFen(d?.won_amount_month),
      hint: targetHint(d?.won_amount_month, d?.target_month),
      icon: Trophy,
      href: "/contracts",
    },
    {
      label: `${prefix}进行中商机`,
      value: String(d?.open_opportunities ?? "—"),
      hint: d ? `预计 ${formatFen(d.open_amount)}` : undefined,
      icon: Target,
      href: "/pipeline",
    },
    // 个人模式不走审批，不显示这张卡
    ...(solo
      ? []
      : [
          {
            label: role === "manager" ? "待我审批" : role === "admin" ? "待审批" : "审批中",
            value: String(d?.pending_approvals ?? "—"),
            hint: pendingCardHint(role, d),
            icon: Clock,
            href: pendingCardHref(role, d),
          },
        ]),
    {
      label: `${prefix}本月预估提成`,
      value: formatFen(d?.estimated_commission_month),
      hint: d ? `已确认 ${formatFen(d.confirmed_commission_month)}` : undefined,
      icon: Wallet,
      href: "/contracts",
    },
  ]

  return (
    <PageFrame
      title="工作台"
      icon={LayoutDashboard}
      actions={
        <>
          {canAiWrite ? (
            <>
              <FrameAction icon={GraduationCap} label="学习问答" href="/ai?mode=learn" />
              <FrameAction icon={Plus} label="出方案" href="/ai?mode=work" primary />
            </>
          ) : (
            <FrameAction icon={Sparkles} label="问 AI" href="/ai" />
          )}
        </>
      }
    >
      <div className="flex-1 overflow-x-hidden overflow-y-auto p-4 sm:p-5">
        <div className="mb-4">
          <div className="text-lg font-semibold">
            {hello}，{user.name}
          </div>
          <div className="mt-0.5 text-zinc-500">
            {isLead ? `${user.scope} · 本月销售概况` : "本月销售概况"}
            {todo ? ` · ${todo}` : ""}
          </div>
        </div>
        {query.isError && !d ? (
          <div className="mb-3 rounded-lg border border-zinc-200">
            <QueryError
              error={query.error}
              onRetry={() => void query.refetch()}
              retrying={query.isFetching}
              feature="工作台"
            />
          </div>
        ) : (
          <div className="mb-3 grid grid-cols-2 gap-3 xl:grid-cols-4">
            {cards.map((c) => (
              <StatCard key={c.label} {...c} loading={loading} />
            ))}
          </div>
        )}
        <div className="mb-3 grid grid-cols-1 gap-3 lg:grid-cols-3">
          <FunnelChart
            stages={d?.funnel}
            loading={loading}
            onRetry={query.isError && !d ? () => void query.refetch() : undefined}
          />
          <TodoCard view={view} title={`${prefix}待办`} />
        </div>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
          <div className="min-w-0 lg:col-span-2">
            <ActivityFeed view={view} isLead={isLead} scope={user.scope} />
          </div>
          <div className="min-w-0">
            <PipelineOverview view={view} />
          </div>
        </div>
      </div>
    </PageFrame>
  )
}
