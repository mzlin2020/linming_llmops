import { NavLink } from "react-router-dom";

import { navLinkClass } from "./nav-link";

export interface SidebarItem {
  to: string;
  label: string;
  end?: boolean;
}

/** 模块左侧栏的纵向导航(如插件页 内置/自定义/商店)。 */
export function SidebarNav({ items }: { items: SidebarItem[] }) {
  return (
    <nav className="flex flex-col gap-1">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            navLinkClass(isActive, "rounded-md px-3 py-2 text-sm transition-colors")
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}
