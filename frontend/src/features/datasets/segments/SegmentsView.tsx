import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ChevronRight, Plus, Trash2 } from "lucide-react";

import { deleteSegment, listSegments, setSegmentEnabled } from "@/api/datasets";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { Pagination } from "@/components/shared/Pagination";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import type { Segment } from "@/types/datasets";
import { SegmentEditorModal } from "./SegmentEditorModal";

const PAGE_SIZE = 20;

/** 片段列表：面包屑 + 增删改启停。 */
export function SegmentsView() {
  const { id, docId } = useParams();
  const datasetId = Number(id);
  const documentId = Number(docId);
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<Segment | null>(null);
  const [creating, setCreating] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<Segment | null>(null);

  const query = useQuery({
    queryKey: ["segments", documentId, { page }],
    queryFn: () => listSegments(datasetId, documentId, { current_page: page, page_size: PAGE_SIZE }),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["segments", documentId] });

  const enabledMutation = useMutation({
    mutationFn: ({ segId, enabled }: { segId: number; enabled: boolean }) =>
      setSegmentEnabled(datasetId, documentId, segId, enabled),
    onSuccess: invalidate,
  });
  const deleteMutation = useMutation({
    mutationFn: (segId: number) => deleteSegment(datasetId, documentId, segId),
    onSuccess: () => {
      invalidate();
      setPendingDelete(null);
    },
  });

  const list = query.data?.list ?? [];

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div className="flex items-center justify-between gap-3">
        <nav className="flex items-center gap-1 text-sm text-muted-foreground">
          <Link to="/datasets" className="hover:text-foreground">
            知识库
          </Link>
          <ChevronRight className="h-4 w-4" />
          <Link to={`/datasets/${datasetId}/documents`} className="hover:text-foreground">
            文档
          </Link>
          <ChevronRight className="h-4 w-4" />
          <span className="text-foreground">片段</span>
        </nav>
        <Button onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" /> 新建片段
        </Button>
      </div>

      {query.isLoading ? (
        <p className="text-sm text-muted-foreground">加载中…</p>
      ) : list.length === 0 ? (
        <p className="py-12 text-center text-sm text-muted-foreground">还没有片段。</p>
      ) : (
        <div className="space-y-2">
          {list.map((seg) => (
            <div key={seg.id} className="rounded-lg border p-3">
              <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <span>#{seg.position}</span>
                <StatusBadge status={seg.status} />
                <span>
                  {seg.character_count} 字符 · {seg.token_count} token · 命中 {seg.hit_count}
                </span>
                <div className="ml-auto flex items-center gap-3">
                  <label className="flex cursor-pointer items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={seg.enabled}
                      disabled={seg.status !== "completed" || enabledMutation.isPending}
                      onChange={() => enabledMutation.mutate({ segId: seg.id, enabled: !seg.enabled })}
                    />
                    启用
                  </label>
                  <button
                    type="button"
                    onClick={() => setEditing(seg)}
                    className="hover:text-foreground"
                    aria-label={`编辑片段 ${seg.position}`}
                  >
                    编辑
                  </button>
                  <button
                    type="button"
                    onClick={() => setPendingDelete(seg)}
                    className="hover:text-destructive"
                    aria-label={`删除片段 ${seg.position}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
              <p className="whitespace-pre-wrap text-sm">{seg.content}</p>
              {seg.keywords.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {seg.keywords.map((kw) => (
                    <span
                      key={kw}
                      className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground"
                    >
                      {kw}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {query.data && <Pagination paginator={query.data.paginator} onChange={setPage} />}

      <SegmentEditorModal
        open={creating || editing !== null}
        datasetId={datasetId}
        documentId={documentId}
        segment={editing}
        onClose={() => {
          setCreating(false);
          setEditing(null);
        }}
      />

      <ConfirmDialog
        open={pendingDelete !== null}
        title="删除片段"
        description="确定删除该片段？此操作不可恢复。"
        confirmText="删除"
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => pendingDelete && deleteMutation.mutate(pendingDelete.id)}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
