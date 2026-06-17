import { useState } from "react";
import { Brain, RotateCcw } from "lucide-react";

import { ChatEmptyState } from "@/features/chat/ChatEmptyState";
import { ChatPanel } from "@/features/chat/ChatPanel";
import { historyToMessages, type HistoryRound } from "@/features/chat/chat-core";
import { useChatStream } from "@/features/chat/use-chat-stream";
import { useFollowups } from "@/features/chat/use-followups";
import { get, post } from "@/lib/http/client";
import type { PageResult } from "@/types/api";

import { LongTermMemoryModal } from "./LongTermMemoryModal";

interface Props {
  appId: number;
  /** 当前草稿配置的开场白 / 开场问题：空会话态在聊天框里展示（可点击发送）。 */
  openingStatement?: string;
  openingQuestions?: string[];
  /** 是否开启长期记忆：开启时头部「长期记忆」按钮可点（查看/编辑滚动摘要）。 */
  longTermMemoryEnabled?: boolean;
  /** 是否在回答后生成建议追问（草稿配置的 suggested_after_answer）。 */
  suggestAfterAnswer?: boolean;
}

/** 编排页右栏：对当前草稿配置的调试预览（SSE 流式）。复用通用聊天内核，仅端点带 app_id。 */
export function DebugChatPanel({
  appId,
  openingStatement,
  openingQuestions,
  longTermMemoryEnabled,
  suggestAfterAnswer,
}: Props) {
  const [memoryOpen, setMemoryOpen] = useState(false);
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

  const followups = useFollowups({ messages, streaming, enabled: !!suggestAfterAnswer });

  const header = (
    <header className="flex items-center justify-between gap-3 border-b px-4 py-3">
      <p className="text-sm font-medium">调试预览</p>
      <div className="flex items-center gap-1">
        <button
          type="button"
          disabled={!longTermMemoryEnabled}
          onClick={() => setMemoryOpen(true)}
          aria-label="查看长期记忆"
          title={longTermMemoryEnabled ? "查看 / 编辑长期记忆" : "开启长期记忆后可查看"}
          className="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"
        >
          <Brain className="h-4 w-4" />
        </button>
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
      </div>
    </header>
  );

  return (
    <>
      <ChatPanel
        messages={messages}
        streaming={streaming}
        onSend={sendMessage}
        onStop={stopGenerating}
        followups={followups}
        onPickFollowup={(q) => void sendMessage(q)}
        header={header}
        emptyState={
          <ChatEmptyState
            openingStatement={openingStatement}
            openingQuestions={openingQuestions}
            onPick={(q) => void sendMessage(q)}
            fallback={
              <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center text-sm text-muted-foreground">
                <p>在此预览当前草稿配置的对话效果。</p>
                <p className="text-xs">配置改动会自动保存，调试读取的是最新草稿。</p>
              </div>
            }
          />
        }
        footerNote={
          <p className="pt-2 text-center text-[10px] tracking-wider text-muted-foreground/70">
            调试对话读取草稿配置 · 回答由 AI 生成
          </p>
        }
      />
      <LongTermMemoryModal appId={appId} open={memoryOpen} onClose={() => setMemoryOpen(false)} />
    </>
  );
}
