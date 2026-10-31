import type { ChatTurn } from "@/lib/agent-reducer"

export interface FeedbackSlot {
  /** 这条回复属于会话里的第几轮（服务端第几条用户消息，从 0 开始）：刷新、重新打开历史后不变 */
  index: number
  question: string
}

/**
 * 每条 AI 回复的反馈序号。按「第几条用户消息」编号，不按「第几条 AI 回复」：
 * 出错的那一轮在历史里没有 AI 回复；「重新生成」在界面上只多一条 AI 回复，服务端却多记一条用户消息。
 * 所以紧跟在另一条 AI 回复后面的（重新生成）也算新的一轮，两边的序号才对得上。
 */
export function feedbackSlots(turns: ChatTurn[]): Map<string, FeedbackSlot> {
  const out = new Map<string, FeedbackSlot>()
  let round = -1
  let question = ""
  let prev: ChatTurn["role"] | null = null
  for (const t of turns) {
    if (t.role === "user") {
      round++
      question = t.text
    } else {
      if (prev === "assistant") round++
      if (round >= 0) out.set(t.id, { index: round, question })
    }
    prev = t.role
  }
  return out
}
