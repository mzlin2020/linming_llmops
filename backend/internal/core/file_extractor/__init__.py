"""文件解析子系统：按扩展名把上传文件读成 LangChain Document。"""
from . import file_extractor
from .file_extractor import SUPPORTED_EXTENSIONS, is_supported, load, load_text

__all__ = ["file_extractor", "load", "load_text", "is_supported", "SUPPORTED_EXTENSIONS"]
