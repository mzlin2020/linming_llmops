import { RotateCcw } from "lucide-react";

import { AiBadge } from "@/features/chat/AiBadge";
import { ChatPanel } from "@/features/chat/ChatPanel";

import { EmptyState } from "./EmptyState";
import { ModelPicker } from "./ModelPicker";
import { useAssistantChat } from "./use-assistant-chat";

/** 首页内嵌的辅助 Agent 流式聊天（去品牌科技质感，整页填充 AppShell 主区）。 */
export function AssistantChat() {
  const { messages, streaming, sendMessage, stopGenerating, clearConversation } =
    useAssistantChat();

  const header = (
    <header className="flex items-center gap-2 border-b px-4 py-3">
      <AiBadge className="size-8 shrink-0 rounded-lg text-xs" />
      <div className="min-w-0">
        <p className="truncate text-sm font-medium leading-tight">AI 助手</p>
        <p className="flex items-center gap-1.5 font-mono text-[10px] tracking-widest text-muted-foreground">
          <span className="size-1.5 rounded-full bg-emerald-500" />
          ONLINE
        </p>
      </div>
      <ModelPicker className="ml-1" />
      {messages.length > 0 && (
        <button
          type="button"
          onClick={() => void clearConversation()}
          aria-label="清空对话"
          title="清空对话"
          className="ml-auto flex size-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <RotateCcw className="h-4 w-4" />
        </button>
      )}
    </header>
  );

  return (
    <ChatPanel
      className="mx-auto max-w-3xl"
      messages={messages}
      streaming={streaming}
      onSend={sendMessage}
      onStop={stopGenerating}
      header={header}
      emptyState={<EmptyState onAsk={sendMessage} />}
      footerNote={
        <p className="pt-2 text-center font-mono text-[10px] tracking-wider text-muted-foreground/70">
          回答由 AI 生成，仅供参考
        </p>
      }
    />
  );
}
