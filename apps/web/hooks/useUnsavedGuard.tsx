"use client"

import { useRouter } from "next/navigation"
import { useEffect, type ReactElement } from "react"

import { useConfirmAction } from "@/components/biz/ConfirmAction"
import type { ConfirmCopy } from "@/lib/confirm-texts"

/** 站内链接点击时要不要拦下来问一句：新标签打开、下载、站外、同一个地址都不拦 */
export function leavingTo(
  a: HTMLAnchorElement | null,
  e: Pick<MouseEvent, "button" | "metaKey" | "ctrlKey" | "shiftKey" | "altKey">,
  here: Location,
): string | null {
  if (!a || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return null
  if (a.target === "_blank" || a.hasAttribute("download")) return null
  const url = new URL(a.href, here.href)
  if (url.origin !== here.origin) return null
  if (url.pathname === here.pathname && url.search === here.search) return null
  return url.pathname + url.search + url.hash
}

/**
 * 有没保存的内容时离开页面先确认：点侧栏 / 页面里的链接弹出确认框；刷新、关闭标签页用浏览器自带提示。
 * 返回确认框，放进组件里渲染。
 */
export function useUnsavedGuard(dirty: boolean, copy: ConfirmCopy): ReactElement {
  const router = useRouter()
  const { ask, dialog } = useConfirmAction()
  const { title, description, confirmLabel, destructive } = copy

  useEffect(() => {
    if (!dirty) return
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ""
    }
    // 捕获阶段拦截，先于 next/link 自己的点击处理
    const onClick = (e: MouseEvent) => {
      const a = (e.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null
      const href = leavingTo(a, e, window.location)
      if (!href) return
      e.preventDefault()
      e.stopPropagation()
      ask({ title, description, confirmLabel, destructive, onConfirm: () => router.push(href) })
    }
    window.addEventListener("beforeunload", onBeforeUnload)
    document.addEventListener("click", onClick, true)
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload)
      document.removeEventListener("click", onClick, true)
    }
  }, [dirty, ask, router, title, description, confirmLabel, destructive])

  return dialog
}
