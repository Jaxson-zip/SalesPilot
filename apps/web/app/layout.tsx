import type { Metadata, Viewport } from "next"

import { Providers } from "./providers"
import "./globals.css"

export const metadata: Metadata = {
  title: "SalesPilot · AI 销售 CRM",
  description: "面向 ToB 销售的 AI CRM",
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body className="font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
