import { RotateCcw } from "lucide-react";

import { AiBadge } from "./AiBadge";
import { Composer } from "./Composer";
import { EmptyState } from "./EmptyState";
import { MessageItem } from "./MessageItem";
import { useAssistantChat } from "./use-assistant-chat";
import { useAutoScroll } from "./use-auto-scroll";

/** 首页内嵌的辅助 Agent 流式聊天（去品牌科技质感，整页填充 AppShell 主区）。 */
export function AssistantChat() {
  const { messages, streaming, sendMessage, stopGenerating, clearConversation } =
    useAssistantChat();
  const { ref: listRef } = useAutoScroll<HTMLDivElement>([messages]);

  return (
    <div className="mx-auto flex h-full w-full max-w-3xl flex-col">
      <header className="flex items-center gap-3 border-b px-4 py-3">
        <AiBadge className="size-8 rounded-lg text-xs" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">AI 助手</p>
          <p className="flex items-center gap-1.5 font-mono text-[10px] tracking-widest text-muted-foreground">
            <span className="size-1.5 rounded-full bg-emerald-500" />
            ONLINE
          </p>
        </div>
        {messages.length > 0 && (
          <button
            type="button"
            onClick={() => void clearConversation()}
            aria-label="清空对话"
            title="清空对话"
            className="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <RotateCcw className="h-4 w-4" />
          </button>
        )}
      </header>

      <div
        ref={listRef}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4"
      >
        {messages.length === 0 ? (
          <EmptyState onAsk={sendMessage} />
        ) : (
          <div className="space-y-5">
            {messages.map((m) => (
              <MessageItem key={m.key} message={m} />
            ))}
          </div>
        )}
      </div>

      <div className="border-t px-3 pb-[max(env(safe-area-inset-bottom),12px)] pt-3 sm:px-4">
        <Composer streaming={streaming} onSend={sendMessage} onStop={stopGenerating} />
        <p className="pt-2 text-center font-mono text-[10px] tracking-wider text-muted-foreground/70">
          回答由 AI 生成，仅供参考
        </p>
      </div>
    </div>
  );
}
