import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Pencil, Plus, Trash2 } from "lucide-react";

import { deleteWorkflow, listWorkflows } from "@/api/workflows";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { Pagination } from "@/components/shared/Pagination";
import { QueryGrid } from "@/components/shared/QueryGrid";
import { SearchInput } from "@/components/shared/SearchInput";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Workflow } from "@/types/workflows";

import { WorkflowFormDialog } from "./WorkflowFormDialog";

const PAGE_SIZE = 12;

function isUrl(s: string): boolean {
  return /^(https?:\/\/|\/)/.test(s);
}

/** 工作流列表：分页卡片网格 + 搜索 + 新建/编辑/删除，卡片进编辑器。 */
export function WorkflowListPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Workflow | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Workflow | null>(null);

  const query = useQuery({
    queryKey: ["workflows", page, search],
    queryFn: () =>
      listWorkflows({ current_page: page, page_size: PAGE_SIZE, search_word: search || undefined }),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["workflows"] });
  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteWorkflow(id),
    onSuccess: () => {
      invalidate();
      setPendingDelete(null);
    },
  });

  const onSearch = (v: string) => {
    setSearch(v);
    setPage(1);
  };

  const list = query.data?.list ?? [];

  return (
    <div className="h-full space-y-4 overflow-auto p-6">
      <div className="flex items-center justify-between gap-3">
        <SearchInput value={search} onChange={onSearch} placeholder="搜索工作流" />
        <Button
          onClick={() => {
            setEditing(null);
            setFormOpen(true);
          }}
        >
          <Plus className="h-4 w-4" /> 新建工作流
        </Button>
      </div>

      <QueryGrid
        isLoading={query.isLoading}
        items={list}
        emptyText="还没有工作流，点「新建工作流」开始。"
      >
        {(wf) => (
          <div key={wf.id} className="flex flex-col gap-3 rounded-lg border p-4">
            <Link to={`/workflow/${wf.id}`} className="flex items-start gap-3">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md border bg-muted/40 text-lg">
                {wf.icon && isUrl(wf.icon) ? (
                  <img src={wf.icon} alt="" className="h-5 w-5 object-contain" />
                ) : (
                  <span>{wf.icon || "🔧"}</span>
                )}
              </span>
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 truncate font-medium">
                  <span className="truncate">{wf.name}</span>
                  <WorkflowBadge wf={wf} />
                </p>
                <p className="truncate font-mono text-xs text-muted-foreground">{wf.tool_call_name}</p>
                <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                  {wf.description || "暂无描述"}
                </p>
              </div>
            </Link>
            <div className="mt-auto flex items-center gap-2 text-xs text-muted-foreground">
              <span>{wf.node_count} 个节点</span>
              <Button asChild variant="outline" size="sm" className="ml-auto">
                <Link to={`/workflow/${wf.id}`}>编辑流程</Link>
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => {
                  setEditing(wf);
                  setFormOpen(true);
                }}
                aria-label={`编辑 ${wf.name} 信息`}
              >
                <Pencil className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="text-muted-foreground"
                onClick={() => setPendingDelete(wf)}
                aria-label={`删除 ${wf.name}`}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </QueryGrid>

      {query.data && <Pagination paginator={query.data.paginator} onChange={setPage} />}

      <WorkflowFormDialog open={formOpen} onClose={() => setFormOpen(false)} workflow={editing} />

      <ConfirmDialog
        open={pendingDelete !== null}
        title="删除工作流"
        description={pendingDelete ? `确定删除「${pendingDelete.name}」？此操作不可恢复。` : ""}
        confirmText="删除"
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => pendingDelete && deleteMutation.mutate(pendingDelete.id)}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}

function WorkflowBadge({ wf }: { wf: Workflow }) {
  const published = wf.status === "published";
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-medium",
        published ? "bg-green-100 text-green-700" : "bg-muted text-muted-foreground",
      )}
    >
      {published ? "已发布" : "草稿"}
    </span>
  );
}
