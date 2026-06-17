import {
  Atom,
  Binary,
  Bot,
  BotMessageSquare,
  BrainCircuit,
  CircuitBoard,
  Component,
  Cpu,
  Hexagon,
  type LucideIcon,
  Network,
  Orbit,
  Radar,
  Sparkles,
  Zap,
} from "lucide-react";

import { cn } from "@/lib/utils";

/** 未上传图标时的默认图标池：统一机器人 / AI / 科技调性的线性图标，贴合卡片简洁风。 */
const DEFAULT_ICONS: LucideIcon[] = [
  Bot,
  BotMessageSquare,
  BrainCircuit,
  Cpu,
  CircuitBoard,
  Binary,
  Atom,
  Sparkles,
  Network,
  Orbit,
  Radar,
  Hexagon,
  Component,
  Zap,
];

/** 按名称稳定挑一个默认图标（同一应用在卡片/商店/编排页都一致）。 */
export function pickDefaultIcon(seed: string): LucideIcon {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return DEFAULT_ICONS[h % DEFAULT_ICONS.length];
}

/**
 * 是否是用户真正上传的图标。后端在用户未上传时会塞 `/app-icons/<name>.png` 这类相对占位路径，
 * 前端没有这些静态图会裂图；故仅 http(s)/data 绝对地址才当上传图，其余（空、相对路径、后端默认精灵图）
 * 一律回退到上面的 lucide 默认池——既给新应用干净占位，也修历史上被塞过占位路径的裂图。
 */
function isCustomIcon(icon?: string | null): icon is string {
  return !!icon && /^(https?:\/\/|data:)/.test(icon);
}

interface Props {
  /** 已上传的图标 URL（绝对地址）；为空或后端默认占位路径时回退到默认图标池。 */
  icon?: string | null;
  name?: string;
  className?: string;
}

/** 应用头像：上传过的绝对 URL 显示图片，否则按名称从图标池稳定取一枚 lucide 占位（避免裂图）。 */
export function AppIcon({ icon, name = "", className }: Props) {
  const box = cn(
    "flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-lg border",
    className,
  );

  if (isCustomIcon(icon)) {
    return (
      <span className={cn(box, "bg-muted/40")}>
        <img src={icon} alt={name} className="size-full object-cover" />
      </span>
    );
  }

  const Icon = pickDefaultIcon(name);
  return (
    <span
      className={cn(box, "bg-gradient-to-br from-primary/15 to-primary/5 text-primary/70")}
      aria-hidden
    >
      <Icon className="size-5" strokeWidth={1.8} />
    </span>
  );
}
