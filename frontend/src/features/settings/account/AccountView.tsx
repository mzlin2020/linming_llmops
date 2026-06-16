import { useQuery } from "@tanstack/react-query";
import { LogOut } from "lucide-react";

import { getMe } from "@/api/account";
import { Button } from "@/components/ui/button";
import { useLogout } from "@/features/auth/useLogout";
import { useAuthStore } from "@/stores/auth-store";

/** 账户页：展示当前账户资料 + 登出。后端 account 仅 /me（无改名/改密端点），故此页只读。 */
export function AccountView() {
  const stored = useAuthStore((s) => s.account);
  // 优先用服务端最新资料，回落到登录时存的账户。
  const query = useQuery({ queryKey: ["account-me"], queryFn: getMe });
  const account = query.data ?? stored;
  const handleLogout = useLogout();
  const initial = (account?.name || account?.email || "?").charAt(0).toUpperCase();

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h2 className="text-lg font-semibold">账户</h2>

      <div className="flex items-center gap-4 rounded-lg border p-4">
        <div className="flex size-14 items-center justify-center overflow-hidden rounded-full bg-muted text-lg font-medium text-muted-foreground">
          {account?.avatar ? (
            <img src={account.avatar} alt={account.name} className="size-full object-cover" />
          ) : (
            initial
          )}
        </div>
        <div className="min-w-0">
          <p className="truncate font-medium">{account?.name || "未命名用户"}</p>
          <p className="truncate text-sm text-muted-foreground">{account?.email}</p>
        </div>
      </div>

      <div className="rounded-lg border">
        <Row label="用户 ID" value={account ? String(account.id) : "—"} />
      </div>

      <Button variant="outline" onClick={handleLogout}>
        <LogOut className="h-4 w-4" /> 退出登录
      </Button>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b px-4 py-3 text-sm last:border-b-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="truncate">{value}</span>
    </div>
  );
}
