import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

import { listDatasets } from "@/api/datasets";
import { cn } from "@/lib/utils";
import { MAX_DATASETS } from "@/types/datasets";

interface Props {
  value: number[];
  onChange: (next: number[]) => void;
}

/**
 * 知识库选择器（本阶段产出，供 5e 编排页复用）：从「我的知识库」勾选，
 * 发出对齐后端 AppConfig.datasets 的 number[] id 列表。受控、合计 ≤5。
 */
export function DatasetSelector({ value, onChange }: Props) {
  // 选择器场景一次性拉较大页（真正分页留 5e 后续按需加）。
  const query = useQuery({
    queryKey: ["datasets", "selector"],
    queryFn: () => listDatasets({ current_page: 1, page_size: 50 }),
  });

  const selected = useMemo(() => new Set(value), [value]);
  const atLimit = value.length >= MAX_DATASETS;

  const toggle = (id: number) => {
    if (selected.has(id)) {
      onChange(value.filter((x) => x !== id));
    } else if (!atLimit) {
      onChange([...value, id]);
    }
  };

  const list = query.data?.list ?? [];

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        已选 {value.length} / {MAX_DATASETS}
      </p>
      {query.isLoading ? (
        <p className="text-sm text-muted-foreground">加载中…</p>
      ) : list.length === 0 ? (
        <div className="rounded-md border border-dashed px-3 py-4 text-sm text-muted-foreground">
          <p>还没有知识库。</p>
          <Link
            to="/datasets"
            className="mt-1.5 inline-flex items-center gap-1 font-medium text-primary hover:underline"
          >
            去创建知识库 <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      ) : (
        <div className="space-y-1">
          {list.map((ds) => {
            const checked = selected.has(ds.id);
            return (
              <label
                key={ds.id}
                className={cn(
                  "flex cursor-pointer items-start gap-2 rounded-md border p-2 text-sm transition-colors hover:bg-muted/50",
                  checked && "border-primary/50 bg-primary/5",
                  !checked && atLimit && "cursor-not-allowed opacity-50 hover:bg-transparent",
                )}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={!checked && atLimit}
                  onChange={() => toggle(ds.id)}
                  className="mt-0.5"
                />
                <span className="min-w-0">
                  <span className="block font-medium">{ds.name}</span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {ds.description || `${ds.document_count} 个文档`}
                  </span>
                </span>
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}
