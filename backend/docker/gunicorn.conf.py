"""gunicorn 配置：仅放启动钩子，运行参数仍由 entrypoint.sh 的 env 驱动 CLI 给出（CLI 覆盖本文件）。

唯一职责：在每个 worker fork 后预热嵌入模型，把本地 CPU 模型的冷加载从「用户首次命中测试请求」
前移到容器启动期（命中测试慢的根因是这次冷加载）。env EMBEDDING_WARMUP=false 可关闭。

选 post_worker_init（每 worker 各自预热）而非 master 预热：稳态内存与现状一致（本就每 worker 首请求各自加载
torch），仅把加载时机提前；规避 --preload 下 torch+fork 的潜在不稳定。预热失败只记日志、不影响 worker 启动。
"""
import os


def post_worker_init(worker):  # noqa: ANN001  gunicorn 钩子签名固定
    if os.getenv("EMBEDDING_WARMUP", "true").lower() == "false":
        return
    try:
        from internal.core.embeddings import warmup_embeddings
        warmup_embeddings()
    except Exception:  # 兜底：任何导入/加载异常都不能拖垮 worker 启动
        worker.log.exception("[embeddings] worker 启动预热异常（退化为首次请求懒加载）")
