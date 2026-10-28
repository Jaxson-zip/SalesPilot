"use client"

import Link from "next/link"

import { Alert } from "@/components/biz/Alert"
import type { SimilarCustomer } from "@/types/api"

/** 新建客户时的查重提示：同名 → 黄色警告（不能创建）；相似 → 灰色提示（确认不是同一家再建） */
export function SimilarCustomersHint({ items }: { items: SimilarCustomer[] }) {
  if (items.length === 0) return null
  const exact = items.some((c) => c.exact)
  return (
    <Alert
      tone={exact ? "warn" : "info"}
      title={exact ? "客户已存在，不能重复创建" : "有名称相近的客户，确认不是同一家再创建"}
    >
      <ul className="mt-1 space-y-0.5 text-[13px]">
        {items.map((c) => (
          <li key={c.name}>
            {c.visible && c.id ? (
              <Link
                href={`/customers/${encodeURIComponent(c.id)}`}
                className="font-medium underline-offset-2 hover:underline"
              >
                {c.name}
              </Link>
            ) : (
              <span className="font-medium">{c.name}</span>
            )}
            <span className="text-zinc-500">
              {" · 负责人 "}
              {c.owner_name ?? "未分配"}
              {c.visible ? "" : "（不在你的客户范围内，需要时请联系主管转移）"}
            </span>
          </li>
        ))}
      </ul>
    </Alert>
  )
}
