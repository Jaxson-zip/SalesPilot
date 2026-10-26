"use client"

import { BookOpen, Boxes, Package, Plus, Scale } from "lucide-react"

import { Alert } from "@/components/biz/Alert"
import { PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { Tag } from "@/components/biz/Tag"
import { ProductLineMapping } from "@/components/packs/ProductLineMapping"
import { RoleGate } from "@/components/shell/RoleGate"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { usePacks, useProductLines } from "@/hooks/useProductLines"
import type { PackOut } from "@/types/api"

/** PackCard：已安装行业包（启停由产品线映射控制，契约没有行业包级别的开关） */
function PackCard({ pack, lines }: { pack: PackOut; lines: number | null }) {
  return (
    <div className="min-w-0 rounded-lg border border-zinc-200 p-4">
      <div className="flex items-center justify-between">
        <span className="inline-flex size-9 items-center justify-center rounded-lg bg-zinc-100">
          <Boxes className="size-4" />
        </span>
        <Tag color="green">已安装</Tag>
      </div>
      <div className="mt-3 truncate font-medium">{pack.name}</div>
      <p className="mt-1 line-clamp-2 min-h-[38px] text-zinc-500">{pack.description}</p>
      <p className="mt-2 text-xs text-zinc-400">
        v{pack.version} · {pack.id}
        {lines !== null ? ` · 映射 ${lines} 条产品线` : ""}
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        {[
          { label: "产品目录", icon: Package },
          { label: "业务规则", icon: Scale },
          { label: "知识库", icon: BookOpen },
        ].map((b) => (
          <Button key={b.label} variant="outline" size="xs" disabled title="行业包内容在 packs/ 目录维护">
            <b.icon />
            {b.label}
          </Button>
        ))}
      </div>
    </div>
  )
}

function PacksContent() {
  const packs = usePacks()
  const lines = useProductLines()
  const countOf = (id: string) => (lines.data ? lines.data.filter((l) => l.pack === id).length : null)
  return (
    <div className="flex-1 space-y-5 overflow-x-hidden overflow-y-auto p-4 sm:p-5">
      <Alert tone="info" title="行业包由管理员统一配置，销售不能切换">
        销售创建商机时选择「产品线」，系统按下方映射自动匹配行业包；AI
        出方案时直接使用该行业包的产品目录、规则和知识库。
      </Alert>
      <div>
        <div className="mb-2 font-medium">已安装的行业包</div>
        {packs.isError ? (
          <div className="rounded-lg border border-zinc-200">
            <QueryError error={packs.error} onRetry={() => void packs.refetch()} feature="行业包" />
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {packs.isPending
              ? [0, 1].map((i) => <Skeleton key={i} className="h-44 w-full rounded-lg" />)
              : packs.data.map((p) => <PackCard key={p.id} pack={p} lines={countOf(p.id)} />)}
            <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-zinc-300 p-4 text-zinc-400">
              <Plus className="size-5" />
              <span className="mt-1">新增行业包</span>
              <span className="mt-0.5 text-xs">按 packs/ 目录规范添加</span>
            </div>
          </div>
        )}
      </div>
      <div>
        <div className="mb-2 font-medium">产品线 → 行业包映射</div>
        <ProductLineMapping packs={packs.data ?? []} />
      </div>
    </div>
  )
}

/** 行业包配置（仅管理员）：PackCard + ProductLineMapping */
export default function PacksPage() {
  const { role } = useSession()
  return (
    <PageFrame title="行业包配置" icon={Boxes}>
      <RoleGate roles={["admin"]} lockedText="行业包由系统管理员统一配置，可在左下角切换为「系统管理员」查看">
        {role === "admin" ? <PacksContent /> : null}
      </RoleGate>
    </PageFrame>
  )
}
