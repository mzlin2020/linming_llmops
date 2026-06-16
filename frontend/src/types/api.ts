/** 后端统一响应信封：`{code, message, data}`，HTTP status 与 code 一致。 */
export interface Envelope<T = unknown> {
  code: number;
  message: string;
  data: T;
}

/** 分页器（后端 `data.paginator`）。 */
export interface Paginator {
  current_page: number;
  page_size: number;
  total_page: number;
  total_record: number;
}

/** 分页响应体（后端 `data` = `{list, paginator}`）。 */
export interface PageResult<T> {
  list: T[];
  paginator: Paginator;
}

/** 通用分页查询参数。 */
export interface PageQuery {
  current_page?: number;
  page_size?: number;
  search_word?: string;
}
