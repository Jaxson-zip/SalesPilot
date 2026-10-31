"use client"

import { FileText } from "lucide-react"
import { useRouter, useSearchParams } from "next/navigation"
import { Suspense, useState } from "react"

import { CustomerCombobox } from "@/components/biz/CustomerCombobox"
import { FormField, SimpleSelect } from "@/components/biz/FormControls"
import { Crumb, PageFrame } from "@/components/biz/PageFrame"
import { QuoteEditor } from "@/components/quotes/QuoteAdjust"
import { RoleGate } from "@/components/shell/RoleGate"
import { useOpportunities, useOpportunity } from "@/hooks/useOpportunities"
import { useDefaultPack, useProductLines } from "@/hooks/useProductLines"
import { useCreateQuote } from "@/hooks/useQuotes"
import type { CustomerBrief } from "@/types/api"

const NO_OPP = "none"

/** 不经过 AI，自己从零出一张报价：选客户（可关联商机）和产品线，再填明细。从商机进来时带 ?opp= */
export default function NewQuotePage() {
  return (
    <PageFrame
      crumb={<Crumb parent="报价单" href="/quotes" icon={FileText} current="新建报价" />}
      bodyClassName="overflow-y-auto"
    >
      <RoleGate roles={["sales", "manager"]} lockedText="报价由销售新建">
        <Suspense>
          <NewQuote />
        </Suspense>
      </RoleGate>
    </PageFrame>
  )
}

function NewQuote() {
  const router = useRouter()
  const oppParam = useSearchParams().get("opp")
  const fromOpp = useOpportunity(oppParam)
  const [customer, setCustomer] = useState<CustomerBrief | null>(null)
  const [oppId, setOppId] = useState<string | null>(oppParam)
  const [picked, setPicked] = useState("")
  const [seeded, setSeeded] = useState(false)
  const lines = useProductLines().data ?? []
  const fallback = useDefaultPack().data?.pack ?? ""
  const opps = useOpportunities({ view: "mine", customer_id: customer?.id, page_size: 50 }, Boolean(customer))
  const create = useCreateQuote()

  // 从商机进来：带上客户和商机的产品线
  if (!seeded && fromOpp.data) {
    setSeeded(true)
    setCustomer(fromOpp.data.customer)
    if (fromOpp.data.product_line) setPicked(fromOpp.data.product_line.pack)
  }
  const oppItems = (opps.data?.items ?? []).filter((o) => o.customer.id === customer?.id)
  const opp = oppItems.find((o) => o.id === oppId)
  const pack = picked || opp?.product_line?.pack || fallback
  const packOptions = lines
    .filter((l, i, all) => all.findIndex((x) => x.pack === l.pack) === i)
    .map((l) => ({ value: l.pack, label: l.name }))

  return (
    <div className="mx-auto w-full max-w-4xl space-y-4 p-4 sm:p-6">
      <div className="grid gap-3 sm:grid-cols-3">
        <FormField label="客户" required>
          <CustomerCombobox
            value={customer}
            onChange={(c) => {
              setCustomer(c)
              setOppId(null)
            }}
          />
        </FormField>
        <FormField label="关联商机" htmlFor="quote-opp">
          <SimpleSelect
            id="quote-opp"
            ariaLabel="关联商机"
            disabled={!customer}
            value={oppId ?? NO_OPP}
            onChange={(v) => setOppId(v === NO_OPP ? null : v)}
            options={[{ value: NO_OPP, label: "不关联商机" }, ...oppItems.map((o) => ({ value: o.id, label: o.name }))]}
          />
        </FormField>
        <FormField label="产品线" htmlFor="quote-pack" hint="决定从哪个产品目录选物料">
          <SimpleSelect
            id="quote-pack"
            ariaLabel="产品线"
            value={pack}
            placeholder="选择产品线"
            onChange={setPicked}
            options={packOptions}
          />
        </FormField>
      </div>
      {customer && pack ? (
        <QuoteEditor
          key={pack}
          title="报价明细"
          pack={pack}
          initial={[]}
          saving={create.isPending}
          saveLabel="创建报价单"
          onSave={(body) =>
            create.mutate(
              { ...body, pack, customer_id: customer.id, opportunity_id: oppId },
              { onSuccess: (q) => router.replace(`/quotes/${encodeURIComponent(q.id)}`) },
            )
          }
        />
      ) : (
        <p className="rounded-xl border border-dashed border-zinc-200 p-8 text-center text-sm text-zinc-500">
          先选客户和产品线，再添加物料
        </p>
      )}
    </div>
  )
}
