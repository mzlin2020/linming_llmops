/**
 * 工作流模块前端类型。**逐字对齐后端契约** —— 见
 * backend/internal/core/workflow/{entities,nodes}/* 与 internal/schema/workflow_schema.py。
 *
 * 两个 pydantic 别名（前端必须用别名键，否则后端收不到）：
 *   - LLM 节点：`model_config`（后端字段 language_model_config）
 *   - 工具节点：`type`（后端字段 tool_type）
 */

export type WorkflowStatus = "draft" | "published";

export type NodeType =
  | "start"
  | "end"
  | "llm"
  | "template_transform"
  | "tool"
  | "dataset_retrieval"
  | "http_request"
  | "code";

export type VariableType = "string" | "int" | "float" | "boolean";
export type VariableValueType = "literal" | "ref" | "generated";
export type ToolKind = "builtin_tool" | "api_tool" | "";
export type HttpMethod = "get" | "post" | "put" | "patch" | "delete" | "head" | "options";
export type HttpInputLocation = "params" | "headers" | "body";
export type RetrievalStrategy = "semantic" | "full_text" | "hybrid";
export type NodeRunStatus = "running" | "succeeded" | "failed";

// 与后端 / 编辑器约束同源。
export const MAX_NODES = 20;
export const MAX_DATASETS_PER_NODE = 5;
export const MAX_WORKFLOWS = 3; // QUOTA_MAX_WORKFLOWS_PER_USER 默认
export const IDENTIFIER_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;
export const HTTP_METHODS: HttpMethod[] = ["get", "post", "put", "patch", "delete", "head", "options"];
export const VARIABLE_TYPES: VariableType[] = ["string", "int", "float", "boolean"];
export const RETRIEVAL_STRATEGIES: RetrievalStrategy[] = ["semantic", "full_text", "hybrid"];

/** 变量引用：指向某前驱节点的某输出变量。 */
export interface RefContent {
  ref_node_id: string | null;
  ref_var_name: string;
}

export type VariableValue =
  | { type: "literal"; content: string | number | boolean }
  | { type: "ref"; content: RefContent }
  | { type: "generated"; content: string | number | boolean };

/** 变量实体（节点 inputs/outputs 的统一形态）。 */
export interface VariableEntity {
  name: string;
  description: string;
  required: boolean;
  type: VariableType;
  value: VariableValue;
  meta: Record<string, unknown>;
}

export interface Position {
  x: number;
  y: number;
}

/** LLM 节点的模型配置（前端别名键 model_config）。 */
export interface NodeModelConfig {
  provider: string;
  model: string;
  parameters: Record<string, unknown>;
}

export interface RetrievalConfig {
  retrieval_strategy: RetrievalStrategy;
  k: number;
  score: number;
}

/** get_draft_graph 为 tool / dataset_retrieval 节点附的展示 meta（只读回显）。 */
export interface NodeMeta {
  type?: ToolKind;
  provider?: { id?: string | number; name?: string; label?: string; icon?: string };
  tool?: { id?: string | number; name?: string; label?: string };
  datasets?: { id: number; name: string; icon: string }[];
}

/**
 * 工作流节点。宽口径单一接口（含全部按类型可选字段），与原编辑器一致——
 * 图编辑器把整个节点存进 ReactFlow 的 `data.wf`，面板按类型补丁对应字段。
 */
export interface WorkflowNode {
  id: string;
  node_type: NodeType;
  title: string;
  description: string;
  position: Position;
  inputs?: VariableEntity[];
  outputs?: VariableEntity[];
  // llm
  prompt?: string;
  model_config?: NodeModelConfig;
  // template_transform
  template?: string;
  // tool（别名 type = tool_type）
  type?: ToolKind;
  provider_id?: string;
  tool_id?: string;
  params?: Record<string, unknown>;
  // dataset_retrieval
  dataset_ids?: number[];
  retrieval_config?: RetrievalConfig;
  // http_request
  url?: string;
  method?: HttpMethod;
  // code
  code?: string;
  // 服务端回填（只读展示）
  meta?: NodeMeta;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  source_type: NodeType;
  target: string;
  target_type: NodeType;
}

export interface DraftGraph {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

/** 工作流（列表项 / 详情，对齐 serialize_workflow）。 */
export interface Workflow {
  id: number;
  name: string;
  tool_call_name: string;
  icon: string;
  description: string;
  status: WorkflowStatus;
  is_debug_passed: boolean;
  node_count: number;
  published_at: number | null;
  created_at: number | null;
  updated_at: number | null;
}

export interface CreateWorkflowReq {
  name: string;
  tool_call_name: string;
  icon?: string;
  description: string;
}

export interface UpdateWorkflowReq {
  name?: string;
  tool_call_name?: string;
  icon?: string;
  description?: string;
}

/** 调试 SSE 的单节点结果帧（event: workflow 的 data；对齐后端 NodeResult + id）。 */
export interface WorkflowDebugFrame {
  id: string;
  node_data: WorkflowNode;
  status: NodeRunStatus;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  latency: number;
  error: string;
}

// ---------------- 变量构造助手（与原编辑器同源） ----------------

/** 节点固定产出（generated）变量。 */
export function generatedVar(name: string, type: VariableType = "string"): VariableEntity {
  return { name, description: "", required: true, type, value: { type: "generated", content: "" }, meta: {} };
}

/** 字面量输入变量（面板新增一行时的默认）。 */
export function literalVar(name = "", type: VariableType = "string"): VariableEntity {
  return { name, description: "", required: true, type, value: { type: "literal", content: "" }, meta: {} };
}

/** 开始节点的输入声明（无 value，仅类型/必填/描述）。 */
export function declareVar(name = "", type: VariableType = "string"): VariableEntity {
  return { name, description: "", required: true, type, value: { type: "generated", content: "" }, meta: {} };
}
