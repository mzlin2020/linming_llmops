import logging
import os

from concurrent_log_handler import ConcurrentTimedRotatingFileHandler
from flask import Flask


def init_app(app: Flask):
    is_dev = app.debug or os.getenv("FLASK_ENV") == "development"
    level = logging.DEBUG if is_dev else logging.WARNING
    logging.getLogger().setLevel(level)

    log_folder = os.path.join(os.getcwd(), "storage", "log")
    os.makedirs(log_folder, exist_ok=True)
    log_file = os.path.join(log_folder, "app.log")

    handler = ConcurrentTimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        "[%(asctime)s.%(msecs)03d] %(filename)s -> %(funcName)s line:%(lineno)d [%(levelname)s]: %(message)s"
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    logging.getLogger().addHandler(handler)

    if is_dev:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logging.getLogger().addHandler(console_handler)
