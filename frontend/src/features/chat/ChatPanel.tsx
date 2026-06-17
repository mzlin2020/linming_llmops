import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import type { ChatMessage } from "./chat-core";
import { Composer } from "./Composer";
import { MessageItem } from "./MessageItem";
import { useAutoScroll } from "./use-auto-scroll";

interface Props {
  messages: ChatMessage[];
  streaming: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
  /** 顶部栏（标题/清空按钮等），由调用方按场景拼装。 */
  header?: ReactNode;
  /** 无消息时展示的空状态。 */
  emptyState: ReactNode;
  /** 输入框下方脚注（免责声明等）。 */
  footerNote?: ReactNode;
  /** 回答后的建议追问；非空且非流式时在输入框上方渲染为可点 chips。 */
  followups?: string[];
  /** 点击某条建议追问（通常即以该文本发送）。 */
  onPickFollowup?: (q: string) => void;
  className?: string;
}

/**
 * 通用聊天面板：头部 + 消息列表（吸底滚动）+ 输入区。
 * 端点/状态由调用方经 useChatStream 提供并传入；首页辅助 Agent 与应用编排调试聊天共用。
 */
export function ChatPanel({
  messages,
  streaming,
  onSend,
  onStop,
  header,
  emptyState,
  footerNote,
  followups,
  onPickFollowup,
  className,
}: Props) {
  const { ref: listRef } = useAutoScroll<HTMLDivElement>([messages]);

  return (
    <div className={cn("flex h-full w-full flex-col", className)}>
      {header}
      <div ref={listRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4">
        {messages.length === 0 ? (
          emptyState
        ) : (
          <div className="space-y-5">
            {messages.map((m) => (
              <MessageItem key={m.key} message={m} />
            ))}
          </div>
        )}
      </div>
      <div className="border-t px-3 pb-[max(env(safe-area-inset-bottom),12px)] pt-3 sm:px-4">
        {followups && followups.length > 0 && !streaming ? (
          <div className="mb-2 flex flex-wrap gap-1.5">
            {followups.map((q, i) => (
              <button
                key={i}
                type="button"
                onClick={() => onPickFollowup?.(q)}
                className="rounded-full border border-border/70 bg-muted/30 px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:bg-primary/5 hover:text-foreground"
              >
                {q}
              </button>
            ))}
          </div>
        ) : null}
        <Composer streaming={streaming} onSend={onSend} onStop={onStop} />
        {footerNote}
      </div>
    </div>
  );
}
