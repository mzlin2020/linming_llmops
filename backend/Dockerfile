# 两段式构建。Phase 1 仅 web/db/auth 栈，无 torch；
# Phase 3 移植核心引擎时再加 CPU-only torch 专装段。
FROM python:3.11-slim-bookworm AS base

# 默认官方 PyPI；国内构建可 --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_INDEX_URL=https://pypi.org/simple

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/pkg --default-timeout=600 --retries 10 --prefer-binary \
      -i "${PIP_INDEX_URL}" -r requirements.txt

FROM python:3.11-slim-bookworm AS production

WORKDIR /app

ENV FLASK_APP=app.http.app
ENV FLASK_ENV=production
ENV FLASK_DEBUG=0
ENV PYTHONPATH=/app
ENV TZ=UTC

COPY --from=base /pkg /usr/local
COPY . /app

EXPOSE 5001

# 经 /bin/bash 显式执行，无需可执行位
ENTRYPOINT ["/bin/bash", "docker/entrypoint.sh"]
