import type { ReactNode } from "react"

import { AiSessionProvider } from "@/components/agent/AiSessionProvider"
import { AppShell } from "@/components/shell/AppShell"

export default function MainLayout({ children }: { children: ReactNode }) {
  return (
    <AiSessionProvider>
      <AppShell>{children}</AppShell>
    </AiSessionProvider>
  )
}
