import { useCallback, useEffect, useReducer, useRef } from "react";

import { getErrorMessage } from "@/lib/http/errors";
import type { SseFrame } from "@/lib/sse/parse-frames";
import { streamSSE } from "@/lib/sse/stream-sse";

import {
  CHAT_URL,
  clearConversation as clearRemote,
  fetchHistory,
  stopTask,
} from "./api";
import type {
  AgentEndData,
  ChatMessage,
  ErrorData,
  MessageDeltaData,
  MessageStatus,
  PingData,
} from "./types";

interface ChatState {
  messages: ChatMessage[];
}

const initialState: ChatState = { messages: [] };

type Action =
  | { type: "INIT"; messages: ChatMessage[] }
  | { type: "PUSH_PAIR"; user: ChatMessage; assistant: ChatMessage }
  | { type: "APPEND_DELTA"; delta: string }
  | { type: "FINISH_ASSISTANT"; status?: ChatMessage["status"] }
  | { type: "ERROR_ASSISTANT"; message: string }
  | { type: "STOP_ASSISTANT" }
  | { type: "CLEAR" };

/** 流式态判定（sending/streaming），供 isStreaming 与收尾守卫共用，避免多处重复状态字面量。 */
function isStreamingStatus(status: MessageStatus): boolean {
  return status === "sending" || status === "streaming";
}

/** 是否正在流式：由末条助手消息状态推导，不另存标志位（免去各分支同步它）。 */
export function isStreaming(messages: ChatMessage[]): boolean {
  const last = messages[messages.length - 1];
  return !!last && last.role === "assistant" && isStreamingStatus(last.status);
}

function patchLastAssistant(
  state: ChatState,
  patch: (last: ChatMessage) => ChatMessage,
): ChatMessage[] {
  const messages = state.messages.slice();
  const last = messages[messages.length - 1];
  if (last && last.role === "assistant") messages[messages.length - 1] = patch(last);
  return messages;
}

/**
 * 仅当末条助手仍在流式态时套用 patch（late 帧/重复收尾不误改已终态的消息）。
 * 四类收尾 action（APPEND_DELTA / FINISH / ERROR / STOP）共用此守卫，免去逐分支重复。
 */
function patchStreamingAssistant(
  state: ChatState,
  patch: (last: ChatMessage) => ChatMessage,
): ChatState {
  return {
    ...state,
    messages: patchLastAssistant(state, (last) =>
      isStreamingStatus(last.status) ? patch(last) : last,
    ),
  };
}

export function reducer(state: ChatState, action: Action): ChatState {
  switch (action.type) {
    case "INIT":
      return { ...state, messages: action.messages };
    case "PUSH_PAIR":
      return { ...state, messages: [...state.messages, action.user, action.assistant] };
    case "APPEND_DELTA":
      return patchStreamingAssistant(state, (last) => ({
        ...last,
        content: last.content + action.delta,
        status: "streaming",
      }));
    case "FINISH_ASSISTANT":
      return patchStreamingAssistant(state, (last) => ({
        ...last,
        status: action.status ?? "done",
      }));
    case "ERROR_ASSISTANT":
      return patchStreamingAssistant(state, (last) => ({
        ...last,
        content: last.content || action.message,
        status: "error",
      }));
    case "STOP_ASSISTANT":
      return patchStreamingAssistant(state, (last) => ({
        ...last,
        content: last.content + (last.content ? "\n\n" : "") + "（已停止生成）",
        status: "stopped",
      }));
    case "CLEAR":
      return { ...state, messages: [] };
    default:
      return state;
  }
}

/**
 * 辅助 Agent 聊天 hook：对接登录态单会话后端（/assistant-agent/*）。
 * - 挂载即拉服务端历史（历史以服务端为准，不做本地落盘）。
 * - 发送走框架无关的 POST-SSE（streamSSE，自动注入 Bearer）。
 * - 停止 = 调真实 stop 端点（task_id 来自 ping）+ 客户端 abort 双保险。
 * - 清空 = 调 delete-conversation + 清空视图。
 */
export function useAssistantChat() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const abortRef = useRef<AbortController | null>(null);
  const taskIdRef = useRef<string | null>(null);
  const stateRef = useRef(state);
  stateRef.current = state;

  const streaming = isStreaming(state.messages);

  useEffect(() => {
    let alive = true;
    fetchHistory()
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
      await streamSSE(
        CHAT_URL,
        { query: trimmed },
        {
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
        },
      );
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
      void stopTask(taskId).catch(() => {
        /* best-effort：裸 LLM 流无 task 登记，stop 为 no-op，靠下方 abort 收尾 */
      });
    }
    abortRef.current?.abort();
    dispatch({ type: "STOP_ASSISTANT" });
  }, []);

  const clearConversation = useCallback(async () => {
    abortRef.current?.abort();
    try {
      await clearRemote();
    } catch {
      /* 即便后端清空失败，前端也先清空视图 */
    }
    dispatch({ type: "CLEAR" });
  }, []);

  return { messages: state.messages, streaming, sendMessage, stopGenerating, clearConversation };
}
