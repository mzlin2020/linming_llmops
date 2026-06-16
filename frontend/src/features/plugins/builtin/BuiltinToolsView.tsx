import { useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronUp } from "lucide-react";

import { listBuiltinCategories, listBuiltinTools } from "@/api/plugins";
import { ToolIcon } from "@/components/shared/ToolIcon";
import { cn } from "@/lib/utils";

const ALL = "__all__";

/** 内置工具：分类筛选 chips + 提供商卡片网格（行内展开看工具列表）。无分页。 */
export function BuiltinToolsView() {
  const toolsQuery = useQuery({ queryKey: ["builtin-tools"], queryFn: listBuiltinTools });
  const catQuery = useQuery({ queryKey: ["builtin-categories"], queryFn: listBuiltinCategories });
  const [category, setCategory] = useState(ALL);
  const [expanded, setExpanded] = useState<string | null>(null);

  const svgByCategory = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of catQuery.data ?? []) m.set(c.category, c.icon);
    return m;
  }, [catQuery.data]);

  const providers = toolsQuery.data ?? [];
  const filtered = category === ALL ? providers : providers.filter((p) => p.category === category);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Chip active={category === ALL} onClick={() => setCategory(ALL)}>
          全部
        </Chip>
        {(catQuery.data ?? []).map((c) => (
          <Chip key={c.category} active={category === c.category} onClick={() => setCategory(c.category)}>
            {c.name}
          </Chip>
        ))}
      </div>

      {toolsQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">加载中…</p>
      ) : filtered.length === 0 ? (
        <p className="py-12 text-center text-sm text-muted-foreground">该分类暂无内置工具。</p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((p) => {
            const open = expanded === p.name;
            return (
              <div key={p.name} className="flex flex-col gap-3 rounded-lg border p-4">
                <div className="flex items-start gap-3">
                  <ToolIcon svg={svgByCategory.get(p.category)} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{p.label || p.name}</p>
                    <p className="line-clamp-2 text-xs text-muted-foreground">{p.description}</p>
                  </div>
                </div>
                <button
                  type="button"
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                  onClick={() => setExpanded(open ? null : p.name)}
                  aria-expanded={open}
                >
                  {p.tools.length} 个工具
                  {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                </button>
                {open && (
                  <ul className="space-y-1 border-t pt-2">
                    {p.tools.map((t) => (
                      <li key={t.name} className="text-sm">
                        <span className="font-medium">{t.label || t.name}</span>
                        <span className="block text-xs text-muted-foreground">{t.description}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-full border px-3 py-1 text-sm transition-colors",
        active
          ? "border-primary/50 bg-primary/10 text-foreground"
          : "text-muted-foreground hover:bg-muted",
      )}
    >
      {children}
    </button>
  );
}
