"use client"

import { Link2 } from "lucide-react"
import { useState } from "react"

import { CustomerCombobox } from "@/components/biz/CustomerCombobox"
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
import { useOpportunities } from "@/hooks/useOpportunities"
import { useLinkQuote } from "@/hooks/useQuotes"
import type { CustomerBrief } from "@/types/api"

const NO_OPP = "__none__"

/**
 * 草稿报价补关联（AI 没识别出客户时）：选客户，可选关联这个客户下进行中的商机。
 * 物料和价格不变；关联后就能提交。
 */
export function QuoteLinkButton({ quoteId }: { quoteId: string }) {
  const [open, setOpen] = useState(false)
  const [customer, setCustomer] = useState<CustomerBrief | null>(null)
  const [oppId, setOppId] = useState(NO_OPP)
  const opps = useOpportunities({ view: "mine", customer_id: customer?.id, page_size: 50 }, open && Boolean(customer))
  const link = useLinkQuote(quoteId)
  // 输单 / 赢单的商机不再出报价
  const oppItems = (opps.data?.items ?? []).filter(
    (o) => o.customer.id === customer?.id && o.stage !== "lost" && o.stage !== "won",
  )
  const submit = () => {
    if (!customer) return
    const body = oppId === NO_OPP ? { customer_id: customer.id } : { opportunity_id: oppId }
    link.mutate(body, { onSuccess: () => setOpen(false) })
  }

  return (
    <>
      <Button size="sm" onClick={() => setOpen(true)} title="关联客户" className="max-sm:w-8 max-sm:px-0">
        <Link2 />
        <span className="max-sm:hidden">关联客户</span>
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>关联客户</DialogTitle>
            <DialogDescription>物料和价格保持不变，关联后就可以提交。</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <FormField label="客户" required>
              <CustomerCombobox
                value={customer}
                onChange={(c) => {
                  setCustomer(c)
                  setOppId(NO_OPP)
                }}
              />
            </FormField>
            <FormField label="关联商机" htmlFor="link-opp">
              <SimpleSelect
                id="link-opp"
                ariaLabel="关联商机"
                disabled={!customer}
                value={oppId}
                onChange={setOppId}
                options={[
                  { value: NO_OPP, label: "不关联商机" },
                  ...oppItems.map((o) => ({ value: o.id, label: o.name })),
                ]}
              />
            </FormField>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              取消
            </Button>
            <Button onClick={submit} disabled={!customer || link.isPending}>
              关联
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
