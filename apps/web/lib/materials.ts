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
