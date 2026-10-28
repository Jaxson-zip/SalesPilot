"use client"

import { Scale } from "lucide-react"

import { Alert } from "@/components/biz/Alert"
import { PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { SettingsForm } from "@/components/settings/SettingsForm"
import { RoleGate } from "@/components/shell/RoleGate"
import { useSession } from "@/components/shell/SessionProvider"
import { Skeleton } from "@/components/ui/skeleton"
import { useSettings } from "@/hooks/useSettings"

function RulesContent() {
  const q = useSettings(null)
  return (
    <div className="flex-1 overflow-x-hidden overflow-y-auto p-4 sm:p-5">
      <div className="mx-auto max-w-3xl space-y-4">
        <Alert tone="info" title="改动保存后立即生效，不用改文件、不用重启">
          毛利底线、折扣权限、提成比例、报销标准、商机赢率和回款计划都在这里维护；每一项都可以「恢复默认」。
          已经生成的报价单、合同不受影响，只作用于之后的新单据。某个行业要单独设置毛利底线，到「行业包配置 →
          业务规则」里改。
        </Alert>
        {q.isPending ? (
          <Skeleton className="h-96 w-full rounded-lg" />
        ) : q.isError ? (
          <QueryError error={q.error} onRetry={() => void q.refetch()} feature="业务规则" />
        ) : (
          <SettingsForm packId={null} data={q.data} />
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
