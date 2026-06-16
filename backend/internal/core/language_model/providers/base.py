"""Provider 的抽象基类:把 ProviderEntity + 凭证 + protocol 组装成可用的 langchain ChatModel。"""
import os
from typing import Any, Optional

from internal.exception import FailException

from ..entities import ModelEntity, ProviderCredential, ProviderEntity


class BaseLanguageModelProvider:
    """所有 provider 实例的统一形态。

    构造时绑定一份 ProviderEntity（公开元数据）+ 一份 ProviderCredential（运行期凭证，可空）。
    instantiate() 把 (provider, model, kwargs) 翻译成具体的 langchain Chat 实例。
    上游协议差异（OpenAI 兼容 vs Anthropic 兼容 vs TTS 等）由子类实现 _instantiate_chat 决定。

    凭证优先级：credential（DB 解密落库；多渠道时为某条渠道的凭证）> 环境变量（旧 provider 兜底）。
    DB 化后 credential 必给（单渠道=provider 自身、多渠道=逐渠道）；credential 为 None 时全走 env 兜底，
    兼容尚未迁移/仅声明 env 的老 provider。
    """

    def __init__(self, entity: ProviderEntity, credential: Optional[ProviderCredential] = None):
        self.entity = entity
        self.credential = credential or ProviderCredential()

    # ----- 凭证与 base_url 读取（credential 优先，env 兜底）-----

    def _read_api_key(self) -> str:
        if self.credential.api_key:
            return self.credential.api_key
        env_name = self.entity.api_key_env
        api_key = os.getenv(env_name) if env_name else None
        if not api_key:
            raise FailException(
                message=f"provider {self.entity.name} 未配置 API Key"
                + (f"（环境变量 {env_name}）" if env_name else "")
            )
        return api_key

    def _read_base_url(self) -> Optional[str]:
        if self.credential.base_url:
            return self.credential.base_url
        if self.entity.base_url_env:
            v = os.getenv(self.entity.base_url_env)
            if v:
                return v
        return self.entity.default_base_url

    # ----- 对外入口 -----

    def find_model(self, model_name: str) -> ModelEntity:
        m = self.entity.find_model(model_name)
        if m is None:
            raise FailException(message=f"provider {self.entity.name} 下不存在模型 {model_name}")
        return m

    def instantiate(self, model_name: str, **kwargs: Any):
        model_entity = self.find_model(model_name)
        return self._instantiate_chat(model_entity, **kwargs)

    def generate_images(
        self, model_name: str, prompt: str, *, image: Any = None, **params: Any
    ) -> list[dict]:
        """文生图 / 图生图：返回上游 data 数组（每项含 url 或 b64_json）。
        image 非空即图生图（传参考图 URL 或其列表）。"""
        model_entity = self.find_model(model_name)
        return self._generate_images(model_entity, prompt, image=image, **params)

    def synthesize_speech(self, model_name: str, text: str, **opts: Any) -> bytes:
        """文本转语音：返回完整音频字节（mp3）。

        通用契约——输入纯文本 + 通用参数（voice_type/encoding/speed_ratio…），输出音频字节。
        厂商鉴权/协议/帧格式差异全部封在子类 _synthesize_speech 里，是唯一与供应商耦合处。"""
        model_entity = self.find_model(model_name)
        return self._synthesize_speech(model_entity, text, **opts)

    # ----- 子类实现 -----

    def _instantiate_chat(self, model_entity: ModelEntity, **kwargs: Any):
        raise NotImplementedError

    def _generate_images(
        self, model_entity: ModelEntity, prompt: str, *, image: Any = None, **params: Any
    ) -> list[dict]:
        raise NotImplementedError

    def _synthesize_speech(self, model_entity: ModelEntity, text: str, **opts: Any) -> bytes:
        raise NotImplementedError


class OpenAICompatProvider(BaseLanguageModelProvider):
    """OpenAI Chat Completions 协议兼容的 provider。
    适用于:OpenAI 官方及所有 OpenAI 兼容层（SiliconFlow、OpenRouter、各家中转/自建网关等）。
    """

    def _instantiate_chat(self, model_entity: ModelEntity, **kwargs: Any):
        from langchain_openai import ChatOpenAI

        api_key = self._read_api_key()
        base_url = self._read_base_url()
        # stream_usage=True：流式末帧回带 usage（OpenAI 兼容的 stream_options.include_usage），
        # 让对话收尾时能拿到厂商真实 token 用量；invoke 本就自带 usage_metadata。
        # 上游若不支持会忽略该选项，usage 即为 None，下游 usage_of 兜底为 0，不影响对话。
        return ChatOpenAI(
            model=model_entity.model_name,
            api_key=api_key,
            base_url=base_url,
            stream_usage=True,
            **kwargs,
        )

    def _generate_images(
        self, model_entity: ModelEntity, prompt: str, *, image: Any = None, **params: Any
    ) -> list[dict]:
        """走 OpenAI 兼容的 POST {base_url}/images/generations（多数图像端点同形态）。

        用原始 requests 而非 OpenAI SDK：image / watermark / guidance_scale 等是各家自定义
        扩展参数，SDK 封装不便。requests 在方法内懒加载，避免导入期硬依赖。
        """
        import requests

        api_key = self._read_api_key()
        base_url = (self._read_base_url() or "").rstrip("/")
        url = f"{base_url}/images/generations"
        body: dict[str, Any] = {
            "model": model_entity.model_name,
            "prompt": prompt,
            "response_format": "url",
        }
        # 只透传非 None 参数（watermark=False 会保留）；image 非空即图生图
        body.update({k: v for k, v in params.items() if v is not None})
        if image is not None:
            body["image"] = image
        resp = requests.post(
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=120,
        )
        if not resp.ok:
            # 把上游错误正文（error.message，如 size 不合法）带出来，仅给状态码很难定位
            try:
                detail = (resp.json().get("error") or {}).get("message")
            except Exception:  # noqa: BLE001 — 上游非 JSON 时退回原始文本
                detail = None
            raise RuntimeError(f"{resp.status_code} {detail or resp.text[:300]}")
        return (resp.json() or {}).get("data", []) or []


class AnthropicCompatProvider(BaseLanguageModelProvider):
    """Anthropic Messages 协议（/v1/messages）。

    适用于 Anthropic 官方，以及暴露 Anthropic 原生面的「第三方中转站」。中转站若只走 OpenAI 兼容面
    （/v1/chat/completions，连 Claude 模型也常这么调）用 protocol=openai 即可；只有要走 Anthropic
    原生面才选 protocol=anthropic。base_url/api_key 走与 OpenAICompat 相同的 credential→env 兜底。
    """

    def _instantiate_chat(self, model_entity: ModelEntity, **kwargs: Any):
        from langchain_anthropic import ChatAnthropic

        api_key = self._read_api_key()
        base_url = self._read_base_url()
        params: dict[str, Any] = {"model": model_entity.model_name, "api_key": api_key}
        if base_url:
            params["base_url"] = base_url
        # Anthropic 必须给 max_tokens；用模型卡的上限兜底（kwargs 可覆盖）
        if model_entity.max_output_tokens:
            params.setdefault("max_tokens", model_entity.max_output_tokens)
        params.update(kwargs)
        return ChatAnthropic(**params)


# 协议名 → provider 类。新增一家 LLM 供应商 = 在此登记一个协议类（外加一条 provider 记录），
# Service/Handler/Manager/前端/数据库 均不感知具体厂商。
# UI「协议」下拉来自本表 key，杜绝配出无法实例化的 provider。
# 注：TTS / 图像生成等供应商在 v1.1 作为可选插件接入，此处暂只登记对话协议。
_PROTOCOL_REGISTRY: dict[str, type[BaseLanguageModelProvider]] = {
    "openai": OpenAICompatProvider,
    "anthropic": AnthropicCompatProvider,
}


def list_protocols() -> list[str]:
    """当前可选的协议 key（供管理后台「协议」下拉）。"""
    return list(_PROTOCOL_REGISTRY.keys())


def build_provider(
    entity: ProviderEntity, credential: Optional[ProviderCredential] = None
) -> BaseLanguageModelProvider:
    cls = _PROTOCOL_REGISTRY.get(entity.protocol)
    if cls is None:
        raise FailException(
            message=f"provider {entity.name} 声明的 protocol={entity.protocol} 暂未支持"
        )
    return cls(entity, credential)
