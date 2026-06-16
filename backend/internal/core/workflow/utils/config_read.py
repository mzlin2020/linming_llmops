"""配置读取（叶子模块）：不依赖 entities，供 workflow_entity 与 helper 共用，避免循环导入。"""
import os


def get_config_int(key: str, default: int) -> int:
    """读 int 配置：优先 Flask 配置（config/ 两文件登记），无应用上下文回退环境变量/默认值。"""
    try:
        from flask import current_app

        return int(current_app.config.get(key, default))
    except Exception:
        try:
            return int(os.getenv(key) or default)
        except (TypeError, ValueError):
            return default
