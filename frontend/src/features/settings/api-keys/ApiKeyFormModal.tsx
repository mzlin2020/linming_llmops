import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import { createApiKey, updateApiKey } from "@/api/settings";
import { FormError, FormRow } from "@/components/shared/form";
import { Modal } from "@/components/shared/Modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { ApiKey } from "@/types/settings";

const schema = z.object({
  remark: z.string().max(255, "备注最多 255 字"),
  is_active: z.boolean(),
});
type FormValues = z.infer<typeof schema>;

const EMPTY: FormValues = { remark: "", is_active: true };

interface Props {
  open: boolean;
  /** 传入则编辑，否则新建。 */
  apiKey?: ApiKey | null;
  onClose: () => void;
}

/** API 密钥 新建/编辑 弹窗（备注 + 启停）。 */
export function ApiKeyFormModal({ open, apiKey, onClose }: Props) {
  const queryClient = useQueryClient();
  const editing = Boolean(apiKey);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: EMPTY });

  useEffect(() => {
    if (open) {
      reset(apiKey ? { remark: apiKey.remark, is_active: apiKey.is_active } : EMPTY);
    }
  }, [open, apiKey, reset]);

  const mutation = useMutation({
    mutationFn: (values: FormValues) =>
      editing ? updateApiKey(apiKey!.id, values) : createApiKey(values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
      onClose();
    },
  });

  return (
    <Modal open={open} title={editing ? "编辑密钥" : "新建密钥"} onClose={onClose} className="max-w-md">
      <form onSubmit={handleSubmit((v) => mutation.mutate(v))} className="space-y-4">
        <FormRow label="备注（可选）" htmlFor="ak-remark" error={errors.remark?.message}>
          <Input id="ak-remark" {...register("remark")} placeholder="例如 生产环境调用" />
        </FormRow>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...register("is_active")} />
          启用
        </label>

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
