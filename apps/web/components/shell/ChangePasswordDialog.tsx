"use client"

import { useState, type FormEvent } from "react"
import { toast } from "sonner"

import { FormField } from "@/components/biz/FormControls"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { errorMessage } from "@/lib/errors"
import { checkPasswordChange } from "@/lib/password"

/**
 * 修改密码。forced：管理员新建 / 重置密码后首次登录，必须改完才能继续用（不能关闭，只能改密码或退出）。
 */
export function ChangePasswordDialog({
  open,
  onOpenChange,
  forced = false,
}: {
  open: boolean
  onOpenChange?: (o: boolean) => void
  forced?: boolean
}) {
  const { changePassword, signOut } = useSession()
  const [v, setV] = useState({ old: "", next: "", confirm: "" })
  const [errors, setErrors] = useState<{ old?: string; next?: string; confirm?: string }>({})
  const [pending, setPending] = useState(false)

  const set = (k: keyof typeof v) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setV({ ...v, [k]: e.target.value })
    setErrors({ ...errors, [k]: undefined })
  }
  const close = () => {
    setV({ old: "", next: "", confirm: "" })
    setErrors({})
    onOpenChange?.(false)
  }
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const found = checkPasswordChange(v)
    if (Object.keys(found).length) return setErrors(found)
    setPending(true)
    try {
      await changePassword(v.old, v.next)
      toast.success("密码已修改", { description: "其他设备上的登录已失效" })
      close()
    } catch (err) {
      setErrors({ old: errorMessage(err) })
    } finally {
      setPending(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && !forced && close()}>
      <DialogContent
        showCloseButton={!forced}
        onEscapeKeyDown={(e) => forced && e.preventDefault()}
        onPointerDownOutside={(e) => forced && e.preventDefault()}
      >
        <form onSubmit={submit} className="space-y-4" aria-label="修改密码">
          <DialogHeader>
            <DialogTitle>{forced ? "首次登录，请先修改密码" : "修改密码"}</DialogTitle>
            <DialogDescription>
              {forced ? "当前是管理员设置的临时密码，改成只有你知道的密码后再继续使用。" : ""}
              新密码至少 8 位，同时包含字母和数字。
            </DialogDescription>
          </DialogHeader>
          <FormField label={forced ? "临时密码" : "当前密码"} required error={errors.old} htmlFor="pw-old">
            <Input
              id="pw-old"
              type="password"
              autoComplete="current-password"
              value={v.old}
              onChange={set("old")}
              aria-invalid={Boolean(errors.old)}
            />
          </FormField>
          <FormField label="新密码" required error={errors.next} htmlFor="pw-new">
            <Input
              id="pw-new"
              type="password"
              autoComplete="new-password"
              value={v.next}
              onChange={set("next")}
              aria-invalid={Boolean(errors.next)}
            />
          </FormField>
          <FormField label="再输一次新密码" required error={errors.confirm} htmlFor="pw-confirm">
            <Input
              id="pw-confirm"
              type="password"
              autoComplete="new-password"
              value={v.confirm}
              onChange={set("confirm")}
              aria-invalid={Boolean(errors.confirm)}
            />
          </FormField>
          <DialogFooter>
            {forced ? (
              <Button type="button" variant="outline" onClick={signOut}>
                退出登录
              </Button>
            ) : (
              <Button type="button" variant="outline" onClick={close}>
                取消
              </Button>
            )}
            <Button type="submit" disabled={pending}>
              {pending ? "保存中…" : "保存新密码"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
