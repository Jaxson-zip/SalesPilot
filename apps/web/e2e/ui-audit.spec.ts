import { expect, test } from "@playwright/test"

import { loginAs } from "./helpers"

/** 条件满足后才可用的按钮（不是「永久禁用」），扫描时放行 */
const CONDITIONAL_NAMES = ["发送"]

const PAGES = [
  "/dashboard",
  "/customers",
  "/pipeline",
  "/quotes",
  "/contracts",
  "/expenses",
  "/approvals",
  "/settings/rules",
  "/settings/packs",
  "/ai",
  "/help",
]

/**
 * 回归测试：页面上不允许出现「看得见却点不了」的按钮。
 * - NO-HANDLER：可见、未禁用，但自身和上两层都没有任何点击 / 键盘处理器（点了没反应）
 * - DISABLED-ATTR：一直显示为禁用状态的按钮（无权操作应隐藏而不是置灰；提交类按钮在条件满足前禁用是允许的，不在扫描页面范围内）
 * 曾发现：看板卡片外层被当成禁用按钮、AI「上传附件」无处理、行业包「产品目录 / 业务规则 / 知识库」永久禁用。
 */
for (const role of ["sales", "manager", "admin"] as const) {
  test(`没有点不了的按钮：${role}`, async ({ page }) => {
    const problems: string[] = []
    await loginAs(page, role)
    for (const path of PAGES) {
      await page.goto(path)
      await page.waitForTimeout(1500)
      const dead = await page.evaluate((conditional) => {
        const CONDITIONAL = new Set(conditional)
        const out: string[] = []
        const handlers = ["onClick", "onPointerDown", "onMouseDown", "onKeyDown", "onPointerUp"]
        const hasHandler = (el: Element): boolean => {
          let cur: Element | null = el
          for (let depth = 0; cur && depth < 3; depth++, cur = cur.parentElement) {
            const key = Object.keys(cur).find((k) => k.startsWith("__reactProps$"))
            const props = key ? (cur as unknown as Record<string, Record<string, unknown>>)[key] : undefined
            if (props && handlers.some((h) => typeof props[h] === "function")) return true
          }
          return false
        }
        for (const el of document.querySelectorAll('button, [role="button"], a:not([href])')) {
          const r = el.getBoundingClientRect()
          if (r.width === 0 || r.height === 0) continue
          const name = el.getAttribute("aria-label") || (el.textContent ?? "").trim().slice(0, 30)
          if ((el as HTMLButtonElement).disabled || el.getAttribute("aria-disabled") === "true") {
            // 允许：条件满足后才可用的提交类按钮（例如输入为空时的「发送」）
            if (!CONDITIONAL.has(name)) out.push(`DISABLED-ATTR: ${name}`)
            continue
          }
          if ((el as HTMLButtonElement).type === "submit" || el.closest("form")) continue
          if (!hasHandler(el)) {
            const label =
              el.getAttribute("aria-label") || (el.textContent ?? "").trim().slice(0, 30) || el.outerHTML.slice(0, 60)
            out.push(`NO-HANDLER: ${label}`)
          }
        }
        return [...new Set(out)]
      }, CONDITIONAL_NAMES)
      problems.push(...dead.map((d) => `${path}  ${d}`))
    }
    expect(problems).toEqual([])
  })
}
