"use client"

import { useQuery } from "@tanstack/react-query"
import { Shield, User, UserCheck, Zap, type LucideIcon } from "lucide-react"
import { useRouter } from "next/navigation"
import { useState, type FormEvent } from "react"

import { FormField } from "@/components/biz/FormControls"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { errorMessage } from "@/lib/errors"
import { DEMO_USERS, fetchAuthOptions, ROLES } from "@/lib/session"
import type { Role } from "@/types/api"

const ROLE_ICONS: Record<Role, LucideIcon> = { sales: User, manager: UserCheck, admin: Shield }

/** 登录后回到原来的页面（只接受站内路径） */
function nextPath(): string {
  const next = new URLSearchParams(window.location.search).get("next")
  return next?.startsWith("/") && !next.startsWith("//") ? next : "/dashboard"
}

/**
 * 登录页：账号密码登录；演示环境（DEMO_LOGIN）下面还有演示账户一键进入。
 * 服务端配置了访问口令时，两种方式都要先填口令。
 */
export default function LoginPage() {
  const router = useRouter()
  const { signIn, signInWithPassword } = useSession()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [code, setCode] = useState("")
  const [errors, setErrors] = useState<{ username?: string; password?: string; code?: string; form?: string }>({})
  const [pending, setPending] = useState<string | null>(null)
  const options = useQuery({ queryKey: ["auth", "options"], queryFn: fetchAuthOptions, staleTime: 60_000 })
  const needCode = options.data?.access_code_required ?? false
  const demo = options.data?.demo_login ?? false

  const run = async (key: string, login: () => Promise<void>) => {
    setPending(key)
    setErrors({})
    try {
      await login()
      router.replace(nextPath())
    } catch (err) {
      const message = errorMessage(err)
      setErrors(message.includes("口令") ? { code: message } : { form: message })
      setPending(null)
    }
  }
  const codeMissing = () => {
    if (needCode && !code.trim()) {
      setErrors({ code: "请输入访问口令" })
      return true
    }
    return false
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const found: typeof errors = {}
    if (!username.trim()) found.username = "请输入账号"
    if (!password) found.password = "请输入密码"
    if (needCode && !code.trim()) found.code = "请输入访问口令"
    if (Object.keys(found).length) return setErrors(found)
    void run("password", () => signInWithPassword(username.trim(), password, code.trim()))
  }
  const enterDemo = (r: Role) => {
    if (codeMissing()) return
    void run(r, () => signIn(r, code.trim()))
  }

  return (
    <main className="flex min-h-dvh items-center justify-center bg-zinc-50 px-4 py-10">
      <div className="w-full max-w-md space-y-6">
        <div className="space-y-2 text-center">
          <span className="bg-primary text-primary-foreground inline-flex size-10 items-center justify-center rounded-lg">
            <Zap className="size-5" />
          </span>
          <h1 className="text-xl font-semibold text-zinc-900">SalesPilot · AI 销售 CRM</h1>
          <p className="text-sm text-zinc-500">登录后开始工作</p>
        </div>

        <form onSubmit={submit} className="space-y-4 rounded-xl border border-zinc-200 bg-white p-5" aria-label="登录">
          <FormField label="账号" required error={errors.username} htmlFor="login-username">
            <Input
              id="login-username"
              autoComplete="username"
              value={username}
              maxLength={50}
              aria-invalid={Boolean(errors.username)}
              onChange={(e) => {
                setUsername(e.target.value)
                setErrors({ ...errors, username: undefined, form: undefined })
              }}
            />
          </FormField>
          <FormField label="密码" required error={errors.password} htmlFor="login-password">
            <Input
              id="login-password"
              type="password"
              autoComplete="current-password"
              value={password}
              maxLength={100}
              aria-invalid={Boolean(errors.password)}
              onChange={(e) => {
                setPassword(e.target.value)
                setErrors({ ...errors, password: undefined, form: undefined })
              }}
            />
          </FormField>
          {needCode ? (
            <FormField label="访问口令" required error={errors.code} hint="由部署方提供" htmlFor="access-code">
              <Input
                id="access-code"
                type="password"
                value={code}
                maxLength={100}
                aria-invalid={Boolean(errors.code)}
                onChange={(e) => {
                  setCode(e.target.value)
                  setErrors({ ...errors, code: undefined })
                }}
              />
            </FormField>
          ) : null}
          {errors.form ? (
            <p role="alert" className="text-sm text-red-600">
              {errors.form}
            </p>
          ) : null}
          <Button type="submit" className="w-full" disabled={pending !== null || options.isPending}>
            {pending === "password" ? "登录中…" : "登录"}
          </Button>
        </form>

        {demo ? (
          <section aria-labelledby="demo-title" className="space-y-2">
            <div className="flex items-center gap-3 text-xs text-zinc-400">
              <span className="h-px flex-1 bg-zinc-200" />
              <span id="demo-title">或用演示账户一键进入</span>
              <span className="h-px flex-1 bg-zinc-200" />
            </div>
            {ROLES.map((r) => {
              const u = DEMO_USERS[r]
              const Icon = ROLE_ICONS[r]
              return (
                <button
                  key={r}
                  type="button"
                  disabled={pending !== null}
                  onClick={() => enterDemo(r)}
                  aria-label={`以${u.name}（${u.title}）进入`}
                  className="flex w-full items-start gap-3 rounded-lg border border-zinc-200 bg-white p-3 text-left transition-colors hover:border-zinc-400 disabled:opacity-60"
                >
                  <span className="mt-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-zinc-100">
                    <Icon className="size-4 text-zinc-600" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-baseline gap-x-2">
                      <span className="font-medium text-zinc-900">{u.name}</span>
                      <span className="text-sm text-zinc-500">
                        {u.title} · {u.scope}
                      </span>
                      <span className="text-xs text-zinc-400">{pending === r ? "进入中…" : u.login}</span>
                    </span>
                    <span className="mt-0.5 block text-xs text-zinc-500">{u.can}</span>
                  </span>
                </button>
              )
            })}
            <p className="pt-1 text-center text-xs text-zinc-400">
              演示环境：数据为虚构的示例数据，可以随意操作；登录后可在左下角切换演示账户
            </p>
          </section>
        ) : null}
      </div>
    </main>
  )
}
