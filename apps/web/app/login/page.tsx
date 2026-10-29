"use client"

import { useQuery } from "@tanstack/react-query"
import { Shield, User, UserCheck, Zap, type LucideIcon } from "lucide-react"
import { useRouter } from "next/navigation"
import { useEffect, useState, type FormEvent } from "react"

import { FormField } from "@/components/biz/FormControls"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { errorMessage } from "@/lib/errors"
import { DEMO_USERS, fetchAuthOptions, getStoredRole, ROLES } from "@/lib/session"
import { cn } from "@/lib/utils"
import type { Role } from "@/types/api"

const ROLE_ICONS: Record<Role, LucideIcon> = { sales: User, manager: UserCheck, admin: Shield }

/** 登录后回到原来的页面（只接受站内路径） */
function nextPath(): string {
  const next = new URLSearchParams(window.location.search).get("next")
  return next?.startsWith("/") && !next.startsWith("//") ? next : "/dashboard"
}

/** 登录页：选一个演示账户进入；服务端配置了访问口令时需要先输入口令 */
export default function LoginPage() {
  const router = useRouter()
  const { signIn } = useSession()
  const [role, setRole] = useState<Role>("sales")
  // 默认选中上次用的账户（localStorage 只能在挂载后读，避免水合不一致）
  useEffect(() => setRole(getStoredRole()), [])
  const [code, setCode] = useState("")
  const [error, setError] = useState<string>()
  const [pending, setPending] = useState(false)
  const options = useQuery({ queryKey: ["auth", "options"], queryFn: fetchAuthOptions, staleTime: 60_000 })
  const needCode = options.data?.access_code_required ?? false

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (needCode && !code.trim()) return setError("请输入访问口令")
    setPending(true)
    setError(undefined)
    try {
      await signIn(role, code.trim())
      router.replace(nextPath())
    } catch (err) {
      setError(errorMessage(err))
      setPending(false)
    }
  }

  return (
    <main className="flex min-h-dvh items-center justify-center bg-zinc-50 px-4 py-10">
      <form onSubmit={submit} className="w-full max-w-md space-y-6" aria-label="登录">
        <div className="space-y-2 text-center">
          <span className="bg-primary text-primary-foreground inline-flex size-10 items-center justify-center rounded-lg">
            <Zap className="size-5" />
          </span>
          <h1 className="text-xl font-semibold text-zinc-900">SalesPilot · AI 销售 CRM</h1>
          <p className="text-sm text-zinc-500">选择一个演示账户进入，登录后可在左下角随时切换</p>
        </div>

        <fieldset className="space-y-2">
          <legend className="mb-2 text-sm font-medium text-zinc-700">演示账户</legend>
          {ROLES.map((r) => {
            const u = DEMO_USERS[r]
            const Icon = ROLE_ICONS[r]
            const active = r === role
            return (
              <label
                key={r}
                className={cn(
                  "flex cursor-pointer items-start gap-3 rounded-lg border bg-white p-3 transition-colors",
                  active ? "border-zinc-900 ring-1 ring-zinc-900" : "border-zinc-200 hover:border-zinc-300",
                )}
              >
                <input
                  type="radio"
                  name="account"
                  value={r}
                  checked={active}
                  onChange={() => setRole(r)}
                  className="sr-only"
                  aria-label={`${u.title} · ${u.name}`}
                />
                <span className="mt-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-zinc-100">
                  <Icon className="size-4 text-zinc-600" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline gap-2">
                    <span className="font-medium text-zinc-900">{u.name}</span>
                    <span className="text-sm text-zinc-500">
                      {u.title} · {u.scope}
                    </span>
                  </span>
                  <span className="mt-0.5 block text-xs text-zinc-500">{u.can}</span>
                </span>
              </label>
            )
          })}
        </fieldset>

        {needCode ? (
          <FormField label="访问口令" required error={error} htmlFor="access-code">
            <Input
              id="access-code"
              type="password"
              autoComplete="current-password"
              value={code}
              maxLength={100}
              aria-invalid={Boolean(error)}
              onChange={(e) => {
                setCode(e.target.value)
                setError(undefined)
              }}
            />
          </FormField>
        ) : error ? (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        ) : null}

        <Button type="submit" className="w-full" disabled={pending || options.isPending}>
          {pending ? "登录中…" : `以「${DEMO_USERS[role].name}」进入`}
        </Button>
        <p className="text-center text-xs text-zinc-400">
          演示环境：数据为虚构的示例数据，可以随意操作；AI 功能使用真实大模型
        </p>
      </form>
    </main>
  )
}
