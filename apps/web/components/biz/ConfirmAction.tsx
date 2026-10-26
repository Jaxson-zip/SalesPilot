"use client"

import { useCallback, useState, type ReactElement } from "react"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { buttonVariants } from "@/components/ui/button"
import type { ConfirmCopy } from "@/lib/confirm-texts"

export interface ConfirmRequest extends ConfirmCopy {
  onConfirm: () => void
}

/**
 * 不可逆操作的确认对话框（AlertDialog）：标题写动作、正文写后果，按钮「取消」/「确认 xxx」。
 * 受控：request 为 null 时关闭。
 */
export function ConfirmAction({ request, onClose }: { request: ConfirmRequest | null; onClose: () => void }) {
  return (
    <AlertDialog open={request !== null} onOpenChange={(o) => !o && onClose()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{request?.title}</AlertDialogTitle>
          <AlertDialogDescription>{request?.description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>取消</AlertDialogCancel>
          <AlertDialogAction
            className={request?.destructive ? buttonVariants({ variant: "destructive" }) : undefined}
            onClick={() => {
              request?.onConfirm()
              onClose()
            }}
          >
            {request?.confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

/** 便捷 hook：ask(request) 弹出确认，dialog 放进 JSX 里渲染一次 */
export function useConfirmAction(): { ask: (r: ConfirmRequest) => void; dialog: ReactElement } {
  const [request, setRequest] = useState<ConfirmRequest | null>(null)
  const ask = useCallback((r: ConfirmRequest) => setRequest(r), [])
  const dialog = <ConfirmAction request={request} onClose={() => setRequest(null)} />
  return { ask, dialog }
}
