import { describe, expect, it } from "vitest"

import { notificationMeta } from "@/lib/notifications"
import { isPublicPath } from "@/lib/session"
import { canShareQuote, shareMessage, shareUrl, viewSummary } from "@/lib/share"

describe("报价分享链接", () => {
  it("审批通过后才能分享", () => {
    expect(canShareQuote("approved")).toBe(true)
    expect(canShareQuote("sent")).toBe(true)
    expect(canShareQuote("accepted")).toBe(true)
    expect(canShareQuote("draft")).toBe(false)
    expect(canShareQuote("pending_approval")).toBe(false)
    expect(canShareQuote("rejected")).toBe(false)
  })

  it("按当前域名拼完整链接", () => {
    expect(shareUrl("http://127.0.0.1:3000/", "/share/q/abc")).toBe("http://127.0.0.1:3000/share/q/abc")
    expect(shareUrl("https://crm.example.com", "share/q/abc")).toBe("https://crm.example.com/share/q/abc")
  })

  it("发给客户的话带项目、编号、有效期和链接", () => {
    const text = shareMessage(
      { code: "Q-2026-018", customer: "明理科技", project: "质检小程序", validUntil: "2026-11-30" },
      "https://x/share/q/a",
    )
    expect(text).toContain("明理科技您好")
    expect(text).toContain("「质检小程序」的报价（Q-2026-018）")
    expect(text).toContain("有效期至 2026-11-30")
    expect(text).toContain("https://x/share/q/a")
    expect(shareMessage({ code: "Q-1" }, "u")).toMatch(/^您好，报价单 Q-1/)
  })

  it("打开次数说明", () => {
    expect(viewSummary(0, null, () => "")).toBe("客户还没有打开过")
    expect(viewSummary(3, "2026-10-31T10:00:00Z", () => "5 分钟前")).toBe("客户打开过 3 次，最近一次 5 分钟前")
  })

  it("分享页和登录页不需要登录", () => {
    expect(isPublicPath("/login")).toBe(true)
    expect(isPublicPath("/share/q/abc")).toBe(true)
    expect(isPublicPath("/quotes/1")).toBe(false)
    expect(isPublicPath(null)).toBe(false)
  })

  it("客户打开报价的通知有中文类型", () => {
    expect(notificationMeta("quote_viewed").label).toBe("客户在看报价")
  })
})
