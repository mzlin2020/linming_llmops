/** 设置模块前端类型。后端契约见 backend/internal/{schema,handler} 的 api_key。 */

/** 开放 API 密钥（GET /api-keys 单项；api_key 为明文串，账号自管自己的密钥）。 */
export interface ApiKey {
  id: number;
  api_key: string;
  is_active: boolean;
  remark: string;
  created_at: number;
  updated_at: number;
}

/** 创建/更新密钥请求体。 */
export interface ApiKeyUpsert {
  remark?: string;
  is_active?: boolean;
}
