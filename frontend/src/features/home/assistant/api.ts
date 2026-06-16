import { historyToMessages } from "@/features/chat/chat-core";
import { get, post } from "@/lib/http/client";
import type { PageResult } from "@/types/api";

import type { ChatMessage, HistoryRound } from "./types";

/** SSE 流式聊天端点（POST，经 streamSSE，不走 axios）。 */
export const CHAT_URL = "/assistant-agent/chat";

/** 拆轮纯函数收口在 chat-core，转出以保持既有引用路径与单测不变。 */
export { historyToMessages };

/** 拉当前会话最新一页历史；无会话时后端返回空页。 */
export async function fetchHistory(): Promise<ChatMessage[]> {
  const page = await get<PageResult<HistoryRound>>("/assistant-agent/messages", {
    params: { current_page: 1, page_size: 20, created_at: 0 },
  });
  return historyToMessages(page.list);
}

/** 清空当前会话（软删）。 */
export function clearConversation(): Promise<unknown> {
  return post("/assistant-agent/delete-conversation");
}

/**
 * 真实停止：按 task_id 置停止 flag（best-effort，调用点忽略失败）。
 * 仅 Agent 工具路径有效；裸 LLM 流无 task 登记，后端为 no-op，靠客户端 abort 收尾。
 */
export function stopTask(taskId: string): Promise<unknown> {
  return post(`/assistant-agent/chat/${encodeURIComponent(taskId)}/stop`);
}
