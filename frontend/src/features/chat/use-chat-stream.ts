import { useCallback, useEffect, useReducer, useRef } from "react";

import { getErrorMessage } from "@/lib/http/errors";
import type { SseFrame } from "@/lib/sse/parse-frames";
import { streamSSE } from "@/lib/sse/stream-sse";

import {
  type AgentEndData,
  type ChatMessage,
  type ErrorData,
  initialState,
  isStreaming,
  type MessageDeltaData,
  type PingData,
  reducer,
} from "./chat-core";

export interface ChatStreamOptions {
  /** SSE 流式聊天端点（POST，经 streamSSE，不走 axios）。 */
  chatUrl: string;
  /** 由 query 构造请求体（不同入口可带 conversation_id / provider 等）。 */
  buildBody: (query: string) => Record<string, unknown>;
  /** 拉服务端历史（拆成正序气泡）。返回空数组表示无历史。 */
  fetchHistory: () => Promise<ChatMessage[]>;
  /** 真实停止：按 task_id 置停止 flag（best-effort）。 */
  stopTask: (taskId: string) => Promise<unknown>;
  /** 清空当前会话（软删）。 */
  clearConversation: () => Promise<unknown>;
}

/**
 * 通用流式聊天 hook：端点/请求体/历史/停止/清空均由调用方注入。
 * - 挂载即拉服务端历史（历史以服务端为准，不做本地落盘）。
 * - 发送走框架无关的 POST-SSE（streamSSE，自动注入 Bearer）。
 * - 停止 = 调真实 stop 端点（task_id 来自 ping）+ 客户端 abort 双保险。
 * - 清空 = 调清空端点 + 清空视图。
 * 首页辅助 Agent 与应用编排调试聊天共用此 hook，仅注入参数不同。
 */
export function useChatStream(options: ChatStreamOptions) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const abortRef = useRef<AbortController | null>(null);
  const taskIdRef = useRef<string | null>(null);
  const stateRef = useRef(state);
  stateRef.current = state;
  // 选项每渲染重建（含闭包端点），存入 ref，让回调保持稳定又总读到最新值。
  const optsRef = useRef(options);
  optsRef.current = options;

  const streaming = isStreaming(state.messages);

  useEffect(() => {
    let alive = true;
    optsRef.current
      .fetchHistory()
      .then((messages) => {
        if (alive && messages.length > 0) dispatch({ type: "INIT", messages });
      })
      .catch(() => {
        /* 静默：首次/空会话无历史 */
      });
    return () => {
      alive = false;
      abortRef.current?.abort();
    };
    // 挂载一次：fetchHistory 经 optsRef 读最新，无需进依赖。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sendMessage = useCallback(async (query: string) => {
    const trimmed = query.trim();
    if (!trimmed || isStreaming(stateRef.current.messages)) return;

    const stamp = Date.now();
    dispatch({
      type: "PUSH_PAIR",
      user: { key: `u-${stamp}`, role: "user", content: trimmed, status: "done" },
      assistant: { key: `a-${stamp}`, role: "assistant", content: "", status: "sending" },
    });

    const controller = new AbortController();
    abortRef.current = controller;
    taskIdRef.current = null;

    try {
      await streamSSE(optsRef.current.chatUrl, optsRef.current.buildBody(trimmed), {
        signal: controller.signal,
        onEvent: (frame: SseFrame) => {
          if (controller.signal.aborted) return;
          switch (frame.event) {
            case "ping":
              taskIdRef.current = (frame.data as PingData)?.task_id ?? null;
              break;
            case "message":
              dispatch({ type: "APPEND_DELTA", delta: (frame.data as MessageDeltaData).delta });
              break;
            case "agent_end":
              dispatch({
                type: "FINISH_ASSISTANT",
                status: (frame.data as AgentEndData).status === "stop" ? "stopped" : "done",
                messageId: (frame.data as AgentEndData).message_id,
              });
              break;
            case "error":
              dispatch({
                type: "ERROR_ASSISTANT",
                message: (frame.data as ErrorData)?.message || "出错了，请稍后再试",
              });
              break;
            case "stop":
              dispatch({ type: "STOP_ASSISTANT" });
              break;
            case "timeout":
              dispatch({ type: "ERROR_ASSISTANT", message: "回答超时了，稍后再试试 🙏" });
              break;
            // agent_thought / agent_action / workflow：v1 安全忽略（工具步骤可视化后置）
          }
        },
      });
    } catch (err) {
      // 非 2xx（如未配模型）→ streamSSE 抛 ApiError；主动 abort 已在 reader 内静默收尾，不会到这。
      dispatch({ type: "ERROR_ASSISTANT", message: getErrorMessage(err) });
    } finally {
      abortRef.current = null;
    }
  }, []);

  const stopGenerating = useCallback(() => {
    if (!isStreaming(stateRef.current.messages)) return;
    const taskId = taskIdRef.current;
    if (taskId) {
      void optsRef.current.stopTask(taskId).catch(() => {
        /* best-effort：裸 LLM 流无 task 登记，stop 为 no-op，靠下方 abort 收尾 */
      });
    }
    abortRef.current?.abort();
    dispatch({ type: "STOP_ASSISTANT" });
  }, []);

  const clearConversation = useCallback(async () => {
    abortRef.current?.abort();
    try {
      await optsRef.current.clearConversation();
    } catch {
      /* 即便后端清空失败，前端也先清空视图 */
    }
    dispatch({ type: "CLEAR" });
  }, []);

  return { messages: state.messages, streaming, sendMessage, stopGenerating, clearConversation };
}
