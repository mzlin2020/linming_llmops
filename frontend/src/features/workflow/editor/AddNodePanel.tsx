import { cn } from "@/lib/utils";
import type { NodeType } from "@/types/workflows";
import { ADDABLE_NODE_TYPES, NODE_DEFS } from "./node-registry";
import { useEditorStore } from "./store";

/** 节点添加面板：点击即在画布上新增对应节点（start/end 已存在则禁用）。 */
export function AddNodePanel() {
  const nodes = useEditorStore((s) => s.nodes);
  const addNode = useEditorStore((s) => s.addNode);
  const present = new Set(nodes.map((n) => n.data.wf.node_type));

  return (
    <div className="space-y-1">
      <p className="px-1 pb-1 text-xs font-medium text-muted-foreground">添加节点</p>
      {ADDABLE_NODE_TYPES.map((type) => {
        const def = NODE_DEFS[type];
        const Icon = def.icon;
        const disabled = def.unique && present.has(type as NodeType);
        return (
          <button
            key={type}
            type="button"
            disabled={disabled}
            onClick={() => addNode(type)}
            className={cn(
              "flex w-full items-start gap-2 rounded-md border p-2 text-left text-sm transition-colors hover:bg-muted/50",
              disabled && "cursor-not-allowed opacity-50 hover:bg-transparent",
            )}
          >
            <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="min-w-0">
              <span className="block font-medium">{def.label}</span>
              <span className="block truncate text-xs text-muted-foreground">{def.hint}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
