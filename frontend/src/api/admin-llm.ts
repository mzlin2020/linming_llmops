/**
 * AI 模型目录管理端点薄封装（写入面，后端 ENABLE_LLM_ADMIN 守护、默认关）。
 * 开关关时这些端点返回 403 —— 调用方据 listLlmProtocols 是否成功判断进不进管理模式。
 * 只读目录浏览仍走 api/apps 的 listLanguageModels（不受开关影响）。
 */
import { get, post } from "@/lib/http/client";
import type {
  AdminLlmModel,
  AdminLlmProvider,
  ModelCreate,
  ModelUpdate,
  ProviderCreate,
  ProviderUpdate,
} from "@/types/admin-llm";

/** 可选协议（如 ["openai","anthropic"]）。开关关时 403 —— 用作管理能力探测。 */
export function listLlmProtocols(): Promise<string[]> {
  return get<string[]>("/admin/llm-protocols");
}

export function listAdminProviders(): Promise<AdminLlmProvider[]> {
  return get<AdminLlmProvider[]>("/admin/llm-providers");
}

export function createProvider(body: ProviderCreate): Promise<AdminLlmProvider> {
  return post<AdminLlmProvider>("/admin/llm-providers", body);
}

export function updateProvider(id: number, body: ProviderUpdate): Promise<AdminLlmProvider> {
  return post<AdminLlmProvider>(`/admin/llm-providers/${id}`, body);
}

export function deleteProvider(id: number): Promise<unknown> {
  return post(`/admin/llm-providers/${id}/delete`);
}

export function createModel(providerId: number, body: ModelCreate): Promise<AdminLlmModel> {
  return post<AdminLlmModel>(`/admin/llm-providers/${providerId}/models`, body);
}

export function updateModel(modelId: number, body: ModelUpdate): Promise<AdminLlmModel> {
  return post<AdminLlmModel>(`/admin/llm-models/${modelId}`, body);
}

export function deleteModel(modelId: number): Promise<unknown> {
  return post(`/admin/llm-models/${modelId}/delete`);
}
