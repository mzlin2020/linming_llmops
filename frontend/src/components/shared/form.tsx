import type { ReactNode } from "react";

import { Label } from "@/components/ui/label";
import { getErrorMessage } from "@/lib/http/errors";

/** 表单字段行:标签 + 控件 + 校验错误。 */
export function FormRow({
  label,
  htmlFor,
  error,
  children,
}: {
  label: string;
  htmlFor: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}

/** 服务端错误提示(统一 getErrorMessage 收口,免各处 `as ApiError`)。 */
export function FormError({ error }: { error: unknown }) {
  return (
    <p role="alert" className="text-sm text-destructive">
      {getErrorMessage(error)}
    </p>
  );
}
