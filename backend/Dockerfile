# 两段式构建。
#   base 段：always 装 requirements.txt（web/db/auth/core 引擎，无 torch）；
#           当 --build-arg INSTALL_ML=true 时再装 requirements-ml.txt（CPU-only torch + sentence-transformers），
#           供一键部署/生产做真实本地 embedding（知识库向量化、查询检索）。
#   production 段：拷贝已装好的包 + 源码。INSTALL_ML 时需系统库 libgomp1（torch CPU 运行时依赖）。
FROM python:3.11-slim-bookworm AS base

# 默认官方 PyPI；国内构建可 --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_INDEX_URL=https://pypi.org/simple
# 是否装本地 ML 嵌入栈（torch/sentence-transformers）。默认 false：CI 单测/轻镜像不受影响。
ARG INSTALL_ML=false
# torch 专用索引：强制 CPU wheel，避免默认拉 CUDA 巨包；国内可 --build-arg 换镜像。
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

COPY requirements.txt requirements-ml.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/pkg --default-timeout=600 --retries 10 --prefer-binary \
      -i "${PIP_INDEX_URL}" -r requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    if [ "${INSTALL_ML}" = "true" ]; then \
      pip install --prefix=/pkg --default-timeout=600 --retries 10 --prefer-binary \
        -i "${PIP_INDEX_URL}" --extra-index-url "${TORCH_INDEX_URL}" -r requirements-ml.txt; \
    fi

FROM python:3.11-slim-bookworm AS production

# 透传到运行段，决定是否装 torch 的系统运行时依赖 libgomp1（OpenMP）。
ARG INSTALL_ML=false

WORKDIR /app

ENV FLASK_APP=app.http.app
ENV FLASK_ENV=production
ENV FLASK_DEBUG=0
ENV PYTHONPATH=/app
ENV TZ=UTC

# torch CPU wheel 在 slim 上运行需 libgomp1；仅 ML 镜像装，保持轻镜像精简。
RUN if [ "${INSTALL_ML}" = "true" ]; then \
      apt-get update && apt-get install -y --no-install-recommends libgomp1 && \
      rm -rf /var/lib/apt/lists/*; \
    fi

COPY --from=base /pkg /usr/local
COPY . /app

EXPOSE 5001

# 经 /bin/bash 显式执行，无需可执行位
ENTRYPOINT ["/bin/bash", "docker/entrypoint.sh"]
