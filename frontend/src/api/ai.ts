/** AI 辅助生成端点（编排页 ✨ 按钮：优化人设 / 生成开场问题 / 生成追问）。 */
import { post } from "@/lib/http/client";

/** 优化人设提示词，返回优化后的文本。 */
export async function optimizePresetPrompt(prompt: string): Promise<string> {
  const data = await post<{ prompt: string }>("/ai/optimize-preset-prompt", { prompt });
  return data.prompt;
}

/** 据人设生成开场建议问题（prompt 可空）。 */
export function suggestOpeningQuestions(prompt: string): Promise<string[]> {
  return post<string[]>("/ai/suggested-opening-questions", { prompt });
}

/** 据某条消息（一轮问答）生成 follow-up 建议问题。 */
export function suggestQuestions(messageId: number): Promise<string[]> {
  return post<string[]>("/ai/suggested-questions", { message_id: messageId });
}
