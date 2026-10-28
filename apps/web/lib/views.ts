/** 数据范围视图（契约：mine 本人 · team 本团队 · all 全部），按角色给出可选项 */
import type { DataView, Role } from "@/types/api"

export interface ScopeOption {
  value: DataView
  label: string
}

/** 每个角色可选的数据范围；第一个是默认值 */
export function scopeOptions(role: Role, noun: string): ScopeOption[] {
  if (role === "admin")
    return [
      { value: "all", label: `全部${noun}` },
      { value: "mine", label: `我负责的` },
    ]
  if (role === "manager")
    return [
      { value: "team", label: `团队${noun}` },
      { value: "mine", label: `我负责的` },
    ]
  return [{ value: "mine", label: `我的${noun}` }]
}

/** 角色的默认数据范围（工作台、审批等不提供切换的页面） */
/** 「全部状态」视图的名称随数据范围：销售「我的报价单」、主管「团队报价单」、管理员「全部报价单」 */
export function scopeLabel(role: Role, noun: string): string {
  return `${role === "admin" ? "全部" : role === "manager" ? "团队" : "我的"}${noun}`
}

export function defaultScope(role: Role): DataView {
  return scopeOptions(role, "")[0].value
}

/** 切换角色后原选择可能不可用，回落到默认值 */
export function resolveScope(role: Role, selected: string): DataView {
  const opts = scopeOptions(role, "")
  return opts.find((o) => o.value === selected)?.value ?? opts[0].value
}
