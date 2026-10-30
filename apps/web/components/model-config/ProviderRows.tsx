"use client"

import { ChevronRight, Loader2, PlugZap } from "lucide-react"
import { useState, type ReactNode } from "react"

import { SimpleSelect } from "@/components/biz/FormControls"
import { Warn } from "@/components/model-config/shared"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useSaveBuiltin, useTestBuiltin, type BuiltinProvider } from "@/hooks/useModelConfig"
import { BUILTIN_PROTOCOLS, fromOption, toOption, type ProtocolOption } from "@/lib/model-config"
import { cn } from "@/lib/utils"

/** 状态点：绿 = 可用，红 = 没 Key 或用不了，灰 = 模型服务连不上、状态未知 */
export function StatusDot({ ok }: { ok: boolean | null }) {
  const text = ok === null ? "状态未知" : ok ? "可用" : "不可用"
  return (
    <span
      role="img"
      aria-label={text}
      title={text}
      className={cn(
        "inline-block size-2 shrink-0 rounded-full",
        ok === null ? "bg-zinc-300" : ok ? "bg-emerald-500" : "bg-red-500",
      )}
    />
  )
}

/** 一行：名称、标签、状态点，右侧操作；展开后下面接编辑区 */
export function RowCard({
  label,
  title,
  tag,
  ok,
  summary,
  actions,
  open,
  children,
}: {
  label: string
  title: ReactNode
  tag?: string
  ok?: boolean | null
  summary?: ReactNode
  actions: ReactNode
  open: boolean
  children?: ReactNode
}) {
  return (
    <li aria-label={label} className="rounded-xl border border-zinc-200 px-4 py-3">
      <div className="flex min-h-8 items-center gap-2">
        <span className="shrink-0 font-medium">{title}</span>
        {tag ? <span className="rounded border border-zinc-200 px-1.5 text-[11px] text-zinc-500">{tag}</span> : null}
        {ok !== undefined ? <StatusDot ok={ok} /> : null}
        {summary ? <span className="hidden min-w-0 truncate text-xs text-zinc-500 sm:inline">{summary}</span> : null}
        <span className="ml-auto flex shrink-0 gap-1">{actions}</span>
      </div>
      {summary ? <p className="mt-1 text-xs text-zinc-500 sm:hidden">{summary}</p> : null}
      {open ? <div className="mt-3 border-t border-zinc-100 pt-3">{children}</div> : null}
    </li>
  )
}

/** 默认折叠的「自定义设置」 */
export function MoreSettings({ children }: { children: ReactNode }) {
  return (
    <details className="group">
      <summary className="flex w-fit cursor-pointer list-none items-center gap-1 text-xs text-zinc-500 hover:text-zinc-800">
        <ChevronRight className="size-3.5 transition-transform group-open:rotate-90" />
        自定义设置
      </summary>
      <div className="mt-3 space-y-3">{children}</div>
    </details>
  )
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-xs text-zinc-500">{label}</span>
      {children}
    </label>
  )
}

/** 内置厂商的编辑区：API Key；接口地址和协议在「自定义设置」里 */
export function BuiltinEditor({ p, onClose }: { p: BuiltinProvider; onClose: () => void }) {
  const save = useSaveBuiltin()
  const test = useTestBuiltin()
  const [key, setKey] = useState("")
  const [base, setBase] = useState(p.base)
  const [protocol, setProtocol] = useState<ProtocolOption>(toOption(p.protocol))
  const [adapter, setAdapter] = useState(p.adapter)
  const typed = key.trim()
  const body = {
    var: p.var,
    base: base.trim(),
    protocol: fromOption(protocol),
    adapter: protocol === "native" ? adapter.trim() : "",
  }
  const dirty =
    typed !== "" ||
    body.base !== p.base ||
    body.protocol !== p.protocol ||
    (protocol === "native" && body.adapter !== p.adapter)
  const stored = p.key_source !== "none" && !p.broken

  return (
    <div className="space-y-3">
      <Field label="API Key">
        <Input
          type="password"
          autoComplete="off"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder={
            p.key_source === "env"
              ? "已在服务器配置，输入新值可替换"
              : stored
                ? `已配置${p.tail ? `（末 4 位 ${p.tail}）` : ""}，输入新值可替换`
                : "输入 API Key"
          }
        />
      </Field>
      {p.broken ? <Warn>保存的 Key 解不开了，请重新填写</Warn> : null}
      {p.hint ? <p className="text-xs text-zinc-400">在哪里申请：{p.hint}</p> : null}
      <MoreSettings>
        <Field label="接口地址">
          <Input value={base} onChange={(e) => setBase(e.target.value)} placeholder={p.default_base || "厂商默认"} />
        </Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="协议">
            <SimpleSelect ariaLabel="协议" value={protocol} onChange={setProtocol} options={BUILTIN_PROTOCOLS} />
          </Field>
          {protocol === "native" ? (
            <Field label="适配名">
              <Input value={adapter} onChange={(e) => setAdapter(e.target.value)} placeholder="deepseek" />
            </Field>
          ) : null}
        </div>
      </MoreSettings>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={test.isPending || (!typed && !stored)}
          onClick={() => test.mutate({ ...body, key: typed || null })}
        >
          {test.isPending ? <Loader2 className="animate-spin" /> : <PlugZap />}
          测试
        </Button>
        {p.key_source === "web" || p.broken ? (
          <Button
            variant="ghost"
            size="sm"
            disabled={save.isPending}
            onClick={() =>
              save.mutate(
                { var: p.var, base: p.base, protocol: p.protocol, adapter: p.adapter, key: "" },
                { onSuccess: onClose },
              )
            }
          >
            清除 Key
          </Button>
        ) : null}
        <span className="ml-auto flex gap-2">
          <Button variant="ghost" size="sm" onClick={onClose}>
            取消
          </Button>
          <Button
            size="sm"
            disabled={!dirty || save.isPending}
            onClick={() => save.mutate({ ...body, ...(typed ? { key: typed } : {}) }, { onSuccess: onClose })}
          >
            保存
          </Button>
        </span>
      </div>
    </div>
  )
}
