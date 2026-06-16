import { NavLink } from "react-router-dom";
import { LogOut, Settings } from "lucide-react";

import { Button } from "@/components/ui/button";
import { navLinkClass } from "@/components/shared/nav-link";
import { useAuthStore } from "@/stores/auth-store";
import { useLogout } from "@/features/auth/useLogout";
import { NAV_ITEMS } from "./nav-items";

function linkClass({ isActive }: { isActive: boolean }) {
  return navLinkClass(isActive, "px-3 py-1.5 rounded-md text-sm font-medium transition-colors");
}

/** 顶部水平导航栏:品牌 + 模块入口 + 设置/账户/退出。 */
export function TopNav() {
  const account = useAuthStore((s) => s.account);
  const handleLogout = useLogout();

  return (
    <header className="flex h-14 items-center gap-2 border-b px-4">
      <NavLink to="/" className="mr-4 font-semibold tracking-tight">
        LLMOps
      </NavLink>
      <nav className="flex items-center gap-1">
        {NAV_ITEMS.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.end} className={linkClass}>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="ml-auto flex items-center gap-1">
        <NavLink to="/settings" className={linkClass} title="设置">
          <Settings className="size-4" />
        </NavLink>
        <span className="px-2 text-sm text-muted-foreground">
          {account?.name || account?.email}
        </span>
        <Button variant="ghost" size="icon" onClick={handleLogout} title="退出登录">
          <LogOut className="size-4" />
        </Button>
      </div>
    </header>
  );
}
