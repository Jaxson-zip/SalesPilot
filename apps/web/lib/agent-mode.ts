/** AI 工作台的两种模式：做方案（出方案、操作 CRM）/ 学习问答（新人了解公司业务，只读） */
export type AgentMode = "work" | "learn"

export const MODE_LABEL: Record<AgentMode, string> = {
  work: "做方案",
  learn: "学习问答",
}

/** 学习问答回答末尾的「可以接着问：」段落（learn.md 约定的格式） */
const FOLLOW_UP_MARK = /\n+\**可以接着问[：:]\**\s*\n/

const MAX_FOLLOW_UPS = 3

/** 把回答拆成正文和追问建议（每行「- 」开头）；没有这一段时原样返回 */
export function splitFollowUps(text: string): { body: string; questions: string[] } {
  const m = FOLLOW_UP_MARK.exec(text)
  if (!m) return { body: text, questions: [] }
  const questions = text
    .slice(m.index + m[0].length)
    .split("\n")
    .map((line) => /^\s*(?:[-*•]|\d+[.、])\s*(.+?)\s*$/.exec(line)?.[1] ?? "")
    .filter(Boolean)
    .slice(0, MAX_FOLLOW_UPS)
  return { body: text.slice(0, m.index).trimEnd(), questions }
}
