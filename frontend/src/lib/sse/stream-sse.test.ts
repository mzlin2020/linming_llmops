import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/http/errors";
import type { SseFrame } from "./parse-frames";
import { streamSSE } from "./stream-sse";

const enc = new TextEncoder();

/** 构造一个按预设字符串 chunk 逐次产出的 fake streaming Response。 */
function streamResponse(chunks: string[]): Response {
  let i = 0;
  const reader = {
    read: async () =>
      i < chunks.length
        ? { done: false, value: enc.encode(chunks[i++]) }
        : { done: true, value: undefined },
    cancel: async () => {},
  };
  return {
    ok: true,
    status: 200,
    body: { getReader: () => reader },
  } as unknown as Response;
}

afterEach(() => vi.unstubAllGlobals());

describe("streamSSE", () => {
  it("跨 chunk 拆帧后按序分发事件", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        streamResponse([
          'event: ping\ndata: {"task_id":"t1"}\n\n',
          "event: mess", // 故意在帧中间切断
          'age\ndata: {"delta":"hi"}\n\n' +
            'event: agent_end\ndata: {"status":"normal"}\n\n',
        ]),
      ),
    );

    const events: SseFrame[] = [];
    await streamSSE("/assistant-agent/chat", { query: "hi" }, {
      onEvent: (f) => events.push(f),
    });

    expect(events.map((e) => e.event)).toEqual(["ping", "message", "agent_end"]);
    expect(events[1].data).toEqual({ delta: "hi" });
  });

  it("中途 AbortError → 静默收尾，不再分发后续事件", async () => {
    let call = 0;
    const reader = {
      read: async () => {
        call += 1;
        if (call === 1) {
          return { done: false, value: enc.encode('event: ping\ndata: {}\n\n') };
        }
        throw new DOMException("aborted", "AbortError");
      },
      cancel: async () => {},
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        body: { getReader: () => reader },
      } as unknown as Response),
    );

    const events: SseFrame[] = [];
    await expect(
      streamSSE("/assistant-agent/chat", {}, { onEvent: (f) => events.push(f) }),
    ).resolves.toBeUndefined();
    expect(events.map((e) => e.event)).toEqual(["ping"]);
  });

  it("非 2xx 响应按信封抛 ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        body: null,
        json: async () => ({ code: 403, message: "未发布或无权访问" }),
      } as unknown as Response),
    );

    await expect(
      streamSSE("/openapi/chat", { app_id: 1 }, { onEvent: () => {} }),
    ).rejects.toMatchObject({ code: 403, message: "未发布或无权访问" });
    await expect(
      streamSSE("/openapi/chat", { app_id: 1 }, { onEvent: () => {} }),
    ).rejects.toBeInstanceOf(ApiError);
  });
});
