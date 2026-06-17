import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Check, History, Loader2, MessageSquare, Store } from "lucide-react";

import {
  cancelPublishApp,
  getApp,
  publishApp,
  setAppPublic,
  updateDraftConfig,
} from "@/api/apps";
import { Button } from "@/components/ui/button";
import { getErrorMessage } from "@/lib/http/errors";
import type { AppConfig } from "@/types/apps";

import { AppStatusBadge } from "../AppStatusBadge";
import { ConfigEditor } from "./ConfigEditor";
import { DebugChatPanel } from "./DebugChatPanel";
import { PublishHistoryModal } from "./PublishHistoryModal";

type SaveState = "idle" | "saving" | "saved" | "error";

/** 应用编排页（全宽双栏）：左侧草稿配置编辑器（改动即自动保存）+ 右侧调试预览；顶部对话/历史/上架/发布。 */
export function OrchestrationPage() {
  const { id } = useParams();
  const appId = Number(id);
  const queryClient = useQueryClient();

  const [config, setConfig] = useState<AppConfig | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [historyOpen, setHistoryOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  // 自动保存用：最新配置 / 是否有未落库改动 / 防抖定时器。
  const configRef = useRef<AppConfig | null>(null);
  configRef.current = config;
  const dirtyRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const query = useQuery({ queryKey: ["app", appId], queryFn: () => getApp(appId) });

  // 首次拿到详情时把草稿配置灌进本地状态；后续编辑/发布刷新不再回灌（仅 config 为 null 时灌）。
  useEffect(() => {
    if (query.data && config === null) setConfig(query.data.app_config);
  }, [query.data, config]);

  /** 立即把当前草稿落库（自动保存的实际写操作）。成功后清脏标记。 */
  const persist = useCallback(async () => {
    const cfg = configRef.current;
    if (!cfg) return;
    setSaveState("saving");
    try {
      await updateDraftConfig(appId, cfg);
      dirtyRef.current = false;
      setSaveState("saved");
    } catch {
      // 留着脏标记，下次改动会再触发保存；指示器提示失败。
      setSaveState("error");
    }
  }, [appId]);

  // 改动即防抖自动保存（600ms）。每次 config 变化重置定时器，只有最后一次改动会落库。
  useEffect(() => {
    if (!config || !dirtyRef.current) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    setSaveState("saving");
    timerRef.current = setTimeout(() => void persist(), 600);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [config, persist]);

  /** 发布前先冲刷未触发的防抖，确保发布到的是最新草稿。 */
  const flushSave = useCallback(async () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (dirtyRef.current) await persist();
  }, [persist]);

  /** 编辑器改动入口：标脏 + 更新本地（自动保存由上面的 effect 驱动）。 */
  const onConfigChange = (next: AppConfig) => {
    dirtyRef.current = true;
    setNotice(null);
    setConfig(next);
  };

  const publishMutation = useMutation({
    mutationFn: async () => {
      await flushSave();
      return publishApp(appId);
    },
    onSuccess: () => {
      setNotice("已发布，可在右上角「对话」中试用");
      queryClient.invalidateQueries({ queryKey: ["app", appId] });
      queryClient.invalidateQueries({ queryKey: ["apps"] });
      queryClient.invalidateQueries({ queryKey: ["app-store"] });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelPublishApp(appId),
    onSuccess: () => {
      setNotice(null);
      queryClient.invalidateQueries({ queryKey: ["app", appId] });
      queryClient.invalidateQueries({ queryKey: ["apps"] });
      queryClient.invalidateQueries({ queryKey: ["app-store"] });
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

  const published = app.status === "published";
  const busy = publishMutation.isPending || cancelMutation.isPending;
  // 写操作错误收口成一处提示（同一时刻至多一个在飞）。
  const actionError = publishMutation.error || cancelMutation.error || storeMutation.error;

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

        <SaveIndicator state={saveState} />

        <div className="ml-auto flex flex-wrap items-center gap-2">
          {published ? (
            <Button asChild variant="outline" size="sm" title="与已发布版对话">
              <Link to={`/apps/${appId}/chat`}>
                <MessageSquare className="h-4 w-4" /> 对话
              </Link>
            </Button>
          ) : (
            <Button variant="outline" size="sm" disabled title="发布后可对话">
              <MessageSquare className="h-4 w-4" /> 对话
            </Button>
          )}
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
          <Button size="sm" disabled={busy} onClick={() => publishMutation.mutate()}>
            {publishMutation.isPending ? "发布中…" : published ? "重新发布" : "发布"}
          </Button>
        </div>
      </header>

      {(notice || actionError) && (
        <p
          className={
            actionError
              ? "border-b bg-destructive/5 px-4 py-2 text-sm text-destructive"
              : "border-b bg-primary/5 px-4 py-2 text-sm text-primary"
          }
        >
          {actionError ? getErrorMessage(actionError) : notice}
        </p>
      )}

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <div className="min-h-0 overflow-auto border-b p-6 lg:w-1/2 lg:border-b-0 lg:border-r">
          <ConfigEditor value={config} onChange={onConfigChange} />
        </div>
        <div className="min-h-0 flex-1">
          <DebugChatPanel
            key={appId}
            appId={appId}
            openingStatement={config.opening_statement}
            openingQuestions={config.opening_questions}
            longTermMemoryEnabled={config.long_term_memory.enable}
          />
        </div>
      </div>

      <PublishHistoryModal
        appId={appId}
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        onApplied={(cfg) => {
          // 历史回退把某版本写回草稿：同步本地并标记已保存（后端已落库）。
          dirtyRef.current = false;
          setSaveState("saved");
          setConfig(cfg);
        }}
      />
    </div>
  );
}

/** 自动保存状态指示（替代原手动「保存草稿」按钮）。 */
function SaveIndicator({ state }: { state: SaveState }) {
  if (state === "idle") return null;
  if (state === "saving") {
    return (
      <span className="flex items-center gap-1 text-xs text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> 保存中…
      </span>
    );
  }
  if (state === "error") {
    return <span className="text-xs text-destructive">保存失败，改动稍后自动重试</span>;
  }
  return (
    <span className="flex items-center gap-1 text-xs text-muted-foreground">
      <Check className="h-3.5 w-3.5" /> 已自动保存
    </span>
  );
}
