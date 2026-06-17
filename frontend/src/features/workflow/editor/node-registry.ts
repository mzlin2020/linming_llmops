/**
 * 节点注册表：8 种节点的元数据 + 默认 data 工厂。
 * 默认 data 的固定 outputs/inputs 与后端实体校验器一致（见 backend nodes/*_entity.py）。
 */
import {
  BookMarked,
  Braces,
  CircleStop,
  Code2,
  Globe,
  Play,
  Sparkles,
  Wrench,
  type LucideIcon,
} from "lucide-react";

import { generatedVar, literalVar, type NodeType, type WorkflowNode } from "@/types/workflows";

export interface NodeDef {
  label: string;
  hint: string;
  icon: LucideIcon;
  /** 全图唯一（start / end）。 */
  unique?: boolean;
  /** 默认 data（不含 id / title / position，由 store 组装）。 */
  createData: () => Partial<WorkflowNode>;
}

export const NODE_DEFS: Record<NodeType, NodeDef> = {
  start: {
    label: "开始",
    hint: "定义工作流入参",
    icon: Play,
    unique: true,
    createData: () => ({ node_type: "start", inputs: [] }),
  },
  end: {
    label: "结束",
    hint: "定义工作流输出",
    icon: CircleStop,
    unique: true,
    createData: () => ({ node_type: "end", outputs: [] }),
  },
  llm: {
    label: "大语言模型",
    hint: "用提示词调用模型",
    icon: Sparkles,
    createData: () => ({
      node_type: "llm",
      prompt: "",
      model_config: { provider: "", model: "", parameters: {} },
      inputs: [],
      outputs: [generatedVar("output")],
    }),
  },
  template_transform: {
    label: "模板转换",
    hint: "Jinja2 模板拼接文本",
    icon: Braces,
    createData: () => ({
      node_type: "template_transform",
      template: "",
      inputs: [],
      outputs: [generatedVar("output")],
    }),
  },
  tool: {
    label: "扩展插件",
    hint: "调用内置/自定义 API 工具",
    icon: Wrench,
    createData: () => ({
      node_type: "tool",
      type: "",
      provider_id: "",
      tool_id: "",
      params: {},
      inputs: [],
      outputs: [generatedVar("text")],
    }),
  },
  dataset_retrieval: {
    label: "知识库检索",
    hint: "从知识库检索相关片段",
    icon: BookMarked,
    createData: () => ({
      node_type: "dataset_retrieval",
      dataset_ids: [],
      retrieval_config: { retrieval_strategy: "semantic", k: 4, score: 0 },
      inputs: [{ ...literalVar("query", "string") }],
      outputs: [generatedVar("combine_documents")],
    }),
  },
  http_request: {
    label: "HTTP 请求",
    hint: "调用外部 HTTP 接口",
    icon: Globe,
    createData: () => ({
      node_type: "http_request",
      url: "",
      method: "get",
      inputs: [],
      outputs: [generatedVar("status_code", "int"), generatedVar("text")],
    }),
  },
  code: {
    label: "Python 代码",
    hint: "在沙箱中执行 Python",
    icon: Code2,
    createData: () => ({
      node_type: "code",
      code: "def main(params):\n    return params\n",
      inputs: [],
      outputs: [],
    }),
  },
};

/** 添加面板按此顺序列出（start/end 在两端）。 */
export const ADDABLE_NODE_TYPES: NodeType[] = [
  "llm",
  "template_transform",
  "tool",
  "dataset_retrieval",
  "http_request",
  "code",
  "start",
  "end",
];

export function nodeLabel(type: NodeType): string {
  return NODE_DEFS[type]?.label ?? type;
}
