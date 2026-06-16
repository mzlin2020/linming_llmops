import { type ReactNode, useEffect } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { getMe } from "@/api/account";
import { useAuthStore } from "@/stores/auth-store";

/**
 * 受保护路由:无 access token → 跳登录(记住来路)。
 * 有 token 但无 account(刷新页面后 persist 只剩 token)→ 拉 /account/me 回填,
 * 顺带校验 token 仍有效(失效会触发 axios 刷新/登出链路)。
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const account = useAuthStore((s) => s.account);
  const location = useLocation();

  useEffect(() => {
    if (accessToken && !account) {
      getMe()
        .then((acc) => useAuthStore.getState().setAccount(acc))
        .catch(() => {
          /* 401 已由 axios 拦截器处理(刷新/登出);其余错误静默 */
        });
    }
  }, [accessToken, account]);

  if (!accessToken) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <>{children}</>;
}
