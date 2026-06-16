import { API_BASE } from "@/lib/http/config";
import { apiErrorFromEnvelope } from "@/lib/http/errors";
import { useAuthStore } from "@/stores/auth-store";
import { createFrameParser, type SseFrame } from "./parse-frames";

export interface StreamSSEOptions {
  onEvent: (frame: SseFrame) => void;
  signal?: AbortSignal;
  headers?: Record<string, string>;
}

function isAbortError(err: unknown): boolean {
  return (err as { name?: string } | null)?.name === "AbortError";
}

/**
 * 框架无关的 POST-SSE 读取器：`fetch` POST + `ReadableStream` 增量解析。
 * （POST 不能用 EventSource。）逐帧回调 `onEvent`；`AbortController` 中断时静默收尾；
 * 非 2xx 响应按后端普通信息封解析为 ApiError 抛出（SSE 端点出错时不走事件流）。
 */
export async function streamSSE(
  url: string,
  body: unknown,
  { onEvent, signal, headers }: StreamSSEOptions,
): Promise<void> {
  const token = useAuthStore.getState().accessToken;
  const res = await fetch(`${API_BASE}${url}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok || !res.body) {
    let body: { code?: number; message?: string } | undefined;
    try {
      body = (await res.json()) as { code?: number; message?: string };
    } catch {
      /* 非 JSON 错误体：用默认 */
    }
    throw apiErrorFromEnvelope(res.status, body, `请求失败（${res.status}）`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  const parser = createFrameParser();

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      const text = decoder.decode(value, { stream: true });
      for (const frame of parser.push(text)) onEvent(frame);
    }
    for (const frame of parser.flush()) onEvent(frame);
  } catch (err) {
    if (isAbortError(err)) return; // 主动中断：静默收尾
    throw err;
  }
}
