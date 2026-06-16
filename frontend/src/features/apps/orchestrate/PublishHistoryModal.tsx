import { useMutation, useQuery } from "@tanstack/react-query";

import { fallbackHistory, listPublishHistories } from "@/api/apps";
import { Modal } from "@/components/shared/Modal";
import { Button } from "@/components/ui/button";
import type { AppConfig, PublishHistory } from "@/types/apps";

interface Props {
  appId: number;
  open: boolean;
  onClose: () => void;
  /** 回退成功后把恢复到草稿的配置回传给编排页。 */
  onApplied: (config: AppConfig) => void;
}

/** 发布历史弹窗：列出已发布版本（version 降序），可回退某版本到草稿。 */
export function PublishHistoryModal({ appId, open, onClose, onApplied }: Props) {
  const query = useQuery({
    queryKey: ["publish-histories", appId],
    queryFn: () => listPublishHistories(appId, { current_page: 1, page_size: 20 }),
    enabled: open,
  });

  const fallback = useMutation({
    mutationFn: (versionId: number) => fallbackHistory(appId, versionId),
    onSuccess: (config) => {
      onApplied(config);
      onClose();
    },
  });

  const list = query.data?.list ?? [];

  return (
    <Modal open={open} title="发布历史" onClose={onClose} className="max-w-md">
      {query.isLoading ? (
        <p className="text-sm text-muted-foreground">加载中…</p>
      ) : list.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">还没有发布记录。</p>
      ) : (
        <ul className="space-y-2">
          {list.map((h: PublishHistory) => (
            <li key={h.id} className="flex items-center justify-between rounded-md border p-2 text-sm">
              <span>
                版本 v{h.version}
                {h.created_at && (
                  <span className="ml-2 text-xs text-muted-foreground">
                    {new Date(h.created_at).toLocaleString()}
                  </span>
                )}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={fallback.isPending}
                onClick={() => fallback.mutate(h.id)}
              >
                回退到此版本
              </Button>
            </li>
          ))}
        </ul>
      )}
      {fallback.isError && (
        <p className="mt-3 text-sm text-destructive">回退失败，请稍后再试</p>
      )}
    </Modal>
  );
}
