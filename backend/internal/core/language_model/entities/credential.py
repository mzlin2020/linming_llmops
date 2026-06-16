"""ProviderCredential：运行期凭证，与公开元数据 ProviderEntity 刻意分离。

ProviderEntity 会被 /api/language-models 序列化给前端，**绝不能**含密钥；
凭证（解密后的 api_key + 落地 base_url）只活在运行期 provider 对象里，由它持有这份 credential。
单渠道 provider 持一份；多渠道 provider 每个渠道一份。
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProviderCredential:
    api_key: Optional[str] = None
    base_url: Optional[str] = None
