import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { ArrowUp, Square } from "lucide-react";

import { cn } from "@/lib/utils";

interface Props {
  streaming: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}

/** 输入区：自适应高度 textarea + 发送/停止切换（圆形图标按钮），中文 IME 安全。 */
export function Composer({ streaming, onSend, onStop }: Props) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  // 自适应高度（≤160px），未超限时藏滚动条消除「假竖线」。
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    const full = el.scrollHeight;
    el.style.height = `${Math.min(full, 160)}px`;
    el.style.overflowY = full > 160 ? "auto" : "hidden";
  }, [value]);

  // 桌面端打开即聚焦；移动端不抢焦点（避免键盘顶起面板）。
  useEffect(() => {
    if (window.matchMedia?.("(pointer: fine)").matches) ref.current?.focus();
  }, []);

  const submit = () => {
    const v = value.trim();
    if (!v || streaming) return;
    onSend(v);
    setValue("");
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // 中文输入法组合（拼音选词）期间的回车用于上屏，不发送。
    if (e.nativeEvent.isComposing || e.keyCode === 229) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div
      className={cn(
        "group flex items-end gap-2 rounded-2xl border border-input bg-card py-2 pl-4 pr-2 transition-all",
        "focus-within:border-primary/50 focus-within:shadow-[0_0_24px_-8px_hsl(var(--primary)/0.5)]",
      )}
    >
      <textarea
        ref={ref}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKeyDown}
        rows={1}
        placeholder="输入消息，Enter 发送，Shift+Enter 换行"
        aria-label="消息输入"
        className="max-h-40 min-h-[32px] flex-1 resize-none overflow-hidden border-0 bg-transparent px-0.5 py-1 text-base leading-relaxed text-foreground placeholder:text-muted-foreground focus:outline-none md:text-sm"
      />
      {streaming ? (
        <button
          type="button"
          onClick={onStop}
          aria-label="停止生成"
          className="flex size-8 shrink-0 items-center justify-center rounded-full border border-primary/40 text-primary transition-all hover:bg-primary/10 active:scale-95"
        >
          <Square className="h-3 w-3 fill-current" />
        </button>
      ) : (
        <button
          type="button"
          onClick={submit}
          disabled={!value.trim()}
          aria-label="发送"
          className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition-all hover:brightness-110 active:scale-95 disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground"
        >
          <ArrowUp className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
