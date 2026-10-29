import { expect, test } from "@playwright/test"

import { loginAs } from "./helpers"

test("没登录打开业务页面会到登录页；选主管账户进入后回到原页面", async ({ page }) => {
  await page.goto("/contracts")
  await expect(page).toHaveURL(/\/login\?next=%2Fcontracts/)
  await expect(page.getByLabel("访问口令")).toHaveCount(0) // 本地没配口令
  await page.getByText("李薇").click()
  await page.getByRole("button", { name: "以「李薇」进入" }).click()
  await expect(page).toHaveURL(/\/contracts$/)
  await expect(page.getByRole("button", { name: /李薇/ })).toBeVisible()
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
  await page.route(/\/api\/auth\/options$/, (r) =>
    r.fulfill({ json: { code: 0, message: "ok", data: { access_code_required: true } } }),
  )
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
  const enter = page.getByRole("button", { name: "以「张晨」进入" })
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
