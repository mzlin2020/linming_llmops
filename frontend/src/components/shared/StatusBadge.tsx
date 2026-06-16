import { cn } from "@/lib/utils";
import type { DocumentStatus, SegmentStatus } from "@/types/datasets";

type Status = DocumentStatus | SegmentStatus;

const META: Record<Status, { label: string; className: string }> = {
  waiting: { label: "排队中", className: "bg-muted text-muted-foreground" },
  parsing: { label: "解析中", className: "bg-blue-100 text-blue-700" },
  splitting: { label: "切分中", className: "bg-blue-100 text-blue-700" },
  indexing: { label: "索引中", className: "bg-blue-100 text-blue-700" },
  completed: { label: "已完成", className: "bg-green-100 text-green-700" },
  error: { label: "失败", className: "bg-destructive/10 text-destructive" },
};

/** 文档/片段处理状态徽标。 */
export function StatusBadge({ status, className }: { status: Status; className?: string }) {
  const meta = META[status] ?? { label: status, className: "bg-muted text-muted-foreground" };
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-medium",
        meta.className,
        className,
      )}
    >
      {meta.label}
    </span>
  );
}
