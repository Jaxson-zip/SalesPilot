"use client"

import { Scale } from "lucide-react"
import Link from "next/link"
import { useState } from "react"

import { PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { LINE_TABS_LIST, LINE_TABS_TRIGGER } from "@/components/biz/RecordTabs"
import { SettingsGroupCard } from "@/components/settings/SettingsForm"
import { RoleGate } from "@/components/shell/RoleGate"
import { useSession } from "@/components/shell/SessionProvider"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useSettings } from "@/hooks/useSettings"
import { cn } from "@/lib/utils"

function RulesContent() {
  const q = useSettings(null)
  const [picked, setPicked] = useState<string | null>(null)
  if (q.isPending)
    return (
      <div className="p-4 sm:p-5">
        <Skeleton className="h-96 rounded-lg" />
      </div>
    )
  if (q.isError)
    return (
      <div className="p-4 sm:p-5">
        <QueryError error={q.error} onRetry={() => void q.refetch()} feature="业务规则" />
      </div>
    )
  const data = q.data
  const current = picked ?? data.groups[0] ?? ""
  const changed = data.fields.filter((f) => f.overridden).length
  // 分组放在顶部一行标签里（与审批页的「待处理 / 已处理」一致），不再在页面里套一个侧栏
  return (
    <Tabs value={current} onValueChange={setPicked} className="flex min-h-0 flex-1 flex-col gap-0">
      <TabsList variant="line" aria-label="规则分组" className={cn(LINE_TABS_LIST, "overflow-x-auto")}>
        {data.groups.map((g) => {
          const n = data.fields.filter((f) => f.group === g && f.overridden).length
          return (
            <TabsTrigger key={g} value={g} className={LINE_TABS_TRIGGER}>
              {g}
              {n ? <span className="size-1.5 rounded-full bg-amber-500" aria-label={`已修改 ${n} 项`} /> : null}
            </TabsTrigger>
          )
        })}
      </TabsList>
      <div className="flex-1 overflow-x-hidden overflow-y-auto p-4 sm:p-5">
        <div className="space-y-3">
          <p className="text-xs text-zinc-500">
            保存后立即生效，只作用于之后的新单据；每项都可以恢复默认。
            {changed ? <span className="text-amber-700"> 当前共修改了 {changed} 项。</span> : null}
            某个行业单独的毛利底线在{" "}
            <Link href="/settings/packs" className="text-zinc-700 underline">
              行业包与产品
            </Link>
            里改。
          </p>
          <SettingsGroupCard packId={null} data={data} group={current} />
        </div>
      </div>
    </Tabs>
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
