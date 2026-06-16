import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, History, Store } from "lucide-react";

import { cancelPublishApp, getApp, publishApp, setAppPublic, updateDraftConfig } from "@/api/apps";
import { Button } from "@/components/ui/button";
import { getErrorMessage } from "@/lib/http/errors";
import type { AppConfig } from "@/types/apps";

import { AppStatusBadge } from "../AppStatusBadge";
import { ConfigEditor } from "./ConfigEditor";
import { DebugChatPanel } from "./DebugChatPanel";
import { PublishHistoryModal } from "./PublishHistoryModal";

const sameConfig = (a: AppConfig | null, b: AppConfig | null) =>
  JSON.stringify(a) === JSON.stringify(b);

/** 应用编排页（全宽双栏）：左侧草稿配置编辑器 + 右侧调试预览；顶部保存/发布/历史/上架。 */
export function OrchestrationPage() {
  const { id } = useParams();
  const appId = Number(id);
  const queryClient = useQueryClient();

  const [config, setConfig] = useState<AppConfig | null>(null);
  const [savedConfig, setSavedConfig] = useState<AppConfig | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);

  const query = useQuery({ queryKey: ["app", appId], queryFn: () => getApp(appId) });

  // 首次拿到详情时把草稿配置灌进本地状态；后续编辑不被后台刷新冲掉（仅 config 为空时灌）。
  useEffect(() => {
    if (query.data && config === null) {
      setConfig(query.data.app_config);
      setSavedConfig(query.data.app_config);
    }
  }, [query.data, config]);

  /** 用服务端返回的规范化配置同步本地（保存/发布/回退后调）。 */
  const syncConfig = (next: AppConfig) => {
    setConfig(next);
    setSavedConfig(next);
  };

  const saveMutation = useMutation({
    mutationFn: (cfg: AppConfig) => updateDraftConfig(appId, cfg),
    onSuccess: syncConfig,
  });

  const publishMutation = useMutation({
    mutationFn: () => publishApp(appId),
    onSuccess: (detail) => {
      syncConfig(detail.app_config);
      queryClient.invalidateQueries({ queryKey: ["app", appId] });
      queryClient.invalidateQueries({ queryKey: ["apps"] });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelPublishApp(appId),
    onSuccess: (detail) => {
      syncConfig(detail.app_config);
      queryClient.invalidateQueries({ queryKey: ["app", appId] });
      queryClient.invalidateQueries({ queryKey: ["apps"] });
    },
  });

  const storeMutation = useMutation({
    mutationFn: (isPublic: boolean) => setAppPublic(appId, isPublic),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["app", appId] });
      queryClient.invalidateQueries({ queryKey: ["app-store"] });
    },
  });

  const app = query.data;

  if (query.isLoading || !config || !app) {
    return (
      <div className="p-6 text-sm text-muted-foreground">
        {query.isError ? getErrorMessage(query.error) : "加载中…"}
      </div>
    );
  }

  const dirty = !sameConfig(config, savedConfig);
  const published = app.status === "published";
  const busy = saveMutation.isPending || publishMutation.isPending || cancelMutation.isPending;
  // 四路写操作的错误收口成一处提示（同一时刻至多一个在飞）。
  const actionError =
    saveMutation.error || publishMutation.error || cancelMutation.error || storeMutation.error;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b px-4 py-3">
        <Button asChild variant="ghost" size="icon" aria-label="返回应用列表">
          <Link to="/apps">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="min-w-0">
          <p className="flex items-center gap-2 font-medium">
            <span className="truncate">{app.name}</span>
            <AppStatusBadge status={app.status} />
          </p>
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setHistoryOpen(true)}
            aria-label="发布历史"
          >
            <History className="h-4 w-4" /> 历史
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!published || storeMutation.isPending}
            title={published ? undefined : "发布后可上架"}
            onClick={() => storeMutation.mutate(!app.is_public)}
          >
            <Store className="h-4 w-4" /> {app.is_public ? "下架商店" : "上架商店"}
          </Button>
          {published ? (
            <Button
              variant="outline"
              size="sm"
              disabled={busy}
              onClick={() => cancelMutation.mutate()}
            >
              取消发布
            </Button>
          ) : null}
          <Button
            size="sm"
            variant="outline"
            disabled={!dirty || busy}
            onClick={() => saveMutation.mutate(config)}
          >
            {saveMutation.isPending ? "保存中…" : dirty ? "保存草稿" : "已保存"}
          </Button>
          <Button
            size="sm"
            disabled={dirty || busy}
            title={dirty ? "有未保存修改，请先保存草稿" : undefined}
            onClick={() => publishMutation.mutate()}
          >
            {publishMutation.isPending ? "发布中…" : published ? "重新发布" : "发布"}
          </Button>
        </div>
      </header>

      {actionError && (
        <p className="border-b bg-destructive/5 px-4 py-2 text-sm text-destructive">
          {getErrorMessage(actionError)}
        </p>
      )}

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <div className="min-h-0 overflow-auto border-b p-6 lg:w-1/2 lg:border-b-0 lg:border-r">
          <ConfigEditor value={config} onChange={setConfig} />
        </div>
        <div className="min-h-0 flex-1">
          <DebugChatPanel key={appId} appId={appId} />
        </div>
      </div>

      <PublishHistoryModal
        appId={appId}
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        onApplied={syncConfig}
      />
    </div>
  );
}
