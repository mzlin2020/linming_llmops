import { AiBadge } from "@/features/chat/AiBadge";

/** 空状态内置建议问题（去品牌的通用集；后续可由编排/配置覆盖）。 */
const SUGGESTED = [
  "你能做什么？",
  "帮我写一段 Python 快速排序",
  "什么是 RAG？",
  "用一句话解释 Transformer",
];

export function EmptyState({ onAsk }: { onAsk: (q: string) => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-5 px-6 text-center">
      <AiBadge className="size-16 rounded-2xl text-2xl" />
      <div className="space-y-1.5">
        <p className="text-base text-foreground/90">嗨，我是你的 AI 助手 👋</p>
        <p className="text-sm text-muted-foreground">有什么可以帮你的吗？</p>
      </div>
      <div className="flex w-full max-w-md flex-col items-stretch gap-2">
        {SUGGESTED.map((q, i) => (
          <button
            key={q}
            type="button"
            onClick={() => onAsk(q)}
            style={{ animationDelay: `${i * 70}ms` }}
            className="animate-in fade-in slide-in-from-bottom-2 rounded-2xl border border-border/70 bg-background px-3.5 py-2 text-left text-sm text-foreground/80 transition-colors hover:border-primary/40 hover:bg-primary/[0.04] hover:text-foreground"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
