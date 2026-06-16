import { get, post } from "@/lib/http/client";
import type { PageQuery, PageResult } from "@/types/api";
import type {
  ApiToolProvider,
  ApiToolProviderDetail,
  ApiToolUpsert,
  BuiltinCategory,
  BuiltinProvider,
  StorePlugin,
} from "@/types/plugins";

// ---------- 内置工具（只读）----------
export function listBuiltinTools() {
  return get<BuiltinProvider[]>("/builtin-tools");
}

export function listBuiltinCategories() {
  return get<BuiltinCategory[]>("/builtin-tools/categories");
}

// ---------- 自定义 API 工具（CRUD，user 隔离）----------
export function listApiTools(query: PageQuery) {
  return get<PageResult<ApiToolProvider>>("/api-tools", { params: query });
}

export function getApiTool(id: number) {
  return get<ApiToolProviderDetail>(`/api-tools/${id}`);
}

export function createApiTool(body: ApiToolUpsert) {
  return post("/api-tools", body);
}

export function updateApiTool(id: number, body: ApiToolUpsert) {
  return post(`/api-tools/${id}`, body);
}

export function deleteApiTool(id: number) {
  return post(`/api-tools/${id}/delete`);
}

export function validateOpenapiSchema(openapi_schema: string) {
  return post("/api-tools/validate-openapi-schema", { openapi_schema });
}

/** 上架/下架到插件商店（切换语义）。 */
export function publishApiTool(id: number, is_public: boolean) {
  return post(`/api-tools/${id}/publish`, { is_public });
}

// ---------- 插件商店 ----------
export function listStorePlugins(query: PageQuery) {
  return get<PageResult<StorePlugin>>("/plugin-store", { params: query });
}

export function addStorePlugin(publicId: number) {
  return post(`/plugin-store/${publicId}/add`);
}
