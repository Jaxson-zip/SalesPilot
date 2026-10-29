import { describe, expect, it } from "vitest"

import { checkPasswordChange, passwordWeakness, USERNAME_RE } from "@/lib/password"

describe("密码与登录名规则", () => {
  it("密码至少 8 位且同时有字母和数字", () => {
    expect(passwordWeakness("abc123")).toBe("密码至少 8 位")
    expect(passwordWeakness("abcdefgh")).toBe("密码要同时包含字母和数字")
    expect(passwordWeakness("12345678")).toBe("密码要同时包含字母和数字")
    expect(passwordWeakness("demo2026")).toBeNull()
  })

  it("改密码：当前密码必填、新密码够强且和旧的不同、两次一致", () => {
    expect(checkPasswordChange({ old: "", next: "short", confirm: "" })).toEqual({
      old: "请输入当前密码",
      next: "密码至少 8 位",
    })
    expect(checkPasswordChange({ old: "demo2026", next: "demo2026", confirm: "demo2026" })).toEqual({
      next: "新密码不能和当前密码相同",
    })
    expect(checkPasswordChange({ old: "demo2026", next: "NewPass2026", confirm: "NewPass2025" })).toEqual({
      confirm: "两次输入的新密码不一致",
    })
    expect(checkPasswordChange({ old: "demo2026", next: "NewPass2026", confirm: "NewPass2026" })).toEqual({})
  })

  it("登录名字母开头、3～30 位", () => {
    expect(USERNAME_RE.test("zhangchen")).toBe(true)
    expect(USERNAME_RE.test("li.wei_2")).toBe(true)
    expect(USERNAME_RE.test("2li")).toBe(false)
    expect(USERNAME_RE.test("ab")).toBe(false)
    expect(USERNAME_RE.test("张晨")).toBe(false)
  })
})
