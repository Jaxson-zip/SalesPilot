"use client"

import { ChipMultiSelect, FixedChip } from "@/components/biz/ChipMultiSelect"
import { CustomerCombobox } from "@/components/biz/CustomerCombobox"
import { DatePicker, FormField, MoneyInput, SimpleSelect } from "@/components/biz/FormControls"
import { useSession } from "@/components/shell/SessionProvider"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { useContacts } from "@/hooks/useFollowups"
import { ExpenseGuidePanel, ExpenseTemplatePicker } from "@/components/expenses/ExpenseGuide"
import { TripFields } from "@/components/expenses/TripFields"
import { useOpportunities } from "@/hooks/useOpportunities"
import { useTemplates } from "@/hooks/useTemplates"
import { useTeamUsers } from "@/hooks/useUsers"
import { isNotImplemented } from "@/lib/errors"
import {
  headcountSummary,
  participantCount,
  toggleId,
  type ExpenseFormErrors,
  type ExpenseFormValues,
} from "@/lib/expense"
import { EXPENSE_TYPE_META } from "@/lib/labels"
import type { CustomerBrief, ExpenseTemplate, ExpenseType } from "@/types/api"

export type { ExpenseFormErrors }

const TYPE_OPTIONS: { value: ExpenseType; label: string }[] = (
  ["entertainment", "transport", "hotel", "other"] as const
).map((t) => ({ value: t, label: EXPENSE_TYPE_META[t].label }))

const NO_OPP = "none"

type OnChange = <K extends keyof ExpenseFormValues>(k: K, v: ExpenseFormValues[K]) => void

/** 关联商机：只列该客户下自己的商机（选了客户之后才显示） */
function OpportunityField({
  customerId,
  value,
  onChange,
}: {
  customerId: string
  value: string | null
  onChange: OnChange
}) {
  const q = useOpportunities({ view: "mine", customer_id: customerId, page_size: 50 })
  const items = (q.data?.items ?? []).filter((o) => o.customer.id === customerId)
  const options = [{ value: NO_OPP, label: "不关联商机" }, ...items.map((o) => ({ value: o.id, label: o.name }))]
  return (
    <FormField label="关联商机" htmlFor="exp-opportunity" hint={q.isPending ? "加载商机…" : undefined}>
      <SimpleSelect
        id="exp-opportunity"
        value={value ?? NO_OPP}
        onChange={(v) => onChange("opportunity_id", v === NO_OPP ? null : v)}
        options={options}
        ariaLabel="关联商机"
      />
    </FormField>
  )
}

/** 客户方参与人：所选客户的联系人（chip 多选） */
function ContactsField({
  customerId,
  values,
  required,
  error,
  onChange,
}: {
  customerId: string | null
  values: ExpenseFormValues
  required: boolean
  error?: string
  onChange: OnChange
}) {
  const q = useContacts(customerId ?? "")
  const options = (q.data ?? []).map((c) => ({ value: c.id, label: c.name, hint: c.title }))
  let empty = "还没有联系人，可在客户详情里添加"
  if (!customerId) empty = "先选择关联客户"
  else if (q.isPending) empty = "加载联系人…"
  else if (q.isError) empty = isNotImplemented(q.error) ? "联系人接口开发中" : "联系人加载失败"
  return (
    <FormField label="客户方参与人" required={required} error={error}>
      <ChipMultiSelect
        ariaLabel="客户方参与人"
        options={customerId ? options : []}
        value={values.contact_ids}
        onToggle={(id) => onChange("contact_ids", toggleId(values.contact_ids, id))}
        empty={empty}
        invalid={Boolean(error)}
      />
    </FormField>
  )
}

/** 我方参与人：本团队同事（chip 多选），申请人本人默认算在内且不可移除 */
function ColleaguesField({ values, onChange }: { values: ExpenseFormValues; onChange: OnChange }) {
  const { user, userId } = useSession()
  const q = useTeamUsers()
  const options = (q.data?.items ?? []).filter((u) => u.id !== userId).map((u) => ({ value: u.id, label: u.name }))
  const empty = q.isPending ? "加载同事…" : q.isError ? "同事列表暂不可用" : undefined
  return (
    <FormField label="我方参与人" hint="申请人本人始终计入人数">
      <ChipMultiSelect
        ariaLabel="我方参与人"
        options={options}
        value={values.colleague_ids}
        onToggle={(id) => onChange("colleague_ids", toggleId(values.colleague_ids, id))}
        fixed={<FixedChip label={`${user.name}（我）`} />}
        empty={empty}
      />
    </FormField>
  )
}

/** 客户招待专属：客户方参与人、我方参与人、其他人数、人数与人均 */
function ParticipantFields({
  values,
  errors,
  onChange,
}: {
  values: ExpenseFormValues
  errors: ExpenseFormErrors
  onChange: OnChange
}) {
  return (
    <>
      <ContactsField
        customerId={values.customer_id}
        values={values}
        required
        error={errors.contact_ids}
        onChange={onChange}
      />
      <ColleaguesField values={values} onChange={onChange} />
      <FormField
        label="其他人数"
        error={errors.extra_guests}
        hint="不在上面名单里的其他参与人"
        htmlFor="exp-extra-guests"
      >
        <Input
          id="exp-extra-guests"
          inputMode="numeric"
          value={values.extra_guests}
          placeholder="0"
          aria-invalid={Boolean(errors.extra_guests) || undefined}
          onChange={(e) => onChange("extra_guests", e.target.value)}
        />
      </FormField>
      <div aria-live="polite" data-testid="expense-headcount" className="text-zinc-600 tabular-nums">
        {headcountSummary(values.amount, participantCount(values))}
      </div>
    </>
  )
}

/**
 * 新建报销表单：模板 → 类型（报销须知随类型变化）→ 金额 / 日期 → 按类型的补充信息 → 关联客户 / 商机 → 事由。
 * 客户招待显示参与人；差旅交通显示行程；差旅住宿显示城市和入住 / 离店日期（v4）。
 */
export function ExpenseForm({
  values,
  customer,
  errors,
  onChange,
  onCustomerChange,
  templateId,
  onTemplate,
}: {
  values: ExpenseFormValues
  customer: CustomerBrief | null
  errors: ExpenseFormErrors
  onChange: OnChange
  onCustomerChange: (c: CustomerBrief | null) => void
  templateId: string | null
  onTemplate: (tpl: ExpenseTemplate, all: ExpenseTemplate[]) => void
}) {
  const templates = useTemplates().data
  const all = templates?.expense_templates ?? []
  const example = all.find((t) => t.id === templateId && t.type === values.type)?.example
  const isEntertainment = values.type === "entertainment"
  return (
    <>
      <ExpenseTemplatePicker templates={all} active={templateId} onPick={(tpl) => onTemplate(tpl, all)} />
      <FormField label="费用类型" required>
        <SimpleSelect
          value={values.type}
          onChange={(t) => onChange("type", t)}
          options={TYPE_OPTIONS}
          ariaLabel="费用类型"
        />
      </FormField>
      <ExpenseGuidePanel guides={templates?.expense_guides ?? []} type={values.type} example={example} />
      <div className="grid grid-cols-2 gap-3">
        <FormField label="金额" required error={errors.amount} htmlFor="exp-amount">
          <MoneyInput
            id="exp-amount"
            value={values.amount}
            invalid={Boolean(errors.amount)}
            onChange={(v) => onChange("amount", v)}
          />
        </FormField>
        <FormField label="发生日期" required error={errors.occurred_on}>
          <DatePicker value={values.occurred_on} onChange={(d) => onChange("occurred_on", d)} ariaLabel="发生日期" />
        </FormField>
      </div>
      <TripFields
        type={values.type}
        trip={values.trip}
        amount={values.amount}
        errors={errors}
        onChange={(t) => onChange("trip", t)}
      />
      <FormField
        label="关联客户"
        required={isEntertainment}
        error={errors.customer_id}
        hint={isEntertainment ? undefined : "出差拜访的客户，选填"}
      >
        <CustomerCombobox value={customer} onChange={onCustomerChange} invalid={Boolean(errors.customer_id)} />
      </FormField>
      {values.customer_id ? (
        <OpportunityField customerId={values.customer_id} value={values.opportunity_id} onChange={onChange} />
      ) : null}
      {isEntertainment ? <ParticipantFields values={values} errors={errors} onChange={onChange} /> : null}
      <FormField label="事由" required error={errors.reason} htmlFor="exp-reason">
        <Textarea
          id="exp-reason"
          rows={3}
          maxLength={500}
          value={values.reason}
          placeholder={example ? `例如：${example}` : "例如：方案沟通晚餐"}
          aria-invalid={Boolean(errors.reason) || undefined}
          onChange={(e) => onChange("reason", e.target.value)}
        />
      </FormField>
    </>
  )
}
