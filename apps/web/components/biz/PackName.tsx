"use client"

import { usePackName } from "@/hooks/useProductLines"

/** 行业包 id → 名称（如 llm_deploy → 大模型部署），名称来自 core 的 /api/packs */
export function PackName({ id }: { id: string | null | undefined }) {
  const packName = usePackName()
  return <>{packName(id)}</>
}
