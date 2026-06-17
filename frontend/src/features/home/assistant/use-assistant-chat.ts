import { useChatStream } from "@/features/chat/use-chat-stream";
import { useAiModelStore } from "@/stores/ai-model-store";

import { CHAT_URL, clearConversation, fetchHistory, stopTask } from "./api";

// reducer / isStreaming 收口在 chat-core，转出以保持既有引用路径与单测不变。
export { isStreaming, reducer } from "@/features/chat/chat-core";

/**
 * 辅助 Agent 聊天 hook：把通用 useChatStream 绑到 /assistant-agent/* 单会话端点。
 * 历史/停止/清空由 ./api 注入；服务端单会话，无需 conversation_id。
 * 请求体带 query；若用户在头部 ModelPicker 选了模型，附 provider/model 覆盖本轮（成对才发）。
 */
export function useAssistantChat() {
  return useChatStream({
    chatUrl: CHAT_URL,
    buildBody: (query) => {
      const { provider, model } = useAiModelStore.getState();
      return provider && model ? { query, provider, model } : { query };
    },
    fetchHistory,
    stopTask,
    clearConversation,
  });
}
