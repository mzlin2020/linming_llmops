#!/usr/bin/env bash
# =============================================================================
# linming_llmops 端到端冒烟（Phase 6 出口）
#
# 默认经前端 nginx（FRONTEND_PORT）打 /api，顺带验证反代与 SSE 不缓冲。
# 链路：ping → 注册/登录 → 建应用 → [SSE 对话*] → 建知识库 → 上传 → 索引 → RAG 检索
#   *SSE 对话步骤需 LLM：仅当设置了 OPENAI_API_KEY 才执行，否则跳过（其余步骤本地嵌入即可，无需付费 key）。
#
# 用法：
#   bash deploy/smoke-test.sh
#   FRONTEND_PORT=8080 OPENAI_API_KEY=sk-... bash deploy/smoke-test.sh
#   BASE_URL=http://127.0.0.1:8080 bash deploy/smoke-test.sh   # 直连后端可设 http://127.0.0.1:5001
#
# 依赖：bash、curl、jq。任一步失败即非零退出。
# =============================================================================
set -euo pipefail

FRONTEND_PORT="${FRONTEND_PORT:-8080}"
BASE_URL="${BASE_URL:-http://127.0.0.1:${FRONTEND_PORT}}"
API="${BASE_URL}/api"
READY_TIMEOUT="${READY_TIMEOUT:-180}"   # 等待全栈就绪的秒数（首启需拉起容器/下载模型）
INDEX_TIMEOUT="${INDEX_TIMEOUT:-180}"   # 等待文档索引完成的秒数

EMAIL="smoke+$(date +%s)-${RANDOM}@example.com"
PASSWORD="smoke-pass-123"

log()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m  ✓ %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m  ✗ %s\033[0m\n' "$*" >&2; exit 1; }

command -v curl >/dev/null || die "需要 curl"
command -v jq   >/dev/null || die "需要 jq"

# api_call METHOD PATH [json_body] —— 带鉴权发请求；非 2xx 即失败。回显响应体 .data。
api_call() {
  local method="$1" path="$2" body="${3:-}"
  local args=(-sS -X "$method" -w '\n%{http_code}' -H "Accept: application/json")
  [[ -n "${TOKEN:-}" ]] && args+=(-H "Authorization: Bearer ${TOKEN}")
  if [[ -n "$body" ]]; then args+=(-H "Content-Type: application/json" -d "$body"); fi
  local out code json
  out="$(curl "${args[@]}" "${API}${path}")" || die "请求失败 ${method} ${path}"
  code="$(tail -n1 <<<"$out")"
  json="$(sed '$d' <<<"$out")"
  if [[ "$code" != 200 ]]; then
    die "${method} ${path} -> HTTP ${code}: $(jq -r '.message // empty' <<<"$json" 2>/dev/null || echo "$json")"
  fi
  jq -c '.data' <<<"$json"
}

# ---------------------------------------------------------------------------
log "1/7 等待全栈就绪（${BASE_URL}）"
deadline=$(( $(date +%s) + READY_TIMEOUT ))
until curl -fsS "${API}/ping" >/dev/null 2>&1; do
  (( $(date +%s) < deadline )) || die "等待 /api/ping 超时（${READY_TIMEOUT}s）"
  sleep 3
done
# 前端静态资源也应可达（验证 nginx 在线）
curl -fsS "${BASE_URL}/" >/dev/null || die "前端首页不可达（${BASE_URL}/）"
ok "后端 /api/ping 与前端首页均就绪"

# ---------------------------------------------------------------------------
log "2/7 注册并登录（${EMAIL}）"
reg="$(curl -sS -X POST -w '\n%{http_code}' -H "Content-Type: application/json" \
  -d "$(jq -nc --arg e "$EMAIL" --arg p "$PASSWORD" '{email:$e, password:$p, name:"smoke"}')" \
  "${API}/auth/register")"
reg_code="$(tail -n1 <<<"$reg")"
if [[ "$reg_code" == 200 ]]; then
  TOKEN="$(sed '$d' <<<"$reg" | jq -r '.data.access_token')"
  ok "注册成功并取得 token"
else
  # 注册关闭/已存在：回落登录（需 .env 配 BOOTSTRAP_ACCOUNT_* 或预置账号）
  EMAIL="${BOOTSTRAP_ACCOUNT_EMAIL:-$EMAIL}"
  PASSWORD="${BOOTSTRAP_ACCOUNT_PASSWORD:-$PASSWORD}"
  TOKEN="$(api_call POST /auth/login "$(jq -nc --arg e "$EMAIL" --arg p "$PASSWORD" '{email:$e, password:$p}')" | jq -r '.access_token')"
  ok "登录成功并取得 token"
fi
[[ -n "$TOKEN" && "$TOKEN" != null ]] || die "未取得 access_token"

# ---------------------------------------------------------------------------
log "3/7 创建应用"
APP_ID="$(api_call POST /apps "$(jq -nc '{name:"smoke-app", description:"e2e smoke"}')" | jq -r '.id')"
[[ -n "$APP_ID" && "$APP_ID" != null ]] || die "建应用未返回 id"
ok "应用 id=${APP_ID}"

# ---------------------------------------------------------------------------
log "4/7 SSE 对话（R4：验证不缓冲）"
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  hdr="$(mktemp)"; bod="$(mktemp)"
  # -N 关闭客户端缓冲；-D 落响应头；--max-time 兜底
  curl -sS -N -D "$hdr" -o "$bod" --max-time 90 \
    -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
    -H "Accept: text/event-stream" \
    -d "$(jq -nc '{query:"用一句话介绍你自己"}')" \
    "${API}/apps/${APP_ID}/conversations" || die "SSE 请求失败"
  # R4：经 nginx 反代应带 X-Accel-Buffering: no
  if grep -iq '^x-accel-buffering: *no' "$hdr"; then
    ok "响应头含 X-Accel-Buffering: no（nginx 不缓冲）"
  else
    echo "  (响应头未见 X-Accel-Buffering: no —— 直连后端时属正常，经前端 nginx 时应出现)"
  fi
  # 应收到至少一条 SSE 数据帧
  grep -q '^data:' "$bod" || die "未收到任何 SSE 数据帧"
  ok "收到 SSE 流式帧"
  rm -f "$hdr" "$bod"
else
  echo "  跳过（未设 OPENAI_API_KEY；SSE 对话需 LLM）"
fi

# ---------------------------------------------------------------------------
log "5/7 创建知识库"
DATASET_ID="$(api_call POST /datasets "$(jq -nc '{name:"smoke-kb", description:"e2e smoke"}')" | jq -r '.id')"
[[ -n "$DATASET_ID" && "$DATASET_ID" != null ]] || die "建知识库未返回 id"
ok "知识库 id=${DATASET_ID}"

# ---------------------------------------------------------------------------
log "6/7 上传文档并触发索引"
TMP_DOC="$(mktemp --suffix=.txt)"
cat >"$TMP_DOC" <<'EOF'
linming_llmops 是一个开源的 LLMOps 平台，支持应用编排、对话、知识库 RAG 检索与工具调用。
向量检索使用本地嵌入模型 bge-small-zh-v1.5，向量库为 Qdrant。
EOF
UP_OUT="$(curl -sS -X POST -w '\n%{http_code}' -H "Authorization: Bearer ${TOKEN}" \
  -F "file=@${TMP_DOC};type=text/plain" "${API}/upload-files/file")"
rm -f "$TMP_DOC"
[[ "$(tail -n1 <<<"$UP_OUT")" == 200 ]] || die "上传文件失败：$(sed '$d' <<<"$UP_OUT")"
UPLOAD_ID="$(sed '$d' <<<"$UP_OUT" | jq -r '.data.id')"
[[ -n "$UPLOAD_ID" && "$UPLOAD_ID" != null ]] || die "上传未返回文件 id"
ok "上传文件 id=${UPLOAD_ID}"

BATCH="$(api_call POST "/datasets/${DATASET_ID}/documents" \
  "$(jq -nc --argjson fid "$UPLOAD_ID" '{upload_file_ids:[$fid], process_type:"automatic"}')" | jq -r '.batch')"
[[ -n "$BATCH" && "$BATCH" != null ]] || die "建文档未返回 batch"
ok "已触发索引 batch=${BATCH}，等待完成…"

deadline=$(( $(date +%s) + INDEX_TIMEOUT ))
while :; do
  STATUS_JSON="$(api_call GET "/datasets/${DATASET_ID}/documents/batch/${BATCH}")"
  # 所有文档进入终态（completed/error）即停
  pending="$(jq '[.[] | select(.status != "completed" and .status != "error")] | length' <<<"$STATUS_JSON")"
  errored="$(jq '[.[] | select(.status == "error")] | length' <<<"$STATUS_JSON")"
  [[ "$errored" == 0 ]] || die "索引出错：$(jq -c '[.[]|{name,status,error}]' <<<"$STATUS_JSON")"
  [[ "$pending" == 0 ]] && break
  (( $(date +%s) < deadline )) || die "索引超时（${INDEX_TIMEOUT}s）：$(jq -c '[.[]|{name,status}]' <<<"$STATUS_JSON")"
  sleep 3
done
ok "文档索引完成"

# ---------------------------------------------------------------------------
log "7/7 RAG 命中测试（语义检索）"
HITS="$(api_call POST "/datasets/${DATASET_ID}/hit" \
  "$(jq -nc '{query:"用什么向量库？", retrieval_strategy:"semantic", k:3, score:0.0}')")"
n="$(jq 'length' <<<"$HITS")"
[[ "$n" -ge 1 ]] || die "RAG 检索未返回任何命中"
ok "RAG 检索返回 ${n} 条命中"

printf '\n\033[1;32m✅ 冒烟全部通过\033[0m\n'
