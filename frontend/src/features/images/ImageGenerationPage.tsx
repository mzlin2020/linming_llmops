import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ImageIcon, Loader2 } from "lucide-react";

import { imageSrc, imageToImage, listImages, textToImage } from "@/api/images";
import { FormError } from "@/components/shared/form";
import { Modal } from "@/components/shared/Modal";
import { Pagination } from "@/components/shared/Pagination";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { IMAGE_SIZE_PRESETS, type GeneratedImage, type ImageGenType } from "@/types/images";

const PAGE_SIZE = 12;

/** 图像生成：左侧文生图 / 图生图表单，右侧历史画廊（点击放大）。 */
export function ImageGenerationPage() {
  const qc = useQueryClient();
  const [mode, setMode] = useState<ImageGenType>("text2img");
  const [prompt, setPrompt] = useState("");
  const [size, setSize] = useState<string>(IMAGE_SIZE_PRESETS[0].value);
  const [imageUrl, setImageUrl] = useState("");
  const [page, setPage] = useState(1);
  const [preview, setPreview] = useState<GeneratedImage | null>(null);

  const gallery = useQuery({
    queryKey: ["images", page],
    queryFn: () => listImages({ current_page: page, page_size: PAGE_SIZE }),
  });

  const generate = useMutation({
    mutationFn: () => {
      const base = { prompt: prompt.trim(), size: size || undefined };
      return mode === "img2img"
        ? imageToImage({ ...base, image_url: imageUrl.trim() })
        : textToImage(base);
    },
    onSuccess: () => {
      setPage(1);
      qc.invalidateQueries({ queryKey: ["images"] });
    },
  });

  const canSubmit =
    prompt.trim().length > 0 && (mode === "text2img" || imageUrl.trim().length > 0) && !generate.isPending;

  const submit = () => {
    if (canSubmit) generate.mutate();
  };

  const images = gallery.data?.list ?? [];

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold tracking-tight">图像生成</h1>
        <p className="text-sm text-muted-foreground">
          根据文字描述生成图片（文生图），或基于参考图改写（图生图）。需在部署环境配置生图模型。
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        {/* ---------------- 左：表单 ---------------- */}
        <div className="space-y-4">
          <div className="inline-flex rounded-md border p-0.5 text-sm">
            {(["text2img", "img2img"] as ImageGenType[]).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={
                  "rounded px-3 py-1.5 transition-colors " +
                  (mode === m ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground")
                }
              >
                {m === "text2img" ? "文生图" : "图生图"}
              </button>
            ))}
          </div>

          {mode === "img2img" && (
            <label className="block space-y-1 text-sm">
              <span className="text-muted-foreground">参考图 URL（须在后端白名单域名内）</span>
              <Input
                value={imageUrl}
                onChange={(e) => setImageUrl(e.target.value)}
                placeholder="https://…/ref.png"
                aria-label="参考图 URL"
              />
            </label>
          )}

          <label className="block space-y-1 text-sm">
            <span className="text-muted-foreground">提示词</span>
            <Textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={5}
              placeholder="对要生成的图片做尽量具体的文字描述…"
              aria-label="提示词"
            />
          </label>

          <label className="block space-y-1 text-sm">
            <span className="text-muted-foreground">尺寸</span>
            <select
              value={size}
              onChange={(e) => setSize(e.target.value)}
              className="block h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              aria-label="尺寸"
            >
              {IMAGE_SIZE_PRESETS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>

          <Button onClick={submit} disabled={!canSubmit} className="w-full">
            {generate.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {generate.isPending ? "生成中…" : "生成图片"}
          </Button>
          {generate.isError && <FormError error={generate.error} />}
        </div>

        {/* ---------------- 右：画廊 ---------------- */}
        <div className="space-y-3">
          {gallery.isLoading ? (
            <p className="py-12 text-center text-sm text-muted-foreground">加载中…</p>
          ) : images.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-16 text-muted-foreground">
              <ImageIcon className="h-8 w-8" />
              <p className="text-sm">还没有生成记录，先在左侧生成一张吧。</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {images.map((img) => (
                <button
                  key={img.id}
                  type="button"
                  onClick={() => setPreview(img)}
                  className="group overflow-hidden rounded-lg border bg-muted/30 text-left"
                  title={img.prompt}
                >
                  <img
                    src={imageSrc(img.url)}
                    alt={img.prompt}
                    loading="lazy"
                    className="aspect-square w-full object-cover transition-transform group-hover:scale-105"
                  />
                  <p className="truncate px-2 py-1.5 text-xs text-muted-foreground">{img.prompt}</p>
                </button>
              ))}
            </div>
          )}
          {gallery.data && <Pagination paginator={gallery.data.paginator} onChange={setPage} />}
        </div>
      </div>

      {/* ---------------- 放大预览 ---------------- */}
      <Modal
        open={preview !== null}
        title={preview?.type === "img2img" ? "图生图" : "文生图"}
        onClose={() => setPreview(null)}
        className="max-w-2xl"
      >
        {preview && (
          <div className="space-y-3">
            <img
              src={imageSrc(preview.url)}
              alt={preview.prompt}
              className="max-h-[60vh] w-full rounded-md object-contain"
            />
            <dl className="space-y-1 text-sm">
              <div className="flex gap-2">
                <dt className="shrink-0 text-muted-foreground">提示词</dt>
                <dd className="break-words">{preview.prompt}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="shrink-0 text-muted-foreground">模型</dt>
                <dd className="break-all">
                  {preview.provider} / {preview.model}
                </dd>
              </div>
              {preview.size && (
                <div className="flex gap-2">
                  <dt className="shrink-0 text-muted-foreground">尺寸</dt>
                  <dd>{preview.size}</dd>
                </div>
              )}
            </dl>
            <a
              href={imageSrc(preview.url)}
              target="_blank"
              rel="noreferrer"
              className="inline-block text-sm text-primary underline"
            >
              在新标签页打开原图
            </a>
          </div>
        )}
      </Modal>
    </div>
  );
}
