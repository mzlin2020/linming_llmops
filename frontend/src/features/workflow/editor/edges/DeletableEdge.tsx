import { BaseEdge, EdgeLabelRenderer, getBezierPath, type EdgeProps } from "@xyflow/react";
import { X } from "lucide-react";

import { useEditorStore } from "../store";

/** 可删除连线：选中时在中点显示删除按钮。 */
export function DeletableEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  selected,
}: EdgeProps) {
  const [path, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });

  return (
    <>
      <BaseEdge id={id} path={path} />
      {selected && (
        <EdgeLabelRenderer>
          <button
            type="button"
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            }}
            className="pointer-events-auto absolute grid h-5 w-5 place-items-center rounded-full border bg-background text-muted-foreground shadow-sm hover:text-destructive"
            onClick={() => useEditorStore.getState().onEdgesChange([{ type: "remove", id }])}
            aria-label="删除连线"
          >
            <X className="h-3 w-3" />
          </button>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
