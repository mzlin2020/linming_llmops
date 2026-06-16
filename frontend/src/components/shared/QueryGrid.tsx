import type { ReactNode } from "react";

interface Props<T> {
  isLoading: boolean;
  items: T[];
  emptyText: string;
  children: (item: T) => ReactNode;
}

/** 列表查询的统一「加载中 / 空 / 卡片网格」呈现，三处插件视图共用。 */
export function QueryGrid<T>({ isLoading, items, emptyText, children }: Props<T>) {
  if (isLoading) return <p className="text-sm text-muted-foreground">加载中…</p>;
  if (items.length === 0)
    return <p className="py-12 text-center text-sm text-muted-foreground">{emptyText}</p>;
  return <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{items.map(children)}</div>;
}
