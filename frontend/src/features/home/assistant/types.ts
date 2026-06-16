/** 辅助 Agent 聊天的前端类型。后端契约见 backend/internal/{schema,entity} 与 assistant_agent_*。 */

export type MessageRole = "user" | "assistant";

/** UI 气泡状态。注意：UI 一条 = 一个气泡，后端「一轮 = query + answer」加载时拆成两条。 */
export type MessageStatus = "sending" | "streaming" | "done" | "error" | "stopped";

export interface ChatMessage {
  /** 渲染稳定 key（历史用 round id 派生，新发用时间戳派生）。 */
  key: string;
  role: MessageRole;
  content: string;
  status: MessageStatus;
}

/** GET /assistant-agent/messages 单条出参（一轮）。对齐后端 MessageItem，仅取本阶段所需字段。 */
export interface HistoryRound {
  id: number;
  query: string;
  answer: string;
  /** normal | stop | error */
  status: string;
  error: string;
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

export interface ErrorData {
  message: string;
  message_id?: number;
}
