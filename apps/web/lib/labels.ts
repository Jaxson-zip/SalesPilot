/**
 * 各状态 / 类型的中文标签与 Tag 颜色（文字照抄 docs/api/业务模块接口契约.md §0）。
 * 页面里不要再手写状态文字，统一从这里取。
 */
import type { TagColor } from "@/components/biz/Tag"
import type {
  ApprovalStatus,
  ApprovalTargetType,
  AttachmentKind,
  ContactRole,
  ContractStatus,
  ExpenseStatus,
  ExpenseType,
  FollowupItem,
  OpportunityStage,
  PlanStatus,
  QuoteStatus,
} from "@/types/api"

export interface LabelMeta {
  label: string
  color: TagColor
}

type LabelMap<K extends string> = Record<K, LabelMeta>

export const STAGE_META: LabelMap<OpportunityStage> = {
  lead: { label: "线索", color: "gray" },
  qualified: { label: "需求确认", color: "blue" },
  proposal: { label: "方案报价", color: "purple" },
  negotiation: { label: "商务谈判", color: "orange" },
  won: { label: "赢单", color: "green" },
  lost: { label: "输单", color: "red" },
}

/** 推进顺序（不含输单） */
export const STAGE_ORDER: OpportunityStage[] = ["lead", "qualified", "proposal", "negotiation", "won"]

export const QUOTE_STATUS_META: LabelMap<QuoteStatus> = {
  draft: { label: "草稿", color: "gray" },
  pending_approval: { label: "待主管审批", color: "yellow" },
  approved: { label: "已审批", color: "sky" },
  sent: { label: "已发送客户", color: "blue" },
  accepted: { label: "已成交", color: "green" },
  rejected: { label: "已驳回", color: "red" },
}

export const CONTRACT_STATUS_META: LabelMap<ContractStatus> = {
  active: { label: "回款中", color: "blue" },
  paid: { label: "已回款", color: "green" },
}

export const EXPENSE_TYPE_META: LabelMap<ExpenseType> = {
  entertainment: { label: "客户招待", color: "orange" },
  transport: { label: "差旅交通", color: "sky" },
  hotel: { label: "差旅住宿", color: "sky" },
  other: { label: "其他", color: "gray" },
}

export const EXPENSE_STATUS_META: LabelMap<ExpenseStatus> = {
  draft: { label: "草稿", color: "gray" },
  pending_approval: { label: "待主管审批", color: "yellow" },
  approved: { label: "已通过", color: "green" },
  rejected: { label: "已驳回", color: "red" },
  paid: { label: "已打款", color: "blue" },
}

export const APPROVAL_STATUS_META: LabelMap<ApprovalStatus> = {
  pending: { label: "待处理", color: "yellow" },
  approved: { label: "已通过", color: "green" },
  rejected: { label: "已驳回", color: "red" },
}

export const APPROVAL_TARGET_LABEL: Record<ApprovalTargetType, string> = {
  quote: "报价单",
  expense: "报销",
}

export const ATTACHMENT_KIND_META: LabelMap<AttachmentKind> = {
  invoice: { label: "发票", color: "blue" },
  receipt: { label: "小票", color: "gray" },
  other: { label: "其他", color: "gray" },
}

export const FOLLOWUP_TYPE_LABEL: Record<FollowupItem["type"], string> = {
  phone: "电话",
  visit: "拜访",
  wechat: "微信",
  email: "邮件",
  ai: "AI 记录",
}

/**
 * 动态动作的中文。core 发的是「对象类型 + 动作代码」（例如 subject_type=quote、action=submit），
 * 先按 `对象.动作` 精确匹配，再按动作通用文案兜底；都没有时原样显示。
 * 动作代码清单见 docs/api/业务模块接口契约.md §0。
 */
const ACTIVITY_LABEL_BY_SUBJECT: Record<string, string> = {
  "opportunity.create": "创建了商机",
  "opportunity.update": "修改了商机",
  "opportunity.stage_changed": "更新了商机阶段",
  "opportunity.task_done": "完成了任务",
  "quote.create": "生成了报价单",
  "quote.update": "调整了报价",
  "quote.submit": "提交了报价单",
  "quote.send": "发送了报价单",
  "quote.accept": "客户接受了报价",
  "quote.reject": "客户拒绝了报价",
  "quote.approval_approve": "主管通过了报价审批",
  "quote.approval_reject": "主管驳回了报价",
  "contract.create": "生成了合同",
  "contract.payment": "登记了回款",
  "expense.create": "新建了报销单",
  "expense.submit": "提交了报销",
  "expense.attachment_added": "上传了票据",
  "expense.attachment_removed": "删除了票据",
  "expense.approval_approve": "主管通过了报销",
  "expense.approval_reject": "主管驳回了报销",
  "customer.create": "创建了客户",
  "customer.task_done": "完成了任务",
  "customer.transfer": "转移了负责人",
}

const ACTIVITY_LABEL_BY_ACTION: Record<string, string> = {
  stage_changed: "更新了商机阶段",
  create: "创建了记录",
  update: "修改了记录",
  submit: "提交了审批",
  approval_approve: "通过了审批",
  approval_reject: "驳回了审批",
  payment: "登记了回款",
  task_done: "完成了任务",
  transfer: "转移了负责人",
  payment_plan: "调整了回款计划",
  contact_added: "添加了联系人",
  contact_updated: "更新了联系人",
  contact_removed: "删除了联系人",
  "followup.phone": "记录了电话跟进",
  "followup.visit": "记录了上门拜访",
  "followup.wechat": "记录了微信沟通",
  "followup.email": "记录了邮件沟通",
  "followup.ai": "根据聊天摘要自动记录",
}

export function activityActionLabel(action: string, subjectType?: string): string {
  return (
    (subjectType ? ACTIVITY_LABEL_BY_SUBJECT[`${subjectType}.${action}`] : undefined) ??
    ACTIVITY_LABEL_BY_ACTION[action] ??
    action
  )
}

export function labelOf<K extends string>(map: LabelMap<K>, key: K | string): LabelMeta {
  return (map as Record<string, LabelMeta | undefined>)[key] ?? { label: key, color: "gray" }
}

/** 联系人角色（B7）：顺序即列表排序和下拉顺序 */
export const CONTACT_ROLE_META: LabelMap<ContactRole> = {
  decision_maker: { label: "决策人", color: "red" },
  influencer: { label: "影响者", color: "orange" },
  technical: { label: "技术把关", color: "blue" },
  finance: { label: "采购 / 财务", color: "purple" },
  user: { label: "使用者", color: "gray" },
}

/** 商机侧栏「关键人」显示的角色 */
export const KEY_CONTACT_ROLES: ContactRole[] = ["decision_maker", "influencer", "technical"]

/** 回款计划每期状态（B9） */
export const PLAN_STATUS_META: LabelMap<PlanStatus> = {
  paid: { label: "已收齐", color: "green" },
  partial: { label: "部分到账", color: "blue" },
  overdue: { label: "逾期", color: "red" },
  pending: { label: "待收", color: "gray" },
}
