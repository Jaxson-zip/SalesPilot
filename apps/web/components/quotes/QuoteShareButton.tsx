"use client"

import { Copy, ExternalLink, Link2, MessageSquareText, Unlink } from "lucide-react"
import { toast } from "sonner"

import { useConfirmAction } from "@/components/biz/ConfirmAction"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { useQuoteShare, useQuoteShareActions, type QuoteShare } from "@/hooks/useQuoteShare"
import { copyText } from "@/lib/clipboard"
import { formatRelative } from "@/lib/format"
import { shareMessage, shareUrl, viewSummary } from "@/lib/share"
import type { QuoteDetail } from "@/types/api"

const SEND_CONFIRM = {
  title: "生成链接并发给客户",
  description: "生成后报价单记为「已发送客户」，不能再修改，并按规则建一条跟进任务。链接本身可以随时撤销。",
  confirmLabel: "生成链接",
}
const REVOKE_CONFIRM = {
  title: "撤销分享链接",
  description: "撤销后客户再打开会显示「链接已失效」。之后可以重新生成一条新链接。",
  confirmLabel: "撤销链接",
  destructive: true,
}

async function copy(text: string, done: string) {
  if (await copyText(text)) toast.success(done)
  else toast.error("复制失败，请手动选中复制")
}

function ShareLink({ q, share, onRevoke }: { q: QuoteDetail; share: QuoteShare; onRevoke: () => void }) {
  const url = shareUrl(window.location.origin, share.path)
  const message = shareMessage(
    { code: q.code, customer: q.customer?.name, project: q.opportunity?.name, validUntil: q.valid_until },
    url,
  )
  return (
    <div className="space-y-3">
      <Input
        readOnly
        value={url}
        aria-label="报价分享链接"
        onFocus={(e) => e.currentTarget.select()}
        className="text-xs"
      />
      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={() => void copy(message, "已复制，粘贴到微信发给客户")}>
          <MessageSquareText />
          复制发给客户的话
        </Button>
        <Button size="sm" variant="outline" onClick={() => void copy(url, "链接已复制")}>
          <Copy />
          复制链接
        </Button>
        <Button size="sm" variant="ghost" asChild>
          <a href={share.path} target="_blank" rel="noreferrer">
            <ExternalLink />
            预览
          </a>
        </Button>
      </div>
      <div className="space-y-0.5 text-xs text-zinc-500">
        <div>{viewSummary(share.view_count, share.last_viewed_at, formatRelative)}（你自己预览不计入）</div>
        <div>有效期至 {share.expires_at.slice(0, 10)} 前，客户每天第一次打开会通知你</div>
      </div>
      <Button size="sm" variant="ghost" className="text-red-600 hover:text-red-700" onClick={onRevoke}>
        <Unlink />
        撤销链接
      </Button>
    </div>
  )
}

/** 报价详情页头的「分享给客户」：只给负责人、只在审批通过后显示（契约 §35） */
export function QuoteShareButton({ q }: { q: QuoteDetail }) {
  const share = useQuoteShare(q.id)
  const { create, revoke } = useQuoteShareActions(q.id)
  const { ask, dialog } = useConfirmAction()
  const generate = () => {
    if (q.status === "approved") ask({ ...SEND_CONFIRM, onConfirm: () => create.mutate() })
    else create.mutate()
  }
  return (
    <>
      <Popover>
        <PopoverTrigger asChild>
          <Button size="sm" variant="outline" title="分享给客户" className="max-sm:w-8 max-sm:px-0">
            <Link2 />
            <span className="max-sm:hidden">分享给客户</span>
          </Button>
        </PopoverTrigger>
        <PopoverContent align="end" className="w-80">
          <div className="mb-2 text-sm font-medium">分享给客户</div>
          {share.data ? (
            <ShareLink
              q={q}
              share={share.data}
              onRevoke={() => ask({ ...REVOKE_CONFIRM, onConfirm: () => revoke.mutate() })}
            />
          ) : (
            <div className="space-y-3">
              <p className="text-xs leading-5 text-zinc-500">
                生成一个客户不用登录、手机上就能看的报价链接：只有明细单价、合计和条款，不含成本和毛利。
              </p>
              <Button size="sm" onClick={generate} disabled={create.isPending || share.isPending}>
                <Link2 />
                生成链接
              </Button>
            </div>
          )}
        </PopoverContent>
      </Popover>
      {dialog}
    </>
  )
}
