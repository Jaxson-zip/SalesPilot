"use client"

import { useState } from "react"

import { CustomerCombobox } from "@/components/biz/CustomerCombobox"
import { DatePicker, FormField, MoneyInput, SimpleSelect } from "@/components/biz/FormControls"
import { FormSheet } from "@/components/biz/FormSheet"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useCreateOpportunity } from "@/hooks/useOpportunities"
import { useProductLines } from "@/hooks/useProductLines"
import { toOpportunityCreate, type OppFormErrors, type OpportunityFormValues } from "@/lib/opportunity"
import type { CustomerBrief } from "@/types/api"

const EMPTY: OpportunityFormValues = {
  customer_id: null,
  name: "",
  amount: "",
  win_rate: "",
  expected_close_date: "",
  product_line_id: null,
}

function ProductLineSelect({ value, onChange }: { value: string | null; onChange: (v: string) => void }) {
  const query = useProductLines()
  const options = (query.data ?? []).filter((pl) => pl.enabled).map((pl) => ({ value: pl.id, label: pl.name }))
  const unavailable = query.isError
  return (
    <FormField
      label="产品线"
      hint={unavailable ? "产品线列表暂不可用（接口开发中或无权限），可稍后在商机上补充" : "系统按产品线自动匹配行业包"}
    >
      <SimpleSelect
        value={value ?? ""}
        onChange={onChange}
        options={options}
        placeholder={query.isPending ? "加载中…" : "选择产品线"}
        disabled={unavailable || options.length === 0}
        ariaLabel="产品线"
      />
    </FormField>
  )
}

/** 新建商机 Sheet：客户 Combobox、名称、金额、赢率、预计成交日、产品线 Select；初始阶段为线索 */
export function NewOpportunitySheet({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const [v, setV] = useState<OpportunityFormValues>(EMPTY)
  const [customer, setCustomer] = useState<CustomerBrief | null>(null)
  const [errors, setErrors] = useState<OppFormErrors>({})
  const create = useCreateOpportunity()
  const set = <K extends keyof OpportunityFormValues>(k: K, val: OpportunityFormValues[K]) =>
    setV((prev) => ({ ...prev, [k]: val }))

  const close = () => {
    onOpenChange(false)
    setV(EMPTY)
    setCustomer(null)
    setErrors({})
  }
  const submit = () => {
    const r = toOpportunityCreate(v)
    if (!r.ok) return setErrors(r.errors)
    setErrors({})
    create.mutate(r.value, { onSuccess: close })
  }

  return (
    <FormSheet
      open={open}
      onOpenChange={(o) => (o ? onOpenChange(true) : close())}
      title="新建商机"
      footer={
        <>
          <Button variant="outline" onClick={close}>
            取消
          </Button>
          <Button onClick={submit} disabled={create.isPending}>
            {create.isPending ? "创建中…" : "创建商机"}
          </Button>
        </>
      }
    >
      <FormField label="客户" required error={errors.customer_id}>
        <CustomerCombobox
          value={customer}
          invalid={Boolean(errors.customer_id)}
          onChange={(c) => {
            setCustomer(c)
            set("customer_id", c?.id ?? null)
          }}
        />
      </FormField>
      <FormField label="商机名称" required error={errors.name} htmlFor="opp-name">
        <Input
          id="opp-name"
          value={v.name}
          maxLength={200}
          placeholder="例如：合同审查私有化"
          aria-invalid={Boolean(errors.name) || undefined}
          onChange={(e) => set("name", e.target.value)}
        />
      </FormField>
      <div className="grid grid-cols-2 gap-3">
        <FormField label="金额" required error={errors.amount} htmlFor="opp-amount">
          <MoneyInput
            id="opp-amount"
            value={v.amount}
            invalid={Boolean(errors.amount)}
            onChange={(x) => set("amount", x)}
          />
        </FormField>
        <FormField label="赢率（%）" error={errors.win_rate} hint="不填默认 10" htmlFor="opp-win">
          <Input
            id="opp-win"
            inputMode="numeric"
            value={v.win_rate}
            placeholder="10"
            aria-invalid={Boolean(errors.win_rate) || undefined}
            onChange={(e) => set("win_rate", e.target.value)}
          />
        </FormField>
      </div>
      <FormField label="预计成交日期">
        <DatePicker value={v.expected_close_date} onChange={(d) => set("expected_close_date", d)} />
      </FormField>
      <ProductLineSelect value={v.product_line_id} onChange={(id) => set("product_line_id", id)} />
    </FormSheet>
  )
}
