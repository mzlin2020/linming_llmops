import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

import { listWorkflows } from "@/api/workflows";
import { cn } from "@/lib/utils";

// 与后端 app_config_service._validate_workflows 一致：每应用最多绑定 5 个已发布工作流。
const MAX_WORKFLOWS_PER_APP = 5;

interface Props {
  value: number[];
  onChange: (next: number[]) => void;
}

/**
 * 工作流选择器：从「我的已发布工作流」勾选，发出对齐后端 AppConfig.workflows 的 number[]。
 * 绑定后这些工作流在与该应用对话时作为工具被 LLM 调用。
 */
export function WorkflowSelector({ value, onChange }: Props) {
  const query = useQuery({
    queryKey: ["workflows", "selector", "published"],
    queryFn: () => listWorkflows({ current_page: 1, page_size: 50, status: "published" }),
  });

  const selected = useMemo(() => new Set(value), [value]);
  const atLimit = value.length >= MAX_WORKFLOWS_PER_APP;

  const toggle = (id: number) => {
    if (selected.has(id)) onChange(value.filter((x) => x !== id));
    else if (!atLimit) onChange([...value, id]);
  };

  const list = query.data?.list ?? [];

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        已选 {value.length} / {MAX_WORKFLOWS_PER_APP}（仅列出已发布的工作流）
      </p>
      {query.isLoading ? (
        <p className="text-sm text-muted-foreground">加载中…</p>
      ) : list.length === 0 ? (
        <div className="rounded-md border border-dashed px-3 py-4 text-sm text-muted-foreground">
          <p>还没有已发布的工作流。</p>
          <Link
            to="/workflow"
            className="mt-1.5 inline-flex items-center gap-1 font-medium text-primary hover:underline"
          >
            去创建工作流 <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      ) : (
        <div className="space-y-1">
          {list.map((wf) => {
            const checked = selected.has(wf.id);
            return (
              <label
                key={wf.id}
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
                  onChange={() => toggle(wf.id)}
                  className="mt-0.5"
                />
                <span className="min-w-0">
                  <span className="block font-medium">{wf.name}</span>
                  <span className="block truncate font-mono text-xs text-muted-foreground">
                    {wf.tool_call_name}
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
