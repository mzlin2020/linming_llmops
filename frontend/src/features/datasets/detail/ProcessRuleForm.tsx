import { Plus, Trash2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { ProcessRule, ProcessType } from "@/types/datasets";

interface Props {
  processType: ProcessType;
  rule: ProcessRule;
  onProcessTypeChange: (t: ProcessType) => void;
  onRuleChange: (r: ProcessRule) => void;
}

const PRE_LABEL: Record<string, string> = {
  remove_extra_space: "清除多余空白",
  remove_url_and_email: "清除 URL 和邮箱",
};

/** 文档切分规则：automatic（用后端默认）/ custom（chunk / 分隔符 / 预处理）。 */
export function ProcessRuleForm({ processType, rule, onProcessTypeChange, onRuleChange }: Props) {
  const setSegment = (patch: Partial<ProcessRule["segment"]>) =>
    onRuleChange({ ...rule, segment: { ...rule.segment, ...patch } });

  const setSeparator = (i: number, v: string) =>
    setSegment({ separators: rule.segment.separators.map((s, idx) => (idx === i ? v : s)) });
  const addSeparator = () => setSegment({ separators: [...rule.segment.separators, ""] });
  const removeSeparator = (i: number) =>
    setSegment({ separators: rule.segment.separators.filter((_, idx) => idx !== i) });

  const togglePre = (id: ProcessRule["pre_process_rules"][number]["id"]) =>
    onRuleChange({
      ...rule,
      pre_process_rules: rule.pre_process_rules.map((p) =>
        p.id === id ? { ...p, enabled: !p.enabled } : p,
      ),
    });

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        {(["automatic", "custom"] as ProcessType[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => onProcessTypeChange(t)}
            className={cn(
              "flex-1 rounded-md border px-3 py-2 text-sm transition-colors",
              processType === t ? "border-primary bg-primary/5 font-medium" : "hover:bg-muted/50",
            )}
          >
            {t === "automatic" ? "自动切分（推荐）" : "自定义规则"}
          </button>
        ))}
      </div>

      {processType === "custom" && (
        <div className="space-y-4 rounded-md border p-3">
          <div className="grid grid-cols-2 gap-3">
            <label className="space-y-1 text-sm">
              <span className="text-muted-foreground">分段最大长度</span>
              <Input
                type="number"
                min={1}
                value={rule.segment.chunk_size}
                onChange={(e) => setSegment({ chunk_size: Number(e.target.value) })}
                aria-label="分段最大长度"
              />
            </label>
            <label className="space-y-1 text-sm">
              <span className="text-muted-foreground">分段重叠长度</span>
              <Input
                type="number"
                min={0}
                value={rule.segment.chunk_overlap}
                onChange={(e) => setSegment({ chunk_overlap: Number(e.target.value) })}
                aria-label="分段重叠长度"
              />
            </label>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">分隔符</span>
              <Button type="button" variant="outline" size="sm" onClick={addSeparator}>
                <Plus className="h-4 w-4" /> 添加
              </Button>
            </div>
            {rule.segment.separators.map((s, i) => (
              <div key={i} className="flex items-center gap-2">
                <Input
                  value={s}
                  onChange={(e) => setSeparator(i, e.target.value)}
                  aria-label={`分隔符 ${i + 1}`}
                  placeholder="如 \n\n"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => removeSeparator(i)}
                  aria-label={`删除分隔符 ${i + 1}`}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>

          <div className="space-y-1.5">
            <span className="text-sm text-muted-foreground">预处理</span>
            {rule.pre_process_rules.map((p) => (
              <label key={p.id} className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={p.enabled} onChange={() => togglePre(p.id)} />
                {PRE_LABEL[p.id] ?? p.id}
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
