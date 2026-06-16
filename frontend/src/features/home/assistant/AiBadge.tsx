import { cn } from "@/lib/utils";

/** 去品牌的「AI」徽标：助手身份的统一视觉，头部 / 气泡头像 / 空状态共用一处。 */
export function AiBadge({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex select-none items-center justify-center border border-primary/30 bg-primary/5 font-mono text-primary",
        className,
      )}
    >
      AI
    </span>
  );
}
