import { QueryClient } from "@tanstack/react-query";

/** 全局 Query 客户端：服务端状态缓存默认温和重试、关闭窗口聚焦刷新。 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 30_000 },
  },
});
