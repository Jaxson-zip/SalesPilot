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
import { useCustomer } from "@/hooks/useCustomers"
import { useCreateQuote } from "@/hooks/useQuotes"
import { defaultQuoteOpportunity } from "@/lib/quote-actions"
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
  const params = useSearchParams()
  const oppParam = params.get("opp")
  const fromOpp = useOpportunity(oppParam)
  // 从客户详情进来：只带客户（有商机参数时以商机为准）
  const fromCustomer = useCustomer(oppParam ? "" : (params.get("customer") ?? ""))
  const [customer, setCustomer] = useState<CustomerBrief | null>(null)
  const [oppId, setOppId] = useState<string | null>(oppParam)
  const [picked, setPicked] = useState("")
  const [seeded, setSeeded] = useState(false)
  /** 换了客户后，商机列表加载完按 defaultQuoteOpportunity 自动选一次；销售手动选过就不再改 */
  const [autoOppFor, setAutoOppFor] = useState<string | null>(null)
  const lines = useProductLines().data ?? []
  const fallback = useDefaultPack().data?.pack ?? ""
  const opps = useOpportunities({ view: "mine", customer_id: customer?.id, page_size: 50 }, Boolean(customer))
  const create = useCreateQuote()

  // 从商机进来：带上客户和商机的产品线
  if (!seeded && fromOpp.data) {
    setSeeded(true)
    // 已输单的商机不能再出报价（后端拦）：不自动关联，只带客户
    if (fromOpp.data.stage === "lost") setOppId(null)
    setCustomer(fromOpp.data.customer)
    if (fromOpp.data.product_line) setPicked(fromOpp.data.product_line.pack)
  }
  if (!seeded && fromCustomer.data) {
    setSeeded(true)
    setCustomer({ id: fromCustomer.data.id, name: fromCustomer.data.name })
  }
  const oppItems = (opps.data?.items ?? []).filter((o) => o.customer.id === customer?.id && o.stage !== "lost")
  if (customer && opps.data && !opps.isPlaceholderData && autoOppFor !== customer.id) {
    setAutoOppFor(customer.id)
    if (!oppId) setOppId(defaultQuoteOpportunity(oppItems))
  }
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
          saving={create.isPending || create.isSuccess}
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
