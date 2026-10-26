/**
 * 操作权限（契约 §0「角色与操作权限」v2）。
 * 只决定按钮显示与否（无权的按钮直接不显示）；真正的权限由 core service 层校验，越权返回 40301。
 * 原则：看得到 ≠ 改得了 —— 业务数据只有负责人本人能改；主管只做审批和回款；管理员只做系统配置。
 */
import type { Role } from "@/types/api"

/** 负责人 id：记录的 owner.id（可能缺失） */
type OwnerId = string | null | undefined
/** 当前登录用户 id（/api/me 或 mock-login 返回；加载中为 null） */
type UserId = string | null | undefined

/** 管理员只读业务数据 */
export function isReadOnlyRole(role: Role): boolean {
  return role === "admin"
}

/** 是否本人负责的记录（任一 id 缺失时按「不是」处理，按钮宁可不显示） */
export function isOwner(ownerId: OwnerId, userId: UserId): boolean {
  return Boolean(ownerId) && Boolean(userId) && ownerId === userId
}

/** 新建客户、商机、报销（主管建的记在自己名下）；管理员不行 */
export function canCreateBusiness(role: Role): boolean {
  return role === "sales" || role === "manager"
}

/** 写跟进：同新建权限 */
export function canWriteFollowup(role: Role): boolean {
  return canCreateBusiness(role)
}

/**
 * 修改业务记录：修改商机 / 切换阶段 / 看板拖拽、报价单提交 / 发送 / 客户接受 / 客户拒绝、
 * 报销上传 / 删除票据、提交。销售和主管都只能改本人的；管理员不行。
 */
export function canEditRecord(role: Role, ownerId: OwnerId, userId: UserId): boolean {
  return canCreateBusiness(role) && isOwner(ownerId, userId)
}

/** 审批报价和报销：仅主管（本团队，由 core 过滤） */
export function canApprove(role: Role): boolean {
  return role === "manager"
}

/** 登记回款：仅主管（本团队），且合同还在回款中 */
export function canRegisterPayment(role: Role, record?: { status: string }): boolean {
  if (role !== "manager") return false
  return record ? record.status === "active" : true
}

/** 行业包配置、产品线映射（修改）：仅管理员 */
export function canConfigurePacks(role: Role): boolean {
  return role === "admin"
}

/** AI 助手：查询类工具所有角色可用 */
export function canUseAiQuery(role: Role): boolean {
  return role === "sales" || role === "manager" || role === "admin"
}

/** AI 助手：写操作工具（生成报价、推进商机、报销、记跟进）；管理员不行，主管仅本人记录（core 校验） */
export function canUseAiWrite(role: Role): boolean {
  return canCreateBusiness(role)
}

/** AI 助手：审批工具 */
export function canUseAiApprove(role: Role): boolean {
  return canApprove(role)
}
