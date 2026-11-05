/**
 * 读屏名称：字段名 + 控件上显示的文字。
 * 名称要包含看得见的文字（WCAG 2.5.3），读屏用户和语音控制用户说「2026-11-05」也能找到这个控件；
 * 字段名放前面，读屏先听到「发生日期」再听到当前值。
 */
export function comboLabel(field: string, shown: string): string {
  const text = shown.trim()
  return text ? `${field}：${text}` : field
}
