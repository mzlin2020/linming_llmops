import { useEffect, type ReactNode } from "react";

import { cn } from "@/lib/utils";

interface Props {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  /** 底部操作区（如确认/取消）。表单弹窗通常把按钮放进 children 内的 <form>，不用此项。 */
  footer?: ReactNode;
  className?: string;
}

/** 通用模态外壳（手写，不引 radix dialog）：遮罩 + 居中卡片 + Esc / 点遮罩关闭。
 *  ConfirmDialog 与各表单弹窗共用同一份遮罩/键盘/点穿逻辑。 */
export function Modal({ open, title, onClose, children, footer, className }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn(
          "max-h-[90vh] w-full max-w-sm overflow-auto rounded-lg border bg-card p-5 shadow-lg",
          className,
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-base font-semibold">{title}</h3>
        <div className="mt-3">{children}</div>
        {footer && <div className="mt-5 flex justify-end gap-2">{footer}</div>}
      </div>
    </div>
  );
}
