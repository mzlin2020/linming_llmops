import { describe, expect, it } from "vitest";

import { historyToMessages } from "./api";
import { isStreaming, reducer } from "./use-assistant-chat";
import type { ChatMessage, HistoryRound } from "./types";

const user = (content: string): ChatMessage => ({
  key: "u",
  role: "user",
  content,
  status: "done",
});
const assistant = (content: string, status: ChatMessage["status"]): ChatMessage => ({
  key: "a",
  role: "assistant",
  content,
  status,
});

describe("reducer", () => {
  it("APPEND_DELTA 累加到末条助手并转 streaming", () => {
    let s = { messages: [user("hi"), assistant("", "sending")] };
    s = reducer(s, { type: "APPEND_DELTA", delta: "你好" });
    s = reducer(s, { type: "APPEND_DELTA", delta: "，世界" });
    const last = s.messages[s.messages.length - 1];
    expect(last.content).toBe("你好，世界");
    expect(last.status).toBe("streaming");
  });

  it("FINISH_ASSISTANT 把流式态收尾为指定状态", () => {
    const s = reducer(
      { messages: [user("hi"), assistant("答", "streaming")] },
      { type: "FINISH_ASSISTANT" },
    );
    expect(s.messages[1].status).toBe("done");
    expect(
      reducer(
        { messages: [assistant("答", "streaming")] },
        { type: "FINISH_ASSISTANT", status: "stopped" },
      ).messages[0].status,
    ).toBe("stopped");
  });

  it("FINISH_ASSISTANT 不改非流式态的末条（防 late/重复收尾）", () => {
    const done = { messages: [assistant("答", "done")] };
    expect(reducer(done, { type: "FINISH_ASSISTANT", status: "stopped" })).toEqual(done);
  });

  it("ERROR_ASSISTANT 空内容时落错误文案并转 error", () => {
    const s = reducer(
      { messages: [user("hi"), assistant("", "sending")] },
      { type: "ERROR_ASSISTANT", message: "出错了" },
    );
    expect(s.messages[1]).toMatchObject({ content: "出错了", status: "error" });
  });

  it("STOP_ASSISTANT 追加停止标记并转 stopped", () => {
    const s = reducer(
      { messages: [assistant("半句", "streaming")] },
      { type: "STOP_ASSISTANT" },
    );
    expect(s.messages[0].content).toBe("半句\n\n（已停止生成）");
    expect(s.messages[0].status).toBe("stopped");
  });

  it("CLEAR 清空、INIT 替换", () => {
    expect(reducer({ messages: [user("x")] }, { type: "CLEAR" }).messages).toHaveLength(0);
    const init = [user("a"), assistant("b", "done")];
    expect(reducer({ messages: [] }, { type: "INIT", messages: init }).messages).toBe(init);
  });
});

describe("isStreaming", () => {
  it("末条助手 sending/streaming → true，其余 → false", () => {
    expect(isStreaming([assistant("", "sending")])).toBe(true);
    expect(isStreaming([assistant("x", "streaming")])).toBe(true);
    expect(isStreaming([assistant("x", "done")])).toBe(false);
    expect(isStreaming([user("x")])).toBe(false);
    expect(isStreaming([])).toBe(false);
  });
});

describe("historyToMessages", () => {
  const round = (over: Partial<HistoryRound>): HistoryRound => ({
    id: 1,
    query: "问",
    answer: "答",
    status: "normal",
    error: "",
    ...over,
  });

  it("倒序的轮次 → 正序的 user/assistant 气泡对", () => {
    // 后端按 created_at 倒序返回：第 2 轮在前、第 1 轮在后
    const out = historyToMessages([
      round({ id: 2, query: "q2", answer: "a2" }),
      round({ id: 1, query: "q1", answer: "a1" }),
    ]);
    expect(out.map((m) => m.content)).toEqual(["q1", "a1", "q2", "a2"]);
    expect(out.map((m) => m.role)).toEqual(["user", "assistant", "user", "assistant"]);
  });

  it("状态映射：error 轮空答案回退到 error 文案、stop→stopped", () => {
    const [, errAssistant] = historyToMessages([
      round({ status: "error", answer: "", error: "模型未配置" }),
    ]);
    expect(errAssistant).toMatchObject({ content: "模型未配置", status: "error" });

    const [, stopAssistant] = historyToMessages([round({ status: "stop", answer: "半句" })]);
    expect(stopAssistant).toMatchObject({ content: "半句", status: "stopped" });
  });
});
