/**
 * 图像生成模块前端类型。对齐后端 image_schema.py + ImageGenerationService._to_dict。
 *
 * 图片地址为后端「能力 URL」（/api/images/file/<uuid>.<ext>，不可猜、无需登录），
 * 可直接作为 <img src> 加载（经 nginx /api 代理到后端）。
 */

export type ImageGenType = "text2img" | "img2img";

/** 一条生图记录（列表项 / 生成结果，对齐 _to_dict）。 */
export interface GeneratedImage {
  id: number;
  type: ImageGenType;
  provider: string;
  model: string;
  prompt: string;
  size: string;
  input_image_url: string;
  url: string;
  created_at: number;
}

/** 文生图请求体（provider/model 留空走后端默认）。 */
export interface TextToImageReq {
  prompt: string;
  size?: string;
  provider?: string;
  model?: string;
  guidance_scale?: number;
}

/** 图生图请求体：在文生图基础上必带参考图 URL（须在后端白名单域名内）。 */
export interface ImageToImageReq extends TextToImageReq {
  image_url: string;
}

/** 常用尺寸预设（满足主流生图模型 ≥ 约369万像素的最小要求；模型不支持时上游会报错）。 */
export const IMAGE_SIZE_PRESETS = [
  { value: "2048x2048", label: "1:1 · 2048×2048" },
  { value: "2304x1728", label: "4:3 · 2304×1728" },
  { value: "1728x2304", label: "3:4 · 1728×2304" },
  { value: "2560x1440", label: "16:9 · 2560×1440" },
  { value: "1440x2560", label: "9:16 · 1440×2560" },
  { value: "4K", label: "4K · 更大更慢" },
] as const;
