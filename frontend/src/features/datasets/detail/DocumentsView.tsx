import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { Pencil, RefreshCw, Trash2, Upload } from "lucide-react";

import {
  deleteDocument,
  listDocuments,
  reindexDocument,
  renameDocument,
  setDocumentEnabled,
} from "@/api/datasets";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { FormError } from "@/components/shared/form";
import { Modal } from "@/components/shared/Modal";
import { Pagination } from "@/components/shared/Pagination";
import { SearchInput } from "@/components/shared/SearchInput";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { AiDocument } from "@/types/datasets";
import { DocumentUploadModal } from "./DocumentUploadModal";

const PAGE_SIZE = 20;
const TERMINAL = new Set(["completed", "error"]);

/** 文档列表：上传 + 行列表（状态/启停/重索引/改名/删除/进片段）。处理中自动轮询。 */
export function DocumentsView() {
  const { id } = useParams();
  const datasetId = Number(id);
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<AiDocument | null>(null);
  const [renameTarget, setRenameTarget] = useState<AiDocument | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const query = useQuery({
    queryKey: ["documents", datasetId, { page, search }],
    queryFn: () =>
      listDocuments(datasetId, {
        current_page: page,
        page_size: PAGE_SIZE,
        search_word: search || undefined,
      }),
    // 存在非终态文档时 2s 轮询，否则停。
    refetchInterval: (q) => {
      const data = q.state.data;
      return data && data.list.some((d) => !TERMINAL.has(d.status)) ? 2000 : false;
    },
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["documents", datasetId] });

  const enabledMutation = useMutation({
    mutationFn: ({ docId, enabled }: { docId: number; enabled: boolean }) =>
      setDocumentEnabled(datasetId, docId, enabled),
    onSuccess: invalidate,
  });
  const reindexMutation = useMutation({
    mutationFn: (docId: number) => reindexDocument(datasetId, docId),
    onSuccess: invalidate,
  });
  const deleteMutation = useMutation({
    mutationFn: (docId: number) => deleteDocument(datasetId, docId),
    onSuccess: () => {
      invalidate();
      setPendingDelete(null);
    },
  });
  const renameMutation = useMutation({
    mutationFn: ({ docId, name }: { docId: number; name: string }) =>
      renameDocument(datasetId, docId, name),
    onSuccess: () => {
      invalidate();
      setRenameTarget(null);
    },
  });

  const onSearch = (v: string) => {
    setSearch(v);
    setPage(1);
  };

  const openRename = (doc: AiDocument) => {
    setRenameTarget(doc);
    setRenameValue(doc.name);
  };

  const list = query.data?.list ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <SearchInput value={search} onChange={onSearch} placeholder="搜索文档" />
        <Button onClick={() => setUploadOpen(true)}>
          <Upload className="h-4 w-4" /> 上传文档
        </Button>
      </div>

      {query.isLoading ? (
        <p className="text-sm text-muted-foreground">加载中…</p>
      ) : list.length === 0 ? (
        <p className="py-12 text-center text-sm text-muted-foreground">
          还没有文档，点「上传文档」开始。
        </p>
      ) : (
        <div className="divide-y rounded-lg border">
          {list.map((doc) => (
            <div key={doc.id} className="flex items-center gap-3 p-3">
              <div className="min-w-0 flex-1">
                <Link
                  to={`/datasets/${datasetId}/documents/${doc.id}/segments`}
                  className="block truncate font-medium hover:underline"
                >
                  {doc.name}
                </Link>
                <p className="text-xs text-muted-foreground">
                  {doc.segment_count} 片段 · {doc.character_count} 字符 · 命中 {doc.hit_count}
                </p>
                {doc.status === "error" && doc.error && (
                  <p className="truncate text-xs text-destructive" title={doc.error}>
                    {doc.error}
                  </p>
                )}
              </div>
              <StatusBadge status={doc.status} />
              {doc.status === "completed" && (
                <label className="flex shrink-0 cursor-pointer items-center gap-1.5 text-xs text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={doc.enabled}
                    disabled={enabledMutation.isPending}
                    onChange={() => enabledMutation.mutate({ docId: doc.id, enabled: !doc.enabled })}
                  />
                  启用
                </label>
              )}
              <Button
                variant="ghost"
                size="icon"
                onClick={() => openRename(doc)}
                aria-label={`重命名 ${doc.name}`}
                title="重命名"
              >
                <Pencil className="h-4 w-4" />
              </Button>
              {TERMINAL.has(doc.status) && (
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => reindexMutation.mutate(doc.id)}
                  disabled={reindexMutation.isPending}
                  aria-label={`重新索引 ${doc.name}`}
                  title="重新索引"
                >
                  <RefreshCw className="h-4 w-4" />
                </Button>
              )}
              <Button
                variant="ghost"
                size="icon"
                className="text-muted-foreground"
                onClick={() => setPendingDelete(doc)}
                disabled={!TERMINAL.has(doc.status)}
                aria-label={`删除 ${doc.name}`}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      )}

      {query.data && <Pagination paginator={query.data.paginator} onChange={setPage} />}

      <DocumentUploadModal
        open={uploadOpen}
        datasetId={datasetId}
        onClose={() => setUploadOpen(false)}
        onUploaded={invalidate}
      />

      <ConfirmDialog
        open={pendingDelete !== null}
        title="删除文档"
        description={
          pendingDelete ? `确定删除「${pendingDelete.name}」？该文档的片段将一并删除。` : ""
        }
        confirmText="删除"
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => pendingDelete && deleteMutation.mutate(pendingDelete.id)}
        onCancel={() => setPendingDelete(null)}
      />

      <Modal
        open={renameTarget !== null}
        title="重命名文档"
        onClose={() => setRenameTarget(null)}
        footer={
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setRenameTarget(null)}
              disabled={renameMutation.isPending}
            >
              取消
            </Button>
            <Button
              size="sm"
              disabled={!renameValue.trim() || renameMutation.isPending}
              onClick={() =>
                renameTarget &&
                renameMutation.mutate({ docId: renameTarget.id, name: renameValue.trim() })
              }
            >
              保存
            </Button>
          </>
        }
      >
        <Input
          value={renameValue}
          onChange={(e) => setRenameValue(e.target.value)}
          aria-label="文档名"
        />
        {renameMutation.isError && (
          <div className="mt-2">
            <FormError error={renameMutation.error} />
          </div>
        )}
      </Modal>
    </div>
  );
}
