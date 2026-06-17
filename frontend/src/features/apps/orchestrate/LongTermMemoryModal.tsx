import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getSummary, updateSummary } from "@/api/apps";
import { Modal } from "@/components/shared/Modal";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { getErrorMessage } from "@/lib/http/errors";
import { LONG_TERM_MEMORY_MAX } from "@/types/apps";

interface Props {
  appId: number;
  open: boolean;
  onClose: () => void;
}

/**
 * 长期记忆查看/编辑窗口：打开即拉当前滚动摘要，可手动修改 / 清空 / 保存。
 * 后端 GET/POST /apps/<id>/summary（对齐源站 long-term-memory-sheet）。
 */
export function LongTermMemoryModal({ appId, open, onClose }: Props) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");

  const query = useQuery({
    queryKey: ["app-summary", appId],
    queryFn: () => getSummary(appId),
    enabled: open,
  });

  // 每次打开/拉到最新摘要时把服务端值灌入草稿（关闭后下次打开重新拉，避免显示陈旧本地态）。
  useEffect(() => {
    if (open && query.data) setDraft(query.data.summary ?? "");
  }, [open, query.data]);

  const save = useMutation({
    mutationFn: (summary: string) => updateSummary(appId, summary),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["app-summary", appId] });
      onClose();
    },
  });

  const loading = query.isLoading;

  return (
    <Modal open={open} title="长期记忆" onClose={onClose} className="max-w-lg">
      <div className="space-y-2">
        <p className="text-xs text-muted-foreground">
          应用跨轮滚动总结的对话记忆，会注入系统提示。可在此查看、手动修改或清空。
        </p>
        {loading ? (
          <p className="py-8 text-center text-sm text-muted-foreground">加载中…</p>
        ) : query.isError ? (
          <p className="py-8 text-center text-sm text-destructive">
            {getErrorMessage(query.error)}
          </p>
        ) : (
          <>
            <Textarea
              rows={8}
              maxLength={LONG_TERM_MEMORY_MAX}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              aria-label="长期记忆内容"
              placeholder="暂无长期记忆。多轮对话后会自动累积摘要，你也可以手动写入。"
            />
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>
                {draft.length}/{LONG_TERM_MEMORY_MAX}
              </span>
              {save.isError && (
                <span className="text-destructive">{getErrorMessage(save.error)}</span>
              )}
            </div>
          </>
        )}
      </div>

      <div className="mt-5 flex items-center justify-between">
        <Button
          variant="outline"
          size="sm"
          disabled={loading || save.isPending || draft.length === 0}
          onClick={() => save.mutate("")}
        >
          清空记忆
        </Button>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onClose}>
            取消
          </Button>
          <Button
            size="sm"
            disabled={loading || save.isPending}
            onClick={() => save.mutate(draft.slice(0, LONG_TERM_MEMORY_MAX))}
          >
            {save.isPending ? "保存中…" : "保存"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
