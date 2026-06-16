import { Outlet } from "react-router-dom";

import { ModuleLayout } from "@/app-shell/ModuleLayout";
import { SidebarNav, type SidebarItem } from "@/components/shared/SidebarNav";

const APP_NAV: SidebarItem[] = [
  { to: "/apps", label: "我的应用", end: true },
  { to: "/apps/store", label: "应用商店" },
];

/** 应用模块外壳：左侧栏（我的应用 / 应用商店）+ 主区 Outlet。编排页为全宽独立路由，不走此外壳。 */
export function AppsLayout() {
  return (
    <ModuleLayout sidebar={<SidebarNav items={APP_NAV} />}>
      <Outlet />
    </ModuleLayout>
  );
}
