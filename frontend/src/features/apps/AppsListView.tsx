import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Copy, MessageSquare, Plus, Settings2, Trash2 } from "lucide-react";

import { copyApp, deleteApp, listApps } from "@/api/apps";
import { AppIcon } from "@/components/shared/AppIcon";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { QueryGrid } from "@/components/shared/QueryGrid";
import { SearchInput } from "@/components/shared/SearchInput";
import { Button } from "@/components/ui/button";
import type { AppListItem } from "@/types/apps";

import { AppFormModal } from "./AppFormModal";
import { AppStatusBadge } from "./AppStatusBadge";

/** 我的应用：卡片网格 + 新建/复制/删除，卡片进编排页。列表为「我的全部应用」非分页，搜索在前端过滤。 */
export function AppsListView() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<AppListItem | null>(null);

  const query = useQuery({ queryKey: ["apps"], queryFn: listApps });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["apps"] });

  const copyMutation = useMutation({ mutationFn: (id: number) => copyApp(id), onSuccess: invalidate });
  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteApp(id),
    onSuccess: () => {
      invalidate();
      // 删除会连带下架其商店条目（后端 app_service.delete），失效商店缓存避免残留幽灵卡片。
      queryClient.invalidateQueries({ queryKey: ["app-store"] });
      setPendingDelete(null);
    },
  });

  const list = useMemo(() => {
    const all = query.data ?? [];
    const kw = search.trim().toLowerCase();
    return kw ? all.filter((a) => a.name.toLowerCase().includes(kw)) : all;
  }, [query.data, search]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <SearchInput value={search} onChange={setSearch} placeholder="搜索应用" />
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" /> 新建应用
        </Button>
      </div>

      <QueryGrid isLoading={query.isLoading} items={list} emptyText="还没有应用，点「新建应用」开始。">
        {(app) => (
          <div key={app.id} className="flex flex-col gap-3 rounded-lg border p-4">
            <Link to={`/apps/${app.id}`} className="flex items-start gap-3">
              <AppIcon icon={app.icon} name={app.name} />
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 truncate font-medium">
                  <span className="truncate">{app.name}</span>
                  <AppStatusBadge status={app.status} />
                </p>
                <p className="line-clamp-2 text-xs text-muted-foreground">
                  {app.description || "暂无描述"}
                </p>
              </div>
            </Link>
            <div className="mt-auto flex items-center gap-2">
              <Button asChild variant="outline" size="sm">
                <Link to={`/apps/${app.id}`}>
                  <Settings2 className="h-4 w-4" /> 编排
                </Link>
              </Button>
              {app.status === "published" && (
                <Button asChild variant="outline" size="sm">
                  <Link to={`/apps/${app.id}/chat`} aria-label={`与 ${app.name} 对话`}>
                    <MessageSquare className="h-4 w-4" /> 对话
                  </Link>
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => copyMutation.mutate(app.id)}
                disabled={copyMutation.isPending}
                aria-label={`复制 ${app.name}`}
              >
                <Copy className="h-4 w-4" /> 复制
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="ml-auto text-muted-foreground"
                onClick={() => setPendingDelete(app)}
                aria-label={`删除 ${app.name}`}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </QueryGrid>

      <AppFormModal open={formOpen} onClose={() => setFormOpen(false)} />

      <ConfirmDialog
        open={pendingDelete !== null}
        title="删除应用"
        description={
          pendingDelete ? `确定删除「${pendingDelete.name}」？此操作不可恢复。` : ""
        }
        confirmText="删除"
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => pendingDelete && deleteMutation.mutate(pendingDelete.id)}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
