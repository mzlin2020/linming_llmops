import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { Account, AuthTokens } from "@/types/auth";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  account: Account | null;
  /** 登录/注册成功：落 token + account。 */
  setSession: (tokens: AuthTokens) => void;
  /** 刷新成功：仅更新 access token。 */
  setAccessToken: (token: string) => void;
  /** 回填 /account/me 的账户信息。 */
  setAccount: (account: Account) => void;
  /** 登出：清空全部。 */
  clear: () => void;
}

/**
 * 鉴权状态（持久化到 localStorage）。
 * 关键：token 读写不依赖 React 上下文——axios 拦截器在组件树外用
 * `useAuthStore.getState()` 取/写 token，支撑 401 排队刷新与登出。
 */
export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      account: null,
      setSession: (tokens) =>
        set({
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
          account: tokens.account,
        }),
      setAccessToken: (token) => set({ accessToken: token }),
      setAccount: (account) => set({ account }),
      clear: () => set({ accessToken: null, refreshToken: null, account: null }),
    }),
    { name: "llmops-auth" },
  ),
);
