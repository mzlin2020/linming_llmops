import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";

import { AiBadge } from "./AiBadge";
import type { ChatMessage } from "./types";

/** 助手 Markdown 排版：无 typography 插件，用 arbitrary variants 自带一套紧凑样式。 */
const MARKDOWN_PROSE = cn(
  "max-w-none text-[15px] leading-relaxed text-foreground/85",
  "[&_p]:my-2 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0",
  "[&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-0.5",
  "[&_a]:text-primary [&_a]:underline [&_a]:underline-offset-2",
  "[&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:text-[0.9em]",
  "[&_pre]:my-2 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-muted [&_pre]:p-3",
  "[&_pre_code]:bg-transparent [&_pre_code]:p-0",
  "[&_h1]:mb-1 [&_h1]:mt-3 [&_h1]:text-lg [&_h1]:font-semibold",
  "[&_h2]:mb-1 [&_h2]:mt-3 [&_h2]:text-base [&_h2]:font-semibold",
  "[&_h3]:mb-1 [&_h3]:mt-2 [&_h3]:font-semibold",
  "[&_blockquote]:border-l-2 [&_blockquote]:border-border [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground",
);

/** 流式光标：去品牌的等宽闪烁竖条（用 Tailwind animate-pulse，无需额外 CSS）。 */
function Caret() {
  return (
    <span
      aria-hidden
      className="ml-0.5 inline-block h-[1.05em] w-[2px] translate-y-[2px] animate-pulse bg-primary align-text-bottom"
    />
  );
}

// memo：流式期间只有末条消息引用在变，历史消息不必随每个 delta 重渲（Markdown 解析不便宜）。
export const MessageItem = memo(function MessageItem({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[82%] whitespace-pre-wrap break-words rounded-2xl rounded-tr-md border border-primary/20 bg-primary/5 px-4 py-2.5 text-[15px] leading-relaxed text-foreground/90">
          {message.content}
        </div>
      </div>
    );
  }

  const streaming = message.status === "sending" || message.status === "streaming";
  const thinking = !message.content && streaming;

  return (
    <div className="flex gap-3">
      <AiBadge className="hidden size-8 shrink-0 rounded-lg text-xs sm:flex" />
      <div className="min-w-0 flex-1 pt-0.5">
        {thinking ? (
          <p className="font-mono text-sm text-muted-foreground">
            正在思考
            <Caret />
          </p>
        ) : (
          <div className={cn(MARKDOWN_PROSE, message.status === "error" && "text-destructive/90")}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            {streaming && <Caret />}
          </div>
        )}
      </div>
    </div>
  );
});
