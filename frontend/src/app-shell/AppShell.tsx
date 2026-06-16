import { Outlet } from "react-router-dom";

import { TopNav } from "./TopNav";

/** 应用外壳:全局顶部导航 + 主内容区。模块自带侧栏时在各模块内用 ModuleLayout 再分栏。 */
export function AppShell() {
  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <TopNav />
      <main className="min-h-0 flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
