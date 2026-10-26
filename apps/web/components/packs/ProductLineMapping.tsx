"use client"

import { SimpleSelect } from "@/components/biz/FormControls"
import { QueryError } from "@/components/biz/QueryStatus"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { useProductLines, useUpdateProductLine } from "@/hooks/useProductLines"
import type { PackOut, ProductLineItem } from "@/types/api"

function PackSelect({
  pl,
  packs,
  onChange,
}: {
  pl: ProductLineItem
  packs: PackOut[]
  onChange: (pack: string) => void
}) {
  const options = packs.map((p) => ({ value: p.id, label: p.name }))
  // 映射到了未安装的行业包时也要能显示出来
  if (pl.pack && !options.some((o) => o.value === pl.pack))
    options.push({ value: pl.pack, label: `${pl.pack}（未安装）` })
  return (
    <SimpleSelect value={pl.pack} onChange={onChange} options={options} size="sm" ariaLabel={`${pl.name} 的行业包`} />
  )
}

/** ProductLineMapping：≥768 表格，<768 逐行列表；Select 改行业包、Switch 启用（乐观更新） */
export function ProductLineMapping({ packs }: { packs: PackOut[] }) {
  const query = useProductLines()
  const update = useUpdateProductLine()

  if (query.isPending) return <Skeleton className="h-32 w-full" />
  if (query.isError)
    return (
      <div className="rounded-lg border border-zinc-200">
        <QueryError
          error={query.error}
          onRetry={() => void query.refetch()}
          retrying={query.isFetching}
          feature="产品线映射"
        />
      </div>
    )
  const rows = query.data
  if (rows.length === 0)
    return <div className="rounded-lg border border-zinc-200 py-8 text-center text-zinc-500">还没有产品线</div>

  const setPack = (pl: ProductLineItem, pack: string) => pack !== pl.pack && update.mutate({ id: pl.id, pack })
  const setEnabled = (pl: ProductLineItem, enabled: boolean) => update.mutate({ id: pl.id, enabled })

  return (
    <div className="overflow-hidden rounded-lg border border-zinc-200">
      <table className="hidden w-full table-fixed md:table">
        <thead>
          <tr className="h-8 bg-zinc-50 text-zinc-500">
            <th className="px-3 text-left font-normal">产品线</th>
            <th className="w-56 px-3 text-left font-normal">行业包</th>
            <th className="w-24 px-3 text-left font-normal">启用</th>
            <th className="w-28 px-3 text-right font-normal">进行中商机</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((pl) => (
            <tr key={pl.id} className="h-11 border-t border-zinc-100">
              <td className="truncate px-3 font-medium">{pl.name}</td>
              <td className="px-3">
                <PackSelect pl={pl} packs={packs} onChange={(p) => setPack(pl, p)} />
              </td>
              <td className="px-3">
                <Switch
                  checked={pl.enabled}
                  onCheckedChange={(v) => setEnabled(pl, v)}
                  aria-label={`启用 ${pl.name}`}
                />
              </td>
              <td className="px-3 text-right tabular-nums">{pl.open_opportunities}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="divide-y divide-zinc-100 md:hidden">
        {rows.map((pl) => (
          <div key={pl.id} className="space-y-2 p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate font-medium">{pl.name}</span>
              <Switch checked={pl.enabled} onCheckedChange={(v) => setEnabled(pl, v)} aria-label={`启用 ${pl.name}`} />
            </div>
            <PackSelect pl={pl} packs={packs} onChange={(p) => setPack(pl, p)} />
            <div className="text-xs text-zinc-500">{pl.open_opportunities} 个进行中商机</div>
          </div>
        ))}
      </div>
    </div>
  )
}
