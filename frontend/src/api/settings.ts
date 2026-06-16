/** 设置模块端点薄封装（API 密钥）。模型目录复用 api/apps 的 listLanguageModels。 */
import { get, post } from "@/lib/http/client";
import type { ApiKey, ApiKeyUpsert } from "@/types/settings";

/** 当前用户的密钥列表（后端返回 {list}，非分页）。 */
export async function listApiKeys(): Promise<ApiKey[]> {
  const data = await get<{ list: ApiKey[] }>("/api-keys");
  return data.list;
}

export function createApiKey(body: ApiKeyUpsert): Promise<ApiKey> {
  return post<ApiKey>("/api-keys", body);
}

export function updateApiKey(keyId: number, body: ApiKeyUpsert): Promise<ApiKey> {
  return post<ApiKey>(`/api-keys/${keyId}`, body);
}

export function deleteApiKey(keyId: number): Promise<unknown> {
  return post(`/api-keys/${keyId}/delete`);
}
