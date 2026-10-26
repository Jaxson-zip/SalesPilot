/** 模板相关的纯函数（跟进模板、输单原因、下一步） */

/**
 * 插入跟进模板：内容为空时直接替换；已经写了内容时追加在后面，不覆盖用户写的字。
 */
export function insertTemplate(content: string, template: string): string {
  const current = content.trimEnd()
  if (!current) return template
  if (current.includes(template)) return content
  return `${current}\n${template}`
}

/**
 * 模板还没填：每一行都只有「标题：」没有内容（例如「沟通对象：\n下一步：」）。
 * 这种内容保存下来没有意义，保存按钮不可用并提示先填写。
 */
export function isUnfilledTemplate(content: string): boolean {
  const lines = content
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
  return lines.length > 0 && lines.every((l) => /[：:]$/.test(l))
}

/** 输单原因：点选常用原因后填入，已经写了补充说明时放在前面（「选择了竞品；对方报价低 20%」） */
export function pickReason(current: string, reason: string): string {
  const rest = current.trim()
  if (!rest) return reason
  if (rest.startsWith(reason)) return current
  return `${reason}；${rest}`
}
