import { useMemo, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { listApiTools, listBuiltinTools } from "@/api/plugins";
import { cn } from "@/lib/utils";
import { toolRefKey, type ToolRef } from "@/types/plugins";

const MAX_TOOLS = 10;

interface Props {
  value: ToolRef[];
  onChange: (next: ToolRef[]) => void;
}

/**
 * 工具选择器（本阶段产出，供 5e 编排页复用）：从「内置工具」与「我的自定义 API 工具」
 * 勾选，发出对齐后端 AppConfig 的 ToolRef 列表。受控、合计 ≤10。
 */
export function ToolSelector({ value, onChange }: Props) {
  const builtinQuery = useQuery({ queryKey: ["builtin-tools"], queryFn: listBuiltinTools });
  // 选择器场景一次性拉较大页（真正分页留 5e 后续按需加）。
  const apiQuery = useQuery({
    queryKey: ["api-tools", "selector"],
    queryFn: () => listApiTools({ current_page: 1, page_size: 50 }),
  });

  const selectedKeys = useMemo(() => new Set(value.map(toolRefKey)), [value]);
  const atLimit = value.length >= MAX_TOOLS;

  const toggle = (ref: ToolRef) => {
    const key = toolRefKey(ref);
    if (selectedKeys.has(key)) {
      onChange(value.filter((r) => toolRefKey(r) !== key));
    } else if (!atLimit) {
      onChange([...value, ref]);
    }
  };

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        已选 {value.length} / {MAX_TOOLS}
      </p>

      <ToolGroup title="内置工具">
        {(builtinQuery.data ?? []).flatMap((p) =>
          p.tools.map((t) => {
            const ref: ToolRef = {
              type: "builtin_tool",
              provider: { name: p.name },
              tool: { name: t.name, params: {} },
            };
            const key = toolRefKey(ref);
            const checked = selectedKeys.has(key);
            return (
              <ToolRow
                key={key}
                label={t.label || t.name}
                sub={`${p.label || p.name} · ${t.description}`}
                checked={checked}
                disabled={(!checked && atLimit) || p.admin_only}
                onToggle={() => toggle(ref)}
              />
            );
          }),
        )}
      </ToolGroup>

      <ToolGroup title="自定义 API 工具">
        {(apiQuery.data?.list ?? []).flatMap((p) =>
          p.tools.map((t) => {
            const ref: ToolRef = {
              type: "api_tool",
              provider: { id: p.id, name: p.name },
              tool: { id: t.id, name: t.name },
            };
            const key = toolRefKey(ref);
            const checked = selectedKeys.has(key);
            return (
              <ToolRow
                key={key}
                label={t.name}
                sub={`${p.name} · ${t.description}`}
                checked={checked}
                disabled={!checked && atLimit}
                onToggle={() => toggle(ref)}
              />
            );
          }),
        )}
      </ToolGroup>
    </div>
  );
}

function ToolGroup({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <h4 className="mb-2 text-sm font-medium">{title}</h4>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function ToolRow({
  label,
  sub,
  checked,
  disabled,
  onToggle,
}: {
  label: string;
  sub: string;
  checked: boolean;
  disabled?: boolean;
  onToggle: () => void;
}) {
  return (
    <label
      className={cn(
        "flex cursor-pointer items-start gap-2 rounded-md border p-2 text-sm transition-colors hover:bg-muted/50",
        checked && "border-primary/50 bg-primary/5",
        disabled && "cursor-not-allowed opacity-50 hover:bg-transparent",
      )}
    >
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={onToggle}
        className="mt-0.5"
      />
      <span className="min-w-0">
        <span className="block font-medium">{label}</span>
        <span className="block truncate text-xs text-muted-foreground">{sub}</span>
      </span>
    </label>
  );
}
