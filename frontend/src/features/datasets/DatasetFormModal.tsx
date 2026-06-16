import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import { createDataset, updateDataset } from "@/api/datasets";
import { FormError, FormRow } from "@/components/shared/form";
import { Modal } from "@/components/shared/Modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { Dataset } from "@/types/datasets";

const schema = z.object({
  name: z.string().min(1, "请输入名称").max(128, "名称最多 128 字"),
  icon: z.string().max(512, "URL 过长"),
  description: z.string().max(2000, "描述最多 2000 字"),
});
type FormValues = z.infer<typeof schema>;

const EMPTY: FormValues = { name: "", icon: "", description: "" };

interface Props {
  open: boolean;
  /** 传入则编辑，否则新建。 */
  dataset?: Dataset | null;
  onClose: () => void;
}

/** 知识库 新建/编辑 弹窗（rhf+zod，基于通用 Modal）。 */
export function DatasetFormModal({ open, dataset, onClose }: Props) {
  const queryClient = useQueryClient();
  const editing = Boolean(dataset);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: EMPTY });

  // 打开时按 编辑/新建 重置表单。
  useEffect(() => {
    if (open) {
      reset(
        dataset
          ? { name: dataset.name, icon: dataset.icon, description: dataset.description }
          : EMPTY,
      );
    }
  }, [open, dataset, reset]);

  const mutation = useMutation({
    mutationFn: (values: FormValues) =>
      editing ? updateDataset(dataset!.id, values) : createDataset(values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
      onClose();
    },
  });

  return (
    <Modal
      open={open}
      title={editing ? "编辑知识库" : "新建知识库"}
      onClose={onClose}
      className="max-w-lg"
    >
      <form onSubmit={handleSubmit((v) => mutation.mutate(v))} className="space-y-4">
        <FormRow label="名称" htmlFor="ds-name" error={errors.name?.message}>
          <Input id="ds-name" {...register("name")} placeholder="例如 产品手册" />
        </FormRow>
        <FormRow label="图标 URL（可选）" htmlFor="ds-icon" error={errors.icon?.message}>
          <Input id="ds-icon" {...register("icon")} placeholder="https://…/icon.png" />
        </FormRow>
        <FormRow label="描述（可选）" htmlFor="ds-desc" error={errors.description?.message}>
          <Textarea id="ds-desc" rows={3} {...register("description")} placeholder="这个知识库的用途…" />
        </FormRow>

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
