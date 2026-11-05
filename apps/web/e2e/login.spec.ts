import { expect, test, type Page } from "@playwright/test"

import { loginAs } from "./helpers"

const ok = (data: unknown) => ({ json: { code: 0, message: "ok", data } })

test("没登录打开业务页面会到登录页；演示账户一键进入后回到原页面", async ({ page }) => {
  await page.goto("/contracts")
  await expect(page).toHaveURL(/\/login\?next=%2Fcontracts/)
  await expect(page.getByLabel("访问口令")).toHaveCount(0) // 本地没配口令
  await page.getByRole("button", { name: "以李薇（销售主管）进入" }).click()
  await expect(page).toHaveURL(/\/contracts$/)
  await expect(page.getByRole("button", { name: /李薇/ })).toBeVisible()
})

test("账号密码登录：密码错误有提示，正确后进入工作台，左下角显示本人和团队", async ({ page }) => {
  await page.goto("/login")
  await page.getByRole("button", { name: "登录", exact: true }).click()
  await expect(page.getByText("请输入账号")).toBeVisible()
  await page.locator("#login-username").fill("zhangchen")
  await page.locator("#login-password").fill("wrong-pass1")
  await page.getByRole("button", { name: "登录", exact: true }).click()
  await expect(page.getByText("账号或密码不正确")).toBeVisible()
  await page.locator("#login-password").fill("demo2026")
  await page.getByRole("button", { name: "登录", exact: true }).click()
  await expect(page).toHaveURL(/\/dashboard$/)
  await expect(page.getByRole("button", { name: /张晨/ })).toContainText("销售")
})

test("退出登录回到登录页", async ({ page }) => {
  await loginAs(page, "sales")
  await page.goto("/dashboard")
  await page.getByRole("button", { name: /张晨/ }).click()
  await page.getByRole("menuitem", { name: "退出登录" }).click()
  await expect(page).toHaveURL(/\/login$/)
  await page.goto("/customers")
  await expect(page).toHaveURL(/\/login/) // token 已清除
})

test("配置了访问口令：必须输入口令，错误时提示（模拟接口）", async ({ page }) => {
  const bodies: Record<string, unknown>[] = []
  await page.route(/\/api\/auth\/options$/, (r) => r.fulfill(ok({ access_code_required: true, demo_login: true })))
  await page.route(/\/api\/auth\/mock-login$/, (r) => {
    const body = r.request().postDataJSON() as Record<string, unknown>
    bodies.push(body)
    if (body.access_code === "right") return r.fallback()
    return r.fulfill({
      status: 401,
      json: { code: 40101, message: "访问口令不正确", data: { rule: "access_code" } },
    })
  })
  await page.goto("/login")
  const enter = page.getByRole("button", { name: "以张晨（销售）进入" })
  await enter.click()
  await expect(page.getByText("请输入访问口令")).toBeVisible()
  expect(bodies).toHaveLength(0)
  await page.getByLabel("访问口令").fill("wrong")
  await enter.click()
  await expect(page.getByText("访问口令不正确")).toBeVisible()
  await expect(page).toHaveURL(/\/login$/)
  await page.getByLabel("访问口令").fill("right")
  await enter.click()
  await expect(page).toHaveURL(/\/dashboard$/)
  expect(bodies.at(-1)).toMatchObject({ role: "sales", access_code: "right" })
})

test("关闭演示账户后登录页只有账号密码，左下角没有切换（模拟接口）", async ({ page }) => {
  await page.route(/\/api\/auth\/options$/, (r) => r.fulfill(ok({ access_code_required: false, demo_login: false })))
  await page.goto("/login")
  await expect(page.locator("#login-username")).toBeVisible()
  await expect(page.getByRole("button", { name: /进入$/ })).toHaveCount(0)
  await loginAs(page, "sales")
  await page.goto("/dashboard")
  await page.getByRole("button", { name: /张晨/ }).click()
  await expect(page.getByText("切换演示账户")).toHaveCount(0)
  await expect(page.getByRole("menuitem", { name: "修改密码" })).toBeVisible()
})

/** 模拟 /api/me：第一次返回需要改密码，改完后正常 */
async function mockMustChange(page: Page) {
  let changed = false
  const passwordCalls: Record<string, unknown>[] = []
  await page.route(/\/api\/me$/, async (r) => {
    const res = await r.fetch()
    const body = await res.json()
    body.data.must_change_password = !changed
    return r.fulfill({ json: body })
  })
  await page.route(/\/api\/auth\/password$/, async (r) => {
    passwordCalls.push(r.request().postDataJSON())
    changed = true
    const res = await r.fetch({ method: "GET", url: r.request().url().replace("/auth/password", "/me") })
    const me = await res.json()
    return r.fulfill(ok({ token: null, user: { ...me.data, must_change_password: false } }))
  })
  return passwordCalls
}

test("临时密码首次登录：必须先改密码，不能关闭（模拟接口，不改真实密码）", async ({ page }) => {
  await loginAs(page, "sales")
  const calls = await mockMustChange(page)
  await page.goto("/dashboard")
  const dialog = page.getByRole("dialog", { name: "首次登录，请先修改密码" })
  await expect(dialog).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(dialog).toBeVisible() // 关不掉
  await dialog.locator("#pw-old").fill("Temp2026x")
  await dialog.locator("#pw-new").fill("short")
  await dialog.getByRole("button", { name: "保存新密码" }).click()
  await expect(dialog.getByText("密码至少 8 位", { exact: true })).toBeVisible()
  await dialog.locator("#pw-new").fill("NewPass2026")
  await dialog.locator("#pw-confirm").fill("NewPass2026")
  await dialog.getByRole("button", { name: "保存新密码" }).click()
  await expect(dialog).toBeHidden()
  expect(calls[0]).toEqual({ old_password: "Temp2026x", new_password: "NewPass2026" })
})
