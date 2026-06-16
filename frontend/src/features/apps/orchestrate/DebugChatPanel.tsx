import { RotateCcw } from "lucide-react";

import { ChatPanel } from "@/features/chat/ChatPanel";
import { historyToMessages, type HistoryRound } from "@/features/chat/chat-core";
import { useChatStream } from "@/features/chat/use-chat-stream";
import { get, post } from "@/lib/http/client";
import type { PageResult } from "@/types/api";

/** 编排页右栏：对当前草稿配置的调试预览（SSE 流式）。复用通用聊天内核，仅端点带 app_id。 */
export function DebugChatPanel({ appId }: { appId: number }) {
  const { messages, streaming, sendMessage, stopGenerating, clearConversation } = useChatStream({
    chatUrl: `/apps/${appId}/conversations`,
    buildBody: (query) => ({ query }),
    fetchHistory: async () => {
      const page = await get<PageResult<HistoryRound>>(`/apps/${appId}/conversations/messages`, {
        params: { current_page: 1, page_size: 20, created_at: 0 },
      });
      return historyToMessages(page.list);
    },
    stopTask: (taskId) =>
      post(`/apps/${appId}/conversations/tasks/${encodeURIComponent(taskId)}/stop`),
    clearConversation: () => post(`/apps/${appId}/conversations/delete-debug-conversation`),
  });

  const header = (
    <header className="flex items-center justify-between gap-3 border-b px-4 py-3">
      <p className="text-sm font-medium">调试预览</p>
      {messages.length > 0 && (
        <button
          type="button"
          onClick={() => void clearConversation()}
          aria-label="清空调试对话"
          title="清空调试对话"
          className="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <RotateCcw className="h-4 w-4" />
        </button>
      )}
    </header>
  );

  return (
    <ChatPanel
      messages={messages}
      streaming={streaming}
      onSend={sendMessage}
      onStop={stopGenerating}
      header={header}
      emptyState={
        <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center text-sm text-muted-foreground">
          <p>在此预览当前草稿配置的对话效果。</p>
          <p className="text-xs">改完配置记得先「保存草稿」，调试读取的是已保存的草稿。</p>
        </div>
      }
      footerNote={
        <p className="pt-2 text-center text-[10px] tracking-wider text-muted-foreground/70">
          调试对话读取草稿配置 · 回答由 AI 生成
        </p>
      }
    />
  );
}
