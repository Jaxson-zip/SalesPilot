"use client"

import { KeyRound, Loader2, PlugZap, TriangleAlert } from "lucide-react"
import { useState } from "react"

import { PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { Tag } from "@/components/biz/Tag"
import { RoleGate } from "@/components/shell/RoleGate"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useModelKeys, useSaveModelKey, useTestModelKey, type ProviderKey } from "@/hooks/useModelKeys"

function time(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function StatusTag({ p }: { p: ProviderKey }) {
  if (p.source === "none") return <Tag>未配置</Tag>
  if (p.available === null || p.available === undefined) return <Tag>状态未知</Tag>
  return p.available ? <Tag color="green">可用</Tag> : <Tag color="yellow">不可用</Tag>
}

function sourceText(p: ProviderKey): string {
  if (p.source === "web") {
    const who = p.saved_by && p.saved_at ? ` · ${p.saved_by} ${time(p.saved_at)} 保存` : ""
    return `网页填写 · 末 4 位 ${p.tail ?? "****"}${who}`
  }
  if (p.source === "env") return `服务器 .env 的 ${p.var}`
  return "网页和 .env 都没有填写"
}

function ProviderCard({ p }: { p: ProviderKey }) {
  const save = useSaveModelKey()
  const test = useTestModelKey()
  const [key, setKey] = useState("")
  const typed = key.trim()

  return (
    <section aria-label={p.label} className="space-y-3 rounded-lg border border-zinc-200 p-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-medium">{p.label}</h3>
        <StatusTag p={p} />
        <span className="text-xs text-zinc-400">来源：{sourceText(p)}</span>
      </div>
      {p.broken ? (
        <p className="flex items-start gap-1.5 text-xs text-red-600">
          <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
          之前在网页上保存的 Key 解不开了（服务器的 JWT_SECRET 换过），请重新填写。
        </p>
      ) : null}
      <div className="space-y-0.5 text-xs text-zinc-500">
        <p>在哪里申请：{p.hint}</p>
        {p.models.length > 0 ? <p>用于模型：{p.models.join("、")}</p> : null}
      </div>
      <Input
        type="password"
        autoComplete="off"
        value={key}
        onChange={(e) => setKey(e.target.value)}
        placeholder={p.source === "none" ? "粘贴 API Key" : "如需更换，粘贴新的 API Key"}
        aria-label={`${p.label} API Key`}
      />
      <div className="flex flex-wrap justify-end gap-2">
        {p.source === "web" || p.broken ? (
          <Button
            variant="ghost"
            size="sm"
            disabled={save.isPending}
            onClick={() => save.mutate({ var: p.var, key: "" })}
          >
            清除网页上的 Key
          </Button>
        ) : null}
        <Button
          variant="outline"
          size="sm"
          disabled={test.isPending || (!typed && p.source === "none")}
          onClick={() => test.mutate(typed ? { var: p.var, key: typed } : { var: p.var })}
        >
          {test.isPending ? <Loader2 className="animate-spin" /> : <PlugZap />}
          {typed ? "测试这个 Key" : "测试当前 Key"}
        </Button>
        <Button
          size="sm"
          disabled={!typed || save.isPending}
          onClick={() => save.mutate({ var: p.var, key: typed }, { onSuccess: () => setKey("") })}
        >
          保存
        </Button>
      </div>
    </section>
  )
}

/** 模型接入：管理员在网页上填写各厂商的 API Key（优先于服务器 .env），保存后立即生效 */
export default function ModelKeysPage() {
  const q = useModelKeys()
  return (
    <PageFrame title="模型接入" icon={KeyRound} bodyClassName="overflow-y-auto">
      <RoleGate roles={["admin"]} lockedText="模型 Key 由系统管理员配置">
        {q.isPending ? (
          <div className="p-5">
            <Skeleton className="h-60 w-full" />
          </div>
        ) : q.isError ? (
          <QueryError error={q.error} onRetry={() => void q.refetch()} feature="模型接入" />
        ) : (
          <div className="w-full space-y-4 p-4 sm:p-5">
            {!q.data.gateway_ok ? (
              <p className="flex items-start gap-1.5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                <TriangleAlert className="mt-0.5 size-4 shrink-0" />
                模型网关暂时连不上，模型是否可用无法确认；在这里保存的 Key 会在网关恢复后自动生效。
              </p>
            ) : null}
            <ul className="list-disc space-y-0.5 pl-5 text-xs text-zinc-500">
              <li>至少配置一家对话模型，AI 工作台才能使用；知识库检索还需要能做向量（Embedding）的厂商。</li>
              <li>网页上填写的优先，没填的继续用服务器 .env 里的；保存后立即生效，不用重启。</li>
              <li>
                Key 加密保存，页面上只显示末 4 位，操作日志只记谁改了哪一家。服务器的 JWT_SECRET
                更换后需要在这里重新填写。
              </li>
            </ul>
            {q.data.providers.map((p) => (
              <ProviderCard key={p.var} p={p} />
            ))}
          </div>
        )}
      </RoleGate>
    </PageFrame>
  )
}
