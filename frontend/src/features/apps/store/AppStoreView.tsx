import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Check, PackagePlus } from "lucide-react";

import { addStoreApp, getAppStore } from "@/api/apps";
import { AppIcon } from "@/components/shared/AppIcon";
import { Pagination } from "@/components/shared/Pagination";
import { QueryGrid } from "@/components/shared/QueryGrid";
import { SearchInput } from "@/components/shared/SearchInput";
import { Button } from "@/components/ui/button";
import { getErrorMessage } from "@/lib/http/errors";

const PAGE_SIZE = 12;

/** 应用商店：搜索 + 卡片网格 + 一键添加到我的应用（已添加则禁用）。 */
export function AppStoreView() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");

  const query = useQuery({
    queryKey: ["app-store", { page, search }],
    queryFn: () =>
      getAppStore({ current_page: page, page_size: PAGE_SIZE, search_word: search || undefined }),
  });

  const addMutation = useMutation({
    mutationFn: (id: number) => addStoreApp(id),
    onSuccess: (app) => {
      queryClient.invalidateQueries({ queryKey: ["app-store"] });
      queryClient.invalidateQueries({ queryKey: ["apps"] });
      navigate(`/apps/${app.id}`);
    },
    // 该条已被发布者下架/删除时后端返回 404：刷新列表抹掉幽灵卡片，并提示而非留个点不动的死按钮。
    onError: () => queryClient.invalidateQueries({ queryKey: ["app-store"] }),
  });

  const onSearch = (v: string) => {
    setSearch(v);
    setPage(1);
  };

  const list = query.data?.list ?? [];

  return (
    <div className="space-y-4">
      <SearchInput value={search} onChange={onSearch} placeholder="搜索应用商店" />

      {addMutation.isError && (
        <p className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          {getErrorMessage(addMutation.error)}
        </p>
      )}

      <QueryGrid isLoading={query.isLoading} items={list} emptyText="商店暂无应用。">
        {(app) => (
          <div key={app.id} className="flex flex-col gap-3 rounded-lg border p-4">
            <div className="flex items-start gap-3">
              <AppIcon icon={app.icon} name={app.name} />
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{app.name}</p>
                <p className="line-clamp-2 text-xs text-muted-foreground">
                  {app.description || "暂无描述"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span>{app.model_name || app.model_provider || "未配置模型"}</span>
              <span>{app.tool_count} 个工具</span>
            </div>
            <div className="mt-auto">
              {app.added ? (
                <Button variant="outline" size="sm" disabled>
                  <Check className="h-4 w-4" /> 已添加
                </Button>
              ) : (
                <Button
                  size="sm"
                  onClick={() => addMutation.mutate(app.id)}
                  disabled={addMutation.isPending}
                >
                  <PackagePlus className="h-4 w-4" /> 添加
                </Button>
              )}
            </div>
          </div>
        )}
      </QueryGrid>

      {query.data && <Pagination paginator={query.data.paginator} onChange={setPage} />}
    </div>
  );
}
