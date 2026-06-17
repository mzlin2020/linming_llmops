import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, RotateCcw } from "lucide-react";

import { getApp, getPublishedConfig } from "@/api/apps";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { AppStatusBadge } from "@/features/apps/AppStatusBadge";
import { ChatEmptyState } from "@/features/chat/ChatEmptyState";
import { ChatPanel } from "@/features/chat/ChatPanel";
import { historyToMessages, type HistoryRound } from "@/features/chat/chat-core";
import { useChatStream } from "@/features/chat/use-chat-stream";
import { useFollowups } from "@/features/chat/use-followups";
import { Button } from "@/components/ui/button";
import { get, post } from "@/lib/http/client";
import { getErrorMessage } from "@/lib/http/errors";
import type { PageResult } from "@/types/api";
import type { AppConfig } from "@/types/apps";

/** 与「已发布应用」对话的全屏页（读已发布配置，独立于编排调试会话）。 */
export function PublishedChatPage() {
  const { id } = useParams();
  const appId = Number(id);

  const appQuery = useQuery({ queryKey: ["app", appId], queryFn: () => getApp(appId) });
  const cfgQuery = useQuery({
    queryKey: ["app-published-config", appId],
    queryFn: () => getPublishedConfig(appId),
  });

  const app = appQuery.data;
  const published = app?.status === "published" && !!cfgQuery.data;

  if (appQuery.isLoading || cfgQuery.isLoading) {
    return <div className="p-6 text-sm text-muted-foreground">加载中…</div>;
  }
  if (appQuery.isError || !app) {
    return (
      <div className="p-6 text-sm text-destructive">{getErrorMessage(appQuery.error)}</div>
    );
  }

  const header = (
    <header className="flex items-center gap-3 border-b px-4 py-3">
      <Button asChild variant="ghost" size="icon" aria-label="返回应用列表">
        <Link to="/apps">
          <ArrowLeft className="h-4 w-4" />
        </Link>
      </Button>
      <p className="flex min-w-0 items-center gap-2 font-medium">
        <span className="truncate">{app.name}</span>
        <AppStatusBadge status={app.status} />
      </p>
    </header>
  );

  return (
    <div className="flex h-full min-h-0 flex-col">
      {published ? (
        <PublishedChat appId={appId} name={app.name} config={cfgQuery.data as AppConfig} />
      ) : (
        <>
          {header}
          <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center text-sm text-muted-foreground">
            <p>该应用尚未发布，无法对话。</p>
            <Button asChild size="sm">
              <Link to={`/apps/${appId}`}>去编排并发布</Link>
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

/** 已发布对话内核：只有应用已发布时才挂载（避免对未发布应用调用已发布端点）。 */
function PublishedChat({ appId, name, config }: { appId: number; name: string; config: AppConfig }) {
  const { messages, streaming, sendMessage, stopGenerating, clearConversation } = useChatStream({
    chatUrl: `/apps/${appId}/published-conversations`,
    buildBody: (query) => ({ query }),
    fetchHistory: async () => {
      const page = await get<PageResult<HistoryRound>>(
        `/apps/${appId}/published-conversations/messages`,
        { params: { current_page: 1, page_size: 20, created_at: 0 } },
      );
      return historyToMessages(page.list);
    },
    // 已发布对话没有 stop 端点：靠客户端 abort 收尾即可。
    stopTask: async () => undefined,
    clearConversation: () => post(`/apps/${appId}/published-conversations/clear`),
  });

  const followups = useFollowups({
    messages,
    streaming,
    enabled: !!config.suggested_after_answer?.enable,
  });
  const [confirmClear, setConfirmClear] = useState(false);

  const header = (
    <header className="flex items-center justify-between gap-3 border-b px-4 py-3">
      <Button asChild variant="ghost" size="icon" aria-label="返回应用列表">
        <Link to="/apps">
          <ArrowLeft className="h-4 w-4" />
        </Link>
      </Button>
      <p className="flex-1 truncate font-medium">{name}</p>
      {messages.length > 0 && (
        <button
          type="button"
          onClick={() => setConfirmClear(true)}
          aria-label="清空对话"
          title="清空对话（保留长期记忆）"
          className="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <RotateCcw className="h-4 w-4" />
        </button>
      )}
    </header>
  );

  return (
    <>
      <ChatPanel
        className="mx-auto max-w-3xl"
        messages={messages}
        streaming={streaming}
        onSend={sendMessage}
        onStop={stopGenerating}
        followups={followups}
        onPickFollowup={(q) => void sendMessage(q)}
        header={header}
        emptyState={
          <ChatEmptyState
            openingStatement={config.opening_statement}
            openingQuestions={config.opening_questions}
            onPick={(q) => void sendMessage(q)}
            fallback={
              <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center text-sm text-muted-foreground">
                <p>开始和「{name}」对话吧。</p>
              </div>
            }
          />
        }
        footerNote={
          <p className="pt-2 text-center text-[10px] tracking-wider text-muted-foreground/70">
            回答由 AI 生成
          </p>
        }
      />
      <ConfirmDialog
        open={confirmClear}
        title="清空对话？"
        description="将清空当前对话记录（保留长期记忆），且不可恢复。"
        confirmText="清空"
        destructive
        onConfirm={() => {
          setConfirmClear(false);
          void clearConversation();
        }}
        onCancel={() => setConfirmClear(false)}
      />
    </>
  );
}
