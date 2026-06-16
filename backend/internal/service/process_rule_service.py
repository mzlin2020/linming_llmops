"""ProcessRuleService：把文档处理规则(rule)翻译成文本分割器 + 文本预处理。

rule 形如 DEFAULT_PROCESS_RULE["rule"]：
  {pre_process_rules: [{id, enabled}], segment: {separators, chunk_size, chunk_overlap}}
"""
import re
from dataclasses import dataclass
from typing import Callable

from injector import inject

from internal.entity import DEFAULT_PROCESS_RULE

_DEFAULT_SEGMENT = DEFAULT_PROCESS_RULE["rule"]["segment"]


@inject
@dataclass
class ProcessRuleService:
    def get_text_splitter_by_rule(self, rule: dict, length_function: Callable[[str], int] = len):
        """按 rule.segment 构建 RecursiveCharacterTextSplitter。"""
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        segment = (rule or {}).get("segment") or _DEFAULT_SEGMENT
        return RecursiveCharacterTextSplitter(
            chunk_size=int(segment.get("chunk_size") or 500),
            chunk_overlap=int(segment.get("chunk_overlap") or 50),
            separators=segment.get("separators") or _DEFAULT_SEGMENT["separators"],
            is_separator_regex=True,
            keep_separator=True,
            length_function=length_function,
        )

    def clean_text_by_rule(self, text: str, rule: dict) -> str:
        """按 rule.pre_process_rules 清洗文本（去多余空白 / 去 URL+邮箱）。"""
        text = text or ""
        enabled_ids = {
            r.get("id") for r in (rule or {}).get("pre_process_rules", []) if r.get("enabled")
        }
        if "remove_extra_space" in enabled_ids:
            text = re.sub(r"\n{3,}", "\n\n", text)
            text = re.sub(r"[ \t\f\r  -   　]{2,}", " ", text)
        if "remove_url_and_email" in enabled_ids:
            text = re.sub(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", "", text)
            text = re.sub(r"https?://[^\s]+", "", text)
        return text.strip()
