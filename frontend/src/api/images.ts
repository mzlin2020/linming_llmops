/** 图像生成端点薄封装。响应经 axios 拦截器解信封后即下列返回值。 */
import { get, post } from "@/lib/http/client";
import { API_BASE } from "@/lib/http/config";
import type { PageQuery, PageResult } from "@/types/api";
import type { GeneratedImage, ImageToImageReq, TextToImageReq } from "@/types/images";

export function textToImage(body: TextToImageReq): Promise<GeneratedImage> {
  return post<GeneratedImage>("/images/text-to-image", body);
}

export function imageToImage(body: ImageToImageReq): Promise<GeneratedImage> {
  return post<GeneratedImage>("/images/image-to-image", body);
}

export function listImages(query: PageQuery): Promise<PageResult<GeneratedImage>> {
  return get<PageResult<GeneratedImage>>("/images", { params: query });
}

/** 把后端返回的相对能力 URL（/api/images/file/...）拼成可加载地址。
 *  后端 url 已含 /api 前缀；API_BASE 默认 /api，去重避免 //api/api。 */
export function imageSrc(url: string): string {
  if (/^https?:\/\//.test(url)) return url;
  if (API_BASE === "/api" || API_BASE === "") return url;
  return `${API_BASE.replace(/\/api$/, "")}${url}`;
}
