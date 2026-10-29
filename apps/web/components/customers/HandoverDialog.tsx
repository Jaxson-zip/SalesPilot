"use client"

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
import { useHandover, useHandoverPreview } from "@/hooks/useCustomers"
import { useTeamUsers } from "@/hooks/useUsers"
import { handoverSummary } from "@/lib/confirm-texts"
import { errorMessage } from "@/lib/errors"

/**
 * 按人一键交接（仅主管）：选交接人 → 预览名下客户和进行中的业务 → 选接手人 →「确认交接」。
 * 已成交的商机和报价、提成、报销不转；回款中的合同交给接手人跟进，提成仍归原负责人。
 */
export function HandoverDialog({
  open,
  onOpenChange,
  initialFrom = "",
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  /** 从「成员已停用」通知进来时预选交接人 */
  initialFrom?: string
}) {
  const [from, setFrom] = useState(initialFrom)
  const [to, setTo] = useState("")
  // 交接人可以是已停用的成员；接手人只能选启用的
  const users = useTeamUsers(open, "team", true)
  const preview = useHandoverPreview(open ? from : "")
  const handover = useHandover()
  const members = (users.data?.items ?? []).filter((u) => u.role === "sales" || u.role === "manager")
  const name = (id: string) => members.find((u) => u.id === id)?.name ?? ""
  const label = (u: { name: string; active?: boolean }) => (u.active === false ? `${u.name}（已停用）` : u.name)
  const summary = preview.data ? handoverSummary(preview.data) : ""
  const empty = preview.isSuccess && !summary

  const close = () => {
    setFrom("")
    setTo("")
    onOpenChange(false)
  }
  const confirm = () =>
    handover.mutate(
      { from_user_id: from, to_user_id: to },
      {
        onSuccess: (r) => {
          toast.success(`已把${name(from)}的客户交接给${name(to)}`, { description: handoverSummary(r) || undefined })
          close()
        },
      },
    )

  let scope = "选择交接人后，这里显示要交接的内容。"
  if (from && preview.isPending) scope = "正在统计…"
  else if (preview.isError) scope = errorMessage(preview.error)
  else if (empty) scope = `${name(from)}名下没有需要交接的客户和业务。`
  else if (summary) scope = `${name(from)}名下：${summary}。`

  return (
    <Dialog open={open} onOpenChange={(o) => !o && close()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>按人交接</DialogTitle>
          <DialogDescription>
            成员离职或调岗时，把这位成员名下全部客户和进行中的业务一次转给接手人，并通知接手人。
          </DialogDescription>
        </DialogHeader>
        <FormField label="交接人" required htmlFor="handover-from">
          <SimpleSelect
            id="handover-from"
            value={from}
            onChange={(v) => {
              setFrom(v)
              if (v === to) setTo("")
            }}
            options={members.map((u) => ({ value: u.id, label: label(u) }))}
            placeholder={users.isPending ? "加载团队成员…" : "选择离职 / 调岗的成员"}
            ariaLabel="交接人"
          />
        </FormField>
        <p role="status" className="rounded-md bg-zinc-50 px-3 py-2 text-sm text-zinc-700">
          {scope}
        </p>
        <FormField label="接手人" required htmlFor="handover-to">
          <SimpleSelect
            id="handover-to"
            value={to}
            onChange={setTo}
            options={members
              .filter((u) => u.id !== from && u.active !== false)
              .map((u) => ({ value: u.id, label: u.name }))}
            placeholder="选择本团队成员"
            ariaLabel="接手人"
          />
        </FormField>
        <p className="text-xs text-zinc-500">
          一起转：联系人、跟进记录、未结束的商机、未成交的报价（含待审批）、未完成的任务、回款中的合同和回款计划。
          不转：已赢单 / 输单的商机、提成（仍归原负责人）、报销单。
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={close}>
            取消
          </Button>
          <Button onClick={confirm} disabled={!from || !to || empty || !preview.isSuccess || handover.isPending}>
            {handover.isPending ? "交接中…" : "确认交接"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
