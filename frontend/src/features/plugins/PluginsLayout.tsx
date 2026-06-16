import { Outlet } from "react-router-dom";

import { ModuleLayout } from "@/app-shell/ModuleLayout";
import { SidebarNav, type SidebarItem } from "@/components/shared/SidebarNav";

const PLUGIN_NAV: SidebarItem[] = [
  { to: "/plugins/builtin", label: "内置插件" },
  { to: "/plugins/custom", label: "自定义插件" },
  { to: "/plugins/store", label: "插件商店" },
];

/** 插件模块外壳:左侧栏(内置/自定义/商店)+ 主区 Outlet。 */
export function PluginsLayout() {
  return (
    <ModuleLayout sidebar={<SidebarNav items={PLUGIN_NAV} />}>
      <Outlet />
    </ModuleLayout>
  );
}
