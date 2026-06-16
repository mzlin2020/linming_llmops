import { useAuthStore } from "@/stores/auth-store";
import { ApiError } from "./errors";
import { rawRefresh } from "./refresh-api";

type Waiter = { resolve: (token: string) => void; reject: (err: unknown) => void };

let isRefreshing = false;
let waiters: Waiter[] = [];

function flush(token: string) {
  waiters.forEach((w) => w.resolve(token));
  waiters = [];
}

function rejectAll(err: unknown) {
  waiters.forEach((w) => w.reject(err));
  waiters = [];
}

/**
 * 单飞刷新 access token：并发的 401 只发起一次 `/auth/refresh`，其余调用排队挂起，
 * 刷新成功后用新 token 一并放行；刷新失败则全部拒绝（由调用方触发登出）。
 * 返回新的 access token。
 */
export async function ensureFreshToken(): Promise<string> {
  const { refreshToken } = useAuthStore.getState();
  if (!refreshToken) throw new ApiError(401, "未登录");

  if (isRefreshing) {
    return new Promise<string>((resolve, reject) => waiters.push({ resolve, reject }));
  }

  isRefreshing = true;
  try {
    const token = await rawRefresh(refreshToken);
    useAuthStore.getState().setAccessToken(token);
    flush(token);
    return token;
  } catch (err) {
    rejectAll(err);
    throw err;
  } finally {
    isRefreshing = false;
  }
}

/** 刷新彻底失败（refresh_token 也过期）：清空会话，跳登录页。 */
export function onAuthFailure(): void {
  useAuthStore.getState().clear();
  if (typeof window !== "undefined" && window.location.pathname !== "/login") {
    try {
      window.location.assign("/login");
    } catch {
      /* jsdom/测试环境无导航实现，忽略 */
    }
  }
}
