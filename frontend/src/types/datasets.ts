/** 知识库（RAG）模块前端类型。后端契约见 backend/internal/{schema,service,entity} 的 dataset / document / segment。 */

/** 检索策略（对齐后端 RetrievalStrategy）。 */
export type RetrievalStrategy = "semantic" | "full_text" | "hybrid";

/** 文档索引状态机（对齐后端 DocumentStatus）。 */
export type DocumentStatus =
  | "waiting"
  | "parsing"
  | "splitting"
  | "indexing"
  | "completed"
  | "error";

/** 片段索引状态机（对齐后端 SegmentStatus）。 */
export type SegmentStatus = "waiting" | "indexing" | "completed" | "error";

/** 文档处理模式（对齐后端 ProcessType）。 */
export type ProcessType = "automatic" | "custom";

/** 知识库（GET /datasets 列表项 & GET /datasets/<id>）。 */
export interface Dataset {
  id: number;
  name: string;
  icon: string;
  description: string;
  document_count: number;
  character_count: number;
  hit_count: number;
  created_at: number;
  updated_at: number;
}

/** 创建/更新知识库请求体。 */
export interface DatasetUpsert {
  name: string;
  icon: string;
  description: string;
}

/** 上传文件登记记录（POST /upload-files/file）。 */
export interface UploadFile {
  id: number;
  name: string;
  key: string;
  size: number;
  extension: string;
  mime_type: string;
  created_at: number;
}

/** 文档（GET /datasets/<id>/documents 列表项）。 */
export interface AiDocument {
  id: number;
  dataset_id: number;
  name: string;
  position: number;
  character_count: number;
  token_count: number;
  segment_count: number;
  hit_count: number;
  enabled: boolean;
  status: DocumentStatus;
  error: string;
  batch: string;
  created_at: number;
}

/** 切分预处理规则项。 */
export interface PreProcessRule {
  id: "remove_extra_space" | "remove_url_and_email";
  enabled: boolean;
}

/** 文档切分规则（custom 模式提交，automatic 模式后端用默认）。 */
export interface ProcessRule {
  pre_process_rules: PreProcessRule[];
  segment: {
    separators: string[];
    chunk_size: number;
    chunk_overlap: number;
  };
}

/** 批量建文档请求体。 */
export interface CreateDocumentsReq {
  upload_file_ids: number[];
  process_type: ProcessType;
  rule?: ProcessRule;
}

/** 批量建文档结果。 */
export interface CreateDocumentsResult {
  documents: AiDocument[];
  batch: string;
}

/** 片段（GET .../segments 列表项 & 增改返回）。 */
export interface Segment {
  id: number;
  document_id: number;
  dataset_id: number;
  position: number;
  content: string;
  keywords: string[];
  character_count: number;
  token_count: number;
  hit_count: number;
  enabled: boolean;
  status: SegmentStatus;
  error: string;
  created_at: number;
}

/** 创建/更新片段请求体。 */
export interface SegmentUpsert {
  content: string;
  keywords?: string[];
}

/** 命中测试请求体。 */
export interface HitReq {
  query: string;
  retrieval_strategy: RetrievalStrategy;
  k: number;
  score: number;
}

/** 命中测试结果项。 */
export interface HitResult {
  id: number;
  document: { id: number; name: string } | null;
  dataset_id: number;
  score: number;
  position: number;
  content: string;
  keywords: string[];
  character_count: number;
  token_count: number;
  hit_count: number;
  enabled: boolean;
}

/** 知识库查询历史项。 */
export interface DatasetQuery {
  id: number;
  query: string;
  source: string;
  created_at: number;
}

/** 单应用最多关联的知识库数（对齐后端 _MAX_DATASETS）。 */
export const MAX_DATASETS = 5;

/** automatic 模式默认切分规则（镜像后端 DEFAULT_PROCESS_RULE.rule）。custom 模式以此为初值。 */
export const DEFAULT_PROCESS_RULE: ProcessRule = {
  pre_process_rules: [
    { id: "remove_extra_space", enabled: true },
    { id: "remove_url_and_email", enabled: true },
  ],
  segment: {
    separators: ["\n\n", "\n", "。|！|？", "\\.\\s|\\!\\s|\\?\\s", "；|;\\s", "，|,\\s", " ", ""],
    chunk_size: 500,
    chunk_overlap: 50,
  },
};

/**
 * 自定义切分规则的前端校验（对齐参考 segment-settings-step，提交前拦非法值）。
 * 返回错误文案；通过返回 null。automatic 模式用后端默认、无需校验。
 */
export function validateProcessRule(rule: ProcessRule): string | null {
  const { chunk_size, chunk_overlap, separators } = rule.segment;
  if (!Number.isFinite(chunk_size) || chunk_size < 1) return "分段最大长度需大于 0";
  if (!Number.isFinite(chunk_overlap) || chunk_overlap < 0 || chunk_overlap >= chunk_size)
    return "分段重叠长度需 ≥ 0 且小于分段最大长度";
  if (separators.filter((s) => s !== "").length === 0) return "请至少保留一个分隔符";
  return null;
}

/** 上传文件默认 accept（仅客户端提示；后端 UPLOAD_ALLOWED_EXTENSIONS 为准）。 */
export const UPLOAD_ACCEPT_EXTENSIONS = ["txt", "md", "markdown", "pdf", "docx", "csv", "xlsx"];
