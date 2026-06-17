/**
 * 应用编排模块前端类型。后端契约见 backend/internal/{schema,service,entity} 的
 * app / app_config / conversation / language_model。
 */
import type { ToolRef } from "./plugins";

export type AppStatus = "draft" | "published";

export interface ModelConfig {
  provider: string;
  model: string;
  parameters: Record<string, unknown>;
}

/** 应用配置全集（14 字段，对齐后端 AppConfigItem / serialize_config）。 */
export interface AppConfig {
  model_config: ModelConfig;
  dialog_round: number;
  preset_prompt: string;
  tools: ToolRef[];
  workflows: number[];
  datasets: number[];
  retrieval_config: Record<string, unknown>;
  long_term_memory: { enable: boolean };
  opening_statement: string;
  opening_questions: string[];
  speech_to_text: { enable: boolean };
  text_to_speech: { enable: boolean };
  suggested_after_answer: { enable: boolean };
  review_config: Record<string, unknown>;
}

/** 应用列表项（GET /apps 单项；含从草稿行合并的 preset/model/dialog）。 */
export interface AppListItem {
  id: number;
  user_id: number | null;
  name: string;
  description: string;
  icon: string;
  status: AppStatus;
  is_default: boolean;
  is_assistant_agent: boolean;
  created_at: string | null;
  updated_at: string | null;
  preset_prompt: string;
  model_config: ModelConfig;
  dialog_round: number;
}

/** 应用详情（GET /apps/<id>：列表项 + 配置全集 + 是否已上架商店）。 */
export interface AppDetail extends AppListItem {
  app_config: AppConfig;
  is_public: boolean;
}

/** 创建应用请求体。 */
export interface AppCreate {
  name: string;
  description?: string;
}

/** 公共应用商店列表项（GET /app-store 单项）。 */
export interface PublicAppBrief {
  id: number;
  name: string;
  icon: string;
  description: string;
  model_provider: string;
  model_name: string;
  tool_count: number;
  added: boolean;
  created_at: number;
}

/** 发布历史项（GET /apps/<id>/publish-histories 单项）。 */
export interface PublishHistory {
  id: number;
  version: number;
  created_at: string | null;
}

/** 模型卡（GET /language-models 中 provider.models 单项，仅取本期所需字段）。 */
export interface LlmModel {
  model_name: string;
  label: Record<string, string>;
  features: string[];
  context_window: number;
  deprecated: boolean;
  /** chat / text2img / tts / embedding（对齐后端 ModelType）；编排页对话模型仅取 chat。 */
  model_type: string;
}

/** 模型提供商（GET /language-models 单项）。 */
export interface LlmProvider {
  name: string;
  label: Record<string, string>;
  description: Record<string, string>;
  models: LlmModel[];
}

/** 多语言标签取值：优先中文，回落英文，再回落 key。 */
export function pickLabel(label: Record<string, string> | undefined, fallback: string): string {
  if (!label) return fallback;
  return label.zh_Hans || label.en_US || Object.values(label)[0] || fallback;
}

// 与后端 app_config_service / app_schema 同步的上限。
export const MAX_TOOLS = 10;
export const MAX_DATASETS = 5;
export const MAX_OPENING_QUESTIONS = 5;
export const OPENING_QUESTION_MAX_LEN = 200;
export const DIALOG_ROUND_MIN = 0;
export const DIALOG_ROUND_MAX = 100;
export const PRESET_PROMPT_MAX = 8000;
export const OPENING_STATEMENT_MAX = 2000;
export const LONG_TERM_MEMORY_MAX = 2000;
export const APP_NAME_MAX = 64;
export const APP_DESCRIPTION_MAX = 512;
