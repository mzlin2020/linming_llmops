"""UploadFileService：文件上传落盘 + ai_upload_file 登记（按 user_id 归属）。

存储委托给 StorageService 适配器（v1 默认本地磁盘，接口预留对象存储切换）。
key 为相对存储根的路径：upload/<user_id>/<uuid>.<ext>。
"""
import hashlib
import os
import uuid
from dataclasses import dataclass

from flask import current_app
from injector import inject

from internal.exception import ValidateErrorException
from internal.extension.database_extension import db
from internal.model import Account, UploadFile
from internal.service.quota_service import QuotaService
from internal.storage import StorageService


@inject
@dataclass
class UploadFileService:
    quota_service: QuotaService
    storage_service: StorageService

    def upload(self, file_storage, user: Account) -> UploadFile:
        """file_storage: werkzeug FileStorage。校验扩展名/大小 → 落盘 → 登记。"""
        filename = (getattr(file_storage, "filename", None) or "").strip()
        if not filename:
            raise ValidateErrorException(message="未检测到上传文件")
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in self._allowed_extensions():
            raise ValidateErrorException(message=f"不支持的文件类型: .{ext}")

        data = file_storage.read()
        if not data:
            raise ValidateErrorException(message="文件内容为空")
        # 单文件大小上限：统一走 QUOTA_USER_UPLOAD_MAX_SIZE（<=0 回落全局 UPLOAD_MAX_SIZE）
        max_size = self.quota_service.max_upload_size(user)
        if len(data) > max_size:
            mb = max_size / 1024 / 1024
            raise ValidateErrorException(message=f"文件超过大小上限（单文件最大 {mb:.0f}MB）")

        key = os.path.join("upload", str(user.id), f"{uuid.uuid4().hex}.{ext}")
        self.storage_service.save(key, data)

        record = UploadFile(
            user_id=user.id,
            name=filename,
            key=key,
            size=len(data),
            extension=ext,
            mime_type=getattr(file_storage, "mimetype", "") or "",
            hash=hashlib.sha256(data).hexdigest(),
        )
        with db.auto_commit():
            db.session.add(record)
        db.session.refresh(record)
        return record

    def get_owned(self, upload_file_id: int, user_id: int):
        """取归属 user 的上传文件行；不存在/越权返回 None（编排校验复用）。"""
        row = db.session.get(UploadFile, upload_file_id)
        if row is None or row.user_id != user_id:
            return None
        return row

    def absolute_path(self, upload_file: UploadFile) -> str:
        return self.storage_service.local_path(upload_file.key)

    @staticmethod
    def to_dict(record: UploadFile) -> dict:
        return {
            "id": record.id,
            "name": record.name,
            "key": record.key,
            "size": record.size,
            "extension": record.extension,
            "mime_type": record.mime_type,
            "created_at": int(record.created_at.timestamp()) if record.created_at else 0,
        }

    # ---------- internal ----------

    @staticmethod
    def _allowed_extensions() -> set:
        raw = current_app.config.get("UPLOAD_ALLOWED_EXTENSIONS") or ""
        return {e.strip().lower() for e in raw.split(",") if e.strip()}
