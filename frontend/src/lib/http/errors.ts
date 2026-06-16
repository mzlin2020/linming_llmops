import { AxiosError } from "axios";

import type { Envelope } from "@/types/api";

/** 统一 API 错误：携带后端信封的业务 code 与 message。 */
export class ApiError extends Error {
  code: number;
  constructor(code: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.code = code;
  }
}

/** 按「信封字段优先、HTTP status 兜底」的统一优先级构造 ApiError（axios 与 SSE 两路共用）。 */
export function apiErrorFromEnvelope(
  status: number,
  body: { code?: number; message?: string } | undefined,
  fallbackMessage = "网络错误",
): ApiError {
  return new ApiError(body?.code ?? status, body?.message ?? fallbackMessage);
}

/** 把 axios 错误（含信封）规整为稳定的 ApiError。 */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (error instanceof AxiosError) {
    const envelope = error.response?.data as Envelope | undefined;
    return apiErrorFromEnvelope(error.response?.status ?? 0, envelope, error.message);
  }
  return new ApiError(0, error instanceof Error ? error.message : "未知错误");
}

/** 取任意错误的展示文案（统一收口 ApiError 收窄，调用点不再各自 `as ApiError`）。 */
export function getErrorMessage(error: unknown): string {
  return toApiError(error).message;
}
