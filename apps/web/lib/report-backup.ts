/** 暂存的内容和暂存时服务器上的版本（base）；服务器上的已经变了（别的设备保存过）就不恢复 */
export function restorable(raw: string | null, saved: string): string | null {
  if (raw === null) return null
  let text: string
  let base: string | undefined
  try {
    const v: unknown = JSON.parse(raw)
    if (typeof v !== "object" || v === null || typeof (v as { text?: unknown }).text !== "string") return null
    text = (v as { text: string }).text
    const b = (v as { base?: unknown }).base
    base = typeof b === "string" ? b : undefined
  } catch {
    return null
  }
  return text !== saved && base === saved ? text : null
}
