import { cn } from "@/lib/utils";

/**
 * 导航链接的激活态样式,顶栏与模块侧栏共用。
 * `base` 由各调用方传入各自的间距/字号;激活/非激活的配色 token 在此单点维护。
 */
export function navLinkClass(isActive: boolean, base: string): string {
  return cn(
    base,
    isActive
      ? "bg-secondary text-secondary-foreground"
      : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
  );
}
