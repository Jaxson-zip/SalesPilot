import { describe, expect, it } from "vitest"

import { restorable } from "@/lib/report-backup"

const raw = (text: string, base: string) => JSON.stringify({ text, base })

describe("日报暂存恢复", () => {
  it("服务器上还是暂存时的版本：恢复没保存的内容", () => {
    expect(restorable(raw("今天拜访了 A", "旧"), "旧")).toBe("今天拜访了 A")
  })
  it("别的设备已经保存过（服务器版本变了）：不恢复，免得盖掉新内容", () => {
    expect(restorable(raw("今天拜访了 A", "旧"), "手机上保存的新内容")).toBeNull()
  })
  it("和服务器一样、格式不对、旧版只存了文字：都不恢复", () => {
    expect(restorable(raw("同", "同"), "同")).toBeNull()
    expect(restorable("纯文字", "")).toBeNull()
    expect(restorable(null, "")).toBeNull()
  })
})
