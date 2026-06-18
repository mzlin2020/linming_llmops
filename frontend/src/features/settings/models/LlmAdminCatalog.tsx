import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";

import { deleteModel, deleteProvider, listAdminProviders } from "@/api/admin-llm";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { Button } from "@/components/ui/button";
import type { AdminLlmModel, AdminLlmProvider } from "@/types/admin-llm";
import { pickLabel } from "@/types/apps";

import { LlmModelFormModal } from "./LlmModelFormModal";
import { LlmProviderFormModal } from "./LlmProviderFormModal";

/** 模型目录管理（ENABLE_LLM_ADMIN 开启时）：提供商 + 模型 的增删改。全局共享，所有用户可用。 */
export function LlmAdminCatalog({ protocols }: { protocols: string[] }) {
  const queryClient = useQueryClient();
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["llm-admin-providers"] });
    // 同时刷新只读目录（首页助手 / 编排页 / 工作流的模型选择器共用此 key），令新模型立即可见
    queryClient.invalidateQueries({ queryKey: ["language-models"] });
  };

  const query = useQuery({ queryKey: ["llm-admin-providers"], queryFn: listAdminProviders });

  const [providerForm, setProviderForm] = useState<{ open: boolean; editing: AdminLlmProvider | null }>({
    open: false,
    editing: null,
  });
  const [modelForm, setModelForm] = useState<{ open: boolean; providerId: number; editing: AdminLlmModel | null }>({
    open: false,
    providerId: 0,
    editing: null,
  });
  const [delProvider, setDelProvider] = useState<AdminLlmProvider | null>(null);
  const [delModel, setDelModel] = useState<AdminLlmModel | null>(null);

  const deleteProviderM = useMutation({
    mutationFn: (id: number) => deleteProvider(id),
    onSuccess: () => {
      invalidate();
      setDelProvider(null);
    },
  });
  const deleteModelM = useMutation({
    mutationFn: (id: number) => deleteModel(id),
    onSuccess: () => {
      invalidate();
      setDelModel(null);
    },
  });

  const providers = query.data ?? [];

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">模型目录</h2>
          <p className="text-sm text-muted-foreground">管理提供商与模型（全局共享，所有用户可用）。</p>
        </div>
        <Button onClick={() => setProviderForm({ open: true, editing: null })}>
          <Plus className="h-4 w-4" /> 新增提供商
        </Button>
      </div>

      {query.isLoading ? (
        <p className="text-sm text-muted-foreground">加载中…</p>
      ) : providers.length === 0 ? (
        <p className="py-12 text-center text-sm text-muted-foreground">还没有提供商，点「新增提供商」开始。</p>
      ) : (
        <div className="space-y-4">
          {providers.map((p) => (
            <div key={p.id} className="rounded-lg border p-4">
              <div className="flex items-start gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{pickLabel(p.label, p.name)}</span>
                    <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-muted-foreground">
                      {p.name}
                    </code>
                    <span className="rounded bg-primary/5 px-1.5 py-0.5 text-xs text-primary">{p.protocol}</span>
                    {!p.enabled && (
                      <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">已禁用</span>
                    )}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {p.base_url || "（未设 base_url）"} · 密钥{" "}
                    {p.has_api_key ? p.api_key_mask : p.api_key_env ? `env ${p.api_key_env}` : "未配置"}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setProviderForm({ open: true, editing: p })}
                  className="text-muted-foreground hover:text-foreground"
                  aria-label={`编辑提供商 ${p.name}`}
                >
                  <Pencil className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setDelProvider(p)}
                  className="text-muted-foreground hover:text-destructive"
                  aria-label={`删除提供商 ${p.name}`}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>

              <div className="mt-3 space-y-1.5">
                {p.models.map((m) => (
                  <div key={m.id} className="flex flex-wrap items-center gap-2 rounded-md border p-2 text-sm">
                    <span className="font-medium">{pickLabel(m.label, m.model_name)}</span>
                    <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-muted-foreground">
                      {m.model_name}
                    </code>
                    <span className="text-xs text-muted-foreground">{m.model_type}</span>
                    {m.is_default && (
                      <span className="rounded bg-primary/5 px-1.5 py-0.5 text-xs text-primary">默认</span>
                    )}
                    {!m.enabled && (
                      <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">禁用</span>
                    )}
                    {m.deprecated && (
                      <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">弃用</span>
                    )}
                    <div className="ml-auto flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setModelForm({ open: true, providerId: p.id, editing: m })}
                        className="text-muted-foreground hover:text-foreground"
                        aria-label={`编辑模型 ${m.model_name}`}
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => setDelModel(m)}
                        className="text-muted-foreground hover:text-destructive"
                        aria-label={`删除模型 ${m.model_name}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                ))}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setModelForm({ open: true, providerId: p.id, editing: null })}
                >
                  <Plus className="h-4 w-4" /> 新增模型
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <LlmProviderFormModal
        open={providerForm.open}
        provider={providerForm.editing}
        protocols={protocols}
        onClose={() => setProviderForm({ open: false, editing: null })}
      />
      <LlmModelFormModal
        open={modelForm.open}
        providerId={modelForm.providerId}
        model={modelForm.editing}
        onClose={() => setModelForm({ open: false, providerId: 0, editing: null })}
      />

      <ConfirmDialog
        open={delProvider !== null}
        title="删除提供商"
        description="将连带删除其下所有模型，且不可恢复。"
        confirmText="删除"
        destructive
        loading={deleteProviderM.isPending}
        onConfirm={() => delProvider && deleteProviderM.mutate(delProvider.id)}
        onCancel={() => setDelProvider(null)}
      />
      <ConfirmDialog
        open={delModel !== null}
        title="删除模型"
        description="删除后使用该模型的应用将回落到默认模型。"
        confirmText="删除"
        destructive
        loading={deleteModelM.isPending}
        onConfirm={() => delModel && deleteModelM.mutate(delModel.id)}
        onCancel={() => setDelModel(null)}
      />
    </div>
  );
}
