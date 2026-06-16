/** 插件模块前端类型。后端契约见 backend/internal/{schema,service} 的 builtin_tool / api_tool / plugin-store。 */

/** 工具入参（内置/自定义工具的 inputs 统一形态）。 */
export interface ToolInput {
  name: string;
  description: string;
  required: boolean;
  type: string;
}

/** 内置工具（provider 下一个工具）。 */
export interface BuiltinTool {
  name: string;
  label: string;
  description: string;
  inputs: ToolInput[];
}

/** 内置工具提供商（GET /builtin-tools 列表项，非分页）。 */
export interface BuiltinProvider {
  name: string;
  label: string;
  description: string;
  background: string;
  category: string;
  created_at: number;
  /** 超管专属（本项目恒无超管，前端据此禁用绑定）。 */
  admin_only?: boolean;
  tools: BuiltinTool[];
}

/** 工具分类（GET /builtin-tools/categories，icon 为内联 SVG 字符串）。 */
export interface BuiltinCategory {
  category: string;
  name: string;
  icon: string;
}

/** 请求头键值对。 */
export interface ToolHeader {
  key: string;
  value: string;
}

/** 自定义 API 工具（provider 下一个工具，列表项简版）。 */
export interface ApiToolBrief {
  id: number;
  name: string;
  description: string;
  inputs: ToolInput[];
}

/** 自定义 API 工具提供商（GET /api-tools 列表项）。 */
export interface ApiToolProvider {
  id: number;
  name: string;
  /** 图标 URL（外链，非鉴权端点）。 */
  icon: string;
  description: string;
  headers: ToolHeader[];
  tools: ApiToolBrief[];
  is_public: boolean;
  created_at: number;
}

/** 自定义 API 工具详情（GET /api-tools/<id>，含原始 schema，供编辑回显）。 */
export interface ApiToolProviderDetail {
  id: number;
  name: string;
  icon: string;
  openapi_schema: string;
  headers: ToolHeader[];
  created_at: number;
}

/** 创建/更新自定义 API 工具的请求体。 */
export interface ApiToolUpsert {
  name: string;
  icon: string;
  openapi_schema: string;
  headers: ToolHeader[];
}

/** 商店插件（GET /plugin-store 列表项）。 */
export interface StorePlugin {
  id: number;
  name: string;
  icon: string;
  description: string;
  tools: Pick<ApiToolBrief, "name" | "description" | "inputs">[];
  /** 当前用户是否已添加。 */
  added: boolean;
  created_at: number;
}

/**
 * 工具引用（ToolSelector 输出，对齐后端 app_config_service._validate_tools 接受的形态）。
 * 5e 编排页直接把它写入 AppConfig.tools。
 */
export type ToolRef =
  | { type: "builtin_tool"; provider: { name: string }; tool: { name: string; params: Record<string, unknown> } }
  | { type: "api_tool"; provider: { id: number; name: string }; tool: { id: number; name: string } };
