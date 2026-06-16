import { type ReactNode } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Plus, Sparkles, Trash2 } from "lucide-react";

import { listLanguageModels } from "@/api/apps";
import { optimizePresetPrompt, suggestOpeningQuestions } from "@/api/ai";
import { DatasetSelector } from "@/components/shared/DatasetSelector";
import { ToolSelector } from "@/components/shared/ToolSelector";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { AppConfig } from "@/types/apps";
import {
  DIALOG_ROUND_MAX,
  DIALOG_ROUND_MIN,
  MAX_OPENING_QUESTIONS,
  OPENING_QUESTION_MAX_LEN,
  OPENING_STATEMENT_MAX,
  PRESET_PROMPT_MAX,
  pickLabel,
} from "@/types/apps";

interface Props {
  value: AppConfig;
  onChange: (next: AppConfig) => void;
}

/** 编排页左栏：草稿配置编辑器（模型 / 对话 / 人设 / 开场 / 工具 / 知识库 / 开关）。受控。 */
export function ConfigEditor({ value, onChange }: Props) {
  const set = (patch: Partial<AppConfig>) => onChange({ ...value, ...patch });

  return (
    <div className="space-y-6">
      <Section title="模型">
        <ModelSelect
          value={value.model_config}
          onChange={(model_config) => set({ model_config })}
        />
        <label className="flex items-center justify-between gap-3 text-sm">
          <span className="text-muted-foreground">携带历史对话轮数</span>
          <Input
            type="number"
            min={DIALOG_ROUND_MIN}
            max={DIALOG_ROUND_MAX}
            value={value.dialog_round}
            onChange={(e) =>
              set({
                dialog_round: Math.max(
                  DIALOG_ROUND_MIN,
                  Math.min(DIALOG_ROUND_MAX, Number(e.target.value) || 0),
                ),
              })
            }
            aria-label="对话轮数"
            className="w-24"
          />
        </label>
      </Section>

      <Section title="人设与回复逻辑">
        <PresetPromptField
          value={value.preset_prompt}
          onChange={(preset_prompt) => set({ preset_prompt })}
        />
      </Section>

      <Section title="对话开场">
        <div className="space-y-1.5">
          <span className="text-sm text-muted-foreground">开场白</span>
          <Textarea
            rows={2}
            maxLength={OPENING_STATEMENT_MAX}
            value={value.opening_statement}
            onChange={(e) => set({ opening_statement: e.target.value })}
            aria-label="开场白"
            placeholder="用户进入对话时看到的第一句话…"
          />
        </div>
        <OpeningQuestionsField
          preset={value.preset_prompt}
          value={value.opening_questions}
          onChange={(opening_questions) => set({ opening_questions })}
        />
      </Section>

      <Section title="工具">
        <ToolSelector value={value.tools} onChange={(tools) => set({ tools })} />
      </Section>

      <Section title="知识库">
        <DatasetSelector value={value.datasets} onChange={(datasets) => set({ datasets })} />
      </Section>

      <Section title="能力开关">
        <ToggleRow
          label="长期记忆"
          hint="跨轮滚动摘要并注入系统提示"
          checked={value.long_term_memory.enable}
          onChange={(enable) => set({ long_term_memory: { enable } })}
        />
        <ToggleRow
          label="回答后推荐问题"
          checked={value.suggested_after_answer.enable}
          onChange={(enable) => set({ suggested_after_answer: { enable } })}
        />
        <ToggleRow
          label="语音输入"
          hint="v1.1 提供"
          checked={value.speech_to_text.enable}
          onChange={(enable) => set({ speech_to_text: { enable } })}
        />
        <ToggleRow
          label="语音输出"
          hint="v1.1 提供"
          checked={value.text_to_speech.enable}
          onChange={(enable) => set({ text_to_speech: { enable } })}
        />
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h3 className="text-sm font-semibold">{title}</h3>
      {children}
    </section>
  );
}

function ToggleRow({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-3 text-sm">
      <span>
        {label}
        {hint && <span className="ml-2 text-xs text-muted-foreground">{hint}</span>}
      </span>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
    </label>
  );
}

function ModelSelect({
  value,
  onChange,
}: {
  value: AppConfig["model_config"];
  onChange: (next: AppConfig["model_config"]) => void;
}) {
  const query = useQuery({ queryKey: ["language-models"], queryFn: listLanguageModels });
  const providers = query.data ?? [];
  const current = providers.find((p) => p.name === value.provider);
  const knownModel = !!current?.models.some((m) => m.model_name === value.model);

  return (
    <div className="grid grid-cols-2 gap-2">
      <select
        aria-label="模型提供商"
        className={SELECT_CLS}
        value={value.provider}
        onChange={(e) => {
          const provider = providers.find((p) => p.name === e.target.value);
          const firstModel = provider?.models[0]?.model_name ?? "";
          onChange({ ...value, provider: e.target.value, model: firstModel });
        }}
      >
        {/* 当前值不在目录里（如默认回落值）时仍保留为可见选项 */}
        <FallbackOption show={!current} value={value.provider} />
        {providers.map((p) => (
          <option key={p.name} value={p.name}>
            {pickLabel(p.label, p.name)}
          </option>
        ))}
      </select>
      <select
        aria-label="模型"
        className={SELECT_CLS}
        value={value.model}
        onChange={(e) => onChange({ ...value, model: e.target.value })}
      >
        <FallbackOption show={!knownModel} value={value.model} />
        {(current?.models ?? []).map((m) => (
          <option key={m.model_name} value={m.model_name}>
            {pickLabel(m.label, m.model_name)}
          </option>
        ))}
      </select>
    </div>
  );
}

const SELECT_CLS =
  "h-9 rounded-md border border-input bg-transparent px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring";

/** provider/model 当前值不在目录里时，把它本身渲染成一个兜底选项，避免下拉显示为空。 */
function FallbackOption({ show, value }: { show: boolean; value: string }) {
  if (!show || !value) return null;
  return <option value={value}>{value}</option>;
}

function PresetPromptField({
  value,
  onChange,
}: {
  value: string;
  onChange: (next: string) => void;
}) {
  const optimize = useMutation({
    mutationFn: () => optimizePresetPrompt(value.trim()),
    onSuccess: (prompt) => onChange(prompt),
  });

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">人设 / 系统提示词</span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!value.trim() || optimize.isPending}
          onClick={() => optimize.mutate()}
        >
          <Sparkles className="h-4 w-4" /> {optimize.isPending ? "优化中…" : "AI 优化"}
        </Button>
      </div>
      <Textarea
        rows={6}
        maxLength={PRESET_PROMPT_MAX}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label="人设提示词"
        placeholder="描述这个应用的角色、语气、能力边界…"
      />
      {optimize.isError && <p className="text-sm text-destructive">优化失败，请稍后再试</p>}
    </div>
  );
}

function OpeningQuestionsField({
  preset,
  value,
  onChange,
}: {
  preset: string;
  value: string[];
  onChange: (next: string[]) => void;
}) {
  const atLimit = value.length >= MAX_OPENING_QUESTIONS;

  const suggest = useMutation({
    mutationFn: () => suggestOpeningQuestions(preset.trim()),
    onSuccess: (qs) => onChange(qs.slice(0, MAX_OPENING_QUESTIONS)),
  });

  const setAt = (i: number, v: string) =>
    onChange(value.map((q, idx) => (idx === i ? v.slice(0, OPENING_QUESTION_MAX_LEN) : q)));
  const add = () => !atLimit && onChange([...value, ""]);
  const removeAt = (i: number) => onChange(value.filter((_, idx) => idx !== i));

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          开场问题 {value.length}/{MAX_OPENING_QUESTIONS}
        </span>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={suggest.isPending}
            onClick={() => suggest.mutate()}
          >
            <Sparkles className="h-4 w-4" /> {suggest.isPending ? "生成中…" : "AI 建议"}
          </Button>
          <Button type="button" variant="outline" size="sm" disabled={atLimit} onClick={add}>
            <Plus className="h-4 w-4" /> 添加
          </Button>
        </div>
      </div>
      {value.map((q, i) => (
        <div key={i} className="flex items-center gap-2">
          <Input
            value={q}
            onChange={(e) => setAt(i, e.target.value)}
            aria-label={`开场问题 ${i + 1}`}
            placeholder="例如：你能帮我做什么？"
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => removeAt(i)}
            aria-label={`删除开场问题 ${i + 1}`}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ))}
      {suggest.isError && <p className="text-sm text-destructive">生成失败，请稍后再试</p>}
    </div>
  );
}
