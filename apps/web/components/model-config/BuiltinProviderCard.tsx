"use client"

import { Loader2, PlugZap } from "lucide-react"
import { useState } from "react"

import { FormField, SimpleSelect } from "@/components/biz/FormControls"
import { AvailTag, ModelChip, Warn, time } from "@/components/model-config/shared"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useSaveBuiltin, useTestBuiltin, type BuiltinInput, type BuiltinProvider } from "@/hooks/useModelConfig"
import {
  BUILTIN_PROTOCOLS,
  builtinDirty,
  builtinForm,
  fromOption,
  keySourceText,
  type BuiltinForm,
} from "@/lib/model-config"

/** 内置厂商（models.yaml 里的）：Key、接口地址、协议都可以在网页上改，留空用服务器默认 */
export function BuiltinProviderCard({ p }: { p: BuiltinProvider }) {
  const save = useSaveBuiltin()
  const test = useTestBuiltin()
  const [form, setForm] = useState<BuiltinForm>(() => builtinForm(p))
  const set = (patch: Partial<BuiltinForm>) => setForm((f) => ({ ...f, ...patch }))
  const typed = form.key.trim()
  const dirty = builtinDirty(p, form)
  const id = p.var.toLowerCase()

  const input = (key: string | null | undefined): BuiltinInput => ({
    var: p.var,
    ...(key === undefined ? {} : { key }),
    base: form.base.trim(),
    protocol: fromOption(form.protocol),
    adapter: form.protocol === "native" ? form.adapter.trim() : "",
  })
  const reset = (next: BuiltinProvider) => setForm(builtinForm(next))
  const afterSave = (data: { builtin: BuiltinProvider[] }) => {
    const next = data.builtin.find((b) => b.var === p.var)
    if (next) reset(next)
  }

  return (
    <section aria-label={p.label} className="space-y-3 rounded-lg border border-zinc-200 p-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-medium">{p.label}</h3>
        <AvailTag available={p.available} configured={p.key_source !== "none"} />
        <span className="text-xs text-zinc-400">Key：{keySourceText(p, time)}</span>
      </div>
      {p.broken ? <Warn>之前在网页上保存的 Key 解不开了（服务器的加密密钥换过），请重新填写。</Warn> : null}
      <div className="space-y-1 text-xs text-zinc-500">
        <p>在哪里申请：{p.hint}</p>
        {p.models.length ? (
          <div className="flex flex-wrap gap-1">
            {p.models.map((m) => (
              <ModelChip key={m.alias} m={m} />
            ))}
          </div>
        ) : null}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <FormField label="API Key" htmlFor={`${id}-key`}>
          <Input
            id={`${id}-key`}
            type="password"
            autoComplete="off"
            value={form.key}
            onChange={(e) => set({ key: e.target.value })}
            placeholder={p.key_source === "none" ? "粘贴 API Key" : "如需更换，粘贴新的 API Key"}
          />
        </FormField>
        <FormField
          label="接口地址"
          htmlFor={`${id}-base`}
          hint={p.default_base ? `留空用默认：${p.default_base}` : "留空用服务器默认"}
        >
          <Input
            id={`${id}-base`}
            value={form.base}
            onChange={(e) => set({ base: e.target.value })}
            placeholder={p.default_base || "https://…/v1"}
          />
        </FormField>
        <FormField
          label="协议"
          hint={
            form.protocol === "default"
              ? "用模型清单里的写法（已通过契约测试）"
              : "对话和向量模型都改走这个协议；重排模型不变"
          }
        >
          <SimpleSelect
            ariaLabel={`${p.label} 协议`}
            value={form.protocol}
            onChange={(v) => set({ protocol: v })}
            options={BUILTIN_PROTOCOLS}
          />
        </FormField>
        {form.protocol === "native" ? (
          <FormField label="适配名" htmlFor={`${id}-adapter`} hint="LiteLLM 的厂商名，例如 deepseek、dashscope">
            <Input
              id={`${id}-adapter`}
              value={form.adapter}
              onChange={(e) => set({ adapter: e.target.value })}
              placeholder="deepseek"
            />
          </FormField>
        ) : null}
      </div>
      <div className="flex flex-wrap justify-end gap-2">
        {p.key_source === "web" || p.broken ? (
          <Button
            variant="ghost"
            size="sm"
            disabled={save.isPending}
            onClick={() =>
              save.mutate(
                { var: p.var, key: "", base: p.base, protocol: p.protocol, adapter: p.adapter },
                { onSuccess: afterSave },
              )
            }
          >
            清除网页上的 Key
          </Button>
        ) : null}
        {p.base || p.protocol ? (
          <Button
            variant="ghost"
            size="sm"
            disabled={save.isPending}
            onClick={() => save.mutate({ var: p.var, base: "", protocol: "", adapter: "" }, { onSuccess: afterSave })}
          >
            恢复默认地址和协议
          </Button>
        ) : null}
        <Button
          variant="outline"
          size="sm"
          disabled={test.isPending || (!typed && p.key_source === "none")}
          onClick={() => test.mutate(input(typed || null))}
        >
          {test.isPending ? <Loader2 className="animate-spin" /> : <PlugZap />}
          {typed ? "测试这个 Key" : "测试连接"}
        </Button>
        <Button
          size="sm"
          disabled={!dirty || save.isPending}
          onClick={() => save.mutate(input(typed || undefined), { onSuccess: afterSave })}
        >
          保存
        </Button>
      </div>
    </section>
  )
}
