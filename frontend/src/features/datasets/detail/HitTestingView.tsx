import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { Search } from "lucide-react";

import { hitDataset, listDatasetQueries } from "@/api/datasets";
import { FormError } from "@/components/shared/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { RetrievalStrategy } from "@/types/datasets";

const STRATEGIES: { value: RetrievalStrategy; label: string }[] = [
  { value: "semantic", label: "语义检索" },
  { value: "full_text", label: "全文检索" },
  { value: "hybrid", label: "混合检索" },
];

/** 命中测试：query + 策略/k/score → 检索结果；侧栏最近查询。 */
export function HitTestingView() {
  const { id } = useParams();
  const datasetId = Number(id);
  const [query, setQuery] = useState("");
  const [strategy, setStrategy] = useState<RetrievalStrategy>("semantic");
  const [k, setK] = useState(4);
  const [score, setScore] = useState(0.5);

  const queriesQuery = useQuery({
    queryKey: ["dataset-queries", datasetId],
    queryFn: () => listDatasetQueries(datasetId),
  });

  const hitMutation = useMutation({
    mutationFn: () =>
      hitDataset(datasetId, {
        query: query.trim(),
        retrieval_strategy: strategy,
        k,
        score: strategy === "full_text" ? 0 : score,
      }),
    onSuccess: () => queriesQuery.refetch(),
  });

  const results = hitMutation.data ?? [];

  const submit = () => {
    if (query.trim()) hitMutation.mutate();
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_220px]">
      <div className="space-y-4">
        <Textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={3}
          placeholder="输入检索内容…"
          aria-label="检索内容"
        />
        <div className="flex flex-wrap items-end gap-3">
          <label className="space-y-1 text-sm">
            <span className="block text-muted-foreground">策略</span>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value as RetrievalStrategy)}
              className="block h-9 rounded-md border border-input bg-transparent px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              aria-label="检索策略"
            >
              {STRATEGIES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-sm">
            <span className="block text-muted-foreground">返回条数</span>
            <Input
              type="number"
              min={1}
              max={10}
              value={k}
              onChange={(e) => setK(Number(e.target.value))}
              className="w-24"
              aria-label="返回条数"
            />
          </label>
          <label className="space-y-1 text-sm">
            <span className="block text-muted-foreground">相关度阈值</span>
            <Input
              type="number"
              min={0}
              max={0.99}
              step={0.01}
              value={score}
              onChange={(e) => setScore(Number(e.target.value))}
              className="w-24"
              disabled={strategy === "full_text"}
              aria-label="相关度阈值"
            />
          </label>
          <Button onClick={submit} disabled={!query.trim() || hitMutation.isPending}>
            <Search className="h-4 w-4" /> 检索
          </Button>
        </div>

        {hitMutation.isError && <FormError error={hitMutation.error} />}

        {hitMutation.isSuccess && results.length === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">没有命中结果。</p>
        )}

        <div className="space-y-3">
          {results.map((r) => (
            <div key={r.id} className="rounded-lg border p-3">
              <div className="mb-1 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                <span className="truncate">
                  {r.document?.name ?? "—"} · #{r.position}
                </span>
                <span className="tabular-nums">score {r.score.toFixed(3)}</span>
              </div>
              <p className="whitespace-pre-wrap text-sm">{r.content}</p>
              {r.keywords.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {r.keywords.map((kw) => (
                    <span
                      key={kw}
                      className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground"
                    >
                      {kw}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <aside className="space-y-2">
        <h4 className="text-sm font-medium">最近查询</h4>
        {(queriesQuery.data ?? []).length === 0 ? (
          <p className="text-xs text-muted-foreground">暂无记录</p>
        ) : (
          <ul className="space-y-1">
            {(queriesQuery.data ?? []).map((q) => (
              <li key={q.id}>
                <button
                  type="button"
                  onClick={() => setQuery(q.query)}
                  className="block w-full truncate rounded-md px-2 py-1 text-left text-sm text-muted-foreground hover:bg-muted/50"
                  title={q.query}
                >
                  {q.query}
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>
    </div>
  );
}
