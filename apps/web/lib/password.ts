/** 密码强度（与 core 的 passwords.weakness 一致）：至少 8 位，同时包含字母和数字 */
export const PASSWORD_MIN = 8

export function passwordWeakness(pw: string): string | null {
  if (pw.length < PASSWORD_MIN) return `密码至少 ${PASSWORD_MIN} 位`
  if (!/[A-Za-z]/.test(pw) || !/\d/.test(pw)) return "密码要同时包含字母和数字"
  return null
}

/** 登录名规则（与 core 的 USERNAME_PATTERN 一致）：字母开头，3～30 位字母、数字或 _ . - */
export const USERNAME_RE = /^[a-zA-Z][a-zA-Z0-9_.-]{2,29}$/

/** 改密码表单校验：返回字段错误 */
export function checkPasswordChange(v: { old: string; next: string; confirm: string }): {
  old?: string
  next?: string
  confirm?: string
} {
  const errors: { old?: string; next?: string; confirm?: string } = {}
  if (!v.old) errors.old = "请输入当前密码"
  const weak = passwordWeakness(v.next)
  if (weak) errors.next = weak
  else if (v.next === v.old) errors.next = "新密码不能和当前密码相同"
  if (!errors.next && v.confirm !== v.next) errors.confirm = "两次输入的新密码不一致"
  return errors
}
