import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import { createProvider, updateProvider } from "@/api/admin-llm";
import { FormError, FormRow } from "@/components/shared/form";
import { Modal } from "@/components/shared/Modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { AdminLlmProvider, ProviderCreate, ProviderUpdate } from "@/types/admin-llm";

const schema = z.object({
  name: z
    .string()
    .min(1, "标识必填")
    .max(64)
    .regex(/^[a-z0-9_-]+$/, "仅小写字母、数字、下划线、连字符"),
  label_zh: z.string().max(128),
  description_zh: z.string().max(512),
  protocol: z.string().min(1, "请选择协议"),
  base_url: z.string().max(512),
  api_key: z.string(),
  supported_types: z.string().max(256),
  enabled: z.boolean(),
  sort: z.number().int(),
});
type FormValues = z.infer<typeof schema>;

const EMPTY: FormValues = {
  name: "",
  label_zh: "",
  description_zh: "",
  protocol: "openai",
  base_url: "",
  api_key: "",
  supported_types: "chat",
  enabled: true,
  sort: 0,
};

interface Props {
  open: boolean;
  /** 传入则编辑，否则新建。 */
  provider?: AdminLlmProvider | null;
  /** 协议下拉选项（来自 listLlmProtocols）。 */
  protocols: string[];
  onClose: () => void;
}

/** 提供商 新建/编辑 弹窗。编辑时 name 不可改、api_key 留空=保留原密钥。 */
export function LlmProviderFormModal({ open, provider, protocols, onClose }: Props) {
  const queryClient = useQueryClient();
  const editing = Boolean(provider);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: EMPTY });

  useEffect(() => {
    if (!open) return;
    reset(
      provider
        ? {
            name: provider.name,
            label_zh: provider.label?.zh_Hans ?? "",
            description_zh: provider.description?.zh_Hans ?? "",
            protocol: provider.protocol || "openai",
            base_url: provider.base_url || "",
            api_key: "",
            supported_types: (provider.supported_model_types || ["chat"]).join(", "),
            enabled: provider.enabled,
            sort: provider.sort ?? 0,
          }
        : EMPTY,
    );
  }, [open, provider, reset]);

  const mutation = useMutation({
    mutationFn: (values: FormValues) => {
      const supported = values.supported_types
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const base: ProviderUpdate = {
        label: values.label_zh ? { zh_Hans: values.label_zh } : {},
        description: values.description_zh ? { zh_Hans: values.description_zh } : {},
        protocol: values.protocol,
        base_url: values.base_url,
        supported_model_types: supported.length ? supported : ["chat"],
        enabled: values.enabled,
        sort: values.sort,
      };
      if (values.api_key) base.api_key = values.api_key; // 非空才覆盖
      if (editing) return updateProvider(provider!.id, base);
      return createProvider({ ...base, name: values.name } as ProviderCreate);
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
      title={editing ? "编辑提供商" : "新增提供商"}
      onClose={onClose}
      className="max-w-md"
    >
      <form onSubmit={handleSubmit((v) => mutation.mutate(v))} className="space-y-3">
        <FormRow label="标识（唯一）" htmlFor="lp-name" error={errors.name?.message}>
          <Input id="lp-name" {...register("name")} disabled={editing} placeholder="例如 my_gateway" />
        </FormRow>
        <FormRow label="显示名" htmlFor="lp-label" error={errors.label_zh?.message}>
          <Input id="lp-label" {...register("label_zh")} placeholder="例如 我的网关" />
        </FormRow>
        <FormRow label="描述（可选）" htmlFor="lp-desc" error={errors.description_zh?.message}>
          <Input id="lp-desc" {...register("description_zh")} />
        </FormRow>
        <FormRow label="协议" htmlFor="lp-protocol" error={errors.protocol?.message}>
          <select
            id="lp-protocol"
            {...register("protocol")}
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            {protocols.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </FormRow>
        <FormRow label="Base URL" htmlFor="lp-baseurl" error={errors.base_url?.message}>
          <Input id="lp-baseurl" {...register("base_url")} placeholder="https://api.example.com/v1" />
        </FormRow>
        <FormRow
          label={editing ? "API Key（留空=保留原密钥）" : "API Key（可选）"}
          htmlFor="lp-key"
          error={errors.api_key?.message}
        >
          <Input
            id="lp-key"
            type="password"
            autoComplete="new-password"
            {...register("api_key")}
            placeholder={
              editing && provider?.has_api_key
                ? `已配置 ${provider.api_key_mask}`
                : provider?.api_key_env
                  ? `留空则用环境变量 ${provider.api_key_env}`
                  : "sk-..."
            }
          />
        </FormRow>
        <FormRow label="支持类型（逗号分隔）" htmlFor="lp-types" error={errors.supported_types?.message}>
          <Input id="lp-types" {...register("supported_types")} placeholder="chat" />
        </FormRow>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" {...register("enabled")} />
            启用
          </label>
          <FormRow label="排序" htmlFor="lp-sort" error={errors.sort?.message}>
            <Input id="lp-sort" type="number" className="w-24" {...register("sort", { valueAsNumber: true })} />
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
