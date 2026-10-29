/** v4：业务模板（GET /api/templates，core app/crm/services/template_service.py） */
import type { ExpenseType, TransportMode } from "@/types/biz"

export interface ExpenseTemplate {
  id: string
  label: string
  type: ExpenseType
  transport_mode: TransportMode | null
  /** 预填到「事由」的开头 */
  reason: string
  example: string
}

/** 「报销须知」：标准说明由后端按 rules.yaml 计算后填入 */
export interface ExpenseGuide {
  type: ExpenseType
  label: string
  standard: string
  must: string
  attachments: string[]
  rule_ref: string
}

export interface FollowupTemplate {
  id: string
  label: string
  type: "phone" | "visit" | "wechat"
  content: string
}

export interface TaskTemplate {
  type: "call" | "visit" | "email" | "meeting" | "todo"
  title: string
}

export interface PromptTemplate {
  title: string
  prompt: string
}

/** 规则说明（悬浮提示）：数字由后端按 rules.yaml 填入 */
export interface RuleNote {
  title: string
  items: { label: string; value: string }[]
  note: string
  source: string
}
export type RuleNoteKey = "commission" | "quote" | "expense"

export interface Templates {
  expense_templates: ExpenseTemplate[]
  expense_guides: ExpenseGuide[]
  followup: FollowupTemplate[]
  task: TaskTemplate[]
  lost_reasons: string[]
  quote_terms: string[]
  /** 合同要素确认单的说明 */
  contract_terms: string[]
  /** 当前角色的 AI 示例问题 */
  ai_prompts: PromptTemplate[]
  /** 学习问答模式的引导问题（所有角色一样） */
  learn_prompts: PromptTemplate[]
  rule_notes: Record<RuleNoteKey, RuleNote>
}
