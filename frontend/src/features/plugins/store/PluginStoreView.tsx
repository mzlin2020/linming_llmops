import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, PackagePlus } from "lucide-react";

import { addStorePlugin, listStorePlugins } from "@/api/plugins";
import { Pagination } from "@/components/shared/Pagination";
import { QueryGrid } from "@/components/shared/QueryGrid";
import { SearchInput } from "@/components/shared/SearchInput";
import { ToolIcon } from "@/components/shared/ToolIcon";
import { Button } from "@/components/ui/button";

const PAGE_SIZE = 12;

/** 插件商店：搜索 + 卡片网格 + 一键添加（已添加则禁用）。 */
export function PluginStoreView() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");

  const query = useQuery({
    queryKey: ["plugin-store", { page, search }],
    queryFn: () =>
      listStorePlugins({ current_page: page, page_size: PAGE_SIZE, search_word: search || undefined }),
  });

  const addMutation = useMutation({
    mutationFn: (id: number) => addStorePlugin(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plugin-store"] });
      queryClient.invalidateQueries({ queryKey: ["api-tools"] });
    },
  });

  const onSearch = (v: string) => {
    setSearch(v);
    setPage(1);
  };

  const list = query.data?.list ?? [];

  return (
    <div className="space-y-4">
      <SearchInput value={search} onChange={onSearch} placeholder="搜索插件商店" />

      <QueryGrid isLoading={query.isLoading} items={list} emptyText="商店暂无插件。">
        {(p) => (
          <div key={p.id} className="flex flex-col gap-3 rounded-lg border p-4">
            <div className="flex items-start gap-3">
              <ToolIcon src={p.icon} alt={p.name} />
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{p.name}</p>
                <p className="line-clamp-2 text-xs text-muted-foreground">{p.description}</p>
              </div>
            </div>
            <p className="text-xs text-muted-foreground">{p.tools.length} 个工具</p>
            <div className="mt-auto">
              {p.added ? (
                <Button variant="outline" size="sm" disabled>
                  <Check className="h-4 w-4" /> 已添加
                </Button>
              ) : (
                <Button
                  size="sm"
                  onClick={() => addMutation.mutate(p.id)}
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
