import { Outlet } from "react-router-dom";

import { ModuleLayout } from "@/app-shell/ModuleLayout";
import { SidebarNav, type SidebarItem } from "@/components/shared/SidebarNav";

const SETTINGS_NAV: SidebarItem[] = [
  { to: "/settings/api-keys", label: "API 密钥" },
  { to: "/settings/models", label: "模型目录" },
  { to: "/settings/account", label: "账户" },
];

/** 设置模块外壳:左侧栏 + 主区 Outlet。LLM 管理入口在 5f 按 403 探测条件加入。 */
export function SettingsLayout() {
  return (
    <ModuleLayout sidebar={<SidebarNav items={SETTINGS_NAV} />}>
      <Outlet />
    </ModuleLayout>
  );
}
