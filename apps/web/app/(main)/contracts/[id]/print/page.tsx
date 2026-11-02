"use client"

import { ArrowLeft, Printer } from "lucide-react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { useState } from "react"

import {
  ClientCostsTable,
  ItemsTable,
  Meta,
  PrintHeader,
  PrintPaper,
  PrintPortal,
  Signatures,
  TermsList,
  useDocTitle,
} from "@/components/biz/PrintSheet"
import { ChatMarkdown } from "@/components/agent/ChatMarkdown"
import { QueryError } from "@/components/biz/QueryStatus"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { useContract, usePaymentPlan } from "@/hooks/useContracts"
import { useCustomer } from "@/hooks/useCustomers"
import { usePrd } from "@/hooks/usePrd"
import { useQuote } from "@/hooks/useQuotes"
import { useOpportunityRequirement } from "@/hooks/useRequirement"
import { useTemplates } from "@/hooks/useTemplates"
import { contractDocTitle, planGap, planRatio, prdForPrint, sowPending, sowScope } from "@/lib/contract-print"
import { formatFen } from "@/lib/format"
import { PRINT_COMPANY } from "@/lib/quote-print"
import { fenToRmbUpper } from "@/lib/rmb"
import type { ContractItem } from "@/types/api"

const TD = "border border-zinc-300 px-2 py-1.5"

/** 合同标的：有关联报价时列出报价明细，否则只写合同金额 */
function Subject({ c }: { c: ContractItem }) {
  const quote = useQuote(c.quote?.id ?? "")
  if (!c.quote) return null
  return (
    <section className="mt-5" aria-label="合同标的">
      <div className="mb-1.5 font-medium">一、合同标的（依据报价单 {c.quote.code}）</div>
      {quote.data ? (
        <ItemsTable items={quote.data.items} />
      ) : quote.isError ? (
        <div className="text-zinc-500">报价明细暂时取不到，以报价单 {c.quote.code} 为准。</div>
      ) : (
        <Skeleton className="h-24 w-full" />
      )}
    </section>
  )
}

/** 运营期客户自付费用：报价时单列的云服务器、域名、大模型调用费等，写明不含在合同金额内 */
function ClientCostsOf({ c }: { c: ContractItem }) {
  const quote = useQuote(c.quote?.id ?? "")
  return (
    <ClientCostsTable
      costs={quote.data?.client_costs ?? []}
      title="运营期客户自付费用预估（不含在合同金额内，由甲方按实际发生支付）"
    />
  )
}

function Plan({ c }: { c: ContractItem }) {
  const plan = usePaymentPlan(c.id)
  const items = plan.data?.items ?? []
  const gap = plan.data ? planGap(items, c.amount) : 0
  return (
    <section className="mt-5" aria-label="回款计划">
      <div className="mb-1.5 font-medium">{c.quote ? "二" : "一"}、付款方式与回款计划</div>
      {plan.isPending ? (
        <Skeleton className="h-20 w-full" />
      ) : items.length === 0 ? (
        <div className="text-zinc-500">尚未制定回款计划，以正式合同约定为准。</div>
      ) : (
        <table className="w-full table-fixed border-collapse">
          <thead>
            <tr className="bg-zinc-100 text-left">
              <th className={`w-16 ${TD} font-medium`}>期次</th>
              <th className={`${TD} font-medium`}>款项</th>
              <th className={`w-16 ${TD} text-right font-medium`}>比例</th>
              <th className={`w-32 ${TD} text-right font-medium`}>金额</th>
              <th className={`w-28 ${TD} font-medium`}>约定付款日</th>
            </tr>
          </thead>
          <tbody>
            {items.map((it) => (
              <tr key={it.seq}>
                <td className={`${TD} whitespace-nowrap tabular-nums`}>第 {it.seq} 期</td>
                <td className={TD}>{it.name}</td>
                <td className={`${TD} text-right tabular-nums`}>{planRatio(it.amount, c.amount)}</td>
                <td className={`${TD} text-right tabular-nums`}>{formatFen(it.amount)}</td>
                <td className={`${TD} tabular-nums`}>{it.due_date}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {gap !== 0 ? (
        <div className="no-print mt-1.5 text-xs text-amber-700">
          回款计划合计与合同金额相差 {formatFen(Math.abs(gap))}，打印前请先在「回款计划」里调整。
        </div>
      ) : null}
    </section>
  )
}

/**
 * 附件一：需求范围说明书（SOW）。商机上生成过 PRD 时附 PRD 全文，否则按已确认的需求清单列出功能范围；
 * 都没有时不显示。另起一页打印。
 */
function SowAppendix({ c }: { c: ContractItem }) {
  const quote = useQuote(c.quote?.id ?? "")
  const oppId = quote.data?.opportunity?.id ?? ""
  const prd = usePrd(oppId, Boolean(oppId))
  const req = useOpportunityRequirement(oppId || null)
  // 成交报价固化的范围优先（和报价单、分享页一致），迁移前的报价没有才用商机的需求清单
  const frozen = quote.data?.scope as Parameters<typeof sowScope>[0] | null | undefined
  const scope = frozen ? sowScope(frozen) : req.data?.confirmed ? sowScope(req.data.data) : null
  if (!prd.data && !scope) return null
  const pending = prd.data ? sowPending(prdForPrint(prd.data.markdown)) : 0
  const warnings = [
    prd.data?.stale ? "PRD 生成之后需求清单又改过，附件可能不是最新的，建议在商机里重新生成" : "",
    pending ? `附件里还有 ${pending} 处「待确认」，签约前请和客户逐项确认后重新生成` : "",
    prd.data && !prd.data.confirmed ? "生成 PRD 时需求清单还没和客户确认" : "",
  ].filter(Boolean)
  return (
    <PrintPaper>
      <section aria-label="附件一 需求范围说明书" className="break-before-page">
        <div className="border-b-2 border-zinc-900 pb-3 text-lg font-semibold">
          附件一：需求范围说明书（SOW）
          <span className="ml-2 text-xs font-normal text-zinc-500">合同 {c.code} 的组成部分</span>
        </div>
        {warnings.length ? (
          <ul className="no-print mt-3 list-disc space-y-0.5 rounded-md bg-amber-50 py-2 pr-3 pl-7 text-amber-800">
            {warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        ) : null}
        {prd.data ? (
          <div className="prose-chat mt-4 text-[12px] break-words">
            <ChatMarkdown text={prdForPrint(prd.data.markdown)} />
          </div>
        ) : scope ? (
          <div className="mt-4 space-y-3">
            <Meta label="交付端" value={scope.platforms || "—"} />
            <table className="w-full table-fixed border-collapse">
              <thead>
                <tr className="bg-zinc-100 text-left">
                  <th className={`${TD} font-medium`}>功能模块</th>
                  <th className={`${TD} w-24 font-medium`}>阶段</th>
                </tr>
              </thead>
              <tbody>
                {scope.modules.map((m) => (
                  <tr key={m.name}>
                    <td className={TD}>{m.name}</td>
                    <td className={TD}>{m.phase}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {scope.excluded.length ? <Meta label="本合同不含" value={scope.excluded.join("、")} /> : null}
            <p className="text-zinc-600">
              上表以外的功能、与第三方系统的对接不在本合同范围内；需求变更按双方确认的变更单另行计价。
            </p>
          </div>
        ) : null}
      </section>
    </PrintPaper>
  )
}

function ContractSheet({ c }: { c: ContractItem }) {
  const customer = useCustomer(c.customer?.id ?? "")
  const terms = useTemplates().data?.contract_terms ?? []
  const [note, setNote] = useState("")
  return (
    <PrintPaper>
      <PrintHeader company={PRINT_COMPANY} title="合同要素确认单" />
      <div className="mt-4 grid grid-cols-2 gap-x-8 gap-y-1.5">
        <Meta label="甲方" value={c.customer?.name ?? "—"} />
        <Meta label="合同编号" value={c.code} />
        <Meta label="甲方地址" value={customer.data?.address || "—"} />
        <Meta label="乙方" value={PRINT_COMPANY} />
        <Meta label="关联报价" value={c.quote?.code ?? "—"} />
        <Meta label="乙方联系人" value={c.owner?.name ?? "—"} />
      </div>
      <Subject c={c} />
      <div className="mt-3 ml-auto w-80 space-y-1">
        <div className="flex justify-between border-t border-zinc-300 pt-1 text-sm font-semibold">
          <span>合同总金额</span>
          <span className="tabular-nums">{formatFen(c.amount)}</span>
        </div>
        <div className="flex justify-between gap-3">
          <span className="shrink-0 text-zinc-500">大写</span>
          <span className="text-right">{fenToRmbUpper(c.amount)}</span>
        </div>
      </div>
      <ClientCostsOf c={c} />
      <Plan c={c} />
      <TermsList title="说明" label="确认单说明" terms={terms} />
      <div className="mt-4">
        <label htmlFor="contract-note" className="font-medium">
          其他约定
        </label>
        <Textarea
          id="contract-note"
          rows={3}
          value={note}
          placeholder="例如：交付地点、验收标准、开票信息（打印时显示填写的内容）"
          onChange={(e) => setNote(e.target.value)}
          className="mt-1 resize-none text-[12px] print:border-0 print:p-0 print:shadow-none print:placeholder:text-transparent"
        />
      </div>
      <Signatures parties={["甲方（盖章）", "乙方（盖章）"]} />
    </PrintPaper>
  )
}

/** 合同要素确认单打印页：双方信息、标的明细、金额大写、回款计划、签字盖章栏；正式条款以合同文本为准 */
export default function ContractPrintPage() {
  const { id } = useParams<{ id: string }>()
  const contractId = decodeURIComponent(id)
  const query = useContract(contractId)
  const c = query.data
  const [withSow, setWithSow] = useState(true)
  useDocTitle(c ? contractDocTitle(c) : null)

  let body
  if (query.isPending) body = <Skeleton className="mx-auto my-6 h-[600px] w-[210mm] max-w-full" />
  else if (query.isError)
    body = (
      <div className="mx-auto my-6 max-w-xl rounded-lg bg-white">
        <QueryError error={query.error} onRetry={() => void query.refetch()} feature="合同" />
      </div>
    )
  else
    body = (
      <>
        <ContractSheet c={query.data} />
        {withSow && query.data.quote ? <SowAppendix c={query.data} /> : null}
      </>
    )

  return (
    <PrintPortal>
      <div className="no-print sticky top-0 z-10 flex h-12 items-center gap-2 border-b border-zinc-200 bg-white px-4">
        <Button variant="ghost" size="sm" asChild>
          <Link href={`/contracts?plan=${encodeURIComponent(contractId)}`}>
            <ArrowLeft />
            返回合同
          </Link>
        </Button>
        <span className="min-w-0 flex-1 truncate text-zinc-500">{c ? contractDocTitle(c) : "合同要素确认单"}</span>
        {c?.quote ? (
          <label className="flex items-center gap-1.5 text-sm text-zinc-600">
            <Checkbox
              checked={withSow}
              onCheckedChange={(v) => setWithSow(v === true)}
              aria-label="附带需求范围说明书"
            />
            <span className="max-sm:hidden">附带需求范围（SOW）</span>
          </label>
        ) : null}
        {c ? (
          <Button size="sm" onClick={() => window.print()}>
            <Printer />
            打印 / 存为 PDF
          </Button>
        ) : null}
      </div>
      {body}
    </PrintPortal>
  )
}
