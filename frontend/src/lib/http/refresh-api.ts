import axios from "axios";

import type { Envelope } from "@/types/api";
import type { RefreshResult } from "@/types/auth";
import { API_BASE } from "./config";

/**
 * 裸刷新调用：用未拦截的 axios 直击 `/auth/refresh`，避免走主实例的响应拦截器
 * 造成 401 递归。`refresh_token` 只进 body（后端 RefreshReq 要求），不进头。
 * 单列一个模块便于在刷新队列单测里 vi.mock。
 */
export async function rawRefresh(refreshToken: string): Promise<string> {
  const resp = await axios.post<Envelope<RefreshResult>>(
    `${API_BASE}/auth/refresh`,
    { refresh_token: refreshToken },
  );
  return resp.data.data.access_token;
}
