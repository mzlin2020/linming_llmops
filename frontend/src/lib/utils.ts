import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** 合并 className，处理 tailwind 冲突类（shadcn 约定）。 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
