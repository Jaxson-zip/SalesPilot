"use client"

import { Pencil, Phone, Plus, Trash2, UserRound } from "lucide-react"
import { useState } from "react"

import { LetterAvatar } from "@/components/biz/Chip"
import { useConfirmAction } from "@/components/biz/ConfirmAction"
import { EmptyState } from "@/components/biz/EmptyState"
import { FormField, SimpleSelect } from "@/components/biz/FormControls"
import { FormSheet } from "@/components/biz/FormSheet"
import { QueryError } from "@/components/biz/QueryStatus"
import { Tag } from "@/components/biz/Tag"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useContacts, useDeleteContact, useSaveContact } from "@/hooks/useFollowups"
import { deleteContactConfirm } from "@/lib/confirm-texts"
import { CONTACT_ROLE_META } from "@/lib/labels"
import type { ContactItem, ContactRole } from "@/types/api"

const NO_ROLE = "none"
const ROLE_OPTIONS: { value: ContactRole | typeof NO_ROLE; label: string }[] = [
  ...(Object.keys(CONTACT_ROLE_META) as ContactRole[]).map((r) => ({ value: r, label: CONTACT_ROLE_META[r].label })),
  { value: NO_ROLE, label: "不标注" },
]

interface FormValues {
  name: string
  title: string
  phone: string
  role: ContactRole | typeof NO_ROLE
}

function toForm(c: ContactItem | null): FormValues {
  return { name: c?.name ?? "", title: c?.title ?? "", phone: c?.phone ?? "", role: c?.role ?? NO_ROLE }
}

/** 新建 / 编辑联系人（target：null = 关闭；"new" = 新建；ContactItem = 编辑） */
function ContactSheet({
  customerId,
  target,
  onClose,
}: {
  customerId: string
  target: ContactItem | "new" | null
  onClose: () => void
}) {
  const editing = target !== null && target !== "new" ? target : null
  const [v, setV] = useState<FormValues>(toForm(editing))
  const [nameError, setNameError] = useState<string>()
  const save = useSaveContact(customerId)
  const [lastTarget, setLastTarget] = useState(target)
  if (target !== lastTarget) {
    // 打开另一位联系人时重置表单（渲染期间同步，避免闪一下旧数据）
    setLastTarget(target)
    setV(toForm(editing))
    setNameError(undefined)
  }
  const set = <K extends keyof FormValues>(k: K, val: FormValues[K]) => setV((p) => ({ ...p, [k]: val }))

  const submit = () => {
    if (!v.name.trim()) return setNameError("请填写姓名")
    const body = {
      name: v.name.trim(),
      title: v.title.trim() || null,
      phone: v.phone.trim() || null,
      role: v.role === NO_ROLE ? null : v.role,
    }
    save.mutate({ id: editing?.id, body }, { onSuccess: onClose })
  }

  return (
    <FormSheet
      open={target !== null}
      onOpenChange={(o) => !o && onClose()}
      title={editing ? `编辑联系人 · ${editing.name}` : "添加联系人"}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button onClick={submit} disabled={save.isPending}>
            {save.isPending ? "保存中…" : "保存"}
          </Button>
        </>
      }
    >
      <FormField label="姓名" required error={nameError} htmlFor="contact-name">
        <Input
          id="contact-name"
          value={v.name}
          placeholder="例如：王律师"
          aria-invalid={Boolean(nameError) || undefined}
          onChange={(e) => set("name", e.target.value)}
        />
      </FormField>
      <FormField label="角色" hint="在这次采购中的作用；商机侧栏会显示决策人、影响者和技术把关" htmlFor="contact-role">
        <SimpleSelect
          id="contact-role"
          value={v.role}
          onChange={(x) => set("role", x)}
          options={ROLE_OPTIONS}
          ariaLabel="联系人角色"
        />
      </FormField>
      <FormField label="职务" htmlFor="contact-title">
        <Input
          id="contact-title"
          value={v.title}
          placeholder="例如：IT 负责人"
          onChange={(e) => set("title", e.target.value)}
        />
      </FormField>
      <FormField label="电话" htmlFor="contact-phone">
        <Input
          id="contact-phone"
          value={v.phone}
          placeholder="例如：138 0000 0000"
          onChange={(e) => set("phone", e.target.value)}
        />
      </FormField>
    </FormSheet>
  )
}

export function ContactRoleTag({ role }: { role: ContactRole | null }) {
  return role ? <Tag color={CONTACT_ROLE_META[role].color}>{CONTACT_ROLE_META[role].label}</Tag> : null
}

/** 客户详情「联系人」标签页：列表 + 增删改（只有客户负责人能改） */
export function ContactsPanel({ customerId, editable }: { customerId: string; editable: boolean }) {
  const q = useContacts(customerId)
  const del = useDeleteContact(customerId)
  const { ask, dialog } = useConfirmAction()
  const [target, setTarget] = useState<ContactItem | "new" | null>(null)

  if (q.isPending) return <Skeleton className="h-24 w-full" />
  if (q.isError) return <QueryError error={q.error} onRetry={() => void q.refetch()} feature="联系人" />
  const add = editable ? (
    <Button size="sm" variant="outline" onClick={() => setTarget("new")}>
      <Plus /> 添加联系人
    </Button>
  ) : null

  return (
    <div className="space-y-3">
      {q.data.length === 0 ? (
        <EmptyState
          icon={UserRound}
          title="还没有联系人"
          description="记下决策人和关键影响者，跟进时更有针对性"
          action={add}
        />
      ) : (
        <>
          <div className="flex items-center justify-between">
            <span className="text-zinc-500">共 {q.data.length} 位</span>
            {add}
          </div>
          <ul className="divide-y divide-zinc-100 rounded-lg border border-zinc-200" aria-label="联系人列表">
            {q.data.map((c) => (
              <li key={c.id} className="flex min-h-12 items-center gap-3 px-3 py-2">
                <LetterAvatar name={c.name} className="size-7 text-xs" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{c.name}</span>
                    <ContactRoleTag role={c.role} />
                  </div>
                  <div className="mt-0.5 flex gap-3 text-xs text-zinc-500">
                    {c.title ? <span>{c.title}</span> : null}
                    {c.phone ? (
                      <span className="inline-flex items-center gap-1">
                        <Phone className="size-3" />
                        {c.phone}
                      </span>
                    ) : null}
                  </div>
                </div>
                {editable ? (
                  <div className="flex shrink-0 gap-1">
                    <Button size="icon-sm" variant="ghost" aria-label={`编辑 ${c.name}`} onClick={() => setTarget(c)}>
                      <Pencil />
                    </Button>
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      aria-label={`删除 ${c.name}`}
                      onClick={() => ask({ ...deleteContactConfirm(c.name), onConfirm: () => del.mutate(c) })}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        </>
      )}
      <ContactSheet customerId={customerId} target={target} onClose={() => setTarget(null)} />
      {dialog}
    </div>
  )
}
