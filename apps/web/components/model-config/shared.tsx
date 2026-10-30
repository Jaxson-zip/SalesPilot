"use client"

import { TriangleAlert } from "lucide-react"
import type { ReactNode } from "react"

export function time(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function Warn({ children }: { children: ReactNode }) {
  return (
    <p className="flex items-start gap-1.5 text-xs text-red-600">
      <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
      <span>{children}</span>
    </p>
  )
}
