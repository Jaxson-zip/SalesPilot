"use client"

import { KeyRound, Plus, TriangleAlert } from "lucide-react"
import { useState } from "react"

import { PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { BuiltinProviderCard } from "@/components/model-config/BuiltinProviderCard"
import { CustomProviderCard } from "@/components/model-config/CustomProviderCard"
import { DefaultModels } from "@/components/model-config/DefaultModels"
import { Section } from "@/components/model-config/shared"
import { RoleGate } from "@/components/shell/RoleGate"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useModelConfig } from "@/hooks/useModelConfig"

/** 模型接入：管理员在网页上配置厂商（Key、接口地址、协议）、自定义厂商和默认模型，保存后立即生效 */
export default function ModelConfigPage() {
  const q = useModelConfig()
  const [adding, setAdding] = useState(false)
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
          <div className="w-full space-y-6 p-4 sm:p-5">
            {!q.data.gateway_ok ? (
              <p className="flex items-start gap-1.5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                <TriangleAlert className="mt-0.5 size-4 shrink-0" />
                模型网关暂时连不上，模型是否可用无法确认；在这里保存的配置会在网关恢复后自动生效。
              </p>
            ) : null}
            <ul className="list-disc space-y-0.5 pl-5 text-xs text-zinc-500">
              <li>网页上填写的优先，没填的继续用服务器 .env 和模型清单里的；保存后立即生效，不用重启。</li>
              <li>Key 加密保存，页面上只显示末 4 位，操作日志只记谁改了哪一家。建议在厂商后台给 Key 设置消费上限。</li>
              {!q.data.allow_private_base ? (
                <li>
                  接口地址不能指向内网或本机。要接自建模型（vLLM、Ollama），在服务器 .env 设置
                  MODEL_ALLOW_PRIVATE_BASE=true。
                </li>
              ) : null}
            </ul>
            <Section title="默认模型" desc="选哪个模型干哪件事；主用出错时自动切到备用。">
              {q.data.gateway_ok ? (
                <DefaultModels key={JSON.stringify(q.data.groups)} config={q.data} />
              ) : (
                <p className="text-xs text-zinc-400">网关连上后才能调整。</p>
              )}
            </Section>
            <Section title="内置厂商" desc="混元、DeepSeek、通义的接口地址和协议已经填好，一般只需要填 Key。">
              {q.data.builtin.map((p) => (
                <BuiltinProviderCard key={p.var} p={p} />
              ))}
            </Section>
            <Section
              title="自定义厂商"
              desc="接入其他 OpenAI 兼容接口（Kimi、智谱、硅基流动、自建 vLLM / Ollama 等）。保存后到「默认模型」里选用。"
            >
              {q.data.custom.map((p) => (
                <CustomProviderCard
                  key={p.id}
                  p={p}
                  dims={q.data.embedding_dims}
                  embedAlias={q.data.groups.embed?.[0] ?? null}
                />
              ))}
              {adding ? (
                <CustomProviderCard
                  dims={q.data.embedding_dims}
                  embedAlias={q.data.groups.embed?.[0] ?? null}
                  onClose={() => setAdding(false)}
                />
              ) : (
                <Button variant="outline" size="sm" onClick={() => setAdding(true)}>
                  <Plus />
                  添加厂商
                </Button>
              )}
            </Section>
          </div>
        )}
      </RoleGate>
    </PageFrame>
  )
}
