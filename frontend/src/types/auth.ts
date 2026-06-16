/** 账户 DTO（后端 `Account.to_dict()`）。 */
export interface Account {
  id: number;
  email: string;
  name: string;
  avatar: string | null;
}

/** 登录/注册返回（`data`）。 */
export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  account: Account;
}

/** 刷新返回（`data`）。 */
export interface RefreshResult {
  access_token: string;
}
