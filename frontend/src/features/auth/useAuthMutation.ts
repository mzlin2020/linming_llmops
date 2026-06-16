import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { useAuthStore } from "@/stores/auth-store";
import type { AuthTokens } from "@/types/auth";

/**
 * 登录/注册共用的提交收尾:成功 → 落会话(setSession)→ 跳目标路由(replace)。
 * `submit` 泛型于各页表单值;`redirectTo` 延迟求值(登录页要读 location.state.from)。
 */
export function useAuthMutation<V>(
  submit: (values: V) => Promise<AuthTokens>,
  redirectTo: () => string,
) {
  const navigate = useNavigate();
  return useMutation({
    mutationFn: submit,
    onSuccess: (tokens: AuthTokens) => {
      useAuthStore.getState().setSession(tokens);
      navigate(redirectTo(), { replace: true });
    },
  });
}
