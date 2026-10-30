import { expect, test, type Page } from "@playwright/test"

import { loginAs } from "./helpers"

const ok = (data: unknown) => ({ json: { code: 0, message: "ok", data } })
const TEAM = {
  id: "t-south",
  name: "华南销售组",
  members: 3,
  managers: ["李薇"],
  default_product_line_id: null,
  default_product_line: null,
  pack: null,
}

const member = (extra: Record<string, unknown>) => ({
  id: "u-1",
  username: "zhangchen",
  name: "张晨",
  role: "sales",
  team_id: TEAM.id,
  team_name: TEAM.name,
  active: true,
  must_change_password: false,
  last_login_at: null,
  customers: 3,
  ...extra,
})

/** 模拟成员与团队接口（不在真实库里建人），记下写请求 */
async function mockAdmin(page: Page) {
  const calls: { method: string; url: string; body: unknown }[] = []
  let users = [
    member({
      id: "u-admin",
      username: "zhoumin",
      name: "周敏",
      role: "admin",
      team_id: null,
      team_name: null,
      customers: 0,
    }),
    member({}),
  ]
  await page.route(/\/api\/admin\/teams$/, (r) => r.fulfill(ok([TEAM])))
  await page.route(/\/api\/admin\/users(\/[^/]+)?(\/reset-password)?$/, async (r) => {
    const method = r.request().method()
    if (method === "GET") return r.fulfill(ok(users))
    const body = r.request().postDataJSON()
    calls.push({ method, url: r.request().url(), body })
    if (method === "POST" && r.request().url().endsWith("/reset-password"))
      return r.fulfill(ok({ account: users[1], temp_password: "Reset2026Ab" }))
    if (method === "POST") {
      const created = member({
        id: "u-new",
        username: body.username,
        name: body.name,
        must_change_password: true,
        customers: 0,
      })
      users = [...users, created]
      return r.fulfill(ok({ account: created, temp_password: "Temp2026Xy" }))
    }
    users = users.map((u) => (u.id === "u-1" ? { ...u, ...body } : u))
    return r.fulfill(ok(users[1]))
  })
  return calls
}

test("管理员新建成员：只显示一次临时密码；停用有客户的成员会提示交接（模拟接口）", async ({ page }) => {
  await loginAs(page, "admin")
  const calls = await mockAdmin(page)
  await page.goto("/settings/accounts")
  await expect(page.getByRole("table", { name: "成员列表" })).toContainText("张晨")

  await page.getByRole("button", { name: "新建成员" }).click()
  const dialog = page.getByRole("dialog", { name: "新建成员" })
  await dialog.getByLabel("登录名").fill("9bad")
  await dialog.getByLabel("姓名").fill("赵新")
  await dialog.getByRole("button", { name: "创建并生成密码" }).click()
  await expect(dialog.getByText("字母开头，3～30 位字母、数字或 _ . -")).toBeVisible()
  expect(calls).toHaveLength(0)
  await dialog.getByLabel("登录名").fill("zhaoxin")
  await dialog.getByRole("button", { name: "创建并生成密码" }).click()
  const temp = page.getByRole("dialog", { name: "临时密码" })
  await expect(temp.getByLabel("临时密码")).toHaveText("Temp2026Xy")
  expect(calls[0].body).toEqual({ username: "zhaoxin", name: "赵新", role: "sales", team_id: TEAM.id })
  await temp.getByRole("button", { name: "我已记下" }).click()
  await expect(page.getByRole("table", { name: "成员列表" })).toContainText("待改密码")

  await page.getByRole("button", { name: "停用张晨" }).click()
  const confirm = page.getByRole("alertdialog")
  await expect(confirm).toContainText("名下还有 3 个客户")
  await confirm.getByRole("button", { name: "确认停用" }).click()
  await expect.poll(() => calls.length).toBe(2)
  expect(calls[1]).toMatchObject({ method: "PATCH", body: { active: false } })
  await expect(page.getByRole("table", { name: "成员列表" })).toContainText("待交接")
})

test("主管从停用通知进入客户页：按人交接预选已停用的成员（模拟接口）", async ({ page }) => {
  await loginAs(page, "manager")
  await page.route(/\/api\/users\?/, (r) =>
    r.fulfill(
      ok({
        items: [
          { id: "m1", name: "李薇", role: "manager", active: true },
          { id: "gone", name: "赵新", role: "sales", active: false },
          { id: "s2", name: "王磊", role: "sales", active: true },
        ],
        total: 3,
      }),
    ),
  )
  await page.route(/\/api\/customers\/handover\/preview\?/, (r) =>
    r.fulfill(ok({ customers: 2, opportunities: 1, tasks: 0, quotes: 0, contracts: 0 })),
  )
  await page.goto("/customers?handover=gone")
  const dialog = page.getByRole("dialog", { name: "按人交接" })
  await expect(dialog.getByRole("combobox", { name: "交接人" })).toHaveText("赵新（已停用）")
  await expect(dialog.getByRole("status")).toContainText("2 个客户")
  await dialog.getByRole("combobox", { name: "接手人" }).click()
  await expect(page.getByRole("option", { name: /赵新/ })).toHaveCount(0) // 停用的不能接手
  await expect(page.getByRole("option", { name: "王磊" })).toBeVisible()
})

test("销售和主管看不到成员与团队", async ({ page }) => {
  await loginAs(page, "manager")
  await page.goto("/settings/accounts")
  await expect(page.getByText("成员和团队由系统管理员维护")).toBeVisible()
})

test("管理员给团队指定默认行业包（模拟接口）", async ({ page }) => {
  await loginAs(page, "admin")
  await mockAdmin(page)
  const lines = [
    { id: "pl-llm", name: "大模型一体机", pack: "llm_deploy", enabled: true },
    { id: "pl-soft", name: "软件定制开发", pack: "software_outsourcing", enabled: true },
  ]
  await page.route(/\/api\/product-lines$/, (r) => r.fulfill(ok({ items: lines, total: 2 })))
  let patched: unknown = null
  await page.route(/\/api\/admin\/teams\/t-south$/, async (r) => {
    patched = r.request().postDataJSON()
    await r.fulfill(ok({ ...TEAM, default_product_line_id: "pl-soft", default_product_line: "软件定制开发" }))
  })
  await page.goto("/settings/accounts")
  await expect(page.getByText("行业包：系统默认")).toBeVisible()
  await page.getByRole("button", { name: "修改华南销售组" }).click()
  await page.getByRole("combobox", { name: "默认产品线" }).click()
  await page.getByRole("option", { name: /软件定制开发/ }).click()
  await page.getByRole("button", { name: "保存" }).click()
  await expect.poll(() => patched).toEqual({ name: "华南销售组", default_product_line_id: "pl-soft" })
})
