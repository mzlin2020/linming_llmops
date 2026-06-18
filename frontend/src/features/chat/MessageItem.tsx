import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { FileText } from "lucide-react";

import { cn } from "@/lib/utils";

import { AiBadge } from "./AiBadge";
import type { ChatMessage } from "./chat-core";
import { ThinkingIndicator } from "./ThinkingIndicator";

// 模块级常量：避免每次渲染新建数组（MessageItem 已 memo，新数组会削弱其稳定性）。
const REMARK_PLUGINS = [remarkGfm];

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

/** user 气泡上方附件区：图片缩略图（点击新开原图）+ 文档 chip（点击打开/下载）。 */
function UserAttachments({ message }: { message: ChatMessage }) {
  const images = message.imageUrls ?? [];
  const files = message.fileInfos ?? [];
  if (images.length === 0 && files.length === 0) return null;
  return (
    <div className="flex max-w-[82%] flex-wrap justify-end gap-1.5">
      {images.map((url) => (
        <a key={url} href={url} target="_blank" rel="noreferrer">
          <img
            src={url}
            alt="附件图片"
            loading="lazy"
            className="size-24 rounded-xl border border-border/60 object-cover sm:size-28"
          />
        </a>
      ))}
      {files.map((f) => (
        <a
          key={f.url}
          href={f.url}
          target="_blank"
          rel="noreferrer"
          title={f.name}
          className="flex max-w-[200px] items-center gap-1.5 rounded-lg border border-border/60 bg-muted/40 px-2.5 py-1.5 text-xs text-foreground/80 transition-colors hover:border-primary/40"
        >
          <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <span className="truncate">{f.name}</span>
        </a>
      ))}
    </div>
  );
}

/** 助手气泡下方：工具（文生图/图生图）产出的图片缩略图（点击新开原图）。
 * 过滤掉已出现在正文 markdown 里的 URL，避免模型复述时与正文图重复渲染。 */
function GeneratedImages({ message }: { message: ChatMessage }) {
  const urls = (message.generatedImages ?? []).filter((u) => !message.content.includes(u));
  if (urls.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {urls.map((url) => (
        <a key={url} href={url} target="_blank" rel="noreferrer">
          <img
            src={url}
            alt="生成图片"
            loading="lazy"
            className="max-h-64 max-w-full rounded-xl border border-border/60 object-contain"
          />
        </a>
      ))}
    </div>
  );
}

// memo：流式期间只有末条消息引用在变，历史消息不必随每个 delta 重渲（Markdown 解析不便宜）。
export const MessageItem = memo(function MessageItem({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex flex-col items-end gap-1.5">
        <UserAttachments message={message} />
        {message.content ? (
          <div className="max-w-[82%] whitespace-pre-wrap break-words rounded-2xl rounded-tr-md border border-primary/20 bg-primary/5 px-4 py-2.5 text-[15px] leading-relaxed text-foreground/90">
            {message.content}
          </div>
        ) : null}
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
          <ThinkingIndicator />
        ) : (
          <div className={cn(MARKDOWN_PROSE, message.status === "error" && "text-destructive/90")}>
            <ReactMarkdown remarkPlugins={REMARK_PLUGINS}>{message.content}</ReactMarkdown>
          </div>
        )}
        <GeneratedImages message={message} />
      </div>
    </div>
  );
});
