import { get } from "@/lib/http/client";
import type { Account } from "@/types/auth";

export function getMe() {
  return get<Account>("/account/me");
}
