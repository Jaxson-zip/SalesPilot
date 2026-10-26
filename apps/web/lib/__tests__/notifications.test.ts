import { describe, expect, it } from "vitest"

import { bellLabel, markReadLocally, notificationHref, notificationMeta, unreadBadge } from "@/lib/notifications"

describe("通知（v3 §15）", () => {
  it("类型文案，未知类型兜底", () => {
    expect(notificationMeta("approval_pending").label).toBe("待审批")
    expect(notificationMeta("approval_decided").tone).toBe("result")
    expect(notificationMeta("customer_assigned").label).toBe("客户转移")
    expect(notificationMeta("task_due").label).toBe("任务到期")
    expect(notificationMeta("xxx")).toEqual({ label: "通知", tone: "other" })
  })
  it("未读角标", () => {
    expect(unreadBadge(0)).toBe("")
    expect(unreadBadge(undefined)).toBe("")
    expect(unreadBadge(5)).toBe("5")
    expect(unreadBadge(120)).toBe("99+")
  })
  it("只跳转站内路由", () => {
    expect(notificationHref("/approvals")).toBe("/approvals")
    expect(notificationHref("/pipeline?opp=o1")).toBe("/pipeline?opp=o1")
    expect(notificationHref("https://evil.example")).toBeNull()
    expect(notificationHref("//evil.example")).toBeNull()
    expect(notificationHref(null)).toBeNull()
  })
  it("铃铛 aria-label", () => {
    expect(bellLabel(0)).toBe("通知")
    expect(bellLabel(3)).toBe("通知，3 条未读")
  })
  it("本地标记已读：指定 id / 全部", () => {
    const items = [
      { id: "a", read: false },
      { id: "b", read: false },
      { id: "c", read: true },
    ]
    const one = markReadLocally(items, ["a"])
    expect(one.changed).toBe(1)
    expect(one.items.map((n) => n.read)).toEqual([true, false, true])
    expect(markReadLocally(items).changed).toBe(2)
  })
})
