"use client"

import { CircleAlert } from "lucide-react"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import { Alert } from "@/components/biz/Alert"
import { useConfirmAction } from "@/components/biz/ConfirmAction"
import { FormField } from "@/components/biz/FormControls"
import { FormSheet } from "@/components/biz/FormSheet"
import { QueryError } from "@/components/biz/QueryStatus"
import { AttachmentUploader } from "@/components/expenses/AttachmentUploader"
import { ExpenseForm } from "@/components/expenses/ExpenseForm"
import { ExpenseSummary } from "@/components/expenses/ExpenseSummary"
import { PolicyCheckAlert } from "@/components/expenses/PolicyCheckAlert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useDebounced } from "@/hooks/useDebounced"
import { useCreateExpense, useExpense, useExpensePrecheck, useSubmitExpense } from "@/hooks/useExpenses"
import { usePermissions } from "@/hooks/usePermissions"
import { newRequestId } from "@/lib/api"
import { EXPENSE_SUBMIT_CONFIRM } from "@/lib/confirm-texts"
import { localDate } from "@/lib/format"
import {
  checkFromPolicy,
  checkFromPrecheck,
  missingAttachmentReason,
  toExpenseCreate,
  toPrecheckBody,
  type ExpenseFormErrors,
  type ExpenseFormValues,
} from "@/lib/expense"
import { applyTemplate, EMPTY_TRIP } from "@/lib/expense-trip"
import type { CustomerBrief, ExpenseCreate } from "@/types/api"

const today = () => localDate()
const emptyForm = (): ExpenseFormValues => ({
  type: "entertainment",
  amount: "",
  occurred_on: today(),
  customer_id: null,
  opportunity_id: null,
  contact_ids: [],
  colleague_ids: [],
  extra_guests: "",
  reason: "",
  trip: EMPTY_TRIP,
})

/** 实时制度校验：表单稳定 400ms 后调用 precheck（用字符串做防抖键，避免对象引用变化导致重复请求） */
function useLivePrecheck(values: ExpenseFormValues, enabled: boolean) {
  const key = useDebounced(enabled ? JSON.stringify(toPrecheckBody(values)) : "null")
  const body = useMemo(() => JSON.parse(key) as ExpenseCreate | null, [key])
  return useExpensePrecheck(body)
}

/**
 * ExpenseSheet：填写 → 选择票据时自动保存草稿并上传（U5）→ 实时制度校验 → 提交。
 * expenseId 为空时是新建；传入时查看 / 继续编辑已有报销单（非草稿只读）。
 */
export function ExpenseSheet({
  open,
  expenseId,
  onClose,
}: {
  open: boolean
  expenseId: string | null
  onClose: () => void
}) {
  const [values, setValues] = useState<ExpenseFormValues>(emptyForm)
  const [customer, setCustomer] = useState<CustomerBrief | null>(null)
  const [errors, setErrors] = useState<ExpenseFormErrors>({})
  const [templateId, setTemplateId] = useState<string | null>(null)
  const [createdId, setCreatedId] = useState<string | null>(null)
  const [idemKey, setIdemKey] = useState(newRequestId)

  const draftId = expenseId ?? createdId
  const detail = useExpense(open ? draftId : null)
  const create = useCreateExpense()
  const submit = useSubmitExpense()
  const { ask, dialog } = useConfirmAction()
  const precheck = useLivePrecheck(values, open && !draftId)

  const { canCreate, canEdit } = usePermissions()
  const exp = detail.data
  // 新建：有新建权限；已有报销单：本人的草稿才能上传票据和提交（契约 §0）
  const editable = !draftId ? canCreate : exp?.status === "draft" && canEdit(exp.owner.id)
  const attachments = exp?.attachments ?? []
  const missing = exp ? missingAttachmentReason(exp.type, attachments) : "保存草稿后上传票据"

  const close = () => {
    onClose()
    setValues(emptyForm())
    setCustomer(null)
    setErrors({})
    setTemplateId(null)
    setCreatedId(null)
    setIdemKey(newRequestId())
  }
  const set = <K extends keyof ExpenseFormValues>(k: K, v: ExpenseFormValues[K]) =>
    setValues((prev) => ({ ...prev, [k]: v }))

  /** 保存草稿，返回报销单 id；表单校验不通过或保存失败返回 null */
  const saveDraft = async (fromUpload = false): Promise<string | null> => {
    const r = toExpenseCreate(values, idemKey)
    if (!r.ok) {
      setErrors(r.errors)
      if (fromUpload) toast.error("请先补全必填项，再上传票据")
      return null
    }
    setErrors({})
    try {
      const e = await create.mutateAsync(r.value)
      setCreatedId(e.id)
      toast.success("草稿已保存", {
        description: fromUpload ? `${e.code} · 正在上传票据` : `${e.code} · 请上传票据后提交`,
      })
      return e.id
    } catch {
      return null // 错误提示由 useCreateExpense 的 onError 负责
    }
  }
  const doSubmit = () => {
    if (!draftId) return
    ask({ ...EXPENSE_SUBMIT_CONFIRM, onConfirm: () => submitNow(draftId) })
  }
  const submitNow = (id: string) => {
    submit.mutate(id, {
      onSuccess: (e) => {
        toast.success(e?.status === "pending_approval" ? "超出报销标准，已提交主管审批" : "制度校验通过，报销已提交", {
          description: e?.code,
        })
        close()
      },
    })
  }

  const title = !draftId ? "新建报销" : exp ? `报销 ${exp.code}` : "报销"
  const footer = !draftId ? (
    <>
      <Button variant="outline" onClick={close}>
        取消
      </Button>
      <Button onClick={() => void saveDraft()} disabled={create.isPending}>
        {create.isPending ? "保存中…" : "保存草稿"}
      </Button>
    </>
  ) : editable ? (
    <>
      <Button variant="outline" onClick={close}>
        稍后提交
      </Button>
      <Button onClick={doSubmit} disabled={Boolean(missing) || submit.isPending || !exp} title={missing ?? undefined}>
        {submit.isPending ? "提交中…" : "提交审批"}
      </Button>
    </>
  ) : (
    <Button variant="outline" onClick={close}>
      关闭
    </Button>
  )

  return (
    <FormSheet open={open} onOpenChange={(o) => !o && close()} title={title} footer={footer}>
      {!draftId ? (
        <ExpenseForm
          values={values}
          customer={customer}
          errors={errors}
          onChange={set}
          onCustomerChange={(c) => {
            setCustomer(c)
            // 换客户后，原来勾选的联系人和商机不再属于新客户
            setValues((prev) => ({ ...prev, customer_id: c?.id ?? null, contact_ids: [], opportunity_id: null }))
          }}
          templateId={templateId}
          onTemplate={(tpl, all) => {
            setTemplateId(tpl.id)
            setValues((prev) => applyTemplate(prev, tpl, all))
          }}
        />
      ) : detail.isPending ? (
        <Skeleton className="h-48 w-full" />
      ) : detail.isError ? (
        <QueryError error={detail.error} onRetry={() => void detail.refetch()} feature="报销详情" />
      ) : (
        <ExpenseSummary e={detail.data} />
      )}
      <FormField label="票据" required>
        <AttachmentUploader
          expenseId={draftId}
          type={exp?.type ?? values.type}
          attachments={attachments}
          editable={editable}
          ensureDraft={draftId ? undefined : () => saveDraft(true)}
        />
      </FormField>
      {!draftId ? (
        <PolicyCheckAlert
          check={precheck.data ? checkFromPrecheck(precheck.data) : null}
          checking={precheck.isFetching}
        />
      ) : exp ? (
        <PolicyCheckAlert check={checkFromPolicy(exp.policy_check)} />
      ) : null}
      {!draftId && precheck.isError ? (
        <Alert tone="info" title="暂时无法实时校验报销制度">
          提交时 core 仍会按制度校验
        </Alert>
      ) : null}
      {draftId && editable && missing ? (
        <div className="flex items-start gap-1.5 text-red-600">
          <CircleAlert className="mt-0.5 size-3.5 shrink-0" />
          <span>无法提交：{missing}</span>
        </div>
      ) : null}
      {dialog}
    </FormSheet>
  )
}
