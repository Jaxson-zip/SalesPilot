"use client"

import { Check, Copy } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { FormField, SimpleSelect } from "@/components/biz/FormControls"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import {
  useCreateAccount,
  useSaveTeam,
  useUpdateAccount,
  type AccountItem,
  type TeamItem,
  type TempPassword,
} from "@/hooks/useAccounts"
import { useProductLines, usePackName } from "@/hooks/useProductLines"
import { copyText } from "@/lib/clipboard"
import { USERNAME_RE } from "@/lib/password"
import { ROLE_TITLE } from "@/lib/session"
import type { Role } from "@/types/api"

const ROLE_OPTIONS: { value: Role; label: string }[] = [
  { value: "sales", label: ROLE_TITLE.sales },
  { value: "manager", label: ROLE_TITLE.manager },
  { value: "admin", label: ROLE_TITLE.admin },
]

/** 新建 / 编辑成员：登录名只在新建时填，之后不能改；管理员不属于团队 */
export function MemberDialog({
  open,
  account,
  teams,
  onClose,
  onCreated,
}: {
  open: boolean
  /** 编辑时传入；新建时为 null */
  account: AccountItem | null
  teams: TeamItem[]
  onClose: () => void
  onCreated: (r: TempPassword) => void
}) {
  const [username, setUsername] = useState("")
  const [name, setName] = useState(account?.name ?? "")
  const [role, setRole] = useState<Role>(account?.role ?? "sales")
  const [teamId, setTeamId] = useState(account?.team_id ?? teams[0]?.id ?? "")
  const [errors, setErrors] = useState<{ username?: string; name?: string; team?: string }>({})
  const create = useCreateAccount()
  const update = useUpdateAccount()
  const pending = create.isPending || update.isPending
  const needTeam = role !== "admin"

  const submit = () => {
    const found: typeof errors = {}
    if (!account && !USERNAME_RE.test(username)) found.username = "字母开头，3～30 位字母、数字或 _ . -"
    if (!name.trim()) found.name = "请填写姓名"
    if (needTeam && !teamId) found.team = "销售和主管要选择所属团队"
    if (Object.keys(found).length) return setErrors(found)
    const team_id = needTeam ? teamId : null
    if (account) {
      update.mutate({ id: account.id, body: { name: name.trim(), role, team_id } }, { onSuccess: onClose })
    } else {
      create.mutate({ username, name: name.trim(), role, team_id }, { onSuccess: onCreated })
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{account ? `编辑成员：${account.name}` : "新建成员"}</DialogTitle>
          <DialogDescription>
            {account
              ? "改角色或团队后立即生效，对方下一次操作就按新权限。"
              : "保存后生成临时密码，成员首次登录必须修改。"}
          </DialogDescription>
        </DialogHeader>
        {account ? null : (
          <FormField label="登录名" required error={errors.username} hint="创建后不能修改" htmlFor="member-username">
            <Input
              id="member-username"
              value={username}
              maxLength={30}
              aria-invalid={Boolean(errors.username)}
              onChange={(e) => setUsername(e.target.value.trim())}
            />
          </FormField>
        )}
        <FormField label="姓名" required error={errors.name} htmlFor="member-name">
          <Input
            id="member-name"
            value={name}
            maxLength={50}
            aria-invalid={Boolean(errors.name)}
            onChange={(e) => setName(e.target.value)}
          />
        </FormField>
        <FormField label="角色" required htmlFor="member-role">
          <SimpleSelect id="member-role" value={role} onChange={setRole} options={ROLE_OPTIONS} ariaLabel="角色" />
        </FormField>
        {needTeam ? (
          <FormField label="所属团队" required error={errors.team} htmlFor="member-team">
            <SimpleSelect
              id="member-team"
              value={teamId}
              onChange={setTeamId}
              options={teams.map((t) => ({ value: t.id, label: t.name }))}
              placeholder="选择团队"
              ariaLabel="所属团队"
            />
          </FormField>
        ) : (
          <p className="text-xs text-zinc-500">管理员不属于任何团队，负责系统配置，业务数据只读。</p>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button onClick={submit} disabled={pending}>
            {pending ? "保存中…" : account ? "保存" : "创建并生成密码"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** 临时密码只显示这一次：提示管理员复制后线下告诉成员 */
export function TempPasswordDialog({ result, onClose }: { result: TempPassword | null; onClose: () => void }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    if (!result) return
    const text = `账号：${result.account.username ?? ""}\n临时密码：${result.temp_password}`
    void copyText(text).then((ok) => (ok ? setCopied(true) : toast.error("复制失败，请手动记下临时密码")))
  }
  return (
    <Dialog
      open={result !== null}
      onOpenChange={(o) => {
        if (!o) {
          setCopied(false)
          onClose()
        }
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>临时密码</DialogTitle>
          <DialogDescription>
            只显示这一次，关闭后无法再查看。请转告 {result?.account.name}，首次登录必须修改。
          </DialogDescription>
        </DialogHeader>
        <dl className="grid grid-cols-[4rem_1fr] gap-y-2 rounded-md bg-zinc-50 px-4 py-3 text-sm">
          <dt className="text-zinc-500">账号</dt>
          <dd className="font-medium">{result?.account.username}</dd>
          <dt className="text-zinc-500">临时密码</dt>
          <dd className="font-mono text-base font-medium tracking-wide" aria-label="临时密码">
            {result?.temp_password}
          </dd>
        </dl>
        <DialogFooter>
          <Button variant="outline" onClick={copy}>
            {copied ? <Check /> : <Copy />}
            {copied ? "已复制" : "复制账号和密码"}
          </Button>
          <Button onClick={onClose}>我已记下</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

const SYSTEM_DEFAULT = "system"

/** 新建团队 / 修改团队名称和默认行业包 */
export function TeamDialog({ open, team, onClose }: { open: boolean; team: TeamItem | null; onClose: () => void }) {
  const [name, setName] = useState(team?.name ?? "")
  const [line, setLine] = useState(team?.default_product_line_id ?? SYSTEM_DEFAULT)
  const [error, setError] = useState<string>()
  const save = useSaveTeam()
  const lines = useProductLines()
  const packName = usePackName()
  const lineOptions = [
    { value: SYSTEM_DEFAULT, label: "系统默认行业包" },
    ...(lines.data ?? [])
      .filter((l) => l.enabled || l.id === line)
      .map((l) => ({ value: l.id, label: `${l.name}（${packName(l.pack)}）` })),
  ]
  const submit = () => {
    if (!name.trim()) return setError("请填写团队名称")
    save.mutate(
      { id: team?.id, name: name.trim(), default_product_line_id: line === SYSTEM_DEFAULT ? null : line },
      { onSuccess: onClose },
    )
  }
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{team ? "修改团队" : "新建团队"}</DialogTitle>
          <DialogDescription>团队决定主管能看到和审批哪些成员的数据，以及成员默认用哪个行业包。</DialogDescription>
        </DialogHeader>
        <FormField label="团队名称" required error={error} htmlFor="team-name">
          <Input
            id="team-name"
            value={name}
            maxLength={100}
            aria-invalid={Boolean(error)}
            onChange={(e) => {
              setName(e.target.value)
              setError(undefined)
            }}
          />
        </FormField>
        <FormField
          label="默认产品线（行业包）"
          hint="成员在 AI 工作台直接出方案、学习问答时用这个行业包；从商机进入时按商机的产品线。"
        >
          <SimpleSelect ariaLabel="默认产品线" value={line} onChange={setLine} options={lineOptions} />
        </FormField>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button onClick={submit} disabled={save.isPending}>
            {save.isPending ? "保存中…" : "保存"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
