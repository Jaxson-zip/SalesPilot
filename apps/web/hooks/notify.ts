"use client"

import { toast } from "sonner"

import { errorMessage, errorMeta } from "@/lib/errors"

/** 写操作失败统一提示（42201 / 40301 / 40901 等转中文，副标题带错误码和 request_id） */
export function notifyError(err: unknown): void {
  toast.error(errorMessage(err), { description: errorMeta(err) })
}
