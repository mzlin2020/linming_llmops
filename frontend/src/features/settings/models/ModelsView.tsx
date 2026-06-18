import { useQuery } from "@tanstack/react-query";

import { listLlmProtocols } from "@/api/admin-llm";
import { listLanguageModels } from "@/api/apps";
import { pickLabel } from "@/types/apps";

import { LlmAdminCatalog } from "./LlmAdminCatalog";

/** 模型能力特性 → 中文短标签（未知特性原样显示）。 */
const FEATURE_LABEL: Record<string, string> = {
  tool_call: "工具调用",
  function_call: "函数调用",
  vision: "视觉",
  streaming: "流式",
  json_mode: "JSON",
  reasoning: "推理",
  agent_thought: "思维链",
};

/**
 * 模型目录页。能力探测：调 /admin/llm-protocols——
 * 成功（ENABLE_LLM_ADMIN 开启）→ 进管理模式（增删改提供商/模型）；
 * 失败（默认关，返回 403）→ 静默降级为只读目录。
 */
export function ModelsView() {
  const protocolsQuery = useQuery({
    queryKey: ["llm-protocols"],
    queryFn: listLlmProtocols,
    retry: false,
  });

  if (protocolsQuery.isPending) {
    return (
      <div className="mx-auto max-w-3xl">
        <p className="text-sm text-muted-foreground">加载中…</p>
      </div>
    );
  }
  if (protocolsQuery.isSuccess) {
    return <LlmAdminCatalog protocols={protocolsQuery.data} />;
  }
  return <ReadonlyCatalog />;
}

/** 只读目录：展示已配置的提供商与模型及其能力特性（ENABLE_LLM_ADMIN 关闭时）。 */
function ReadonlyCatalog() {
  const query = useQuery({ queryKey: ["language-models"], queryFn: listLanguageModels });
  const providers = query.data ?? [];

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div>
        <h2 className="text-lg font-semibold">模型目录</h2>
        <p className="text-sm text-muted-foreground">平台已接入的模型提供商与模型（只读）。</p>
      </div>

      {query.isLoading ? (
        <p className="text-sm text-muted-foreground">加载中…</p>
      ) : providers.length === 0 ? (
        <p className="py-12 text-center text-sm text-muted-foreground">尚未配置任何模型提供商。</p>
      ) : (
        <div className="space-y-4">
          {providers.map((p) => {
            const desc = pickLabel(p.description, "");
            return (
              <div key={p.name} className="rounded-lg border p-4">
                <div className="mb-3">
                  <p className="font-medium">{pickLabel(p.label, p.name)}</p>
                  {desc && <p className="text-xs text-muted-foreground">{desc}</p>}
                </div>
                <div className="space-y-2">
                  {p.models.map((m) => (
                    <div
                      key={m.model_name}
                      className="flex flex-wrap items-center gap-2 rounded-md border p-2 text-sm"
                    >
                      <span className="font-medium">{pickLabel(m.label, m.model_name)}</span>
                      <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-muted-foreground">
                        {m.model_name}
                      </code>
                      {m.deprecated && (
                        <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                          已弃用
                        </span>
                      )}
                      <span className="ml-auto text-xs text-muted-foreground">
                        上下文 {m.context_window.toLocaleString()}
                      </span>
                      {m.features.length > 0 && (
                        <div className="flex w-full flex-wrap gap-1">
                          {m.features.map((f) => (
                            <span
                              key={f}
                              className="rounded bg-primary/5 px-1.5 py-0.5 text-xs text-primary"
                            >
                              {FEATURE_LABEL[f] ?? f}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
