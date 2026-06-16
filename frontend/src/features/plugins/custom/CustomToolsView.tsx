import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Pencil, Plus, Trash2 } from "lucide-react";

import { deleteApiTool, listApiTools, publishApiTool } from "@/api/plugins";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { Pagination } from "@/components/shared/Pagination";
import { SearchInput } from "@/components/shared/SearchInput";
import { ToolIcon } from "@/components/shared/ToolIcon";
import { Button } from "@/components/ui/button";
import type { ApiToolProvider } from "@/types/plugins";

const PAGE_SIZE = 12;

/** 自定义 API 工具：搜索 + 卡片网格 + 编辑/删除/上下架。 */
export function CustomToolsView() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [pendingDelete, setPendingDelete] = useState<ApiToolProvider | null>(null);

  const query = useQuery({
    queryKey: ["api-tools", { page, search }],
    queryFn: () =>
      listApiTools({ current_page: page, page_size: PAGE_SIZE, search_word: search || undefined }),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["api-tools"] });

  const publishMutation = useMutation({
    mutationFn: ({ id, is_public }: { id: number; is_public: boolean }) =>
      publishApiTool(id, is_public),
    onSuccess: invalidate,
  });
  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteApiTool(id),
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
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <SearchInput value={search} onChange={onSearch} placeholder="搜索自定义插件" />
        <Button asChild>
          <Link to="/plugins/custom/new">
            <Plus className="h-4 w-4" /> 新建插件
          </Link>
        </Button>
      </div>

      {query.isLoading ? (
        <p className="text-sm text-muted-foreground">加载中…</p>
      ) : list.length === 0 ? (
        <p className="py-12 text-center text-sm text-muted-foreground">
          还没有自定义插件，点「新建插件」开始。
        </p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {list.map((p) => (
            <div key={p.id} className="flex flex-col gap-3 rounded-lg border p-4">
              <div className="flex items-start gap-3">
                <ToolIcon src={p.icon} alt={p.name} />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{p.name}</p>
                  <p className="line-clamp-2 text-xs text-muted-foreground">{p.description}</p>
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                {p.tools.length} 个工具{p.is_public && " · 已上架"}
              </p>
              <div className="mt-auto flex items-center gap-2">
                <Button asChild variant="outline" size="sm">
                  <Link to={`/plugins/custom/${p.id}`} aria-label={`编辑 ${p.name}`}>
                    <Pencil className="h-4 w-4" /> 编辑
                  </Link>
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => publishMutation.mutate({ id: p.id, is_public: !p.is_public })}
                  disabled={publishMutation.isPending}
                >
                  {p.is_public ? "下架" : "上架"}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="ml-auto text-muted-foreground"
                  onClick={() => setPendingDelete(p)}
                  aria-label={`删除 ${p.name}`}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {query.data && <Pagination paginator={query.data.paginator} onChange={setPage} />}

      <ConfirmDialog
        open={pendingDelete !== null}
        title="删除自定义插件"
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
