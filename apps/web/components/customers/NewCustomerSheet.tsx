"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"

import { FormField, MoneyInput, SimpleSelect } from "@/components/biz/FormControls"
import { FormSheet } from "@/components/biz/FormSheet"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useCreateCustomer } from "@/hooks/useCustomers"
import { EMPTY_CUSTOMER_FORM, toCustomerCreate, type CustomerFormErrors, type CustomerFormValues } from "@/lib/customer"
import type { CustomerLevel } from "@/types/api"

const LEVEL_OPTIONS: { value: CustomerLevel; label: string }[] = [
  { value: "A", label: "A 级（重点客户）" },
  { value: "B", label: "B 级" },
  { value: "C", label: "C 级" },
]

type TextKey = "name" | "industry" | "size" | "address" | "website"

/** 新建客户 Sheet：名称、行业、等级、规模、地址、网站、年度预算；成功后刷新列表并打开客户详情 */
export function NewCustomerSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const router = useRouter()
  const [v, setV] = useState<CustomerFormValues>(EMPTY_CUSTOMER_FORM)
  const [errors, setErrors] = useState<CustomerFormErrors>({})
  const create = useCreateCustomer()
  const set = <K extends keyof CustomerFormValues>(k: K, val: CustomerFormValues[K]) =>
    setV((prev) => ({ ...prev, [k]: val }))

  const close = () => {
    onOpenChange(false)
    setV(EMPTY_CUSTOMER_FORM)
    setErrors({})
  }
  const submit = () => {
    const r = toCustomerCreate(v)
    if (!r.ok) return setErrors(r.errors)
    setErrors({})
    create.mutate(r.value, {
      onSuccess: (c) => {
        close()
        router.push(`/customers/${encodeURIComponent(c.id)}`)
      },
    })
  }

  const text = (k: TextKey, label: string, placeholder: string, required = false) => (
    <FormField label={label} required={required} error={errors[k]} htmlFor={`cust-${k}`}>
      <Input
        id={`cust-${k}`}
        value={v[k]}
        placeholder={placeholder}
        aria-invalid={Boolean(errors[k]) || undefined}
        onChange={(e) => set(k, e.target.value)}
      />
    </FormField>
  )

  return (
    <FormSheet
      open={open}
      onOpenChange={(o) => (o ? onOpenChange(true) : close())}
      title="新建客户"
      footer={
        <>
          <Button variant="outline" onClick={close}>
            取消
          </Button>
          <Button onClick={submit} disabled={create.isPending}>
            {create.isPending ? "创建中…" : "创建客户"}
          </Button>
        </>
      }
    >
      {text("name", "客户名称", "例如：深圳明理律师事务所", true)}
      <div className="grid grid-cols-2 gap-3">
        {text("industry", "行业", "例如：法律")}
        <FormField label="等级" htmlFor="cust-level">
          <SimpleSelect
            value={v.level}
            onChange={(x) => set("level", x)}
            options={LEVEL_OPTIONS}
            ariaLabel="客户等级"
            id="cust-level"
          />
        </FormField>
      </div>
      {text("size", "规模", "例如：200–500 人")}
      {text("address", "地址", "例如：深圳市南山区科技园")}
      {text("website", "网站", "例如：https://example.com")}
      <FormField label="年度预算" error={errors.annual_budget} hint="单位：元" htmlFor="cust-budget">
        <MoneyInput
          id="cust-budget"
          value={v.annual_budget}
          invalid={Boolean(errors.annual_budget)}
          onChange={(x) => set("annual_budget", x)}
        />
      </FormField>
    </FormSheet>
  )
}
