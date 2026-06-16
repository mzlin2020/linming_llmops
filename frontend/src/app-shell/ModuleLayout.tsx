import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface ModuleLayoutProps {
  /** 左侧栏内容(模块按需提供,如插件页的 内置/自定义/商店)。 */
  sidebar: ReactNode;
  children: ReactNode;
  className?: string;
}

/** 模块级「左侧栏 + 主区」双栏布局。顶栏由 AppShell 提供,此处只管模块内分栏。 */
export function ModuleLayout({ sidebar, children, className }: ModuleLayoutProps) {
  return (
    <div className="flex h-full min-h-0">
      <aside className="w-56 shrink-0 overflow-auto border-r p-3">{sidebar}</aside>
      <section className={cn("min-w-0 flex-1 overflow-auto p-6", className)}>
        {children}
      </section>
    </div>
  );
}
