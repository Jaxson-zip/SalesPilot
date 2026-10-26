"use client"

import { CustomerCombobox } from "@/components/biz/CustomerCombobox"
import { DatePicker, FormField, MoneyInput, SimpleSelect } from "@/components/biz/FormControls"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import type { ExpenseFormValues } from "@/lib/expense"
import { EXPENSE_TYPE_META } from "@/lib/labels"
import type { CustomerBrief, ExpenseType } from "@/types/api"

const TYPE_OPTIONS: { value: ExpenseType; label: string }[] = (
  ["entertainment", "transport", "hotel", "other"] as const
).map((t) => ({ value: t, label: EXPENSE_TYPE_META[t].label }))

export type ExpenseFormErrors = Partial<Record<keyof ExpenseFormValues, string>>

/** 新建报销表单字段：Select / 金额 / 人数 / DatePicker / 客户 Combobox / 参与人 / 事由 */
export function ExpenseForm({
  values,
  customer,
  errors,
  onChange,
  onCustomerChange,
}: {
  values: ExpenseFormValues
  customer: CustomerBrief | null
  errors: ExpenseFormErrors
  onChange: <K extends keyof ExpenseFormValues>(k: K, v: ExpenseFormValues[K]) => void
  onCustomerChange: (c: CustomerBrief | null) => void
}) {
  const isEntertainment = values.type === "entertainment"
  return (
    <>
      <FormField label="费用类型" required>
        <SimpleSelect
          value={values.type}
          onChange={(t) => onChange("type", t)}
          options={TYPE_OPTIONS}
          ariaLabel="费用类型"
        />
      </FormField>
      <div className="grid grid-cols-2 gap-3">
        <FormField label="金额" required error={errors.amount} htmlFor="exp-amount">
          <MoneyInput
            id="exp-amount"
            value={values.amount}
            invalid={Boolean(errors.amount)}
            onChange={(v) => onChange("amount", v)}
          />
        </FormField>
        <FormField label="人数" required error={errors.headcount} htmlFor="exp-headcount">
          <Input
            id="exp-headcount"
            inputMode="numeric"
            value={values.headcount}
            aria-invalid={Boolean(errors.headcount) || undefined}
            onChange={(e) => onChange("headcount", e.target.value)}
          />
        </FormField>
      </div>
      <FormField label="发生日期" required error={errors.occurred_on}>
        <DatePicker value={values.occurred_on} onChange={(d) => onChange("occurred_on", d)} />
      </FormField>
      <FormField label="关联客户">
        <CustomerCombobox value={customer} onChange={onCustomerChange} />
      </FormField>
      <FormField
        label="参与人"
        required={isEntertainment}
        error={errors.participants}
        hint={isEntertainment ? "客户招待需写明双方参与人" : undefined}
        htmlFor="exp-participants"
      >
        <Input
          id="exp-participants"
          value={values.participants}
          placeholder="客户：王律师、陈工；我方：张晨"
          aria-invalid={Boolean(errors.participants) || undefined}
          onChange={(e) => onChange("participants", e.target.value)}
        />
      </FormField>
      <FormField label="事由" required error={errors.reason} htmlFor="exp-reason">
        <Textarea
          id="exp-reason"
          rows={3}
          maxLength={500}
          value={values.reason}
          placeholder="例如：方案沟通晚餐"
          aria-invalid={Boolean(errors.reason) || undefined}
          onChange={(e) => onChange("reason", e.target.value)}
        />
      </FormField>
    </>
  )
}
