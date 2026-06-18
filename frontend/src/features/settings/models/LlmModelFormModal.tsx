import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import { createModel, updateModel } from "@/api/admin-llm";
import { FormError, FormRow } from "@/components/shared/form";
import { Modal } from "@/components/shared/Modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { AdminLlmModel, ModelCreate, ModelUpdate } from "@/types/admin-llm";

const MODEL_TYPES = ["chat", "text2img", "tts", "embedding", "rerank", "completion", "stt"];
const FEATURES = ["tool_call", "vision", "streaming", "json_mode", "reasoning"];

const schema = z.object({
  model_name: z.string().min(1, "模型名必填").max(128),
  label_zh: z.string().max(128),
  model_type: z.string().min(1),
  features: z.array(z.string()),
  context_window: z.number().int().min(1),
  max_output_tokens: z.string(),
  is_default: z.boolean(),
  deprecated: z.boolean(),
  enabled: z.boolean(),
  sort: z.number().int(),
});
type FormValues = z.infer<typeof schema>;

const EMPTY: FormValues = {
  model_name: "",
  label_zh: "",
  model_type: "chat",
  features: [],
  context_window: 4096,
  max_output_tokens: "",
  is_default: false,
  deprecated: false,
  enabled: true,
  sort: 0,
};

interface Props {
  open: boolean;
  /** 新建时所属提供商 id。 */
  providerId: number;
  /** 传入则编辑，否则新建。 */
  model?: AdminLlmModel | null;
  onClose: () => void;
}

/** 模型 新建/编辑 弹窗。 */
export function LlmModelFormModal({ open, providerId, model, onClose }: Props) {
  const queryClient = useQueryClient();
  const editing = Boolean(model);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: EMPTY });

  useEffect(() => {
    if (!open) return;
    reset(
      model
        ? {
            model_name: model.model_name,
            label_zh: model.label?.zh_Hans ?? "",
            model_type: model.model_type || "chat",
            features: model.features || [],
            context_window: model.context_window ?? 4096,
            max_output_tokens:
              model.max_output_tokens != null ? String(model.max_output_tokens) : "",
            is_default: model.is_default,
            deprecated: model.deprecated,
            enabled: model.enabled,
            sort: model.sort ?? 0,
          }
        : EMPTY,
    );
  }, [open, model, reset]);

  const mutation = useMutation({
    mutationFn: (values: FormValues) => {
      const maxOut = values.max_output_tokens.trim();
      const body: ModelUpdate = {
        label: values.label_zh ? { zh_Hans: values.label_zh } : {},
        model_type: values.model_type,
        features: values.features,
        context_window: values.context_window,
        max_output_tokens: maxOut ? Number(maxOut) : null,
        is_default: values.is_default,
        deprecated: values.deprecated,
        enabled: values.enabled,
        sort: values.sort,
      };
      if (editing) return updateModel(model!.id, { ...body, model_name: values.model_name });
      return createModel(providerId, { ...body, model_name: values.model_name } as ModelCreate);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["llm-admin-providers"] });
      queryClient.invalidateQueries({ queryKey: ["language-models"] });
      onClose();
    },
  });

  return (
    <Modal
      open={open}
      title={editing ? "编辑模型" : "新增模型"}
      onClose={onClose}
      className="max-w-md"
    >
      <form onSubmit={handleSubmit((v) => mutation.mutate(v))} className="space-y-3">
        <FormRow label="模型名（上游 model 参数）" htmlFor="lm-name" error={errors.model_name?.message}>
          <Input id="lm-name" {...register("model_name")} placeholder="例如 gpt-4o-mini" />
        </FormRow>
        <FormRow label="显示名（可选）" htmlFor="lm-label" error={errors.label_zh?.message}>
          <Input id="lm-label" {...register("label_zh")} />
        </FormRow>
        <FormRow label="类型" htmlFor="lm-type" error={errors.model_type?.message}>
          <select
            id="lm-type"
            {...register("model_type")}
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            {MODEL_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </FormRow>
        <div className="space-y-1.5">
          <p className="text-sm font-medium">能力特性</p>
          <div className="flex flex-wrap gap-3">
            {FEATURES.map((f) => (
              <label key={f} className="flex items-center gap-1.5 text-sm">
                <input type="checkbox" value={f} {...register("features")} />
                {f}
              </label>
            ))}
          </div>
        </div>
        <div className="flex gap-3">
          <FormRow label="上下文窗口" htmlFor="lm-ctx" error={errors.context_window?.message}>
            <Input id="lm-ctx" type="number" {...register("context_window", { valueAsNumber: true })} />
          </FormRow>
          <FormRow label="最大输出 tokens（可选）" htmlFor="lm-maxout" error={errors.max_output_tokens?.message}>
            <Input id="lm-maxout" type="number" {...register("max_output_tokens")} />
          </FormRow>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" {...register("enabled")} />
            启用
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" {...register("is_default")} />
            默认模型
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" {...register("deprecated")} />
            已弃用
          </label>
          <FormRow label="排序" htmlFor="lm-sort" error={errors.sort?.message}>
            <Input id="lm-sort" type="number" className="w-20" {...register("sort", { valueAsNumber: true })} />
          </FormRow>
        </div>

        {mutation.isError && <FormError error={mutation.error} />}

        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="outline" onClick={onClose} disabled={mutation.isPending}>
            取消
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {editing ? "保存" : "创建"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
