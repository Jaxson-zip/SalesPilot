"use client"

import { Scale } from "lucide-react"
import Link from "next/link"
import { useState } from "react"

import { PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { SettingsGroupCard } from "@/components/settings/SettingsForm"
import { RoleGate } from "@/components/shell/RoleGate"
import { useSession } from "@/components/shell/SessionProvider"
import { Skeleton } from "@/components/ui/skeleton"
import { useSettings } from "@/hooks/useSettings"
import type { SettingsOut } from "@/lib/settings"
import { cn } from "@/lib/utils"

/** 分组导航：桌面左侧竖排，手机顶部横向滑动；改过的组显示数量 */
function GroupNav({ data, current, onPick }: { data: SettingsOut; current: string; onPick: (g: string) => void }) {
  return (
    <nav
      aria-label="规则分组"
      className="-mx-4 flex gap-1 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0 lg:sticky lg:top-0 lg:flex-col lg:overflow-visible lg:pb-0"
    >
      {data.groups.map((g) => {
        const fields = data.fields.filter((f) => f.group === g)
        const changed = fields.filter((f) => f.overridden).length
        const active = g === current
        return (
          <button
            key={g}
            type="button"
            aria-current={active ? "true" : undefined}
            onClick={() => onPick(g)}
            className={cn(
              "flex h-8 shrink-0 items-center gap-2 rounded-md px-3 text-left whitespace-nowrap transition-colors lg:h-9",
              active ? "bg-zinc-100 font-medium text-zinc-900" : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900",
            )}
          >
            <span className="lg:flex-1">{g}</span>
            {changed ? (
              <span className="rounded bg-amber-50 px-1.5 text-[11px] leading-5 font-normal text-amber-700">
                改 {changed}
              </span>
            ) : (
              <span className="hidden text-xs font-normal text-zinc-400 tabular-nums lg:inline">{fields.length}</span>
            )}
          </button>
        )
      })}
    </nav>
  )
}

function RulesContent() {
  const q = useSettings(null)
  const [picked, setPicked] = useState<string | null>(null)
  const changed = q.data?.fields.filter((f) => f.overridden).length ?? 0
  const current = picked ?? q.data?.groups[0] ?? ""
  return (
    <div className="flex-1 overflow-x-hidden overflow-y-auto p-4 sm:p-5">
      <div className="mx-auto max-w-4xl space-y-4">
        <p className="text-sm text-zinc-500">
          保存后立即生效，只作用于之后的新单据；每项都可以恢复默认。
          {changed ? <span className="text-amber-700"> 当前已修改 {changed} 项。</span> : null}
          <span className="hidden sm:inline">
            {" "}
            某个行业单独的毛利底线在{" "}
            <Link href="/settings/packs" className="text-zinc-700 underline">
              行业包配置
            </Link>
            里改。
          </span>
        </p>
        {q.isPending ? (
          <Skeleton className="h-96 w-full rounded-lg" />
        ) : q.isError ? (
          <QueryError error={q.error} onRetry={() => void q.refetch()} feature="业务规则" />
        ) : (
          <div className="grid gap-4 lg:grid-cols-[176px_minmax(0,1fr)] lg:items-start">
            <GroupNav data={q.data} current={current} onPick={setPicked} />
            <SettingsGroupCard packId={null} data={q.data} group={current} />
          </div>
        )}
      </div>
    </div>
  )
}

/** 业务规则（仅管理员）：rules.yaml 是默认值，网页上的改动存数据库 */
export default function RulesPage() {
  const { role } = useSession()
  return (
    <PageFrame title="业务规则" icon={Scale}>
      <RoleGate roles={["admin"]} lockedText="业务规则由系统管理员维护，可在左下角切换为「系统管理员」查看">
        {role === "admin" ? <RulesContent /> : null}
      </RoleGate>
    </PageFrame>
  )
}
