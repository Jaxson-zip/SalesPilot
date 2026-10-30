"use client"

import { Loader2, PlugZap } from "lucide-react"
import { useState } from "react"

import { SimpleSelect } from "@/components/biz/FormControls"
import { AvailTag, Warn } from "@/components/model-config/shared"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useSaveBuiltin, useTestBuiltin, type BuiltinProvider } from "@/hooks/useModelConfig"
import { BUILTIN_PROTOCOLS, fromOption, keySourceText, toOption, type ProtocolOption } from "@/lib/model-config"

const saved = (p: BuiltinProvider) => ({ var: p.var, base: p.base, protocol: p.protocol, adapter: p.adapter })

/** 一家厂商一行：状态 + 填 Key + 测试 / 保存。地址和协议在「高级设置」里 */
export function KeyRow({ p }: { p: BuiltinProvider }) {
  const save = useSaveBuiltin()
  const test = useTestBuiltin()
  const [key, setKey] = useState("")
  const typed = key.trim()

  return (
    <li aria-label={p.label} className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:gap-4">
      <div className="min-w-0 sm:w-56">
        <div className="flex items-center gap-2">
          <span className="font-medium">{p.label}</span>
          <AvailTag available={p.available} configured={p.key_source !== "none"} />
        </div>
        {p.key_source !== "none" ? <p className="mt-0.5 text-xs text-zinc-500">{keySourceText(p)}</p> : null}
        {p.broken ? <Warn>保存的 Key 解不开了，请重新填写</Warn> : null}
      </div>
      <Input
        type="password"
        autoComplete="off"
        value={key}
        onChange={(e) => setKey(e.target.value)}
        placeholder={p.key_source === "none" ? `粘贴 Key（${p.hint}）` : "更换 Key"}
        aria-label={`${p.label} API Key`}
        className="sm:flex-1"
      />
      <div className="flex shrink-0 gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={test.isPending || (!typed && p.key_source === "none")}
          onClick={() => test.mutate({ ...saved(p), key: typed || null })}
        >
          {test.isPending ? <Loader2 className="animate-spin" /> : <PlugZap />}
          测试
        </Button>
        <Button
          size="sm"
          disabled={!typed || save.isPending}
          onClick={() => save.mutate({ ...saved(p), key: typed }, { onSuccess: () => setKey("") })}
        >
          保存
        </Button>
        {p.key_source === "web" || p.broken ? (
          <Button
            variant="ghost"
            size="sm"
            disabled={save.isPending}
            title="删掉网页上填的 Key，改用服务器配置"
            onClick={() => save.mutate({ ...saved(p), key: "" })}
          >
            清除
          </Button>
        ) : null}
      </div>
    </li>
  )
}

/** 高级设置：内置厂商的接口地址和协议（留空 = 官方地址、按模型清单） */
export function EndpointRow({ p }: { p: BuiltinProvider }) {
  const save = useSaveBuiltin()
  const [base, setBase] = useState(p.base)
  const [protocol, setProtocol] = useState<ProtocolOption>(toOption(p.protocol))
  const [adapter, setAdapter] = useState(p.adapter)
  const dirty =
    base.trim() !== p.base ||
    fromOption(protocol) !== p.protocol ||
    (protocol === "native" && adapter.trim() !== p.adapter)

  return (
    <li
      aria-label={`${p.label} 接口`}
      className="grid gap-2 px-4 py-3 sm:grid-cols-[8rem_1fr_11rem_auto] sm:items-center"
    >
      <span className="font-medium">{p.label}</span>
      <Input
        value={base}
        onChange={(e) => setBase(e.target.value)}
        placeholder={p.default_base || "https://…/v1"}
        aria-label={`${p.label} 接口地址`}
      />
      <SimpleSelect ariaLabel={`${p.label} 协议`} value={protocol} onChange={setProtocol} options={BUILTIN_PROTOCOLS} />
      <div className="flex gap-2">
        {protocol === "native" ? (
          <Input
            value={adapter}
            onChange={(e) => setAdapter(e.target.value)}
            placeholder="适配名"
            aria-label={`${p.label} 适配名`}
            className="w-28"
          />
        ) : null}
        <Button
          size="sm"
          variant="outline"
          disabled={!dirty || save.isPending}
          onClick={() =>
            save.mutate({
              var: p.var,
              base: base.trim(),
              protocol: fromOption(protocol),
              adapter: protocol === "native" ? adapter.trim() : "",
            })
          }
        >
          保存
        </Button>
      </div>
    </li>
  )
}
