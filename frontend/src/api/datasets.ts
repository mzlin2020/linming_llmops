import { get, post, postForm } from "@/lib/http/client";
import type { PageQuery, PageResult } from "@/types/api";
import type {
  AiDocument,
  CreateDocumentsReq,
  CreateDocumentsResult,
  Dataset,
  DatasetQuery,
  DatasetUpsert,
  HitReq,
  HitResult,
  Segment,
  SegmentUpsert,
  UploadFile,
} from "@/types/datasets";

// ---------- 知识库 CRUD + 命中测试 + 查询历史 ----------
export function listDatasets(query: PageQuery) {
  return get<PageResult<Dataset>>("/datasets", { params: query });
}

export function getDataset(id: number) {
  return get<Dataset>(`/datasets/${id}`);
}

/** 创建知识库（后端仅返回 {id}）。 */
export function createDataset(body: DatasetUpsert) {
  return post<{ id: number }>("/datasets", body);
}

export function updateDataset(id: number, body: DatasetUpsert) {
  return post(`/datasets/${id}`, body);
}

export function deleteDataset(id: number) {
  return post(`/datasets/${id}/delete`);
}

export function hitDataset(id: number, body: HitReq) {
  return post<HitResult[]>(`/datasets/${id}/hit`, body);
}

export function listDatasetQueries(id: number) {
  return get<DatasetQuery[]>(`/datasets/${id}/queries`);
}

// ---------- 文件上传 ----------
export function uploadFile(file: File) {
  const form = new FormData();
  form.append("file", file);
  return postForm<UploadFile>("/upload-files/file", form);
}

// ---------- 文档 ----------
export function listDocuments(datasetId: number, query: PageQuery) {
  return get<PageResult<AiDocument>>(`/datasets/${datasetId}/documents`, { params: query });
}

export function createDocuments(datasetId: number, body: CreateDocumentsReq) {
  return post<CreateDocumentsResult>(`/datasets/${datasetId}/documents`, body);
}

export function renameDocument(datasetId: number, documentId: number, name: string) {
  return post<AiDocument>(`/datasets/${datasetId}/documents/${documentId}/name`, { name });
}

export function setDocumentEnabled(datasetId: number, documentId: number, enabled: boolean) {
  return post(`/datasets/${datasetId}/documents/${documentId}/enabled`, { enabled });
}

export function deleteDocument(datasetId: number, documentId: number) {
  return post(`/datasets/${datasetId}/documents/${documentId}/delete`);
}

export function reindexDocument(datasetId: number, documentId: number) {
  return post<AiDocument>(`/datasets/${datasetId}/documents/${documentId}/re-index`);
}

// ---------- 片段 ----------
export function listSegments(datasetId: number, documentId: number, query: PageQuery) {
  return get<PageResult<Segment>>(
    `/datasets/${datasetId}/documents/${documentId}/segments`,
    { params: query },
  );
}

export function createSegment(datasetId: number, documentId: number, body: SegmentUpsert) {
  return post<Segment>(`/datasets/${datasetId}/documents/${documentId}/segments`, body);
}

export function updateSegment(
  datasetId: number,
  documentId: number,
  segmentId: number,
  body: SegmentUpsert,
) {
  return post<Segment>(
    `/datasets/${datasetId}/documents/${documentId}/segments/${segmentId}`,
    body,
  );
}

export function setSegmentEnabled(
  datasetId: number,
  documentId: number,
  segmentId: number,
  enabled: boolean,
) {
  return post(
    `/datasets/${datasetId}/documents/${documentId}/segments/${segmentId}/enabled`,
    { enabled },
  );
}

export function deleteSegment(datasetId: number, documentId: number, segmentId: number) {
  return post(`/datasets/${datasetId}/documents/${documentId}/segments/${segmentId}/delete`);
}
