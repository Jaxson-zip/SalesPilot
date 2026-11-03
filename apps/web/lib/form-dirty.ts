/** 表单内容和打开时相比有没有改过（字段都是可 JSON 序列化的简单值）；首尾空白不算修改 */
export function changedFrom(current: unknown, initial: unknown): boolean {
  return normalize(current) !== normalize(initial)
}

function normalize(v: unknown): string {
  return JSON.stringify(v, (_k, x: unknown) => (typeof x === "string" ? x.trim() : x))
}
