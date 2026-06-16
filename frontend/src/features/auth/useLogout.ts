import { useCallback } from "react";
import { useNavigate } from "react-router-dom";

import { logout as logoutApi } from "@/api/auth";
import { useAuthStore } from "@/stores/auth-store";

/**
 * 无状态登出：调登出端点（失败也忽略）→ 清本地令牌 → 跳登录页。
 * 顶栏与账户页共用同一份收尾逻辑。
 */
export function useLogout() {
  const navigate = useNavigate();
  return useCallback(async () => {
    try {
      await logoutApi();
    } catch {
      /* 无状态登出：即便接口失败也丢弃本地令牌 */
    }
    useAuthStore.getState().clear();
    navigate("/login", { replace: true });
  }, [navigate]);
}
