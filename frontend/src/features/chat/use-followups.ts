import { useEffect, useRef, useState } from "react";

import { suggestQuestions } from "@/api/ai";

import type { ChatMessage } from "./chat-core";

/**
 * 「回答后建议追问」：末条助手消息完成后，按其 message_id 拉 follow-up 问题（string[]）。
 * 对齐参考站 debug-preview 的 follow-up 行为：
 * - 仅对「本轮会话内实时产生」的回答取（key 以 `a-` 开头），不给加载来的历史末条拉；
 * - 流式中 / 新发送 / 清空 / `enabled=false`（应用未开 suggested_after_answer）→ 隐藏 chips；
 * - 同一条只取一次，取到后保留直至下一次发送。
 */
export function useFollowups(params: {
  messages: ChatMessage[];
  streaming: boolean;
  enabled: boolean;
}): string[] {
  const { messages, streaming, enabled } = params;
  const [followups, setFollowups] = useState<string[]>([]);
  const fetchedForId = useRef<number | null>(null);

  useEffect(() => {
    const last = messages[messages.length - 1];
    const eligible =
      enabled &&
      !streaming &&
      !!last &&
      last.role === "assistant" &&
      last.status === "done" &&
      typeof last.id === "number" &&
      last.key.startsWith("a-");

    if (!eligible) {
      // 流式中 / 新发送 / 清空 / 未开启：隐藏上一轮 chips（仅在非空时更新，避免无谓重渲）。
      setFollowups((f) => (f.length ? [] : f));
      return;
    }
    const id = last.id as number;
    if (fetchedForId.current === id) return; // 已为这条取过 → 保留现有 chips
    fetchedForId.current = id;
    let alive = true;
    suggestQuestions(id)
      .then((qs) => {
        if (alive) setFollowups(Array.isArray(qs) ? qs : []);
      })
      .catch(() => {
        if (alive) setFollowups([]);
      });
    return () => {
      alive = false;
    };
  }, [messages, streaming, enabled]);

  return followups;
}
