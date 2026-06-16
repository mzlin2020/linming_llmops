"""UploadFileHandler：知识库文件上传（multipart/form-data，字段名 file）。要求登录，按 user 归属落盘。"""
from dataclasses import dataclass

from flask import request
from flask_login import current_user
from injector import inject

from internal.exception import ValidateErrorException
from internal.middleware import RequireLogin
from internal.service import UploadFileService
from pkg.response import success


@inject
@dataclass
class UploadFileHandler:
    upload_file_service: UploadFileService

    @RequireLogin
    def upload_file(self):
        """POST /api/upload-files/file —— 上传单个文件，返回登记记录。"""
        file_storage = request.files.get("file")
        if file_storage is None:
            raise ValidateErrorException(message="未检测到上传文件（form-data 字段名应为 file）")
        record = self.upload_file_service.upload(file_storage, current_user)
        return success(UploadFileService.to_dict(record))
