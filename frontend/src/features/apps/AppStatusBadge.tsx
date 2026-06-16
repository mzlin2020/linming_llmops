import { cn } from "@/lib/utils";
import type { AppStatus } from "@/types/apps";

const MAP: Record<AppStatus, { label: string; cls: string }> = {
  draft: { label: "草稿", cls: "bg-muted text-muted-foreground" },
  published: { label: "已发布", cls: "bg-green-100 text-green-700" },
};

/** 应用发布状态徽标（草稿 / 已发布）。 */
export function AppStatusBadge({ status, className }: { status: AppStatus; className?: string }) {
  const { label, cls } = MAP[status] ?? MAP.draft;
  return (
    <span
      className={cn("inline-flex rounded px-1.5 py-0.5 text-xs font-medium", cls, className)}
    >
      {label}
    </span>
  );
}
