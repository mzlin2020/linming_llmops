/** 顶部水平导航的主模块入口。 */
export interface NavItem {
  to: string;
  label: string;
  /** 仅首页用精确匹配，避免被子路由高亮。 */
  end?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "首页", end: true },
  { to: "/apps", label: "应用" },
  { to: "/plugins", label: "插件" },
  { to: "/datasets", label: "知识库" },
  { to: "/workflow", label: "工作流" },
];
