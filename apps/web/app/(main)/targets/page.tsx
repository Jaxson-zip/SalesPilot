"use client"

import { ChevronLeft, ChevronRight, Copy, Flag } from "lucide-react"
import { useState } from "react"

import { ProgressBar } from "@/components/biz/Progress"
import { PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { Tag } from "@/components/biz/Tag"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useTargets, useUpdateTargets } from "@/hooks/useTargets"
import { api } from "@/lib/api"
import { formatFen, formatPercent, localDate } from "@/lib/format"
import {
  changedItems,
  gapText,
  monthLabel,
  pace,
  PACE_LABEL,
  parseWan,
  shiftMonth,
  toWan,
  type Pace,
  type TargetBoard,
  type TargetRow,
} from "@/lib/targets"

const PACE_COLOR: Record<Pace, "green" | "blue" | "orange" | "gray"> = {
  done: "green",
  ahead: "blue",
  behind: "orange",
  none: "gray",
}

function Summary({ b }: { b: TargetBoard }) {
  const t = b.total
  const p = pace(t.rate, b.time_progress)
  return (
    <section aria-label="目标汇总" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <div className="rounded-lg border border-zinc-200 p-4">
        <div className="text-zinc-500">目标</div>
        <div className="mt-1 text-[22px] font-semibold tabular-nums">{formatFen(t.target)}</div>
        <div className="text-xs text-zinc-500">{t.target ? "成员目标之和" : "还没有设目标"}</div>
      </div>
      <div className="rounded-lg border border-zinc-200 p-4">
        <div className="text-zinc-500">已签约</div>
        <div className="mt-1 text-[22px] font-semibold tabular-nums">{formatFen(t.achieved)}</div>
        <div className="text-xs text-zinc-500">{gapText(t.target, t.achieved) || "按当月新签合同"}</div>
      </div>
      <div className="rounded-lg border border-zinc-200 p-4">
        <div className="flex items-center justify-between text-zinc-500">
          完成率 <Tag color={PACE_COLOR[p]}>{PACE_LABEL[p]}</Tag>
        </div>
        <div className="mt-1 text-[22px] font-semibold tabular-nums">
          {t.rate === null ? "—" : formatPercent(t.rate, 0)}
        </div>
        <div className="text-xs text-zinc-500">时间进度 {formatPercent(b.time_progress, 0)}</div>
      </div>
      <div className="rounded-lg border border-zinc-200 p-4">
        <div className="text-zinc-500">商机预测</div>
        <div className="mt-1 text-[22px] font-semibold tabular-nums">{formatFen(t.forecast)}</div>
        <div className="text-xs text-zinc-500">预计当月成交的商机 × 赢率</div>
      </div>
    </section>
  )
}

function TargetCell({
  row,
  editing,
  draft,
  onDraft,
}: {
  row: TargetRow
  editing: boolean
  draft: string | undefined
  onDraft: (v: string) => void
}) {
  if (!editing) return <>{formatFen(row.target)}</>
  const value = draft ?? toWan(row.target)
  const invalid = parseWan(value) === undefined
  return (
    <span className="inline-flex items-center gap-1">
      <Input
        value={value}
        inputMode="decimal"
        aria-label={`${row.user.name}的目标（万元）`}
        aria-invalid={invalid}
        placeholder="未设"
        className="h-7 w-24 text-right tabular-nums"
        onChange={(e) => onDraft(e.target.value)}
      />
      <span className="text-xs text-zinc-500">万</span>
    </span>
  )
}

function Body({ month, setMonth }: { month: string; setMonth: (m: string) => void }) {
  const q = useTargets(month)
  const save = useUpdateTargets(month)
  const [editing, setEditing] = useState(false)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [copying, setCopying] = useState(false)
  const b = q.data

  if (q.isError && !b) {
    return <QueryError error={q.error} onRetry={() => void q.refetch()} retrying={q.isFetching} feature="业绩目标" />
  }
  if (!b) return <Skeleton className="h-64 w-full" />

  const items = changedItems(b.rows, drafts)
  const invalid = Object.values(drafts).some((v) => parseWan(v) === undefined)
  const showTeam = b.rows.some((r) => r.team_name) && !b.editable && b.rows.length > 1
  const go = (n: number) => {
    setEditing(false)
    setDrafts({})
    setMonth(shiftMonth(b.month, n))
  }
  const copyLast = async () => {
    setCopying(true)
    try {
      const last = await api.get<TargetBoard>("/api/targets", { month: shiftMonth(b.month, -1) })
      const next: Record<string, string> = {}
      for (const r of last.rows) if (r.target !== null) next[r.user.id] = toWan(r.target)
      setDrafts(next)
      setEditing(true)
    } finally {
      setCopying(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon-sm" aria-label="上个月" onClick={() => go(-1)}>
            <ChevronLeft />
          </Button>
          <span className="min-w-28 text-center font-medium tabular-nums" aria-live="polite">
            {monthLabel(b.month)}
          </span>
          <Button variant="ghost" size="icon-sm" aria-label="下个月" onClick={() => go(1)}>
            <ChevronRight />
          </Button>
        </div>
        {b.editable ? (
          editing ? (
            <div className="flex items-center gap-2">
              {invalid ? <span className="text-xs text-red-600">目标填数字（万元），最多 4 位小数</span> : null}
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setEditing(false)
                  setDrafts({})
                }}
              >
                取消
              </Button>
              <Button
                size="sm"
                disabled={invalid || items.length === 0 || save.isPending}
                onClick={() =>
                  save.mutate(
                    { items },
                    {
                      onSuccess: () => {
                        setEditing(false)
                        setDrafts({})
                      },
                    },
                  )
                }
              >
                {save.isPending ? "保存中…" : `保存${items.length ? `（${items.length} 人）` : ""}`}
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" disabled={copying} onClick={() => void copyLast()}>
                <Copy />
                复制上月目标
              </Button>
              <Button size="sm" onClick={() => setEditing(true)}>
                设置目标
              </Button>
            </div>
          )
        ) : null}
      </div>

      <Summary b={b} />

      <div className="overflow-x-auto rounded-lg border border-zinc-200 bg-white">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="border-b border-zinc-200 text-xs text-zinc-500">
            <tr>
              <th className="px-4 py-2 font-normal">成员</th>
              {showTeam ? <th className="py-2 font-normal">团队</th> : null}
              <th className="py-2 text-right font-normal">目标</th>
              <th className="py-2 pl-6 text-right font-normal">已签约</th>
              <th className="py-2 pl-6 font-normal">完成率</th>
              <th className="py-2 text-right font-normal">商机预测</th>
              <th className="px-4 py-2 font-normal">状态</th>
            </tr>
          </thead>
          <tbody>
            {b.rows.map((r) => {
              const p = pace(r.rate, b.time_progress)
              return (
                <tr key={r.user.id} className="border-b border-zinc-100 last:border-0">
                  <td className="px-4 py-2">
                    {r.user.name}
                    {r.role === "manager" ? <span className="ml-1.5 text-xs text-zinc-400">主管</span> : null}
                    {!r.active ? <span className="ml-1.5 text-xs text-zinc-400">已停用</span> : null}
                  </td>
                  {showTeam ? <td className="py-2 text-zinc-500">{r.team_name ?? "—"}</td> : null}
                  <td className="py-2 text-right tabular-nums">
                    <TargetCell
                      row={r}
                      editing={editing}
                      draft={drafts[r.user.id]}
                      onDraft={(v) => setDrafts({ ...drafts, [r.user.id]: v })}
                    />
                  </td>
                  <td className="py-2 pl-6 text-right tabular-nums">
                    {formatFen(r.achieved)}
                    <div className="text-xs text-zinc-400">{r.contracts} 份合同</div>
                  </td>
                  <td className="py-2 pl-6">
                    {r.rate === null ? (
                      <span className="text-zinc-400">—</span>
                    ) : (
                      <ProgressBar percent={r.rate * 100} />
                    )}
                  </td>
                  <td className="py-2 text-right text-zinc-600 tabular-nums">{formatFen(r.forecast)}</td>
                  <td className="px-4 py-2">
                    <Tag color={PACE_COLOR[p]}>{PACE_LABEL[p]}</Tag>
                    {r.target ? <div className="text-xs text-zinc-400">{gapText(r.target, r.achieved)}</div> : null}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-zinc-500">
        已签约按当月新签合同金额（与工作台「本月成交」一致）；商机预测是预计当月成交的进行中商机「金额 ×
        赢率」之和；完成率低于当月时间进度时提示落后。{b.editable ? "目标由主管设置，团队目标是成员目标之和。" : ""}
      </p>
    </div>
  )
}

/** 业绩目标：主管设置本团队每人每月签约额目标；销售看自己的完成情况；管理员只读查看全公司 */
export default function TargetsPage() {
  const [month, setMonth] = useState(() => localDate().slice(0, 7))
  return (
    <PageFrame title="业绩目标" icon={Flag}>
      <div className="flex-1 overflow-y-auto p-4 sm:p-5">
        <Body month={month} setMonth={setMonth} />
      </div>
    </PageFrame>
  )
}
