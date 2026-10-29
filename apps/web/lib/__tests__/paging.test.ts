import { afterEach, describe, expect, it, vi } from "vitest"

import { api } from "@/lib/api"
import { filterParams, serverQuery, type FilterDef } from "@/lib/list-view"
import { fetchAllPaged } from "@/lib/paging"

type Row = { id: string }

const defs: FilterDef<Row>[] = [
  { id: "level", label: "等级", options: [] },
  { id: "owner", label: "负责人", param: "owner_id", options: [] },
]

describe("服务端列表参数", () => {
  it("生效筛选按 param 名转成多选参数，空选项不发送", () => {
    expect(filterParams(defs, { level: ["A", "B"], owner: ["u1"] })).toEqual({ level: ["A", "B"], owner_id: ["u1"] })
    expect(filterParams(defs, { level: [] })).toEqual({})
  })

  it("默认排序不发送", () => {
    expect(serverQuery({ sort: "default", filters: { level: ["A"] } })).toEqual({ sort: undefined, level: ["A"] })
    expect(serverQuery({ sort: "amount_desc" })).toEqual({ sort: "amount_desc" })
  })
})

describe("数组查询参数", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("数组按重复键发送", async () => {
    const fetchMock = vi.fn(async () => Response.json({ code: 0, message: "ok", data: null }))
    vi.stubGlobal("fetch", fetchMock)
    await api.get("/api/customers", { level: ["A", "B"], industry: ["软件, 互联网"], view: "mine", q: undefined })
    const url = String((fetchMock.mock.calls[0] as unknown[])[0])
    expect(url).toContain("level=A&level=B")
    expect(new URL(url, "http://x").searchParams.getAll("industry")).toEqual(["软件, 互联网"]) // 值里有逗号也不会被拆开
    expect(url).not.toContain("q=")
  })
})

describe("fetchAllPaged", () => {
  afterEach(() => vi.restoreAllMocks())

  it("逐页取到 total 为止", async () => {
    const all = Array.from({ length: 230 }, (_, i) => ({ id: String(i) }))
    const get = vi.spyOn(api, "get").mockImplementation(async (_path, query) => {
      const page = Number(query?.page)
      return { items: all.slice((page - 1) * 100, page * 100), total: all.length }
    })
    const out = await fetchAllPaged<Row>("/api/x", { view: "all" })
    expect(out.items).toHaveLength(230)
    expect(out.total).toBe(230)
    expect(get).toHaveBeenCalledTimes(3)
  })

  it("超过上限只取前 max 条，total 保持真实总数", async () => {
    vi.spyOn(api, "get").mockImplementation(async () => ({
      items: Array.from({ length: 100 }, (_, i) => ({ id: String(i) })),
      total: 5000,
    }))
    const out = await fetchAllPaged<Row>("/api/x", {}, 250)
    expect(out.items).toHaveLength(250)
    expect(out.total).toBe(5000)
  })
})
