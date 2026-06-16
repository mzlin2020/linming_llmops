import { useCallback, useEffect, useRef } from "react";

/**
 * 通用聊天吸底滚动 hook：贴底跟随流式输出；用户上滚翻历史时让出控制；
 * 容器变矮（输入框长高等）时补一次贴底。
 */
export function useAutoScroll<T extends HTMLElement>(deps: unknown[], threshold = 80) {
  const ref = useRef<T | null>(null);
  const stickRef = useRef(true);
  const rafRef = useRef<number | null>(null);
  const programmaticRef = useRef(false);

  const scrollToBottom = useCallback(() => {
    if (rafRef.current !== null) return;
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null;
      const el = ref.current;
      // 用户在流式期间向上翻看时 stickRef 被置 false，此处再校验，避免已排队的这帧把人强拉回底部。
      if (!el || !stickRef.current) return;
      const target = el.scrollHeight - el.clientHeight;
      if (Math.abs(el.scrollTop - target) < 1) return;
      programmaticRef.current = true;
      el.scrollTop = target;
    });
  }, []);

  useEffect(() => {
    if (stickRef.current) scrollToBottom();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  // 容器自身变矮（输入框长高等）会压矮可视区且不触发 deps，贴底状态被悄悄破坏 —— 监听尺寸补贴底。
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      if (stickRef.current) scrollToBottom();
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [scrollToBottom]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const onScroll = () => {
      // 忽略我们自己触发的滚动，否则它会把刚被用户解除的「贴底」又设回 true。
      if (programmaticRef.current) {
        programmaticRef.current = false;
        return;
      }
      const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
      stickRef.current = distance < threshold;
    };
    // 桌面端：向上滚轮即刻解除贴底，比等 scroll 事件更跟手。
    const onWheel = (e: WheelEvent) => {
      if (e.deltaY < 0) stickRef.current = false;
    };

    el.addEventListener("scroll", onScroll, { passive: true });
    el.addEventListener("wheel", onWheel, { passive: true });
    return () => {
      el.removeEventListener("scroll", onScroll);
      el.removeEventListener("wheel", onWheel);
    };
  }, [threshold]);

  return { ref, scrollToBottom };
}
