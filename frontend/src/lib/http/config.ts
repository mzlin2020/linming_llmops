/** API 基址。生产由 nginx 反代 `/api`；dev 由 Vite proxy 转发。可用 env 覆盖。 */
export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api";
