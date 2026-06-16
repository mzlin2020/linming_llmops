/** 应用编排相关端点薄封装。响应经 axios 拦截器解信封后即下列返回值。 */
import { get, post } from "@/lib/http/client";
import type { PageQuery, PageResult } from "@/types/api";
import type {
  AppConfig,
  AppCreate,
  AppDetail,
  AppListItem,
  LlmProvider,
  PublicAppBrief,
  PublishHistory,
} from "@/types/apps";

// ---------- 应用 CRUD ----------

export function listApps(): Promise<AppListItem[]> {
  return get<AppListItem[]>("/apps");
}

export function getApp(appId: number): Promise<AppDetail> {
  return get<AppDetail>(`/apps/${appId}`);
}

export function createApp(body: AppCreate): Promise<AppListItem> {
  return post<AppListItem>("/apps", body);
}

export function deleteApp(appId: number): Promise<unknown> {
  return post(`/apps/${appId}/delete`);
}

export function copyApp(appId: number): Promise<AppListItem> {
  return post<AppListItem>(`/apps/${appId}/copy`);
}

// ---------- 草稿配置 ----------

export function getDraftConfig(appId: number): Promise<AppConfig> {
  return get<AppConfig>(`/apps/${appId}/draft-app-config`);
}

/** 原地更新草稿配置（部分字段即可；后端只取已知键，返回更新后的配置全集）。 */
export function updateDraftConfig(appId: number, config: Partial<AppConfig>): Promise<AppConfig> {
  return post<AppConfig>(`/apps/${appId}/draft-app-config`, config);
}

// ---------- 发布 / 历史 ----------

export function publishApp(appId: number): Promise<AppDetail> {
  return post<AppDetail>(`/apps/${appId}/publish`);
}

export function cancelPublishApp(appId: number): Promise<AppDetail> {
  return post<AppDetail>(`/apps/${appId}/cancel-publish`);
}

export function listPublishHistories(
  appId: number,
  query: PageQuery,
): Promise<PageResult<PublishHistory>> {
  return get<PageResult<PublishHistory>>(`/apps/${appId}/publish-histories`, { params: query });
}

export function fallbackHistory(appId: number, versionId: number): Promise<AppConfig> {
  return post<AppConfig>(`/apps/${appId}/fallback-history`, {
    app_config_version_id: versionId,
  });
}

// ---------- 公共应用商店 ----------

export function getAppStore(query: PageQuery): Promise<PageResult<PublicAppBrief>> {
  return get<PageResult<PublicAppBrief>>("/app-store", { params: query });
}

export function setAppPublic(appId: number, isPublic: boolean): Promise<unknown> {
  return post(`/apps/${appId}/store-publish`, { is_public: isPublic });
}

export function addStoreApp(publicId: number): Promise<AppListItem> {
  return post<AppListItem>(`/app-store/${publicId}/add`);
}

// ---------- 模型目录（编排页模型选择器）----------

export function listLanguageModels(): Promise<LlmProvider[]> {
  return get<LlmProvider[]>("/language-models");
}
