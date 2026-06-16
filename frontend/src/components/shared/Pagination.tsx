import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Paginator } from "@/types/api";

interface Props {
  paginator: Paginator;
  onChange: (page: number) => void;
}

/** 通用分页控件：吃后端 Paginator，上一页/下一页 + 页码。所有分页列表页复用。 */
export function Pagination({ paginator, onChange }: Props) {
  const { current_page, total_page, total_record } = paginator;
  if (total_page <= 1) return null;

  return (
    <div className="flex items-center justify-between pt-2 text-sm text-muted-foreground">
      <span>共 {total_record} 条</span>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={current_page <= 1}
          onClick={() => onChange(current_page - 1)}
          aria-label="上一页"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <span className="tabular-nums">
          {current_page} / {total_page}
        </span>
        <Button
          variant="outline"
          size="sm"
          disabled={current_page >= total_page}
          onClick={() => onChange(current_page + 1)}
          aria-label="下一页"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
