import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { getDraftGraph, getWorkflow } from "@/api/workflows";
import { getErrorMessage } from "@/lib/http/errors";
import { AddNodePanel } from "./AddNodePanel";
import { Canvas } from "./Canvas";
import { DebugSheet } from "./DebugSheet";
import { NodePanel } from "./NodePanel";
import { Toolbar } from "./Toolbar";
import { useEditorStore } from "./store";

/** 工作流可视化编辑器（全宽）：顶栏 + 左侧节点面板 + 画布 + 右侧属性/调试面板。 */
export function WorkflowEditorPage() {
  const { id } = useParams();
  const workflowId = Number(id);

  const init = useEditorStore((s) => s.init);
  const reset = useEditorStore((s) => s.reset);
  const ready = useEditorStore((s) => s.workflow?.id === workflowId);
  const selectedNodeId = useEditorStore((s) => s.selectedNodeId);
  const debugOpen = useEditorStore((s) => s.debugOpen);

  const query = useQuery({
    queryKey: ["workflow-editor", workflowId],
    queryFn: async () => {
      const [wf, graph] = await Promise.all([getWorkflow(workflowId), getDraftGraph(workflowId)]);
      return { wf, graph };
    },
  });

  useEffect(() => {
    if (query.data) init(query.data.wf, query.data.graph);
  }, [query.data, init]);
  useEffect(() => () => reset(), [reset]);

  if (query.isError) {
    return <div className="p-6 text-sm text-destructive">{getErrorMessage(query.error)}</div>;
  }
  if (!ready) {
    return <div className="p-6 text-sm text-muted-foreground">加载中…</div>;
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <Toolbar />
      <div className="flex min-h-0 flex-1">
        <aside className="w-56 shrink-0 overflow-auto border-r p-3">
          <AddNodePanel />
        </aside>
        <div className="min-h-0 flex-1">
          <Canvas />
        </div>
        <aside className="w-80 shrink-0 overflow-hidden border-l">
          {debugOpen ? (
            <DebugSheet workflowId={workflowId} />
          ) : selectedNodeId ? (
            <NodePanel nodeId={selectedNodeId} />
          ) : (
            <div className="p-4 text-sm text-muted-foreground">选择一个节点以编辑其配置。</div>
          )}
        </aside>
      </div>
    </div>
  );
}
