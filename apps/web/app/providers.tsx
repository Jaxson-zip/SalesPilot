"use client"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { useState, type ReactNode } from "react"

import { SessionProvider } from "@/components/shell/SessionProvider"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { isApiError } from "@/lib/api"

/** 4xx 业务错误不重试；网络 / 5xx 最多重试 1 次 */
function shouldRetry(failureCount: number, error: unknown): boolean {
  if (isApiError(error) && error.status >= 400 && error.status < 500) return false
  return failureCount < 1
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30_000, retry: shouldRetry, refetchOnWindowFocus: false },
          mutations: { retry: false },
        },
      }),
  )
  return (
    <QueryClientProvider client={client}>
      <SessionProvider>
        <TooltipProvider delayDuration={300}>
          {children}
          <Toaster theme="light" position="bottom-right" />
        </TooltipProvider>
      </SessionProvider>
    </QueryClientProvider>
  )
}
