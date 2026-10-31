"use client"

import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { AlertTriangle, Gauge, ThumbsDown } from "lucide-react"
import Link from "next/link"
import { useState } from "react"

import { PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { RoleGate } from "@/components/shell/RoleGate"
import { useSession } from "@/components/shell/SessionProvider"
import { Skeleton } from "@/components/ui/skeleton"
import { useFeedbackReview } from "@/hooks/useAiFeedback"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"

type Period = "7d" | "30d" | "month"

export interface UsageRow {
  key: string
  label: string
  calls: number
  prompt_tokens: number
  completion_tokens: number
  cost: number
}

export interface UsageStats {
  period: Period
  date_from: string
  date_to: string
  scope: "company" | "team"
  total: UsageRow
  by_user: UsageRow[]
  by_feature: UsageRow[]
  by_model: UsageRow[]
  by_day: UsageRow[]
  input_price: number
  output_price: number
  monthly_budget: number
  month_cost: number
  unattributed_calls: number
}

const PERIODS: { value: Period; label: string }[] = [
  { value: "7d", label: "近 7 天" },
  { value: "30d", label: "近 30 天" },
  { value: "month", label: "本月" },
]

/** 费用（分）→ ¥12.34；不足 1 分显示 <¥0.01 */
function yuan(fen: number, tokens = 1): string {
  if (fen === 0 && tokens > 0) return "<¥0.01"
  return `¥${(fen / 100).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function tokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

const total = (r: UsageRow) => r.prompt_tokens + r.completion_tokens

function Tile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 px-4 py-3">
      <div className="text-xs text-zinc-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
      {hint ? <div className="mt-0.5 text-xs text-zinc-400">{hint}</div> : null}
    </div>
  )
}

/** 预算进度：只提醒不拦截；80% 起变色并配图标 + 文字 */
function Budget({ cost, budget, scope }: { cost: number; budget: number; scope: UsageStats["scope"] }) {
  if (!budget) return null
  const ratio = cost / budget
  const warn = ratio >= 0.8
  return (
    <div className="rounded-lg border border-zinc-200 px-4 py-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">本月{scope === "team" ? "团队" : "全公司"}预算</span>
        <span className="text-zinc-500 tabular-nums">
          {yuan(cost)} / {yuan(budget)}（{Math.round(ratio * 100)}%）
        </span>
        {warn ? (
          <span className="inline-flex items-center gap-1 text-xs text-amber-700">
            <AlertTriangle className="size-3.5" />
            {ratio >= 1 ? "已超出预算（不会拦截调用）" : "已用超过 80%"}
          </span>
        ) : null}
      </div>
      <div
        className="mt-2 h-2 overflow-hidden rounded-full bg-zinc-100"
        role="meter"
        aria-label="本月预算使用"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.min(100, Math.round(ratio * 100))}
      >
        <div
          className={cn("h-full rounded-full", warn ? "bg-amber-500" : "bg-zinc-800")}
          style={{ width: `${Math.min(100, ratio * 100)}%` }}
        />
      </div>
    </div>
  )
}

/** 每日 token 用量：单一序列柱状图，悬停显示当天数字；同时提供表格视图 */
function DailyBars({ rows }: { rows: UsageRow[] }) {
  const max = Math.max(1, ...rows.map(total))
  const [hover, setHover] = useState<UsageRow | null>(null)
  const shown = hover ?? rows[rows.length - 1]
  return (
    <section aria-label="每日用量" className="rounded-lg border border-zinc-200 p-4 text-sm">
      <div className="flex flex-wrap items-baseline gap-2">
        <h3 className="font-medium">每日 token 用量</h3>
        {shown ? (
          <span className="text-xs text-zinc-500 tabular-nums" aria-live="polite">
            {shown.label}：{tokens(total(shown))} tokens · {shown.calls} 次 · {yuan(shown.cost, total(shown))}
          </span>
        ) : null}
      </div>
      <div className="mt-3 flex h-32 items-end gap-0.5" onMouseLeave={() => setHover(null)}>
        {rows.map((r) => (
          <button
            key={r.key}
            type="button"
            className="group flex h-full min-w-0 flex-1 items-end"
            aria-label={`${r.label} ${tokens(total(r))} tokens`}
            onMouseEnter={() => setHover(r)}
            onFocus={() => setHover(r)}
          >
            <span
              className={cn(
                "w-full rounded-t-[4px] bg-zinc-700 group-hover:bg-zinc-950",
                total(r) === 0 && "bg-transparent",
              )}
              style={{ height: `${(total(r) / max) * 100}%`, minHeight: total(r) ? 2 : 0 }}
            />
          </button>
        ))}
      </div>
      <div className="mt-1 flex justify-between text-xs text-zinc-400 tabular-nums">
        <span>{rows[0]?.label}</span>
        <span>{rows[rows.length - 1]?.label}</span>
      </div>
    </section>
  )
}

/** 排行表：名称、调用次数、token、估算费用；费用列带同色比例条 */
function RankTable({ title, rows, nameHeader }: { title: string; rows: UsageRow[]; nameHeader: string }) {
  const max = Math.max(1, ...rows.map((r) => r.cost || total(r) / 1e6))
  return (
    <section aria-label={title} className="min-w-0 rounded-lg border border-zinc-200 text-sm">
      <h3 className="border-b border-zinc-100 px-4 py-2.5 font-medium">{title}</h3>
      {rows.length === 0 ? (
        <p className="px-4 py-3 text-zinc-400">这段时间没有调用。</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="text-xs whitespace-nowrap text-zinc-500">
              <tr>
                <th className="px-4 py-2 text-left font-normal">{nameHeader}</th>
                <th className="px-2 py-2 text-right font-normal">调用</th>
                <th className="px-2 py-2 text-right font-normal">tokens（入 / 出）</th>
                <th className="w-40 px-4 py-2 text-right font-normal">估算费用</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.key} className="border-t border-zinc-100">
                  <td className="px-4 py-2 whitespace-nowrap">{r.label}</td>
                  <td className="px-2 py-2 text-right tabular-nums">{r.calls}</td>
                  <td className="px-2 py-2 text-right whitespace-nowrap text-zinc-600 tabular-nums">
                    {tokens(r.prompt_tokens)} / {tokens(r.completion_tokens)}
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex items-center justify-end gap-2">
                      <span className="h-1.5 w-16 overflow-hidden rounded-full bg-zinc-100 max-sm:hidden">
                        <span
                          className="block h-full rounded-full bg-zinc-700"
                          style={{ width: `${((r.cost || total(r) / 1e6) / max) * 100}%` }}
                        />
                      </span>
                      <span className="tabular-nums">{yuan(r.cost, total(r))}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function UsageContent() {
  const { role } = useSession()
  const [period, setPeriod] = useState<Period>("30d")
  const q = useQuery({
    queryKey: ["ai-usage", period],
    queryFn: ({ signal }) => api.get<UsageStats>("/api/ai-usage", { period }, signal),
    placeholderData: keepPreviousData,
  })
  return (
    <div className="w-full space-y-3 p-4 sm:p-5">
      <div role="radiogroup" aria-label="统计时间" className="flex gap-1">
        {PERIODS.map((p) => (
          <button
            key={p.value}
            type="button"
            role="radio"
            aria-checked={period === p.value}
            onClick={() => setPeriod(p.value)}
            className={cn(
              "h-8 rounded-md px-3 text-sm",
              period === p.value ? "bg-zinc-900 text-white" : "text-zinc-600 hover:bg-zinc-100",
            )}
          >
            {p.label}
          </button>
        ))}
      </div>
      {q.isPending ? (
        <Skeleton className="h-80 w-full" />
      ) : q.isError ? (
        <QueryError error={q.error} onRetry={() => void q.refetch()} feature="AI 用量" />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Tile label="调用次数" value={q.data.total.calls.toLocaleString("zh-CN")} />
            <Tile
              label="输入 tokens"
              value={tokens(q.data.total.prompt_tokens)}
              hint={`单价 ¥${q.data.input_price}/百万`}
            />
            <Tile
              label="输出 tokens"
              value={tokens(q.data.total.completion_tokens)}
              hint={`单价 ¥${q.data.output_price}/百万`}
            />
            <Tile
              label="估算费用"
              value={yuan(q.data.total.cost, total(q.data.total))}
              hint={`${q.data.date_from} 起`}
            />
          </div>
          <Budget cost={q.data.month_cost} budget={q.data.monthly_budget} scope={q.data.scope} />
          <DailyBars rows={q.data.by_day} />
          <div className="grid gap-3 lg:grid-cols-2">
            <RankTable title="按人员" nameHeader="人员" rows={q.data.by_user} />
            <RankTable title="按功能" nameHeader="功能" rows={q.data.by_feature} />
          </div>
          <RankTable title="按模型" nameHeader="模型" rows={q.data.by_model} />
          <BadAnswers />
          <p className="text-xs text-zinc-400">
            {q.data.scope === "team" ? "只统计本团队成员的调用。" : "统计全公司的调用。"}
            费用按 token 数 × 单价估算，与模型厂商账单可能有出入；
            {role === "admin" ? (
              <>
                单价和预算在{" "}
                <Link href="/settings/rules" className="text-zinc-600 underline">
                  业务规则 → AI 用量
                </Link>{" "}
                里修改。
              </>
            ) : (
              "单价和预算由系统管理员设置。"
            )}
            {q.data.unattributed_calls
              ? ` 其中 ${q.data.unattributed_calls} 次为系统任务（如知识库处理），不归属到人。`
              : ""}
          </p>
        </>
      )}
    </div>
  )
}

/** 被点了「没帮助」的回复：看提问、回答和原因，用来调提示词、补知识库 */
function BadAnswers() {
  const q = useFeedbackReview()
  const rows = q.data ?? []
  return (
    <section aria-label="没帮助的回复" className="rounded-lg border border-zinc-200 text-sm">
      <h3 className="flex items-center gap-1.5 border-b border-zinc-100 px-4 py-2.5 font-medium">
        <ThumbsDown className="size-3.5 text-zinc-500" />
        没帮助的回复
        <span className="font-normal text-zinc-400">最近 50 条</span>
      </h3>
      {q.isLoading ? (
        <Skeleton className="m-4 h-12" />
      ) : rows.length === 0 ? (
        <p className="px-4 py-3 text-zinc-400">还没有人点过「没帮助」。</p>
      ) : (
        <ul className="divide-y divide-zinc-100">
          {rows.map((f) => (
            <li key={f.id} className="space-y-1 px-4 py-3">
              <div className="flex flex-wrap items-center gap-x-2 text-xs text-zinc-500">
                <span className="text-zinc-700">{f.user_name}</span>
                <span>{f.mode === "learn" ? "学习问答" : "做方案"}</span>
                <span>{f.created_at.slice(0, 16).replace("T", " ")}</span>
              </div>
              {f.comment ? <p className="font-medium">「{f.comment}」</p> : null}
              <p className="line-clamp-2 text-zinc-600">问：{f.question || "（无文字，可能是上传的材料）"}</p>
              <p className="line-clamp-3 text-zinc-500">答：{f.answer || "（只有卡片）"}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/** AI 用量与成本：管理员看全公司，主管看本团队 */
export default function AiUsagePage() {
  return (
    <PageFrame title="AI 用量" icon={Gauge} bodyClassName="overflow-y-auto">
      <RoleGate roles={["admin", "manager"]} lockedText="AI 用量统计仅主管和管理员可以查看">
        <UsageContent />
      </RoleGate>
    </PageFrame>
  )
}
