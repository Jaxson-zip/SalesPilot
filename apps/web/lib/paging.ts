import { api, type Query } from "@/lib/api"
import type { Paged } from "@/types/api"

/** 列表页每页条数 */
export const PAGE_SIZE = 50

/** 接口单页上限 */
const MAX_PAGE = 100

/**
 * 按当前条件逐页取全（看板用）。max 是保护上限：超过时只取前 max 条，total 仍是真实总数。
 */
export async function fetchAllPaged<T>(
  path: string,
  query: Query,
  max = 1000,
  signal?: AbortSignal,
): Promise<Paged<T>> {
  const items: T[] = []
  let total = 0
  for (let page = 1; ; page++) {
    const data = await api.get<Paged<T>>(path, { ...query, page, page_size: MAX_PAGE }, signal)
    items.push(...data.items)
    total = data.total
    if (data.items.length < MAX_PAGE || items.length >= total || items.length >= max) {
      return { items: items.slice(0, max), total }
    }
  }
}

/** 导出用：当前条件下的全部行 */
export async function fetchAllPages<T>(path: string, query: Query, max = 1000): Promise<T[]> {
  return (await fetchAllPaged<T>(path, query, max)).items
}
