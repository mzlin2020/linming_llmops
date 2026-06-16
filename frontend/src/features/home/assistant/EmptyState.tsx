import { AiBadge } from "./AiBadge";

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
      <div className="flex flex-wrap items-center justify-center gap-2">
        {SUGGESTED.map((q, i) => (
          <button
            key={q}
            type="button"
            onClick={() => onAsk(q)}
            style={{ animationDelay: `${i * 70}ms` }}
            className="animate-in fade-in slide-in-from-bottom-2 rounded-full border border-primary/30 px-3.5 py-1.5 text-sm text-foreground/75 transition-colors hover:border-primary/60 hover:bg-primary/5 hover:text-foreground"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
