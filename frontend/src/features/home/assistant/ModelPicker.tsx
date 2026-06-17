import { useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";

import { listLanguageModels } from "@/api/apps";
import { cn } from "@/lib/utils";
import { useAiModelStore } from "@/stores/ai-model-store";
import { pickLabel } from "@/types/apps";

const DEFAULT_VALUE = "__default__";
const SEP = "::";

/**
 * 首页助手头部的模型选择器：「默认模型」+ 按提供商分组的对话模型（原生 select + optgroup）。
 * 选择写入持久化的 ai-model store；发送时 useAssistantChat 读它覆盖本轮模型，缺省走后端默认。
 */
export function ModelPicker({ className }: { className?: string }) {
  const query = useQuery({ queryKey: ["language-models"], queryFn: listLanguageModels });
  const provider = useAiModelStore((s) => s.provider);
  const model = useAiModelStore((s) => s.model);
  const setModel = useAiModelStore((s) => s.setModel);
  const clearModel = useAiModelStore((s) => s.clearModel);

  // 仅保留对话模型（剔除 text2img/tts/embedding 与弃用项），与编排页模型下拉同口径。
  const providers = (query.data ?? [])
    .map((p) => ({ ...p, models: p.models.filter((m) => m.model_type === "chat" && !m.deprecated) }))
    .filter((p) => p.models.length > 0);

  const known = providers.some(
    (p) => p.name === provider && p.models.some((m) => m.model_name === model),
  );
  const value = provider && model ? `${provider}${SEP}${model}` : DEFAULT_VALUE;

  const onChange = (next: string) => {
    if (next === DEFAULT_VALUE) {
      clearModel();
      return;
    }
    const idx = next.indexOf(SEP);
    const p = next.slice(0, idx);
    const m = next.slice(idx + SEP.length);
    if (p && m) setModel(p, m);
  };

  return (
    <div className={cn("relative inline-flex items-center", className)}>
      <span
        aria-hidden
        className="pointer-events-none absolute left-2.5 size-1.5 rounded-full bg-emerald-500"
      />
      <select
        aria-label="选择模型"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-8 max-w-[44vw] cursor-pointer appearance-none truncate rounded-full border border-border/60 bg-card/40 pl-6 pr-7 text-xs font-medium text-foreground/90 outline-none transition-colors hover:border-primary/40 focus:outline-none sm:max-w-[200px]"
      >
        <option value={DEFAULT_VALUE}>默认模型</option>
        {/* 选定值已下线 / 不在目录时仍保留为兜底选项，避免下拉显示空白 */}
        {!known && provider && model ? <option value={value}>{model}</option> : null}
        {providers.map((p) => (
          <optgroup key={p.name} label={pickLabel(p.label, p.name)}>
            {p.models.map((m) => (
              <option
                key={`${p.name}${SEP}${m.model_name}`}
                value={`${p.name}${SEP}${m.model_name}`}
              >
                {pickLabel(m.label, m.model_name)}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
      <ChevronDown
        aria-hidden
        className="pointer-events-none absolute right-2 h-3.5 w-3.5 opacity-60"
      />
    </div>
  );
}
