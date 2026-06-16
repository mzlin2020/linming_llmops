/** 后端 SSE 事件名（QueueEvent，见 backend/internal/entity/chat_entity.py）。 */
export type SseEventName =
  | "ping"
  | "message"
  | "agent_thought"
  | "agent_action"
  | "agent_end"
  | "error"
  | "stop"
  | "timeout"
  | "workflow";

/** 终止类事件：收到即代表本轮结束。 */
export const TERMINAL_EVENTS: ReadonlySet<string> = new Set([
  "agent_end",
  "stop",
  "timeout",
  "error",
]);
