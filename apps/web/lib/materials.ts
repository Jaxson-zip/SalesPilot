import { api } from "@/lib/api"

/** 一手材料（会议纪要、聊天记录、名片截图）：POST /api/agent/materials 解析成文字，不入库 */
export interface MaterialOut {
  name: string
  kind: "text" | "docx" | "pdf" | "image"
  text: string
  chars: number
  truncated: boolean
}

export interface MaterialIn {
  name: string
  text: string
}

export const MATERIAL_ACCEPT = ".txt,.md,.csv,.docx,.pdf,.png,.jpg,.jpeg,.webp"
export const MATERIAL_DEFAULT_ASK = "帮我整理这份材料：记成跟进，补充联系人，安排下一步"

export function extractMaterial(file: File): Promise<MaterialOut> {
  const form = new FormData()
  form.append("file", file)
  return api.upload<MaterialOut>("/api/agent/materials", form)
}

/** 与后端 MaterialIn.text 上限一致 */
export const MATERIAL_MAX_CHARS = 12_000
const PASTE_KEY = "sp.pastedMaterial"

/** 写跟进处粘贴的纪要 / 聊天记录：直接当作一份文字材料（不用上传解析） */
export function pastedMaterial(text: string, customer: string): MaterialOut {
  const clean = text.trim()
  return {
    name: `${customer} 沟通纪要.txt`,
    kind: "text",
    text: clean.slice(0, MATERIAL_MAX_CHARS),
    chars: clean.length,
    truncated: clean.length > MATERIAL_MAX_CHARS,
  }
}

export function digestPrompt(customer: string, opportunity?: string): string {
  const target = opportunity ? `「${customer}」的「${opportunity}」商机` : `「${customer}」`
  return `把这份沟通纪要整理成${target}的跟进记录：提炼跟进重点和客户关注点，补充新出现的联系人，安排下一步待办`
}

/** 纪要可能有上万字，放不进地址栏：先存到本标签页的 sessionStorage，AI 工作台取一次就删 */
export function stashPastedMaterial(m: MaterialOut): boolean {
  try {
    sessionStorage.setItem(PASTE_KEY, JSON.stringify(m))
    return true
  } catch {
    return false
  }
}

export function takePastedMaterial(): MaterialOut | null {
  try {
    const raw = sessionStorage.getItem(PASTE_KEY)
    sessionStorage.removeItem(PASTE_KEY)
    return raw ? (JSON.parse(raw) as MaterialOut) : null
  } catch {
    return null
  }
}
