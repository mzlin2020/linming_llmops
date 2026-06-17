import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

import { cn } from "@/lib/utils";
import { useEditorStore } from "../store";
import { NODE_DEFS } from "../node-registry";
import type { WfNodeData } from "../serialize";

/** 统一节点卡片渲染器（8 种节点共用）：图标 + 标题 + 类型 + 调试态徽标 + 连接点。 */
function BaseNodeImpl({ id, data, selected }: NodeProps) {
  const wf = (data as WfNodeData).wf;
  const def = NODE_DEFS[wf.node_type];
  const Icon = def?.icon;
  const frame = useEditorStore((s) => s.debugByNode[id]);

  return (
    <div
      className={cn(
        "w-52 rounded-lg border bg-card px-3 py-2 shadow-sm transition-colors",
        selected ? "border-primary ring-1 ring-primary" : "border-border",
        frame?.status === "failed" && "border-destructive",
        frame?.status === "succeeded" && "border-emerald-500",
      )}
    >
      {wf.node_type !== "start" && <Handle type="target" position={Position.Left} />}
      <div className="flex items-center gap-2">
        {Icon && <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />}
        <span className="min-w-0 flex-1 truncate text-sm font-medium">{wf.title}</span>
        {frame?.status === "running" && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
        {frame?.status === "succeeded" && <CheckCircle2 className="h-4 w-4 text-emerald-500" />}
        {frame?.status === "failed" && <XCircle className="h-4 w-4 text-destructive" />}
      </div>
      <p className="mt-0.5 truncate text-xs text-muted-foreground">{def?.label ?? wf.node_type}</p>
      {wf.node_type !== "end" && <Handle type="source" position={Position.Right} />}
    </div>
  );
}

export const BaseNode = memo(BaseNodeImpl);
