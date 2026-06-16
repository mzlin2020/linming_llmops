import { post } from "@/lib/http/client";
import type { AuthTokens } from "@/types/auth";

export function login(email: string, password: string) {
  return post<AuthTokens>("/auth/login", { email, password });
}

export function register(email: string, password: string, name?: string) {
  return post<AuthTokens>("/auth/register", { email, password, name });
}

export function logout() {
  return post<Record<string, never>>("/auth/logout", {});
}
