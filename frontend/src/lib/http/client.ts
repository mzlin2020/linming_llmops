import axios, {
  type AxiosError,
  type AxiosRequestConfig,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios";

import type { Envelope } from "@/types/api";
import { useAuthStore } from "@/stores/auth-store";
import { API_BASE } from "./config";
import { toApiError } from "./errors";
import { ensureFreshToken, onAuthFailure } from "./refresh-queue";

/** 标记已重试过的请求，避免刷新后无限重放。 */
interface RetriableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

export const instance = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

// 请求拦截器：注入 Bearer（在 React 树外取 token）。
instance.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// 响应拦截器：成功解封信封返回 data；401 走单飞刷新并重放；其余规整为 ApiError。
// 注：此处刻意把已解封的业务 data 作为 resolve 值（下方 get/post 再 cast 成 T），
// 故对 axios 的 AxiosResponse 返回类型做一次显式 cast。
instance.interceptors.response.use(
  (response) => (response.data as Envelope).data as unknown as AxiosResponse,
  async (error: AxiosError) => {
    const original = error.config as RetriableConfig | undefined;
    const status = error.response?.status;
    const isRefreshCall = original?.url?.includes("/auth/refresh");

    if (status === 401 && original && !original._retry && !isRefreshCall) {
      original._retry = true;
      try {
        const token = await ensureFreshToken();
        original.headers.Authorization = `Bearer ${token}`;
        return instance(original);
      } catch {
        onAuthFailure();
        return Promise.reject(toApiError(error));
      }
    }
    return Promise.reject(toApiError(error));
  },
);

// 类型化薄封装：响应拦截器已把信封解封为 data，故 resolve 值即业务 data。
export function get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return instance.get(url, config) as unknown as Promise<T>;
}

export function post<T>(url: string, body?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return instance.post(url, body, config) as unknown as Promise<T>;
}

export function postForm<T>(url: string, form: FormData): Promise<T> {
  return instance.post(url, form, {
    headers: { "Content-Type": "multipart/form-data" },
  }) as unknown as Promise<T>;
}
