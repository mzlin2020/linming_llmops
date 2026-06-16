/**
 * 首页辅助 Agent 聊天的前端类型。通用聊天类型（ChatMessage/状态/SSE 载荷/HistoryRound）
 * 收口在 @/features/chat/chat-core，本文件仅做转出，保持既有引用路径不变。
 */
export type {
  AgentEndData,
  ChatMessage,
  ErrorData,
  HistoryRound,
  MessageDeltaData,
  MessageRole,
  MessageStatus,
  PingData,
} from "@/features/chat/chat-core";
