/** 流式「思考中…」指示：渐变文字扫光动画，替代旧的闪烁竖条光标（更柔和、无突兀竖线）。 */
export function ThinkingIndicator() {
  return (
    <span
      className="inline-block bg-clip-text text-sm leading-relaxed text-transparent"
      style={{
        backgroundImage:
          "linear-gradient(90deg, hsl(var(--foreground) / 0.35) 0%, hsl(var(--foreground)) 50%, hsl(var(--foreground) / 0.35) 100%)",
        backgroundSize: "200% 100%",
        animation: "shimmer 2.2s linear infinite",
      }}
    >
      思考中…
    </span>
  );
}
