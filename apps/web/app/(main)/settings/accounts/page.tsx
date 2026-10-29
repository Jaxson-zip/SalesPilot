"use client"

import { Pencil, Plus, UsersRound } from "lucide-react"
import { useState } from "react"

import { useConfirmAction } from "@/components/biz/ConfirmAction"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { Tag } from "@/components/biz/Tag"
import { MemberDialog, TeamDialog, TempPasswordDialog } from "@/components/settings/AccountDialogs"
import { RoleGate } from "@/components/shell/RoleGate"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  useAccounts,
  useResetPassword,
  useTeams,
  useUpdateAccount,
  type AccountItem,
  type TeamItem,
  type TempPassword,
} from "@/hooks/useAccounts"
import { formatRelative } from "@/lib/format"
import { ROLE_TITLE } from "@/lib/session"
import { cn } from "@/lib/utils"

function Status({ a }: { a: AccountItem }) {
  if (!a.active) return <Tag color="gray">已停用</Tag>
  if (a.must_change_password) return <Tag color="orange">待改密码</Tag>
  return <Tag color="green">正常</Tag>
}

function Teams({ teams, onEdit }: { teams: TeamItem[]; onEdit: (t: TeamItem | null) => void }) {
  return (
    <section aria-label="团队" className="space-y-2">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-zinc-700">团队</h2>
        <Button size="xs" variant="outline" onClick={() => onEdit(null)}>
          <Plus />
          新建团队
        </Button>
      </div>
      <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {teams.map((t) => (
          <li
            key={t.id}
            className="flex items-start justify-between gap-2 rounded-lg border border-zinc-200 bg-white p-3"
          >
            <div className="min-w-0">
              <div className="truncate font-medium">{t.name}</div>
              <div className="text-xs text-zinc-500">
                {t.members} 名成员 · 主管：{t.managers.length ? t.managers.join("、") : "未设置"}
              </div>
            </div>
            <Button size="icon-xs" variant="ghost" aria-label={`修改${t.name}名称`} onClick={() => onEdit(t)}>
              <Pencil />
            </Button>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Members({
  accounts,
  me,
  onEdit,
  onReset,
  onToggle,
}: {
  accounts: AccountItem[]
  me: string | null
  onEdit: (a: AccountItem) => void
  onReset: (a: AccountItem) => void
  onToggle: (a: AccountItem) => void
}) {
  return (
    <section aria-label="成员" className="space-y-2">
      <h2 className="text-sm font-medium text-zinc-700">成员</h2>
      <div className="overflow-x-auto rounded-lg border border-zinc-200 bg-white">
        <table className="w-full min-w-[720px] text-left text-sm" aria-label="成员列表">
          <thead className="border-b border-zinc-200 text-xs text-zinc-500">
            <tr>
              <th className="px-4 py-2 font-normal">姓名</th>
              <th className="py-2 font-normal">角色</th>
              <th className="py-2 font-normal">团队</th>
              <th className="py-2 font-normal">状态</th>
              <th className="py-2 font-normal">最近登录</th>
              <th className="py-2 text-right font-normal">名下客户</th>
              <th className="px-4 py-2 text-right font-normal">操作</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((a) => (
              <tr key={a.id} className={cn("border-b border-zinc-100 last:border-0", !a.active && "text-zinc-400")}>
                <td className="px-4 py-2.5">
                  <div className="font-medium">{a.name}</div>
                  <div className="text-xs text-zinc-400">{a.username ?? "未设置登录名"}</div>
                </td>
                <td className="py-2.5">{ROLE_TITLE[a.role]}</td>
                <td className="py-2.5">{a.team_name ?? "—"}</td>
                <td className="py-2.5">
                  <Status a={a} />
                </td>
                <td className="py-2.5 text-zinc-500">
                  {a.last_login_at ? formatRelative(a.last_login_at) : "从未登录"}
                </td>
                <td className="py-2.5 text-right tabular-nums">
                  {a.customers}
                  {!a.active && a.customers > 0 ? (
                    <Tag color="orange" className="ml-1.5">
                      待交接
                    </Tag>
                  ) : null}
                </td>
                <td className="px-4 py-2.5">
                  <div className="flex justify-end gap-1">
                    <Button size="xs" variant="ghost" onClick={() => onEdit(a)} aria-label={`编辑${a.name}`}>
                      编辑
                    </Button>
                    <Button size="xs" variant="ghost" onClick={() => onReset(a)} aria-label={`重置${a.name}的密码`}>
                      重置密码
                    </Button>
                    {a.id === me ? null : (
                      <Button
                        size="xs"
                        variant="ghost"
                        onClick={() => onToggle(a)}
                        aria-label={`${a.active ? "停用" : "启用"}${a.name}`}
                      >
                        {a.active ? "停用" : "启用"}
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function AccountsBody() {
  const { userId } = useSession()
  const accounts = useAccounts()
  const teams = useTeams()
  const update = useUpdateAccount()
  const reset = useResetPassword()
  const { ask, dialog } = useConfirmAction()
  const [editing, setEditing] = useState<AccountItem | "new" | null>(null)
  const [teamOf, setTeamOf] = useState<TeamItem | "new" | null>(null)
  const [temp, setTemp] = useState<TempPassword | null>(null)

  if (accounts.isError) {
    return (
      <QueryError
        error={accounts.error}
        onRetry={() => void accounts.refetch()}
        retrying={accounts.isFetching}
        feature="成员"
      />
    )
  }
  if (!accounts.data || !teams.data) return <Skeleton className="h-64 w-full" />

  const onReset = (a: AccountItem) =>
    ask({
      title: `重置「${a.name}」的密码？`,
      description: "会生成新的临时密码，对方当前的登录立即失效，下次登录必须修改密码。",
      confirmLabel: "确认重置",
      onConfirm: () => reset.mutate(a.id, { onSuccess: setTemp }),
    })
  const onToggle = (a: AccountItem) =>
    ask(
      a.active
        ? {
            title: `停用「${a.name}」？`,
            description:
              a.customers > 0
                ? `停用后不能登录，当前登录立即失效。名下还有 ${a.customers} 个客户，会通知所在团队的主管用「按人交接」转给其他成员。`
                : "停用后不能登录，当前登录立即失效。历史数据保留，可以随时重新启用。",
            confirmLabel: "确认停用",
            destructive: true,
            onConfirm: () => update.mutate({ id: a.id, body: { active: false } }),
          }
        : {
            title: `重新启用「${a.name}」？`,
            description: "启用后可以用原来的密码登录。",
            confirmLabel: "确认启用",
            onConfirm: () => update.mutate({ id: a.id, body: { active: true } }),
          },
    )

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <FrameAction icon={Plus} label="新建成员" primary onClick={() => setEditing("new")} />
      </div>
      <Teams teams={teams.data} onEdit={(t) => setTeamOf(t ?? "new")} />
      <Members accounts={accounts.data} me={userId} onEdit={setEditing} onReset={onReset} onToggle={onToggle} />
      {editing ? (
        <MemberDialog
          key={editing === "new" ? "new" : editing.id}
          open
          account={editing === "new" ? null : editing}
          teams={teams.data}
          onClose={() => setEditing(null)}
          onCreated={(r) => {
            setEditing(null)
            setTemp(r)
          }}
        />
      ) : null}
      {teamOf ? (
        <TeamDialog
          key={teamOf === "new" ? "new" : teamOf.id}
          open
          team={teamOf === "new" ? null : teamOf}
          onClose={() => setTeamOf(null)}
        />
      ) : null}
      <TempPasswordDialog result={temp} onClose={() => setTemp(null)} />
      {dialog}
    </div>
  )
}

/** 成员与团队（仅管理员）：新建成员、改角色 / 团队、重置密码、停用 / 启用；新建 / 改名团队 */
export default function AccountsPage() {
  return (
    <PageFrame title="成员与团队" icon={UsersRound}>
      <RoleGate roles={["admin"]} lockedText="成员和团队由系统管理员维护">
        <AccountsBody />
      </RoleGate>
    </PageFrame>
  )
}
