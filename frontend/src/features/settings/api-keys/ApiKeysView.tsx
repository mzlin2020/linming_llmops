import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Pencil, Plus, Trash2 } from "lucide-react";

import { deleteApiKey, listApiKeys, updateApiKey } from "@/api/settings";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { Button } from "@/components/ui/button";
import type { ApiKey } from "@/types/settings";

import { ApiKeyFormModal } from "./ApiKeyFormModal";

/** API 密钥管理：列出 / 新建 / 复制 / 启停 / 改备注 / 删除。供外部以 Bearer 调 OpenAPI。 */
export function ApiKeysView() {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ApiKey | null>(null);
  const [pendingDelete, setPendingDelete] = useState<ApiKey | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);

  const query = useQuery({ queryKey: ["api-keys"], queryFn: listApiKeys });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["api-keys"] });

  const toggleMutation = useMutation({
    mutationFn: (k: ApiKey) => updateApiKey(k.id, { is_active: !k.is_active }),
    onSuccess: invalidate,
  });
  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteApiKey(id),
    onSuccess: () => {
      invalidate();
      setPendingDelete(null);
    },
  });

  const copy = (k: ApiKey) => {
    void navigator.clipboard?.writeText(k.api_key);
    setCopiedId(k.id);
    window.setTimeout(() => setCopiedId((id) => (id === k.id ? null : id)), 1500);
  };

  const openCreate = () => {
    setEditing(null);
    setFormOpen(true);
  };
  const openEdit = (k: ApiKey) => {
    setEditing(k);
    setFormOpen(true);
  };

  const list = query.data ?? [];

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">API 密钥</h2>
          <p className="text-sm text-muted-foreground">用于以 Bearer 头调用开放 API。</p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" /> 新建密钥
        </Button>
      </div>

      {query.isLoading ? (
        <p className="text-sm text-muted-foreground">加载中…</p>
      ) : list.length === 0 ? (
        <p className="py-12 text-center text-sm text-muted-foreground">还没有密钥，点「新建密钥」开始。</p>
      ) : (
        <div className="space-y-2">
          {list.map((k) => (
            <div key={k.id} className="rounded-lg border p-3">
              <div className="flex items-center gap-2">
                <code className="min-w-0 flex-1 truncate rounded bg-muted px-2 py-1 font-mono text-xs">
                  {k.api_key}
                </code>
                <button
                  type="button"
                  onClick={() => copy(k)}
                  className="shrink-0 text-muted-foreground hover:text-foreground"
                  aria-label={`复制密钥 ${k.id}`}
                  title="复制"
                >
                  <Copy className="h-4 w-4" />
                </button>
                {copiedId === k.id && <span className="shrink-0 text-xs text-green-600">已复制</span>}
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                <label className="flex cursor-pointer items-center gap-1.5">
                  <input
                    type="checkbox"
                    checked={k.is_active}
                    disabled={toggleMutation.isPending}
                    onChange={() => toggleMutation.mutate(k)}
                  />
                  启用
                </label>
                <span className="truncate">{k.remark || "无备注"}</span>
                <span>{new Date(k.created_at * 1000).toLocaleDateString()}</span>
                <div className="ml-auto flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => openEdit(k)}
                    className="hover:text-foreground"
                    aria-label={`编辑密钥 ${k.id}`}
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setPendingDelete(k)}
                    className="hover:text-destructive"
                    aria-label={`删除密钥 ${k.id}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <ApiKeyFormModal open={formOpen} apiKey={editing} onClose={() => setFormOpen(false)} />

      <ConfirmDialog
        open={pendingDelete !== null}
        title="删除密钥"
        description="删除后使用该密钥的调用将立即失效，且不可恢复。"
        confirmText="删除"
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => pendingDelete && deleteMutation.mutate(pendingDelete.id)}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
