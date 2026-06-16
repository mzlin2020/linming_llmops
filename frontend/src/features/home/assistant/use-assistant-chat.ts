import { useChatStream } from "@/features/chat/use-chat-stream";

import { CHAT_URL, clearConversation, fetchHistory, stopTask } from "./api";

// reducer / isStreaming 收口在 chat-core，转出以保持既有引用路径与单测不变。
export { isStreaming, reducer } from "@/features/chat/chat-core";

/**
 * 辅助 Agent 聊天 hook：把通用 useChatStream 绑到 /assistant-agent/* 单会话端点。
 * 历史/停止/清空由 ./api 注入；请求体仅带 query（服务端单会话，无需 conversation_id）。
 */
export function useAssistantChat() {
  return useChatStream({
    chatUrl: CHAT_URL,
    buildBody: (query) => ({ query }),
    fetchHistory,
    stopTask,
    clearConversation,
  });
}
