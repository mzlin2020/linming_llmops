"""对话后异步任务：会话自动命名 + 长期记忆滚动摘要。

把这两段 LLM 往返从 SSE 收尾路径上摘掉（原来挂在 finalize 之后、agent_end 之前同步跑，
首轮 / 开长期记忆时每轮多 0.5~1.5s 延迟），改到 Celery worker 异步执行。

任务体只做"取 ConversationService → 委托 after_round"，injector/服务在函数内延迟 import，避免与 service 层的导入环。
FlaskTask（celery_extension）已包 app_context，worker 内可直接用 db。

故意不加 acks_late / 重试：命名/摘要是 best-effort，且摘要非幂等（每次把本轮并入 conv.summary），
worker 崩溃重投反而可能把同一轮重复并入摘要。这里取 at-most-once——丢一轮收尾完全可接受
（命名仅首轮一次、摘要下一轮才被读到），不值得为它引入去重。
"""
from typing import Optional

from celery import shared_task


@shared_task(name="ai.after_round")
def after_round_task(
    message_id: int,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    long_term_memory_enabled: bool = False,
) -> None:
    from app.http.module import injector
    from internal.service.conversation_service import ConversationService

    injector.get(ConversationService).after_round(
        message_id,
        provider=provider,
        model=model,
        long_term_memory_enabled=long_term_memory_enabled,
    )
