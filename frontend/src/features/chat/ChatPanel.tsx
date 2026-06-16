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
        <Composer streaming={streaming} onSend={onSend} onStop={onStop} />
        {footerNote}
      </div>
    </div>
  );
}
