import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import { createApp } from "@/api/apps";
import { FormError, FormRow } from "@/components/shared/form";
import { Modal } from "@/components/shared/Modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { APP_DESCRIPTION_MAX, APP_NAME_MAX, PRESET_PROMPT_MAX } from "@/types/apps";

const schema = z.object({
  name: z.string().min(1, "请输入名称").max(APP_NAME_MAX, `名称最多 ${APP_NAME_MAX} 字`),
  description: z.string().max(APP_DESCRIPTION_MAX, `描述最多 ${APP_DESCRIPTION_MAX} 字`),
  preset_prompt: z.string().max(PRESET_PROMPT_MAX, `提示词最多 ${PRESET_PROMPT_MAX} 字`),
});
type FormValues = z.infer<typeof schema>;

const EMPTY: FormValues = { name: "", description: "", preset_prompt: "" };

interface Props {
  open: boolean;
  onClose: () => void;
}

/** 新建应用弹窗：创建成功后直接进入编排页。 */
export function AppFormModal({ open, onClose }: Props) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: EMPTY });

  useEffect(() => {
    if (open) reset(EMPTY);
  }, [open, reset]);

  const mutation = useMutation({
    mutationFn: (values: FormValues) =>
      createApp({ ...values, preset_prompt: values.preset_prompt.trim() || undefined }),
    onSuccess: (app) => {
      queryClient.invalidateQueries({ queryKey: ["apps"] });
      onClose();
      navigate(`/apps/${app.id}`);
    },
  });

  return (
    <Modal open={open} title="新建应用" onClose={onClose} className="max-w-lg">
      <form onSubmit={handleSubmit((v) => mutation.mutate(v))} className="space-y-4">
        <FormRow label="名称" htmlFor="app-name" error={errors.name?.message}>
          <Input id="app-name" {...register("name")} placeholder="例如 客服助手" />
        </FormRow>
        <FormRow label="描述（可选）" htmlFor="app-desc" error={errors.description?.message}>
          <Textarea id="app-desc" rows={3} {...register("description")} placeholder="这个应用是做什么的…" />
        </FormRow>
        <FormRow label="人设 / 提示词（可选）" htmlFor="app-preset" error={errors.preset_prompt?.message}>
          <Textarea
            id="app-preset"
            rows={4}
            {...register("preset_prompt")}
            placeholder="你是一个……（可稍后在编排页再细调）"
          />
        </FormRow>

        {mutation.isError && <FormError error={mutation.error} />}

        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="outline" onClick={onClose} disabled={mutation.isPending}>
            取消
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            创建
          </Button>
        </div>
      </form>
    </Modal>
  );
}
