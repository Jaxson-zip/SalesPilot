"use client"

import { ChevronDown, KeyRound, Plus } from "lucide-react"
import { useState } from "react"

import { PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { EndpointRow, KeyRow } from "@/components/model-config/ProviderRows"
import { CustomProviderCard } from "@/components/model-config/CustomProviderCard"
import { DefaultModels } from "@/components/model-config/DefaultModels"
import { Section } from "@/components/model-config/shared"
import { StatusSummary } from "@/components/model-config/StatusSummary"
import { RoleGate } from "@/components/shell/RoleGate"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useModelConfig, type ModelConfig } from "@/hooks/useModelConfig"
import { cn } from "@/lib/utils"

/** 高级设置：主备顺序、换知识库模型、接口地址和协议、自定义厂商。大多数情况不用动 */
function Advanced({ config }: { config: ModelConfig }) {
  const [adding, setAdding] = useState(false)
  const embedAlias = config.groups.embed?.[0] ?? null
  return (
    <div className="space-y-6">
      <Section title="用哪个模型">
        {config.gateway_ok ? (
          <DefaultModels key={JSON.stringify(config.groups)} config={config} />
        ) : (
          <p className="text-xs text-zinc-400">模型服务连上后才能调整。</p>
        )}
      </Section>
      <Section title="接口地址和协议" desc="留空用官方地址。走代理或私有部署时才需要改。">
        <ul className="divide-y divide-zinc-100 rounded-lg border border-zinc-200 text-sm">
          {config.builtin.map((p) => (
            <EndpointRow key={`${p.var}:${p.base}:${p.protocol}:${p.adapter}`} p={p} />
          ))}
        </ul>
      </Section>
      <Section
        title="其他厂商"
        desc={
          config.allow_private_base
            ? "Kimi、智谱、硅基流动，或自己部署的模型。"
            : "Kimi、智谱、硅基流动等。接自己部署的模型需在服务器 .env 设置 MODEL_ALLOW_PRIVATE_BASE=true。"
        }
      >
        {config.custom.map((p) => (
          <CustomProviderCard key={p.id} p={p} dims={config.embedding_dims} embedAlias={embedAlias} />
        ))}
        {adding ? (
          <CustomProviderCard dims={config.embedding_dims} embedAlias={embedAlias} onClose={() => setAdding(false)} />
        ) : (
          <Button variant="outline" size="sm" onClick={() => setAdding(true)}>
            <Plus />
            添加厂商
          </Button>
        )}
      </Section>
    </div>
  )
}

/** 模型接入：先看 AI 能不能用，再填 Key；其余收在「高级设置」 */
export default function ModelConfigPage() {
  const q = useModelConfig()
  const [advanced, setAdvanced] = useState(false)
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
          <div className="w-full max-w-4xl space-y-6 p-4 sm:p-5">
            <StatusSummary config={q.data} />
            <Section title="API Key">
              <ul className="divide-y divide-zinc-100 rounded-lg border border-zinc-200 text-sm">
                {q.data.builtin.map((p) => (
                  <KeyRow key={p.var} p={p} />
                ))}
              </ul>
              <p className="text-xs text-zinc-400">Key 加密保存，只显示末 4 位。建议在厂商后台给 Key 设消费上限。</p>
            </Section>
            <div>
              <button
                type="button"
                aria-expanded={advanced}
                onClick={() => setAdvanced((v) => !v)}
                className="flex items-center gap-1 text-sm font-semibold text-zinc-700 hover:text-zinc-900"
              >
                高级设置
                <ChevronDown className={cn("size-4 transition-transform", advanced && "rotate-180")} />
              </button>
              {!advanced ? (
                <p className="mt-0.5 text-xs text-zinc-500">主备顺序、换知识库模型、接口地址、其他厂商</p>
              ) : (
                <div className="mt-4">
                  <Advanced config={q.data} />
                </div>
              )}
            </div>
          </div>
        )}
      </RoleGate>
    </PageFrame>
  )
}
