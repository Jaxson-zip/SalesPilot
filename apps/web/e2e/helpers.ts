import { expect, type APIRequestContext, type Locator, type Page } from "@playwright/test"

import type { Role } from "@/types/api"

/** 每个用例的数据都带唯一后缀，互不干扰 */
export const uniq = (prefix: string): string => `${prefix} ${Date.now().toString(36)}`

interface Envelope<T> {
  code: number
  message: string
  data: T
}

/** 以某个演示角色调用 core 接口（经 web 的 /api 代理） */
export class Api {
  private constructor(
    private readonly request: APIRequestContext,
    private readonly token: string,
  ) {}

  static async as(request: APIRequestContext, role: Role): Promise<Api> {
    const res = await request.post("/api/auth/mock-login", { data: { role } })
    const body = (await res.json()) as Envelope<{ token: string }>
    expect(body.code, body.message).toBe(0)
    return new Api(request, body.data.token)
  }

  get authHeader(): Record<string, string> {
    return { Authorization: `Bearer ${this.token}` }
  }

  async call<T>(method: "GET" | "POST" | "PATCH" | "PUT" | "DELETE", path: string, data?: unknown): Promise<T> {
    const res = await this.request.fetch(path, { method, data, headers: this.authHeader })
    const body = (await res.json()) as Envelope<T>
    expect(body.code, `${method} ${path}: ${body.message}`).toBe(0)
    return body.data
  }

  async upload(expenseId: string, kind: string, name: string, mimeType: string, buffer: Buffer): Promise<void> {
    const res = await this.request.post(`/api/expenses/${expenseId}/attachments`, {
      headers: this.authHeader,
      multipart: { kind, file: { name, mimeType, buffer } },
    })
    expect(((await res.json()) as Envelope<unknown>).code).toBe(0)
  }

  /** 调用 Agent 的 SSE 接口，返回整个事件流文本（APIRequestContext 会等流结束） */
  async sse(path: string, data: unknown): Promise<string> {
    const res = await this.request.post(path, { data, headers: this.authHeader, timeout: 60_000 })
    expect(res.status()).toBe(200)
    return res.text()
  }
}

/**
 * 通过接口建一张客户招待报销草稿（v3 参与人结构化）：客户方选明理律所的第一位联系人，
 * 加上申请人本人，其余计入「其他人数」，总人数 = headcount。
 */
export async function entertainmentDraft(
  api: Api,
  amount: number,
  headcount: number,
  reason: string,
): Promise<{ id: string; code: string; status: string }> {
  const customers = await api.call<{ items: { id: string; name: string }[] }>(
    "GET",
    "/api/customers?view=mine&q=深圳明理&page_size=50",
  )
  const mingli = customers.items.find((c) => c.name === "深圳明理律师事务所")
  if (!mingli) throw new Error("演示数据缺少深圳明理律师事务所，请先运行 seed")
  const contacts = await api.call<{ items: { id: string }[] }>("GET", `/api/customers/${mingli.id}/contacts`)
  return api.call("POST", "/api/expenses", {
    type: "entertainment",
    amount,
    occurred_on: new Date().toISOString().slice(0, 10),
    customer_id: mingli.id,
    contact_ids: [contacts.items[0].id],
    extra_guests: Math.max(headcount - 2, 0),
    reason,
  })
}

/** 解析 SSE 文本里某类 artifact 的 data */
export function artifactOf<T>(stream: string, type: string): T {
  const blocks = stream.split(/\r?\n\r?\n/)
  for (const block of blocks) {
    if (!/^event: artifact$/m.test(block)) continue
    const line = block.split(/\r?\n/).find((l) => l.startsWith("data:"))
    const payload = line ? (JSON.parse(line.slice(5)) as { type: string; data: T }) : null
    if (payload?.type === type) return payload.data
  }
  throw new Error(`没有找到 artifact: ${type}`)
}

/** 让页面以某个角色打开（写入前端 session 用的 localStorage，再由页面自动 mock 登录） */
export async function loginAs(page: Page, role: Role): Promise<void> {
  await page.addInitScript((r) => {
    window.localStorage.setItem("sp.role", r)
    window.localStorage.removeItem("sp.token")
  }, role)
}

/**
 * 用鼠标拖拽（dnd-kit 的 PointerSensor 需要先移动超过 6px 才开始拖，并且要有中间过程）。
 */
export async function dragTo(page: Page, source: Locator, target: Locator): Promise<void> {
  const from = await source.boundingBox()
  if (!from) throw new Error("拖拽源不可见")
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2)
  await page.mouse.down()
  await page.mouse.move(from.x + from.width / 2 + 10, from.y + from.height / 2 + 10, { steps: 5 })
  await expect(target).toBeVisible()
  const to = await target.boundingBox()
  if (!to) throw new Error("拖拽目标不可见")
  await page.mouse.move(to.x + to.width / 2, to.y + Math.min(to.height / 2, 60), { steps: 15 })
  await page.mouse.up()
}

/** 最小的合法 PDF / PNG，用作票据 */
export const PDF = Buffer.from("%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
export const PNG = Buffer.from(
  "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000000020001e221bc330000000049454e44ae426082",
  "hex",
)
