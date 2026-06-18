import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { FileText, Pencil, Plus, Target, Trash2 } from "lucide-react";

import { deleteDataset, listDatasets } from "@/api/datasets";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { Pagination } from "@/components/shared/Pagination";
import { QueryGrid } from "@/components/shared/QueryGrid";
import { SearchInput } from "@/components/shared/SearchInput";
import { ToolIcon } from "@/components/shared/ToolIcon";
import { Button } from "@/components/ui/button";
import type { Dataset } from "@/types/datasets";
import { DatasetFormModal } from "./DatasetFormModal";

const PAGE_SIZE = 12;

/** 知识库列表：搜索 + 卡片网格 + 新建/编辑/删除。 */
export function DatasetsListView() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Dataset | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Dataset | null>(null);

  const query = useQuery({
    queryKey: ["datasets", { page, search }],
    queryFn: () =>
      listDatasets({ current_page: page, page_size: PAGE_SIZE, search_word: search || undefined }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteDataset(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
      setPendingDelete(null);
    },
  });

  const onSearch = (v: string) => {
    setSearch(v);
    setPage(1);
  };

  const openCreate = () => {
    setEditing(null);
    setFormOpen(true);
  };
  const openEdit = (ds: Dataset) => {
    setEditing(ds);
    setFormOpen(true);
  };

  const list = query.data?.list ?? [];

  return (
    <div className="h-full space-y-4 overflow-auto p-6">
      <div className="flex items-center justify-between gap-3">
        <SearchInput value={search} onChange={onSearch} placeholder="搜索知识库" />
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" /> 新建知识库
        </Button>
      </div>

      <QueryGrid
        isLoading={query.isLoading}
        items={list}
        emptyText="还没有知识库，点「新建知识库」开始。"
      >
        {(ds) => (
          <div key={ds.id} className="flex flex-col gap-3 rounded-lg border p-4">
            <Link to={`/datasets/${ds.id}`} className="flex items-start gap-3">
              <ToolIcon src={ds.icon} alt={ds.name} />
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{ds.name}</p>
                <p className="line-clamp-2 text-xs text-muted-foreground">
                  {ds.description || "暂无描述"}
                </p>
              </div>
            </Link>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <FileText className="h-3.5 w-3.5" />
                {ds.document_count}
              </span>
              <span>{ds.character_count} 字符</span>
              <span className="inline-flex items-center gap-1">
                <Target className="h-3.5 w-3.5" />
                {ds.hit_count}
              </span>
            </div>
            <div className="mt-auto flex items-center gap-2">
              <Button asChild variant="outline" size="sm">
                <Link to={`/datasets/${ds.id}`}>管理</Link>
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => openEdit(ds)}
                aria-label={`编辑 ${ds.name}`}
              >
                <Pencil className="h-4 w-4" /> 编辑
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="ml-auto text-muted-foreground"
                onClick={() => setPendingDelete(ds)}
                aria-label={`删除 ${ds.name}`}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </QueryGrid>

      {query.data && <Pagination paginator={query.data.paginator} onChange={setPage} />}

      <DatasetFormModal open={formOpen} dataset={editing} onClose={() => setFormOpen(false)} />

      <ConfirmDialog
        open={pendingDelete !== null}
        title="删除知识库"
        description={
          pendingDelete
            ? `确定删除「${pendingDelete.name}」？文档与片段将一并删除，不可恢复。`
            : ""
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
