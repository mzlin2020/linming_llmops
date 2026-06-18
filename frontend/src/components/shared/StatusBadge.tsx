import { Loader2 } from "lucide-react";

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

// 非终态（解析/切分/灌库进行中）：徽标内带转圈，给用户明确的「处理中」反馈。
const ACTIVE = new Set<Status>(["waiting", "parsing", "splitting", "indexing"]);

/** 文档/片段处理状态徽标。 */
export function StatusBadge({ status, className }: { status: Status; className?: string }) {
  const meta = META[status] ?? { label: status, className: "bg-muted text-muted-foreground" };
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        meta.className,
        className,
      )}
    >
      {ACTIVE.has(status) && <Loader2 className="h-3 w-3 animate-spin" />}
      {meta.label}
    </span>
  );
}
