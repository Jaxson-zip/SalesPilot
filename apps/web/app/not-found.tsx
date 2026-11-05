import Link from "next/link"

import { Button } from "@/components/ui/button"

/** 地址写错或对象已删除时的 404：原来是 Next.js 默认的英文白页，没有回去的入口 */
export default function NotFound() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-3 px-4 text-center">
      <p className="text-4xl font-semibold text-zinc-300">404</p>
      <h1 className="text-base font-medium">页面不存在</h1>
      <p className="text-sm text-zinc-500">地址可能写错了，或者这条记录已经被删除。</p>
      <Button asChild className="mt-2">
        <Link href="/dashboard">回到工作台</Link>
      </Button>
    </main>
  )
}
