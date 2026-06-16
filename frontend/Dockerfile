# ---- 构建阶段：编译 SPA ----
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# ---- 运行阶段：nginx 静态托管 + 反代 ----
FROM nginx:1.27-alpine
# BACKEND_UPSTREAM 可经 compose/.env 覆盖；NGINX_ENVSUBST_FILTER 限定只替换 BACKEND_*，
# 保护 nginx.conf.template 里的 $host/$uri 等内置变量不被 envsubst 误伤。
ENV BACKEND_UPSTREAM=backend:5001 \
    NGINX_ENVSUBST_FILTER=BACKEND_
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
# 用 nginx 官方 entrypoint：启动时对 templates 做 envsubst 后再拉起 nginx（无需自定义 CMD）。
