import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowLeft, LayoutGrid, Pencil, Play } from "lucide-react";

import { cancelPublishWorkflow, publishWorkflow } from "@/api/workflows";
import { Button } from "@/components/ui/button";
import { getErrorMessage } from "@/lib/http/errors";
import { cn } from "@/lib/utils";
import { WorkflowFormDialog } from "../WorkflowFormDialog";
import { useEditorStore } from "./store";

const SAVE_LABEL: Record<string, string> = {
  saving: "保存中…",
  saved: "已保存",
  error: "保存失败",
  idle: "",
};

/** 编辑器顶栏：返回 / 标题编辑 / 状态 / 整理布局 / 调试 / 发布 / 取消发布。 */
export function Toolbar() {
  const queryClient = useQueryClient();
  const workflow = useEditorStore((s) => s.workflow);
  const saveState = useEditorStore((s) => s.saveState);
  const applyLayout = useEditorStore((s) => s.applyLayout);
  const setDebugOpen = useEditorStore((s) => s.setDebugOpen);
  const setWorkflow = useEditorStore((s) => s.setWorkflow);
  const [editOpen, setEditOpen] = useState(false);

  const publishMutation = useMutation({
    mutationFn: () => publishWorkflow(workflow!.id),
    onSuccess: () => {
      setWorkflow({ status: "published", is_debug_passed: false });
      queryClient.invalidateQueries({ queryKey: ["workflows"] });
    },
  });
  const cancelMutation = useMutation({
    mutationFn: () => cancelPublishWorkflow(workflow!.id),
    onSuccess: () => {
      setWorkflow({ status: "draft", is_debug_passed: false });
      queryClient.invalidateQueries({ queryKey: ["workflows"] });
    },
  });

  if (!workflow) return null;
  const published = workflow.status === "published";
  const busy = publishMutation.isPending || cancelMutation.isPending;
  const actionError = publishMutation.error || cancelMutation.error;

  return (
    <header className="flex flex-wrap items-center gap-3 border-b px-4 py-3">
      <Button asChild variant="ghost" size="icon" aria-label="返回工作流列表">
        <Link to="/workflow">
          <ArrowLeft className="h-4 w-4" />
        </Link>
      </Button>
      <div className="flex min-w-0 items-center gap-2">
        <span className="truncate font-medium">{workflow.name}</span>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setEditOpen(true)} aria-label="编辑信息">
          <Pencil className="h-3.5 w-3.5" />
        </Button>
        <span
          className={cn(
            "rounded-full px-2 py-0.5 text-xs font-medium",
            published ? "bg-green-100 text-green-700" : "bg-muted text-muted-foreground",
          )}
        >
          {published ? "已发布" : "草稿"}
        </span>
        {workflow.is_debug_passed && (
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
            调试通过
          </span>
        )}
      </div>

      <div className="ml-auto flex flex-wrap items-center gap-2">
        {SAVE_LABEL[saveState] && (
          <span className={cn("text-xs", saveState === "error" ? "text-destructive" : "text-muted-foreground")}>
            {SAVE_LABEL[saveState]}
          </span>
        )}
        {actionError && (
          <span className="text-xs text-destructive">{getErrorMessage(actionError)}</span>
        )}
        <Button variant="outline" size="sm" onClick={applyLayout}>
          <LayoutGrid className="h-4 w-4" /> 整理
        </Button>
        <Button variant="outline" size="sm" onClick={() => setDebugOpen(true)}>
          <Play className="h-4 w-4" /> 调试
        </Button>
        {published && (
          <Button variant="outline" size="sm" disabled={busy} onClick={() => cancelMutation.mutate()}>
            取消发布
          </Button>
        )}
        <Button
          size="sm"
          disabled={busy || !workflow.is_debug_passed}
          title={workflow.is_debug_passed ? undefined : "请先调试通过再发布"}
          onClick={() => publishMutation.mutate()}
        >
          {published ? "重新发布" : "发布"}
        </Button>
      </div>

      <WorkflowFormDialog open={editOpen} onClose={() => setEditOpen(false)} workflow={workflow} />
    </header>
  );
}
