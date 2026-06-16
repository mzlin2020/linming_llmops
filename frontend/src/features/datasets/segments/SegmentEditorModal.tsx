import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import { createSegment, updateSegment } from "@/api/datasets";
import { FormError, FormRow } from "@/components/shared/form";
import { Modal } from "@/components/shared/Modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { Segment } from "@/types/datasets";

const schema = z.object({
  content: z.string().min(1, "请输入片段内容").max(4000, "内容最多 4000 字"),
  keywords: z.string(),
});
type FormValues = z.infer<typeof schema>;

interface Props {
  open: boolean;
  datasetId: number;
  documentId: number;
  segment?: Segment | null;
  onClose: () => void;
}

/** 片段 新建/编辑 弹窗。keywords 逗号分隔，留空则后端自动抽取。 */
export function SegmentEditorModal({ open, datasetId, documentId, segment, onClose }: Props) {
  const queryClient = useQueryClient();
  const editing = Boolean(segment);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { content: "", keywords: "" },
  });

  useEffect(() => {
    if (open) {
      reset(
        segment
          ? { content: segment.content, keywords: segment.keywords.join(", ") }
          : { content: "", keywords: "" },
      );
    }
  }, [open, segment, reset]);

  const mutation = useMutation({
    mutationFn: (values: FormValues) => {
      const keywords = values.keywords
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const body = { content: values.content, keywords: keywords.length ? keywords : undefined };
      return editing
        ? updateSegment(datasetId, documentId, segment!.id, body)
        : createSegment(datasetId, documentId, body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["segments", documentId] });
      onClose();
    },
  });

  return (
    <Modal
      open={open}
      title={editing ? "编辑片段" : "新建片段"}
      onClose={onClose}
      className="max-w-xl"
    >
      <form onSubmit={handleSubmit((v) => mutation.mutate(v))} className="space-y-4">
        <FormRow label="内容" htmlFor="seg-content" error={errors.content?.message}>
          <Textarea id="seg-content" rows={6} {...register("content")} placeholder="片段内容…" />
        </FormRow>
        <FormRow
          label="关键词（逗号分隔，留空自动抽取）"
          htmlFor="seg-keywords"
          error={errors.keywords?.message}
        >
          <Input id="seg-keywords" {...register("keywords")} placeholder="关键词1, 关键词2" />
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
