import { useCallback, useRef, useState } from "react";

import { workflowDebugUrl } from "@/api/workflows";
import { getErrorMessage } from "@/lib/http/errors";
import { streamSSE } from "@/lib/sse/stream-sse";
import type { WorkflowDebugFrame } from "@/types/workflows";
import { useEditorStore } from "./store";
import { validateGraph } from "./validation";

/** 工作流调试运行：客户端校验 → flushSave → SSE 流式逐节点结果，跑通点亮发布闸门。 */
export function useWorkflowDebug(workflowId: number) {
  const running = useEditorStore((s) => s.debugRunning);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const run = useCallback(
    async (inputs: Record<string, unknown>) => {
      const store = useEditorStore.getState();
      const wfNodes = store.nodes.map((n) => n.data.wf);
      const miniEdges = store.edges.map((e) => ({ source: e.source, target: e.target }));
      const errs = validateGraph(wfNodes, miniEdges);
      if (errs.length) {
        setError(errs[0]);
        return;
      }
      setError(null);
      if (!(await store.flushSave())) {
        setError("保存草稿失败，无法调试");
        return;
      }

      store.startDebug();
      const ac = new AbortController();
      abortRef.current = ac;
      let failed = false;
      try {
        await streamSSE(workflowDebugUrl(workflowId), inputs, {
          signal: ac.signal,
          onEvent: (frame) => {
            if (frame.event === "workflow") {
              const f = frame.data as WorkflowDebugFrame;
              useEditorStore.getState().upsertDebugFrame(f);
              if (f.status === "failed") failed = true;
            } else if (frame.event === "error") {
              failed = true;
              setError((frame.data as { message?: string })?.message ?? "调试运行失败");
            }
          },
        });
        // 全程无 error/failed 帧 = 跑通：乐观点亮发布闸门（发布时后端会再校验）。
        if (!failed) useEditorStore.getState().setWorkflow({ is_debug_passed: true });
      } catch (e) {
        setError(getErrorMessage(e));
      } finally {
        useEditorStore.getState().endDebug();
      }
    },
    [workflowId],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  return { run, stop, running, error };
}
