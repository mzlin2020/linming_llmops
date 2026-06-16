import { Puzzle } from "lucide-react";

import { cn } from "@/lib/utils";

interface Props {
  /** 外链图标 URL（自定义/商店插件）。 */
  src?: string | null;
  /** 内联 SVG 字符串（内置工具按分类，来自后端 categories；第一方可信内容）。 */
  svg?: string | null;
  alt?: string;
  className?: string;
}

/** 统一工具/提供商图标：URL 优先 → 内联 SVG → 兜底通用图标。 */
export function ToolIcon({ src, svg, alt = "", className }: Props) {
  const box = cn(
    "flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-lg border bg-muted/40 [&_svg]:size-6",
    className,
  );

  if (src) {
    return (
      <span className={box}>
        <img src={src} alt={alt} className="size-full object-contain" />
      </span>
    );
  }
  if (svg) {
    // 第一方后端打包的分类 SVG，可信内联。
    return <span className={box} aria-hidden dangerouslySetInnerHTML={{ __html: svg }} />;
  }
  return (
    <span className={box} aria-hidden>
      <Puzzle className="size-5 text-muted-foreground" />
    </span>
  );
}
