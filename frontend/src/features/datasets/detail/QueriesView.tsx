import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { Clock, History, Search } from "lucide-react";

import { listDatasetQueries } from "@/api/datasets";

/** 检索来源 → 中文标签（对齐后端 RetrievalSource）；未知值回退原始字符串。 */
const SOURCE_LABELS: Record<string, string> = {
  hit_testing: "命中测试",
  app: "应用对话",
};

/** unix 秒 → MM-DD HH:mm。 */
function fmtTime(unixSec: number): string {
  const d = new Date(unixSec * 1000);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

/** 知识库「查询历史」：最近的检索记录（来源徽标 + 时间）。数据/接口已就绪，本视图补 UI。 */
export function QueriesView() {
  const { id } = useParams();
  const datasetId = Number(id);
  const query = useQuery({
    queryKey: ["dataset-queries", datasetId],
    queryFn: () => listDatasetQueries(datasetId),
    enabled: Number.isFinite(datasetId),
  });

  if (query.isLoading) {
    return <div className="h-40 animate-pulse rounded-xl border bg-muted/40" />;
  }

  const rows = query.data ?? [];
  if (rows.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-6 py-14 text-center text-sm text-muted-foreground">
        <History className="h-7 w-7 opacity-60" strokeWidth={1.6} />
        还没有检索记录，去「命中测试」试试吧。
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border">
      <ul className="divide-y">
        {rows.map((q) => (
          <li key={q.id} className="flex items-center gap-3 px-4 py-3">
            <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="min-w-0 flex-1 truncate text-sm" title={q.query}>
              {q.query}
            </span>
            <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
              {SOURCE_LABELS[q.source] ?? q.source}
            </span>
            <span className="hidden shrink-0 items-center gap-1 text-[11px] text-muted-foreground sm:flex">
              <Clock className="h-3 w-3" />
              {fmtTime(q.created_at)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
