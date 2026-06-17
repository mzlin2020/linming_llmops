import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Sparkles } from "lucide-react";

const REMARK_PLUGINS = [remarkGfm];

interface Props {
  /** 开场白：有内容时仿「助手首条消息」渲染在顶部。 */
  openingStatement?: string;
  /** 开场建议问题：渲染成可点击气泡，点击即作为首条消息发送。 */
  openingQuestions?: string[];
  /** 既无开场白也无开场问题时回退到各界面自带的占位内容。 */
  fallback: ReactNode;
  onPick: (q: string) => void;
}

/**
 * 空会话态：配了开场白/开场问题就仿「助手首条消息 + 可点击建议问题」，否则回退到各界面占位。
 * 首页助手与应用编排调试聊天共用（对齐源站 chat-empty-state）。
 */
export function ChatEmptyState({ openingStatement, openingQuestions, fallback, onPick }: Props) {
  const statement = (openingStatement || "").trim();
  const questions = (openingQuestions || []).map((q) => q.trim()).filter(Boolean);

  if (!statement && questions.length === 0) return <>{fallback}</>;

  return (
    <div className="space-y-3 duration-300 animate-in fade-in">
      {statement ? (
        <div className="flex gap-3">
          <div
            aria-hidden
            className="mt-0.5 hidden size-8 shrink-0 select-none items-center justify-center rounded-full bg-primary/10 ring-1 ring-primary/20 sm:flex"
          >
            <Sparkles className="size-4 text-primary" />
          </div>
          <div className="min-w-0 flex-1 text-[15px] leading-relaxed text-foreground/85 [&_p]:my-1 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0">
            <ReactMarkdown remarkPlugins={REMARK_PLUGINS}>{statement}</ReactMarkdown>
          </div>
        </div>
      ) : null}

      {questions.length > 0 ? (
        <div className="flex flex-col items-start gap-2 sm:pl-11">
          {questions.map((q, i) => (
            <button
              key={i}
              type="button"
              onClick={() => onPick(q)}
              className="max-w-full rounded-2xl border border-border/70 bg-background px-3.5 py-2 text-left text-sm text-foreground/80 transition-colors hover:border-primary/40 hover:bg-primary/[0.04] hover:text-foreground"
            >
              {q}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
