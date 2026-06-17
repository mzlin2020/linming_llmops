import { useMemo, useState } from "react";
import { CheckCircle2, Loader2, Play, Square, X, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import type { VariableEntity, WorkflowDebugFrame } from "@/types/workflows";
import { TypedValueInput } from "./panels/shared/TypedValueInput";
import { useEditorStore } from "./store";
import { useWorkflowDebug } from "./use-workflow-debug";

function defaultFor(v: VariableEntity): string | number | boolean {
  if (v.type === "boolean") return false;
  if (v.type === "int" || v.type === "float") return 0;
  return "";
}

/** 调试面板：按开始节点入参填表 → 运行 → 逐节点结果。 */
export function DebugSheet({ workflowId }: { workflowId: number }) {
  const setDebugOpen = useEditorStore((s) => s.setDebugOpen);
  const frames = useEditorStore((s) => s.debugFrames);
  const startInputs = useEditorStore(
    (s) => s.nodes.find((n) => n.data.wf.node_type === "start")?.data.wf.inputs ?? [],
  );
  const { run, stop, running, error } = useWorkflowDebug(workflowId);

  const initial = useMemo(() => {
    const o: Record<string, string | number | boolean> = {};
    for (const v of startInputs) o[v.name] = defaultFor(v);
    return o;
  }, [startInputs]);
  const [values, setValues] = useState<Record<string, string | number | boolean>>(initial);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <p className="font-medium">调试运行</p>
        <Button variant="ghost" size="icon" onClick={() => setDebugOpen(false)} aria-label="关闭调试">
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex-1 space-y-4 overflow-auto px-4 py-3">
        <div className="space-y-2">
          {startInputs.length === 0 && (
            <p className="text-xs text-muted-foreground">开始节点没有入参，可直接运行。</p>
          )}
          {startInputs.map((v) => (
            <div key={v.name} className="space-y-1">
              <Label htmlFor={`dbg-${v.name}`}>
                {v.name}
                {v.description ? <span className="text-muted-foreground"> · {v.description}</span> : null}
              </Label>
              <TypedValueInput
                type={v.type}
                value={values[v.name] ?? defaultFor(v)}
                onChange={(val) => setValues((s) => ({ ...s, [v.name]: val }))}
              />
            </div>
          ))}
        </div>

        {running ? (
          <Button variant="outline" className="w-full" onClick={stop}>
            <Square className="h-4 w-4" /> 停止
          </Button>
        ) : (
          <Button className="w-full" onClick={() => run(values)}>
            <Play className="h-4 w-4" /> 运行
          </Button>
        )}

        {error && <p className="rounded-md bg-destructive/5 p-2 text-sm text-destructive">{error}</p>}

        <div className="space-y-2">
          {frames.map((f) => (
            <FrameCard key={f.id} frame={f} />
          ))}
        </div>
      </div>
    </div>
  );
}

function FrameCard({ frame }: { frame: WorkflowDebugFrame }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-md border text-sm">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-2 py-1.5 text-left"
      >
        {frame.status === "running" && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
        {frame.status === "succeeded" && <CheckCircle2 className="h-4 w-4 text-emerald-500" />}
        {frame.status === "failed" && <XCircle className="h-4 w-4 text-destructive" />}
        <span className="min-w-0 flex-1 truncate font-medium">{frame.node_data.title}</span>
        <span className="text-xs text-muted-foreground">{frame.latency.toFixed(2)}s</span>
      </button>
      {open && (
        <div className="space-y-2 border-t px-2 py-2 text-xs">
          {frame.error && <p className="text-destructive">{frame.error}</p>}
          <JsonBlock label="输入" value={frame.inputs} />
          <JsonBlock label="输出" value={frame.outputs} />
        </div>
      )}
    </div>
  );
}

function JsonBlock({ label, value }: { label: string; value: unknown }) {
  return (
    <div>
      <p className="mb-0.5 text-muted-foreground">{label}</p>
      <pre className="overflow-auto rounded bg-muted/50 p-2">{JSON.stringify(value, null, 2)}</pre>
    </div>
  );
}
