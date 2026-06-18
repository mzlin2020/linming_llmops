/**
 * AI 模型目录管理（provider + model 增删改）类型。
 * 字段对齐后端 internal/schema/llm_admin_schema.py 与
 * llm_admin_service._provider_dict / _model_dict。本期不含 channel（多渠道）。
 * 密钥永不回明文：读取只有 has_api_key + api_key_mask。
 */

/** 管理面模型卡（GET /admin/llm-providers 内嵌、create/update model 返回）。 */
export interface AdminLlmModel {
  id: number;
  provider_id: number;
  model_name: string;
  label: Record<string, string>;
  model_type: string;
  features: string[];
  context_window: number;
  max_output_tokens: number | null;
  parameter_rules: unknown[];
  pricing: Record<string, unknown> | null;
  deprecated: boolean;
  admin_only: boolean;
  is_default: boolean;
  enabled: boolean;
  sort: number;
}

/** 管理面提供商（GET /admin/llm-providers 单项）。 */
export interface AdminLlmProvider {
  id: number;
  name: string;
  label: Record<string, string>;
  description: Record<string, string>;
  icon: string;
  background: string;
  supported_model_types: string[];
  protocol: string;
  multi_channel: boolean;
  base_url: string;
  has_api_key: boolean;
  api_key_mask: string;
  api_key_env: string;
  enabled: boolean;
  sort: number;
  models: AdminLlmModel[];
}

/** 创建提供商载荷（对齐 CreateProviderReq）。 */
export interface ProviderCreate {
  name: string;
  label?: Record<string, string>;
  description?: Record<string, string>;
  icon?: string;
  background?: string;
  supported_model_types?: string[];
  protocol?: string;
  multi_channel?: boolean;
  base_url?: string;
  api_key?: string;
  api_key_env?: string;
  enabled?: boolean;
  sort?: number;
}

/** 更新提供商载荷（对齐 UpdateProviderReq；全部可选，给了才改；api_key 空=保留原密钥）。 */
export type ProviderUpdate = Partial<Omit<ProviderCreate, "name">>;

/** 创建模型载荷（对齐 CreateModelReq）。 */
export interface ModelCreate {
  model_name: string;
  label?: Record<string, string>;
  model_type?: string;
  features?: string[];
  context_window?: number;
  max_output_tokens?: number | null;
  parameter_rules?: unknown[];
  pricing?: Record<string, unknown> | null;
  deprecated?: boolean;
  admin_only?: boolean;
  is_default?: boolean;
  enabled?: boolean;
  sort?: number;
}

/** 更新模型载荷（对齐 UpdateModelReq；全部可选，给了才改）。 */
export type ModelUpdate = Partial<ModelCreate>;
