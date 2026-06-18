/**
 * 聊天内核：UI 气泡类型 + reducer + 流式态判定 + 历史拆轮 + SSE 载荷类型。
 * 与具体端点无关，供首页辅助 Agent 与应用编排调试聊天共用（端点差异在 use-chat-stream 注入）。
 * 后端契约见 backend/internal/{schema,entity} 的 chat / conversation。
 */

export type MessageRole = "user" | "assistant";

/** UI 气泡状态。注意：UI 一条 = 一个气泡，后端「一轮 = query + answer」加载时拆成两条。 */
export type MessageStatus = "sending" | "streaming" | "done" | "error" | "stopped";

/** 文档附件元数据（对齐后端 MessageItem.file_infos 的 {url,name,extension}）。 */
export interface ChatFileInfo {
  url: string;
  name: string;
  extension?: string;
}

export interface ChatMessage {
  /** 渲染稳定 key（历史用 round id 派生，新发用时间戳派生）。 */
  key: string;
  role: MessageRole;
  content: string;
  status: MessageStatus;
  /** 后端消息（轮）id：助手气泡完成后回填，供「建议追问」按 message_id 拉 follow-up。 */
  id?: number;
  /** 本轮图片附件 URL（仅 user 气泡：缩略图渲染）。 */
  imageUrls?: string[];
  /** 本轮文档附件元数据（仅 user 气泡：文件 chip 渲染）。 */
  fileInfos?: ChatFileInfo[];
  /** 工具（文生图/图生图）在本轮 agent_action 里产出的图片 URL（仅 assistant 气泡）。
   * 这些图片只在 observation 里，不一定被模型复述进最终答案，故单独挂出来渲染。 */
  generatedImages?: string[];
}

/** 消息分页出参的一轮（对齐后端 MessageItem，仅取本期所需字段）。 */
export interface HistoryRound {
  id: number;
  query: string;
  answer: string;
  /** normal | stop | error */
  status: string;
  error: string;
  /** 本轮用户图片附件 URL。 */
  image_urls?: string[];
  /** 本轮用户文档附件元数据。 */
  file_infos?: ChatFileInfo[];
}

/** SSE data 载荷（QueueEvent，见 backend/internal/entity/chat_entity.py）。 */
export interface PingData {
  task_id: string;
}

export interface MessageDeltaData {
  conversation_id: number;
  message_id: number;
  delta: string;
}

export interface AgentEndData {
  conversation_id: number;
  message_id: number;
  total_token_count: number;
  latency: number;
  status: "normal" | "stop" | "error";
}

export interface AgentActionData {
  conversation_id: number;
  message_id: number;
  position: number;
  tool: string;
  /** 工具执行结果（文生图工具返回 markdown 图片字符串）。 */
  observation: string;
}

export interface ErrorData {
  message: string;
  message_id?: number;
}

/** 从工具 observation 文本里抽取 markdown 图片语法 `![alt](url)` 的 URL（纯函数，便于单测）。
 * 仅匹配带感叹号的图片语法，普通链接 `[text](url)` 与纯文本都不会被抽取，
 * 因此只有文生图/图生图这类返回图片 markdown 的工具会贡献结果，不会把别的工具的文本输出倒进对话。 */
const IMAGE_MD_RE = /!\[[^\]]*\]\(([^)\s]+)\)/g;

export function extractImageUrls(observation: string): string[] {
  if (!observation) return [];
  const out: string[] = [];
  for (const m of observation.matchAll(IMAGE_MD_RE)) {
    if (m[1]) out.push(m[1]);
  }
  return out;
}

export interface ChatState {
  messages: ChatMessage[];
}

export const initialState: ChatState = { messages: [] };

export type Action =
  | { type: "INIT"; messages: ChatMessage[] }
  | { type: "PUSH_PAIR"; user: ChatMessage; assistant: ChatMessage }
  | { type: "APPEND_DELTA"; delta: string }
  | { type: "ADD_GENERATED_IMAGES"; urls: string[] }
  | { type: "FINISH_ASSISTANT"; status?: ChatMessage["status"]; messageId?: number }
  | { type: "ERROR_ASSISTANT"; message: string }
  | { type: "STOP_ASSISTANT" }
  | { type: "CLEAR" };

/** 流式态判定（sending/streaming），供 isStreaming 与收尾守卫共用，避免多处重复状态字面量。 */
function isStreamingStatus(status: MessageStatus): boolean {
  return status === "sending" || status === "streaming";
}

/** 是否正在流式：由末条助手消息状态推导，不另存标志位（免去各分支同步它）。 */
export function isStreaming(messages: ChatMessage[]): boolean {
  const last = messages[messages.length - 1];
  return !!last && last.role === "assistant" && isStreamingStatus(last.status);
}

function patchLastAssistant(
  state: ChatState,
  patch: (last: ChatMessage) => ChatMessage,
): ChatMessage[] {
  const messages = state.messages.slice();
  const last = messages[messages.length - 1];
  if (last && last.role === "assistant") messages[messages.length - 1] = patch(last);
  return messages;
}

/**
 * 仅当末条助手仍在流式态时套用 patch（late 帧/重复收尾不误改已终态的消息）。
 * 四类收尾 action（APPEND_DELTA / FINISH / ERROR / STOP）共用此守卫，免去逐分支重复。
 */
function patchStreamingAssistant(
  state: ChatState,
  patch: (last: ChatMessage) => ChatMessage,
): ChatState {
  return {
    ...state,
    messages: patchLastAssistant(state, (last) =>
      isStreamingStatus(last.status) ? patch(last) : last,
    ),
  };
}

export function reducer(state: ChatState, action: Action): ChatState {
  switch (action.type) {
    case "INIT":
      return { ...state, messages: action.messages };
    case "PUSH_PAIR":
      return { ...state, messages: [...state.messages, action.user, action.assistant] };
    case "APPEND_DELTA":
      return patchStreamingAssistant(state, (last) => ({
        ...last,
        content: last.content + action.delta,
        status: "streaming",
      }));
    case "ADD_GENERATED_IMAGES":
      return patchStreamingAssistant(state, (last) => ({
        ...last,
        // 去重并集：agent_action 可能多次到达，避免重复图片
        generatedImages: [...new Set([...(last.generatedImages ?? []), ...action.urls])],
      }));
    case "FINISH_ASSISTANT":
      return patchStreamingAssistant(state, (last) => ({
        ...last,
        status: action.status ?? "done",
        id: action.messageId ?? last.id,
      }));
    case "ERROR_ASSISTANT":
      return patchStreamingAssistant(state, (last) => ({
        ...last,
        content: last.content || action.message,
        status: "error",
      }));
    case "STOP_ASSISTANT":
      return patchStreamingAssistant(state, (last) => ({
        ...last,
        content: last.content + (last.content ? "\n\n" : "") + "（已停止生成）",
        status: "stopped",
      }));
    case "CLEAR":
      return { ...state, messages: [] };
    default:
      return state;
  }
}

/** 后端单轮状态 → UI 助手气泡状态。 */
function mapRoundStatus(status: string): MessageStatus {
  if (status === "stop") return "stopped";
  if (status === "error") return "error";
  return "done";
}

/**
 * 把后端「一轮」列表拆成正序的 UI 气泡序列：每轮 → user(query) + assistant(answer)。
 * 后端按 created_at 倒序返回，故先 reverse 成时间正序。纯函数，便于单测。
 */
export function historyToMessages(rounds: HistoryRound[]): ChatMessage[] {
  const out: ChatMessage[] = [];
  for (const r of [...rounds].reverse()) {
    out.push({
      key: `h-${r.id}-user`,
      role: "user",
      content: r.query,
      status: "done",
      imageUrls: r.image_urls ?? [],
      fileInfos: r.file_infos ?? [],
    });
    const status = mapRoundStatus(r.status);
    out.push({
      key: `h-${r.id}-assistant`,
      role: "assistant",
      content: r.answer || (status === "error" ? r.error : ""),
      status,
      id: r.id,
    });
  }
  return out;
}
