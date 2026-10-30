"use client"

import { KeyRound, Plus } from "lucide-react"
import { useState } from "react"

import { useConfirmAction } from "@/components/biz/ConfirmAction"
import { PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { CustomEditor } from "@/components/model-config/CustomEditor"
import { DefaultModels } from "@/components/model-config/DefaultModels"
import { BuiltinEditor, RowCard } from "@/components/model-config/ProviderRows"
import { RoleGate } from "@/components/shell/RoleGate"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useDeleteCustom, useModelConfig, type ModelConfig } from "@/hooks/useModelConfig"
import { aiStatus } from "@/lib/model-config"

/** 一家厂商的状态：有 Key 才看网关结果；网关连不上为 null */
const usable = (configured: boolean, available: boolean | null) => (configured ? available : false)

function Providers({ config }: { config: ModelConfig }) {
  // 同一时间只展开一张：内置用变量名，其他厂商用标识，"new" 是新增，"defaults" 是默认模型
  const [open, setOpen] = useState<string | null>(null)
  const remove = useDeleteCustom()
  const { ask, dialog } = useConfirmAction()
  const toggle = (id: string) => setOpen((cur) => (cur === id ? null : id))
  const close = () => setOpen(null)
  const status = aiStatus(config)
  const embedAlias = config.groups.embed?.[0] ?? null
  const summary = status
    .filter((l) => l.value)
    .map((l) => `${l.label} ${l.value}`)
    .join(" · ")
  const editButton = (id: string, name: string) => (
    <Button variant="outline" size="sm" aria-label={`编辑${name}`} onClick={() => toggle(id)}>
      {open === id ? "收起" : "编辑"}
    </Button>
  )

  return (
    <div className="space-y-6">
      {!config.gateway_ok ? (
        <p className="text-sm text-amber-700">模型服务暂时连不上，保存的配置会在恢复后生效。</p>
      ) : !status[0].value ? (
        <p className="text-sm text-red-600">还没有能用的对话模型，先给一家厂商填 Key。</p>
      ) : null}

      <ul className="space-y-2 text-sm">
        {config.builtin.map((p) => (
          <RowCard
            key={p.var}
            label={p.label}
            title={p.label}
            ok={usable(p.key_source !== "none" && !p.broken, p.available)}
            actions={editButton(p.var, p.label)}
            open={open === p.var}
          >
            <BuiltinEditor key={`${p.var}:${p.tail}:${p.base}:${p.protocol}`} p={p} onClose={close} />
          </RowCard>
        ))}
        {config.custom.map((p) => {
          const inUse = Boolean(embedAlias?.startsWith(`${p.id}-`))
          return (
            <RowCard
              key={p.id}
              label={p.name}
              title={p.name}
              tag="自定义"
              ok={usable(p.has_key && !p.broken, p.available)}
              actions={
                <>
                  {editButton(p.id, p.name)}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-red-600"
                    disabled={remove.isPending || inUse}
                    title={inUse ? "知识库正在用它的模型，先在默认模型里换掉" : undefined}
                    onClick={() =>
                      ask({
                        title: `删除${p.name}？`,
                        description: "会删掉它的配置和保存的 Key。",
                        confirmLabel: "删除",
                        destructive: true,
                        onConfirm: () => remove.mutate(p.id, { onSuccess: close }),
                      })
                    }
                  >
                    删除
                  </Button>
                </>
              }
              open={open === p.id}
            >
              <CustomEditor p={p} dims={config.embedding_dims} onDone={close} />
            </RowCard>
          )
        })}
        {open === "new" ? (
          <li aria-label="添加厂商" className="rounded-xl border border-zinc-200 px-4 py-3">
            <p className="mb-3 font-medium">添加厂商</p>
            <CustomEditor dims={config.embedding_dims} onDone={close} />
          </li>
        ) : null}
      </ul>
      {open !== "new" ? (
        <Button variant="outline" className="w-full" onClick={() => setOpen("new")}>
          <Plus />
          添加厂商
        </Button>
      ) : null}

      <ul className="text-sm">
        <RowCard
          label="默认模型"
          title="默认模型"
          summary={summary || "未配置"}
          actions={editButton("defaults", "默认模型")}
          open={open === "defaults"}
        >
          {config.gateway_ok ? (
            <DefaultModels key={JSON.stringify(config.groups)} config={config} />
          ) : (
            <p className="text-xs text-zinc-400">模型服务连上后才能调整。</p>
          )}
        </RowCard>
      </ul>
      {dialog}
    </div>
  )
}

/** 模型接入：一家厂商一行，点「编辑」在原地展开；默认模型单独一行 */
export default function ModelConfigPage() {
  const q = useModelConfig()
  return (
    <PageFrame title="模型接入" icon={KeyRound} bodyClassName="overflow-y-auto">
      <RoleGate roles={["admin"]} lockedText="模型接入由系统管理员配置">
        {q.isPending ? (
          <div className="p-5">
            <Skeleton className="h-60 w-full" />
          </div>
        ) : q.isError ? (
          <QueryError error={q.error} onRetry={() => void q.refetch()} feature="模型接入" />
        ) : (
          <div className="w-full max-w-3xl space-y-4 p-4 sm:p-6">
            <p className="text-sm text-zinc-500">填入厂商的 API Key 就能用它的模型。Key 加密保存。</p>
            <Providers config={q.data} />
          </div>
        )}
      </RoleGate>
    </PageFrame>
  )
}
